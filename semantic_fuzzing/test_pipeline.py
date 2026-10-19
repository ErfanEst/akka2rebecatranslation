import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from .pipeline import FuzzingConfig, FuzzingPipeline, campaign_verdict
from .__main__ import check_job


def completed_candidate(**updates):
    model = {"kind": "candidate", "pipeline_status": "EXECUTED",
             "trusted_trace_result": True, "trusted_semantic_result": True,
             "trace_status": "TRACE_PREFIX_MATCH", "observed_event_count": 4}
    model.update(updates)
    return {"campaign_status": "COMPLETED",
            "cases": [{"status": "COMPLETED", "model_results": [model]}]}


class VerdictTests(unittest.TestCase):
    def test_complete_nonempty_trusted_trace_is_bounded_match(self):
        self.assertEqual(campaign_verdict(completed_candidate(), 1)[0], "BOUNDED_MATCH")

    def test_empty_trace_never_passes(self):
        self.assertEqual(campaign_verdict(completed_candidate(observed_event_count=0), 1)[0],
                         "INCONCLUSIVE")

    def test_missing_case_never_passes(self):
        self.assertEqual(campaign_verdict(completed_candidate(), 2)[0], "INCONCLUSIVE")

    def test_missing_summary_never_passes(self):
        self.assertEqual(campaign_verdict({}, 1)[0], "INCONCLUSIVE")

    def test_unknown_campaign_status_never_passes(self):
        summary = completed_candidate()
        summary["campaign_status"] = "UNKNOWN"
        self.assertEqual(campaign_verdict(summary, 1)[0], "INCONCLUSIVE")

    def test_duplicate_candidate_cannot_mask_missing_candidate_in_another_case(self):
        summary = completed_candidate()
        summary["cases"][0]["model_results"] *= 2
        summary["cases"].append({"status": "COMPLETED", "model_results": []})
        self.assertEqual(campaign_verdict(summary, 2)[0], "INCONCLUSIVE")

    def test_untrusted_mismatch_is_inconclusive(self):
        summary = completed_candidate(trace_status="TRACE_PREFIX_MISMATCH",
                                      trusted_semantic_result=False, trusted_trace_result=False)
        self.assertEqual(campaign_verdict(summary, 1)[0], "INCONCLUSIVE")

    def test_state_and_mailbox_mismatches_are_rejected(self):
        for kind in ("STATE_MISMATCH", "MAILBOX_MISMATCH", "ARGUMENT_MISMATCH"):
            with self.subTest(kind=kind):
                summary = completed_candidate(trace_status="TRACE_PREFIX_MISMATCH", mismatch_kind=kind)
                self.assertEqual(campaign_verdict(summary, 1)[0], "MISMATCH")

    def test_trusted_queue_overflow_is_not_a_pass(self):
        summary = completed_candidate(trace_status="NOT_CHECKED", trusted_trace_result=False,
                                      rmc_verdict={"status": "QUEUE_OVERFLOW"})
        self.assertEqual(campaign_verdict(summary, 1)[0], "MISMATCH")

    def test_mutant_mismatch_does_not_reject_candidate(self):
        summary = completed_candidate()
        mutant = copy.deepcopy(summary["cases"][0]["model_results"][0])
        mutant.update(kind="mutant", trace_status="TRACE_PREFIX_MISMATCH")
        summary["cases"][0]["model_results"].append(mutant)
        self.assertEqual(campaign_verdict(summary, 1)[0], "BOUNDED_MATCH")

    def test_execution_error_is_distinct(self):
        summary = completed_candidate(pipeline_status="INFRA_ERROR")
        self.assertEqual(campaign_verdict(summary, 1)[0], "ERROR")

    def test_actual_counterexample_survives_other_case_error(self):
        summary = completed_candidate(trace_status="TRACE_PREFIX_MISMATCH")
        summary["campaign_status"] = "COMPLETED_WITH_ERRORS"
        self.assertEqual(campaign_verdict(summary, 2)[0], "MISMATCH")


