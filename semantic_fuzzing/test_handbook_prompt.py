import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from .handbook_prompt import PROMPT_DIRECTORY, build_handbook_prompt
from .pipeline import FuzzingConfig
from .translator import FuzzingTranslator


class HandbookPromptTests(unittest.TestCase):
    def test_both_complete_extractions_are_included_unchanged(self):
        prompt, metadata = build_handbook_prompt()
        self.assertEqual(metadata["system_prompt_sha256"], hashlib.sha256(prompt.encode()).hexdigest())
        for source in metadata["documents"]:
            raw = (PROMPT_DIRECTORY / source["text_file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source["text_sha256"])
            self.assertEqual(raw.count(b"\f"), source["pages"])
            self.assertIn(raw.decode("utf-8"), prompt)
        self.assertEqual([s["pages"] for s in metadata["documents"]], [52, 8])

    def test_actual_first_and_retry_calls_include_full_prompt_and_original_source(self):
        config = FuzzingConfig(Path("/unused/engine"), Path("/unused/rmc.jar"))
        config.validate = Mock()
        pipeline = Mock(config=config)
        pipeline.check.side_effect = [
            {"status": "MISMATCH", "success": False, "reason": "State differs",
             "campaign": {"candidate_counterexamples": [{"mismatch": {"kind": "STATE_MISMATCH"}}]}},
            {"status": "BOUNDED_MATCH", "success": True, "reason": "Matched"},
        ]
        llm = Mock()
        llm.invoke.side_effect = [AIMessage(content="reactiveclass Bad {}"),
                                  AIMessage(content="reactiveclass Good {}")]
        settings = {"experiment_name": "handbook_test", "max_retries": 2,
                    "system_prompt": "LEGACY_SYSTEM", "initial_prompt_template": "LEGACY_INITIAL",
                    "retry_prompt_template": "LEGACY_RETRY"}
        source = 'object Example { val literal = "{errors} {previous_code}" }'
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch("experiments.base_model_v2.ChatOpenAI", return_value=llm), patch("builtins.print"):
                    translator = FuzzingTranslator(pipeline, settings)
                    input_file = Path("Example.scala")
                    input_file.write_text(source)
                    result = translator.run_on_file(str(input_file))
                full_prompt, metadata = build_handbook_prompt()
                self.assertEqual(llm.invoke.call_count, 2)
                for call in llm.invoke.call_args_list:
                    system, user = call.args[0]
                    self.assertEqual(system.content, full_prompt)
                    self.assertIn(source, user.content)
                    self.assertIn('"message_count": 10', user.content)
                    self.assertNotIn("LEGACY_", system.content + user.content)
                retry_message = llm.invoke.call_args_list[1].args[0][1].content
                self.assertIn("reactiveclass Bad {}", retry_message)
                self.assertIn("STATE_MISMATCH", retry_message)
                self.assertEqual(result["prompt_profile"], "handbook_rebeca")
                self.assertEqual(result["prompt_metadata"], metadata)
                saved = json.loads((translator.output_dir / "Example_result.json").read_text())
                self.assertEqual(saved["prompt_metadata"], metadata)
                for attempt in (1, 2):
                    log = (translator.output_dir / "prompt_logs" /
                           f"Example_attempt_{attempt}_prompts.txt").read_text()
                    self.assertIn(full_prompt, log)
                self.assertEqual(settings["system_prompt"], "LEGACY_SYSTEM")
                self.assertEqual(translator.model_name, "gpt-4o")
            finally:
                os.chdir(original_cwd)

    def test_small_context_model_is_rejected_before_api_initialization(self):
        with patch("experiments.base_model_v2.ChatOpenAI") as client:
            with self.assertRaisesRegex(ValueError, "larger context"):
                FuzzingTranslator(Mock(), {"model": "gpt-4"})
            client.assert_not_called()

    def test_custom_profile_remains_explicitly_available(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch("experiments.base_model_v2.ChatOpenAI"):
                    translator = FuzzingTranslator(Mock(), {
                        "prompt_profile": "custom", "system_prompt": "custom instructions",
                        "initial_prompt_template": "Original: {akka_code}",
                    })
                self.assertEqual(translator.system_prompt, "custom instructions")
                self.assertEqual(translator.initial_prompt_template, "Original: {akka_code}")
                self.assertIsNone(translator.prompt_metadata)
            finally:
                os.chdir(original_cwd)

    def test_reasoning_model_uses_medium_effort_without_sampling_parameters(self):
        config = FuzzingConfig(Path("/unused/engine"), Path("/unused/rmc.jar"))
        config.validate = Mock()
        pipeline = Mock(config=config)
        base_client = Mock(openai_api_key="test-key")
        reasoning_client = Mock()
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch("experiments.base_model_v2.ChatOpenAI", return_value=base_client), \
                        patch("semantic_fuzzing.translator.ChatOpenAI",
                              return_value=reasoning_client) as client:
                    translator = FuzzingTranslator(pipeline, {
                        "experiment_name": "reasoning_test",
                        "model": "gpt-5.6-sol",
                        "reasoning_effort": "medium",
                        "temperature": 1,
                    })
                self.assertIs(translator.llm, reasoning_client)
                self.assertEqual(translator.reasoning_effort, "medium")
                client.assert_called_once_with(
                    model="gpt-5.6-sol", temperature=1.0,
                    model_kwargs={"reasoning_effort": "medium"}, api_key="test-key")
            finally:
                os.chdir(original_cwd)

    def test_reasoning_model_rejects_incompatible_sampling_settings(self):
        with self.assertRaisesRegex(ValueError, "sampling settings"):
            FuzzingTranslator(Mock(), {
                "model": "gpt-5.6-sol", "reasoning_effort": "medium", "top_p": 0.8})


if __name__ == "__main__":
    unittest.main()
