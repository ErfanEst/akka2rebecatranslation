import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from src.llm.llm_client import (
    ModelConfigurationError,
    OpenAILangChainClient,
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

        # temperature=1.0 is intentionally retained because the pinned
        # langchain-openai wrapper otherwise injects temperature=0.7.
        # The other default sampling parameters can remain omitted.
        self.assertEqual(
            effective,
            {
                "temperature": 1.0,
                "reasoning_effort": "medium",
            },
        )

    def test_gpt_5_6_rejects_non_default_temperature_before_api_call(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ModelConfigurationError,
            "temperature=1.0",
        ):
            _effective_parameters(
                "openai",
                "gpt-5.6-sol",
                GenerationConfig(temperature=0.0),
            )

    def test_gpt_5_6_rejects_unsupported_reasoning_effort(self) -> None:
        with self.assertRaisesRegex(
            ModelConfigurationError,
            "does not support",
        ):
            _effective_parameters(
                "openai",
                "gpt-5.6-sol",
                GenerationConfig(reasoning_effort="minimal"),
            )

    def test_gpt_5_1_sampling_requires_none_reasoning(self) -> None:
        effective = _effective_parameters(
            "openai",
            "gpt-5.1-2025-11-13",
            GenerationConfig(
                temperature=0.2,
                reasoning_effort="none",
            ),
        )

        self.assertEqual(
            effective,
            {
                "temperature": 0.2,
                "reasoning_effort": "none",
            },
        )

        with self.assertRaisesRegex(
            ModelConfigurationError,
            "only with",
        ):
            _effective_parameters(
                "openai",
                "gpt-5.1",
                GenerationConfig(
                    temperature=0.2,
                    reasoning_effort="medium",
                ),
            )

    def test_gpt_5_1_accepts_versioned_cache_routing_and_24h_retention(
        self,
    ) -> None:
        effective = _effective_parameters(
            "openai",
            "gpt-5.1-2025-11-13",
            GenerationConfig(
                prompt_cache_key="akka2rebeca:gpt-5.1:handbook:v1",
                prompt_cache_retention="24h",
            ),
        )

        self.assertEqual(
            effective,
            {
                "prompt_cache_key": "akka2rebeca:gpt-5.1:handbook:v1",
                "prompt_cache_retention": "24h",
            },
        )

    def test_gpt_5_6_rejects_legacy_cache_retention_but_keeps_key(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ModelConfigurationError,
            "does not accept",
        ):
            _effective_parameters(
                "openai",
                "gpt-5.6-sol",
                GenerationConfig(prompt_cache_retention="24h"),
            )

        effective = _effective_parameters(
            "openai",
            "gpt-5.6-sol",
            GenerationConfig(
                prompt_cache_key="akka2rebeca:gpt56",
            ),
        )

        self.assertEqual(
            effective,
            {
                "prompt_cache_key": "akka2rebeca:gpt56",
                "temperature": 1.0,
            },
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
        self.assertEqual(
            infer_provider("claude-sonnet-4-5"),
            "anthropic",
        )
        self.assertEqual(
            infer_provider("deepseek-reasoner"),
            "deepseek",
        )

        target = parse_model_target("openai:gpt-5.4")

        self.assertEqual(target.provider, "openai")
        self.assertEqual(target.model, "gpt-5.4")

    def test_new_openai_cache_fields_use_sdk_extra_body(self) -> None:
        captured = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        fake_module = ModuleType("langchain_openai")
        fake_module.ChatOpenAI = FakeChatOpenAI

        with patch.dict(
            sys.modules,
            {"langchain_openai": fake_module},
        ):
            OpenAILangChainClient(
                model="gpt-5.1-2025-11-13",
                api_key="test-key",
                config=GenerationConfig(
                    temperature=0.1,
                    reasoning_effort="none",
                    prompt_cache_key="ping-pong-v1",
                    prompt_cache_retention="24h",
                ),
            )

        self.assertEqual(
            captured["temperature"],
            0.1,
        )
        self.assertEqual(
            captured["extra_body"],
            {
                "reasoning_effort": "none",
                "prompt_cache_key": "ping-pong-v1",
                "prompt_cache_retention": "24h",
            },
        )
        self.assertNotIn(
            "model_kwargs",
            captured,
        )


if __name__ == "__main__":
    unittest.main()