class InputTests(unittest.TestCase):
    def test_config_paths_are_relative_to_config_not_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.json"
            path.write_text(json.dumps({"fuzzing_repo": "engine", "rmc_jar": "tool.jar",
                                        "sbt": "bin/sbt", "generation_spec": "spec.json"}))
            config = FuzzingConfig.from_file(path)
            self.assertEqual(config.fuzzing_repo, root / "engine")
            self.assertEqual(config.sbt, str(root / "bin/sbt"))
            self.assertEqual(config.generation_spec, root / "spec.json")

    def test_failed_archived_translation_is_not_rechecked_as_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "result.json").write_text('{"success": false, "final_code": "bad"}')
            engine = Mock()
            with self.assertRaises(ValueError):
                check_job(engine, {"akka_sources": ["original.scala"],
                                   "translation_result": "result.json"}, root, root / "new")
            engine.check.assert_not_called()

    def test_archived_translation_uses_explicit_original_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "result.json").write_text('{"success": true, "final_code": "reactiveclass X {}"}')
            engine = Mock()
            check_job(engine, {"akka_sources": ["original.txt"],
                               "translation_result": "result.json"}, root, root / "new")
            sources, candidate, output, mutants = engine.check.call_args.args
            self.assertEqual(sources, [root / "original.txt"])
            self.assertEqual(candidate.read_text(), "reactiveclass X {}")
            self.assertEqual(output, root / "new/fuzzing")

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.scala"
            candidate = root / "candidate.rebeca"
            source.write_text("original")
            candidate.write_text("original")
            config = FuzzingConfig(root, candidate)
            with patch.object(config, "validate"), self.assertRaises(FileExistsError):
                FuzzingPipeline(config).check([source], candidate, root)
            self.assertEqual(candidate.read_text(), "original")


class TranslationGateTests(unittest.TestCase):
    def test_experiment_cannot_escape_new_output_namespace(self):
        from .translator import FuzzingTranslator
        for name in ("../legacy", "/tmp/legacy", "semantic_fuzzing/../../legacy", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                FuzzingTranslator(Mock(), {"experiment_name": name})

    def test_retry_uses_fuzz_counterexample_and_only_accepts_match(self):
        from langchain_core.messages import AIMessage
        from .translator import FuzzingTranslator
        engine = Mock()
        engine.check.side_effect = [
            {"status": "MISMATCH", "success": False, "reason": "State differs",
             "campaign": {"candidate_counterexamples": [{"mismatch": {"kind": "STATE_MISMATCH"}}]}},
            {"status": "BOUNDED_MATCH", "success": True, "reason": "Matched"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            # Avoid initializing the real API client while exercising the inherited retry loop.
            translator = FuzzingTranslator.__new__(FuzzingTranslator)
            translator.pipeline = engine
            translator.output_dir = Path(directory)
            translator.max_retries = 2
            translator.system_prompt = "Translate"
            translator.initial_prompt_template = "{akka_code}"
            translator.retry_prompt_template = "{previous_code}\n{errors}"
            translator.total_api_calls = 0
            translator.experiment_name = "test"
            translator.llm = Mock()
            translator.llm.invoke.side_effect = [AIMessage(content="reactiveclass Bad {}"),
                                                AIMessage(content="reactiveclass Good {}")]
            with patch("builtins.print"):
                result = translator.translate("object Example", "Example")
            self.assertTrue(result["success"])
            self.assertEqual(result["total_attempts"], 2)
            self.assertEqual(result["semantic_status"], "BOUNDED_MATCH")
            feedback = translator.llm.invoke.call_args_list[1].args[0][1].content
            self.assertIn("STATE_MISMATCH", feedback)
            self.assertEqual(engine.check.call_count, 2)


if __name__ == "__main__":
    unittest.main()
