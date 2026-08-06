import unittest

from src.llm.llm_client import (
    ModelConfigurationError,
    _effective_parameters,
    categorize_llm_error,
    infer_provider,
)
from src.llm.model_config import GenerationConfig, parse_model_target


class LLMClientConfigurationTests(unittest.TestCase):
    def test_gpt_5_6_omits_default_sampling_parameters(self) -> None:
        effective = _effective_parameters(
            "openai",
            "gpt-5.6-sol",
            GenerationConfig(
                temperature=1.0,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                reasoning_effort="medium",
            ),
        )
        self.assertEqual(effective, {"reasoning_effort": "medium"})

    def test_gpt_5_6_rejects_non_default_temperature_before_api_call(self) -> None:
        with self.assertRaisesRegex(ModelConfigurationError, "temperature=1.0"):
            _effective_parameters(
                "openai",
                "gpt-5.6-sol",
                GenerationConfig(temperature=0.0),
            )

    def test_gpt_5_6_rejects_unsupported_reasoning_effort(self) -> None:
        with self.assertRaisesRegex(ModelConfigurationError, "does not support"):
            _effective_parameters(
                "openai",
                "gpt-5.6-sol",
                GenerationConfig(reasoning_effort="minimal"),
            )

    def test_unsupported_api_value_has_own_error_category(self) -> None:
        category = categorize_llm_error(
            RuntimeError(
                "Error code: 400 invalid_request_error: unsupported value "
                "for param temperature"
            )
        )
        self.assertEqual(category, "UNSUPPORTED_PARAMETER")

    def test_provider_inference_and_explicit_model_target(self) -> None:
        self.assertEqual(infer_provider("claude-sonnet-4-5"), "anthropic")
        self.assertEqual(infer_provider("deepseek-reasoner"), "deepseek")
        target = parse_model_target("openai:gpt-5.4")
        self.assertEqual(target.provider, "openai")
        self.assertEqual(target.model, "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
