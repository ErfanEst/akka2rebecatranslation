"""Initial and compiler-feedback retry prompt construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


DEFAULT_SYSTEM_PROMPT = (
    "You are an expert in Akka and Rebeca. Translate the supplied Akka program "
    "to compilable Rebeca while preserving actor behavior. Output only Rebeca code."
)
DEFAULT_INITIAL_TEMPLATE = """Translate this Akka program to Rebeca:\n\n{akka_code}"""
DEFAULT_RETRY_TEMPLATE = """The previous Rebeca candidate did not compile.

Original Akka source:
{akka_code}

Previous candidate:
{previous_code}

RMC compiler error:
{compiler_error}

Correct the candidate while preserving its intended behavior. Output only Rebeca code."""


@dataclass(frozen=True)
class BuiltPrompt:
    system: str
    user: str
    strategy: str
    version: str
    phase: str = "initial_generation"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "user": self.user,
            "strategy": self.strategy,
            "version": self.version,
            "phase": self.phase,
            "metadata": dict(self.metadata),
        }


class PromptBuilder:
    def __init__(
        self,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        initial_template: str = DEFAULT_INITIAL_TEMPLATE,
        retry_template: str = DEFAULT_RETRY_TEMPLATE,
        codegen_retry_template: str | None = None,
        semantic_retry_template: str | None = None,
        strategy: str = "default",
        version: str = "v1",
        syntax_repair_version: str = "v1",
        codegen_repair_version: str = "v1",
        semantic_repair_version: str = "v1",
        rmc_extension: str = "CORE_REBECA",
        mailbox_policy: str = (
            "Choose explicit finite mailbox bounds from the source behavior; if no "
            "tight safe bound can be inferred, use a conservative finite bound."
        ),
        semantic_contracts: Mapping[str, str] | None = None,
        default_semantic_contract: str = "Preserve the observable actor protocol of the Akka source.",
    ) -> None:
        self.system_prompt = system_prompt
        self.initial_template = initial_template
        self.retry_template = retry_template
        self.codegen_retry_template = codegen_retry_template
        self.semantic_retry_template = semantic_retry_template
        self.strategy = strategy
        self.version = version
        self.syntax_repair_version = syntax_repair_version
        self.codegen_repair_version = codegen_repair_version
        self.semantic_repair_version = semantic_repair_version
        self.rmc_extension = rmc_extension
        self.mailbox_policy = mailbox_policy
        # Accepted for source compatibility with older experiment drivers.  Built-in
        # generation prompts deliberately never expose benchmark-specific contracts.
        self.semantic_contracts = dict(semantic_contracts or {})
        self.default_semantic_contract = default_semantic_contract

    def _semantic_contract(self, benchmark: str | None) -> str:
        del benchmark
        return self.default_semantic_contract

    def build(
        self,
        *,
        attempt_number: int,
        akka_code: str,
        benchmark: str | None = None,
        previous_code: str | None = None,
        compiler_error: str | None = None,
        error_categories: str | None = None,
        rmc_stdout: str | None = None,
        rmc_stderr: str | None = None,
        retrieved_examples: str | None = None,
        retrieval_metadata: Mapping[str, Any] | None = None,
    ) -> BuiltPrompt:
        common = {
            "akka_code": akka_code,
            "benchmark": benchmark or "unspecified",
            "semantic_contract": self._semantic_contract(benchmark),
            "rmc_extension": self.rmc_extension,
            "mailbox_policy": self.mailbox_policy,
            "retrieved_examples": retrieved_examples or "<no eligible examples retrieved>",
        }
        if attempt_number == 1:
            user = self.initial_template.format(**common)
            phase = "initial_generation"
            prompt_version = self.version
        else:
            compiler_error = compiler_error or "Unknown previous-attempt error"
            user = self.retry_template.format(
                **common,
                previous_code=previous_code or "<no candidate was produced>",
                compiler_error=compiler_error,
                errors=compiler_error,
                error_categories=error_categories or "UNKNOWN",
                rmc_stdout=rmc_stdout or "<empty>",
                rmc_stderr=rmc_stderr or "<empty>",
            )
            phase = "syntax_repair"
            prompt_version = self.syntax_repair_version
        return BuiltPrompt(
            system=self.system_prompt,
            user=user,
            strategy=self.strategy,
            version=prompt_version,
            phase=phase,
            metadata={
                "benchmark_oracle_exposed": False,
                **dict(retrieval_metadata or {}),
            },
        )

    def build_codegen_repair(
        self,
        *,
        akka_code: str,
        previous_code: str,
        codegen_diagnostic: str,
        benchmark: str | None = None,
        repair_number: int = 1,
    ) -> BuiltPrompt:
        if not self.codegen_retry_template:
            raise ValueError("No codegen-repair prompt template was configured.")
        user = self.codegen_retry_template.format(
            akka_code=akka_code,
            previous_code=previous_code,
            codegen_diagnostic=codegen_diagnostic,
            benchmark=benchmark or "unspecified",
            rmc_extension=self.rmc_extension,
            mailbox_policy=self.mailbox_policy,
        )
        return BuiltPrompt(
            system=self.system_prompt,
            user=user,
            strategy=self.strategy,
            version=self.codegen_repair_version,
            phase="codegen_repair",
            metadata={
                "benchmark_oracle_exposed": False,
                "codegen_repair_number": repair_number,
            },
        )

    def build_semantic_repair(
        self,
        *,
        akka_code: str,
        previous_code: str,
        semantic_diagnostic: str,
        benchmark: str | None = None,
        repair_number: int = 1,
    ) -> BuiltPrompt:
        if not self.semantic_retry_template:
            raise ValueError("No semantic-repair prompt template was configured.")
        user = self.semantic_retry_template.format(
            akka_code=akka_code,
            previous_code=previous_code,
            semantic_diagnostic=semantic_diagnostic,
            benchmark=benchmark or "unspecified",
            rmc_extension=self.rmc_extension,
            mailbox_policy=self.mailbox_policy,
        )
        return BuiltPrompt(
            system=self.system_prompt,
            user=user,
            strategy=self.strategy,
            version=self.semantic_repair_version,
            phase="semantic_repair",
            metadata={
                "benchmark_oracle_exposed": True,
                "semantic_repair_number": repair_number,
            },
        )
