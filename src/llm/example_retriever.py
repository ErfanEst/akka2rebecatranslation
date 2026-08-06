"""Deterministic, metadata-aware retrieval for verified few-shot examples.

The retriever intentionally has no vector-database dependency.  Structural
features are more auditable for the thesis and make the leakage decisions
reproducible in every grid run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _normalise_family(value: str | None) -> str:
    family = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    for prefix in ("simple_", "savina_", "benchmark_"):
        if family.startswith(prefix):
            family = family[len(prefix) :]
    return family


def _source_tokens(source: str) -> set[str]:
    ignored = {
        "actor", "actorref", "actorsystem", "case", "class", "def", "extends",
        "import", "object", "package", "private", "props", "receive", "scala",
        "val", "var",
    }
    return {
        token.lower()
        for token in _IDENTIFIER.findall(source)
        if token.lower() not in ignored and len(token) > 2
    }


def extract_structural_features(source: str) -> frozenset[str]:
    """Extract transparent Akka constructs used by the ranking function."""

    checks = {
        "knownrebec": r"\bActorRef\b|Props\s*\(",
        "sender_reply": r"\bsender\s*\(\s*\)\s*!|\bsender\s*!",
        "state_counter": r"\b(?:var|val)\s+\w+\s*=\s*\d+|\+=|-=",
        "threshold": r"(?:>=|<=|==|>|<)\s*\d+",
        "startup": r"\b(?:Start|Begin|Kickoff)\w*\b|extends\s+App",
        "become": r"context\.become|context\.unbecome",
        "stop": r"context\.stop|PoisonPill|Kill",
        "explicit_sender": r"\.tell\s*\(",
        "timed": r"schedule|Duration|FiniteDuration|context\.system\.scheduler",
        "message_parameters": r"case\s+(?:class|\w+\s*\()",
        "multiple_actors": r"class\s+\w+[^\n]*extends\s+Actor[\s\S]*class\s+\w+[^\n]*extends\s+Actor",
    }
    return frozenset(name for name, pattern in checks.items() if re.search(pattern, source))


@dataclass(frozen=True)
class TranslationExample:
    example_id: str
    akka_source: str
    rebeca_source: str
    features: frozenset[str]
    benchmark: str | None = None
    benchmark_family: str | None = None
    source_sha256: str | None = None
    leakage_groups: tuple[str, ...] = ()
    compiler: str = "RMC 2.14"
    extension: str = "CORE_REBECA"
    syntax_verified: bool = False
    semantic_verified: bool = False

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any], *, origin: str) -> "TranslationExample":
        try:
            example_id = str(item["example_id"])
            akka_source = str(item["akka_source"])
            rebeca_source = str(item["rebeca_source"])
        except KeyError as exc:
            raise ValueError(f"{origin}: missing required field {exc.args[0]!r}") from exc
        declared = {str(value) for value in item.get("features", [])}
        declared_hash = str(item["source_sha256"]) if item.get("source_sha256") else None
        actual_hash = hashlib.sha256(akka_source.encode("utf-8")).hexdigest()
        if declared_hash and declared_hash != actual_hash:
            raise ValueError(
                f"{origin}: source_sha256 does not match the supplied akka_source"
            )
        return cls(
            example_id=example_id,
            akka_source=akka_source,
            rebeca_source=rebeca_source,
            features=frozenset(declared or extract_structural_features(akka_source)),
            benchmark=str(item["benchmark"]) if item.get("benchmark") else None,
            benchmark_family=(
                str(item["benchmark_family"])
                if item.get("benchmark_family")
                else str(item["source_family"])
                if item.get("source_family")
                else None
            ),
            source_sha256=declared_hash,
            leakage_groups=tuple(str(value) for value in item.get("leakage_groups", [])),
            compiler=str(item.get("compiler", "RMC 2.14")),
            extension=str(item.get("extension", "CORE_REBECA")),
            syntax_verified=bool(item.get("syntax_verified", False)),
            semantic_verified=bool(item.get("semantic_verified", False)),
        )


@dataclass(frozen=True)
class RetrievedExample:
    example: TranslationExample
    score: float
    matched_features: tuple[str, ...]

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "example_id": self.example.example_id,
            "score": self.score,
            "matched_features": list(self.matched_features),
            "benchmark_family": self.example.benchmark_family,
            "source_sha256": self.example.source_sha256
            or hashlib.sha256(self.example.akka_source.encode("utf-8")).hexdigest(),
        }


class VerifiedExampleRetriever:
    def __init__(
        self,
        examples: Sequence[TranslationExample],
        *,
        top_k: int = 3,
        extension: str = "CORE_REBECA",
        near_duplicate_threshold: float = 0.9,
    ) -> None:
        if top_k < 1:
            raise ValueError("retrieval top_k must be at least 1")
        self.examples = tuple(examples)
        self.top_k = top_k
        self.extension = extension
        self.near_duplicate_threshold = near_duplicate_threshold

    @classmethod
    def from_path(
        cls,
        corpus_path: str | Path,
        **kwargs: Any,
    ) -> "VerifiedExampleRetriever":
        root = Path(corpus_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"few-shot corpus not found: {root}")
        paths = sorted(root.glob("*.json")) if root.is_dir() else [root]
        examples: list[TranslationExample] = []
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload.get("examples", []) if isinstance(payload, dict) else payload
            if not isinstance(records, list):
                raise ValueError(f"{path}: expected a JSON list or an 'examples' list")
            examples.extend(
                TranslationExample.from_mapping(item, origin=f"{path}[{index}]")
                for index, item in enumerate(records)
            )
        if not examples:
            raise ValueError(f"few-shot corpus contains no examples: {root}")
        duplicate_ids = {
            item.example_id
            for item in examples
            if sum(other.example_id == item.example_id for other in examples) > 1
        }
        if duplicate_ids:
            raise ValueError(f"duplicate example_id values: {sorted(duplicate_ids)}")
        return cls(examples, **kwargs)

    def retrieve(
        self,
        akka_source: str,
        *,
        benchmark: str | None,
    ) -> tuple[list[RetrievedExample], dict[str, Any]]:
        current_hash = hashlib.sha256(akka_source.encode("utf-8")).hexdigest()
        current_family = _normalise_family(benchmark)
        current_features = extract_structural_features(akka_source)
        current_tokens = _source_tokens(akka_source)
        excluded: list[dict[str, str]] = []
        eligible: list[RetrievedExample] = []

        for example in self.examples:
            reason = self._exclusion_reason(
                example,
                current_hash=current_hash,
                current_family=current_family,
                current_tokens=current_tokens,
                benchmark=benchmark,
            )
            if reason:
                excluded.append({"example_id": example.example_id, "reason": reason})
                continue
            union = current_features | example.features
            matched = tuple(sorted(current_features & example.features))
            score = len(matched) / len(union) if union else 0.0
            eligible.append(RetrievedExample(example, round(score, 6), matched))

        eligible.sort(key=lambda item: (-item.score, item.example.example_id))
        selected = eligible[: self.top_k]
        manifest = {
            "retrieval_policy": "structural_jaccard_v1",
            "benchmark_oracle_exposed": False,
            "current_benchmark": benchmark,
            "current_family": current_family or None,
            "current_source_sha256": current_hash,
            "current_features": sorted(current_features),
            "top_k": self.top_k,
            "selected": [item.manifest_entry() for item in selected],
            "excluded": excluded,
        }
        return selected, manifest

    def _exclusion_reason(
        self,
        example: TranslationExample,
        *,
        current_hash: str,
        current_family: str,
        current_tokens: set[str],
        benchmark: str | None,
    ) -> str | None:
        if not (example.syntax_verified and example.semantic_verified):
            return "not_syntax_and_semantic_verified"
        if example.compiler != "RMC 2.14":
            return "compiler_profile_mismatch"
        if example.extension != self.extension:
            return "target_extension_mismatch"
        if not example.benchmark_family:
            return "missing_benchmark_family"
        example_hash = example.source_sha256 or hashlib.sha256(
            example.akka_source.encode("utf-8")
        ).hexdigest()
        if example_hash == current_hash:
            return "identical_source"
        if benchmark and _normalise_family(example.benchmark) == _normalise_family(benchmark):
            return "same_benchmark"
        example_family = _normalise_family(example.benchmark_family)
        blocked_groups = {_normalise_family(value) for value in example.leakage_groups}
        if current_family and (example_family == current_family or current_family in blocked_groups):
            return "same_benchmark_family"
        example_tokens = _source_tokens(example.akka_source)
        token_union = current_tokens | example_tokens
        token_similarity = len(current_tokens & example_tokens) / len(token_union) if token_union else 0.0
        if token_similarity >= self.near_duplicate_threshold:
            return "near_duplicate_source"
        return None

    @staticmethod
    def format_for_prompt(examples: Iterable[RetrievedExample]) -> str:
        blocks = []
        for index, item in enumerate(examples, start=1):
            example = item.example
            blocks.append(
                f'<retrieved_example index="{index}" id="{example.example_id}" '
                f'compiler="{example.compiler}" extension="{example.extension}">\n'
                f"<example_akka_source>\n{example.akka_source}\n</example_akka_source>\n"
                f"<verified_rebeca_translation>\n{example.rebeca_source}\n"
                f"</verified_rebeca_translation>\n</retrieved_example>"
            )
        return "\n\n".join(blocks) or "<no eligible examples retrieved>"
