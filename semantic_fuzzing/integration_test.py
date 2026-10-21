"""Real syntax/fuzzing retry test; only the LLM boundary is scripted, never live."""

import argparse
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from .pipeline import FuzzingConfig, FuzzingPipeline, read_json, write_json
from .translator import FuzzingTranslator


class ScriptedTestTranslator(FuzzingTranslator):
    def translate(self, akka_code: str, file_id: str = "test") -> dict:
        result = super().translate(akka_code, file_id)
        result["llm_mode"] = "SCRIPTED_TEST_RESPONSES"
        result["live_api_executed"] = False
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = FuzzingConfig.from_file(args.config)
    cfg.validate()
    if args.output.exists():
        raise ValueError("Use a fresh output directory")
    engine = cfg.fuzzing_repo
    responses = ["reactiveclass Broken(10) { statevars { int ; } } main {}",
                 (engine / "examples/session_workflow_mutant_wrong_submit_id.rebeca").read_text(),
                 (engine / "examples/session_workflow.rebeca").read_text()]
    client = Mock()
    client.invoke.side_effect = [AIMessage(content=value) for value in responses]
    with patch("experiments.base_model_v2.ChatOpenAI", return_value=client):
        translator = ScriptedTestTranslator(FuzzingPipeline(cfg), {
            "experiment_name": "scripted_integration_test", "max_retries": 3})
    args.output.mkdir(parents=True)
    translator.output_dir = args.output.resolve()
    result = translator.run_on_file(str(engine / "examples/akka/SessionWorkflow.scala"))
    statuses = [attempt["pipeline_status"] for attempt in result["attempts"]]
    expected = ["SYNTAX_ERROR", "MISMATCH", "BOUNDED_MATCH"]
    checks = [read_json(Path(check["result_file"])) for check in result["semantic_checks"]]
    passed = (statuses == expected and result["success"]
              and checks[0]["semantic_status"] == "NOT_RUN"
              and checks[0]["campaign_summary_file"] is None
              and client.invoke.call_count == 3)
    write_json(args.output / "verification.json", {
        "passed": passed, "llm_mode": "SCRIPTED_TEST_RESPONSES", "live_api_executed": False,
        "actual_statuses": statuses, "expected_statuses": expected,
        "real_components": ["RMC frontend", "Scala extractor/instrumenter", "Akka runner",
                            "C++ model checkers", "semantic differential fuzzing campaign"],
        "result_file": str(translator.output_dir / "SessionWorkflow_result.json")})
    print(f"SCRIPTED LLM / REAL VALIDATORS: {statuses}; passed={passed}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
