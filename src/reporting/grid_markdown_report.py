"""Render a complete, evidence-preserving Markdown report for one grid run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: str | Path) -> dict[str, Any] | None:
    resolved = Path(path)
    if not resolved.is_file():
        return None
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_text(path: str | Path | None) -> str | None:
    if not path:
        return None
    resolved = Path(path)
    if not resolved.is_file():
        return None
    try:
        return resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _inline(value: Any) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _block(text: str | None, language: str = "text") -> str:
    body = text if text is not None else "<artifact unavailable>"
    fence = "````" if "```" in body else "```"
    return f"{fence}{language}\n{body.rstrip()}\n{fence}"


def _json_block(payload: Any) -> str:
    return _block(json.dumps(payload, indent=2, ensure_ascii=False), "json")


def render_grid_markdown(grid_result: dict[str, Any]) -> str:
    """Render all request, candidate, compiler, and semantic evidence."""

    usage = grid_result.get("usage_and_cost", {})
    lines = [
        "# Akka-to-Rebeca Grid Experiment Report",
        "",
        "This report is generated from the JSON artifacts. It embeds every generated "
        "candidate, including compiler-rejected code, and every available semantic "
        "evaluation result.",
        "",
        "## Experiment summary",
        "",
        f"- Started: `{_inline(grid_result.get('started_at'))}`",
        f"- Finished: `{_inline(grid_result.get('finished_at'))}`",
        f"- Input: `{_inline(grid_result.get('input'))}`",
        f"- Workspace: `{_inline(grid_result.get('workspace_root'))}`",
        f"- Completed settings: `{_inline(grid_result.get('completed_settings'))}` / "
        f"`{_inline(grid_result.get('total_settings'))}`",
        f"- Setting statuses: `{json.dumps(grid_result.get('setting_status_counts', {}), ensure_ascii=False)}`",
        f"- Candidate statuses: `{json.dumps(grid_result.get('candidate_status_counts', {}), ensure_ascii=False)}`",
        "",
        "## Outcome index",
        "",
        "This table is the authoritative map from a grid setting to its candidate "
        "result; it avoids mixing reports from unrelated workspace runs.",
        "",
        "| Setting | Candidate | Final | Syntax attempt | Codegen | Semantic | Report |",
        "|---|---|---|---:|---|---|---|",
    ]
    for outcome in grid_result.get("outcome_index", []):
        lines.append(
            "| "
            + " | ".join(
                _inline(outcome.get(key))
                for key in (
                    "setting_id",
                    "candidate_id",
                    "status",
                    "syntax_valid_attempt",
                    "final_codegen_status",
                    "semantic_status",
                    "report",
                )
            )
            + " |"
        )
    semantic_passes = grid_result.get("semantic_passes", [])
    lines.extend(
        [
            "",
            "### Semantic passes",
            "",
            (
                _json_block(semantic_passes)
                if semantic_passes
                else "No `SEMANTIC_PASS` candidate has been recorded in this grid."
            ),
            "",
            "## Usage, cache, and cost",
            "",
            f"- Requests: `{_inline(usage.get('request_count'))}`",
            f"- Input tokens: `{_inline(usage.get('input_tokens'))}`",
            f"- Cached input tokens: `{_inline(usage.get('cached_input_tokens'))}`",
            f"- Cache-read requests: `{_inline(usage.get('cache_read_request_count'))}`",
            f"- Cache-read ratio: `{_inline(usage.get('cache_read_ratio'))}`",
            f"- Estimated cache savings (USD): `{_inline(usage.get('estimated_cache_savings_usd'))}`",
            f"- Known total cost (USD): `{_inline(usage.get('known_cost_usd'))}`",
            f"- Cost report complete: `{_inline(usage.get('is_complete'))}`",
            "",
            "### Totals by model",
            "",
            "| Provider | Model | Requests | Input | Cached input | Output | Cache ratio | Cost USD |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in grid_result.get("usage_and_cost_by_model", []):
        lines.append(
            "| "
            + " | ".join(
                _inline(item.get(key))
                for key in (
                    "provider",
                    "model",
                    "request_count",
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "cache_read_ratio",
                    "known_cost_usd",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Request-level ledger",
            "",
            "| Setting | Attempt | Phase | Cache | Input | Cached | Output | Latency s | Cost USD | Syntax |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    candidate_records: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for setting in grid_result.get("settings", []):
        setting_id = str(setting.get("setting_id", "unknown"))
        for candidate in setting.get("candidates", []):
            report_path = candidate.get("report")
            report = _load_json(report_path) if report_path else None
            if report is None:
                continue
            candidate_records.append((setting, report, str(report_path)))
            for attempt in report.get("attempts", []):
                llm = attempt.get("llm", {})
                syntax = attempt.get("syntax", {})
                lines.append(
                    "| "
                    + " | ".join(
                        _inline(value)
                        for value in (
                            setting_id,
                            attempt.get("attempt_number"),
                            attempt.get("prompt", {}).get("phase"),
                            llm.get("cache_status"),
                            llm.get("input_tokens"),
                            llm.get("cached_input_tokens"),
                            llm.get("output_tokens"),
                            llm.get("latency_seconds"),
                            llm.get("cost_usd"),
                            "PASS" if syntax.get("passed") else syntax.get("error_category"),
                        )
                    )
                    + " |"
                )

    lines.extend(["", "## Setting and candidate evidence", ""])
    for setting in grid_result.get("settings", []):
        setting_id = str(setting.get("setting_id", "unknown"))
        lines.extend(
            [
                f"### Setting `{setting_id}`",
                "",
                f"- Status: `{_inline(setting.get('status'))}`",
                f"- Requested parameters: `{json.dumps(setting.get('requested_parameters', {}), ensure_ascii=False)}`",
                f"- Effective parameters: `{json.dumps(setting.get('effective_parameters', {}), ensure_ascii=False)}`",
                f"- Cache key: `{_inline(setting.get('prompt_cache_key'))}`",
                "",
            ]
        )
        for error in setting.get("infrastructure_errors", []):
            lines.extend(
                [
                    "#### Infrastructure error",
                    "",
                    _json_block(error),
                    "",
                    _block(_read_text(error.get("log"))),
                    "",
                ]
            )

        matched = [record for record in candidate_records if record[0] is setting]
        for _, candidate, report_path in matched:
            semantic = candidate.get("semantic", {})
            lines.extend(
                [
                    f"#### Candidate `{_inline(candidate.get('candidate_id'))}`",
                    "",
                    f"- Final status: `{_inline(candidate.get('final_status'))}`",
                    f"- Candidate JSON: `{report_path}`",
                    f"- Syntax pass: `{_inline(candidate.get('syntax_pass'))}`",
                    f"- Semantic status: `{_inline(semantic.get('status'))}`",
                    f"- Failed semantic test IDs: `{json.dumps(semantic.get('failed_test_ids', []), ensure_ascii=False)}`",
                    f"- Not-observed semantic test IDs: `{json.dumps(semantic.get('not_observed_test_ids', []), ensure_ascii=False)}`",
                    "",
                    "Semantic test results:",
                    "",
                    _json_block(semantic.get("semantic_test_results", [])),
                    "",
                ]
            )
            for attempt in candidate.get("attempts", []):
                number = attempt.get("attempt_number")
                llm = attempt.get("llm", {})
                syntax = attempt.get("syntax", {})
                lines.extend(
                    [
                        f"##### Attempt {number}",
                        "",
                        f"- Prompt phase: `{_inline(attempt.get('prompt', {}).get('phase'))}`",
                        f"- LLM error: `{_inline(llm.get('error_category'))}` — {_inline(llm.get('error_message'))}",
                        f"- Cache: `{_inline(llm.get('cache_status'))}`; cached tokens: "
                        f"`{_inline(llm.get('cached_input_tokens'))}`; cost USD: "
                        f"`{_inline(llm.get('cost_usd'))}`",
                        f"- Syntax: `{'PASS' if syntax.get('passed') else _inline(syntax.get('error_category'))}`",
                        f"- Syntax error: {_inline(syntax.get('error_message'))}",
                        "",
                        "Generated Rebeca candidate:",
                        "",
                        _block(attempt.get("generated_code"), "rebeca"),
                        "",
                        "Raw LLM response:",
                        "",
                        _block(llm.get("response")),
                        "",
                        "RMC stdout:",
                        "",
                        _block(_read_text(syntax.get("stdout_path"))),
                        "",
                        "RMC stderr:",
                        "",
                        _block(_read_text(syntax.get("stderr_path"))),
                        "",
                    ]
                )

            candidate_root = Path(report_path).parent
            semantic_results = sorted(
                candidate_root.glob("attempt_*/semantic/semantic_result.json")
            )
            if semantic_results:
                lines.extend(["##### Full semantic evaluations", ""])
                for semantic_path in semantic_results:
                    payload = _load_json(semantic_path)
                    lines.extend(
                        [
                            f"Semantic artifact: `{semantic_path}`",
                            "",
                            _json_block(payload or {"error": "artifact unavailable"}),
                            "",
                        ]
                    )

    if not candidate_records:
        lines.extend(
            [
                "No readable candidate reports are available yet. This is expected "
                "for an incomplete grid or an infrastructure failure before candidate creation.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_grid_markdown_report(
    grid_root: str | Path, *, output_path: str | Path | None = None
) -> Path:
    root = Path(grid_root).expanduser().resolve()
    result_path = root / "grid_result.json"
    result = _load_json(result_path)
    if result is None:
        raise FileNotFoundError(f"Readable grid result not found: {result_path}")
    destination = Path(output_path) if output_path else root / "grid_report.md"
    destination.write_text(render_grid_markdown(result), encoding="utf-8")
    return destination
