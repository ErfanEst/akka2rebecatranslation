import unittest
from types import SimpleNamespace

from src.llm.llm_client import _LangChainChatClient
from src.llm.model_config import GenerationConfig
from src.llm.pricing import PricingCatalog, TokenUsage


class PricingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = PricingCatalog.from_path()

    def test_openai_usage_and_cost_include_cache_and_reasoning(self) -> None:
        response = SimpleNamespace(
            usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
                "input_token_details": {"cache_read": 200},
                "output_token_details": {"reasoning": 40},
            },
            response_metadata={},
        )
        usage = TokenUsage.from_response(response, provider="openai")
        estimate = self.catalog.estimate(
            provider="openai", model="gpt-5.6-sol", usage=usage
        )

        self.assertEqual(usage.uncached_input_tokens, 800)
        self.assertEqual(usage.cached_input_tokens, 200)
        self.assertEqual(usage.reasoning_tokens, 40)
        self.assertEqual(usage.cache_status, "HIT")
        self.assertAlmostEqual(usage.cache_read_ratio, 0.2)
        self.assertEqual(estimate["status"], "CALCULATED")
        self.assertAlmostEqual(estimate["total_cost_usd"], 0.0071)
        self.assertAlmostEqual(estimate["estimated_cache_savings_usd"], 0.0009)

    def test_anthropic_raw_usage_keeps_cache_creation_separate(self) -> None:
        response = SimpleNamespace(
            usage_metadata={},
            response_metadata={
                "usage": {
                    "input_tokens": 100,
                    "cache_creation_input_tokens": 50,
                    "cache_read_input_tokens": 25,
                    "output_tokens": 20,
                }
            },
        )
        usage = TokenUsage.from_response(response, provider="anthropic")
        estimate = self.catalog.estimate(
            provider="anthropic", model="claude-sonnet-4-5", usage=usage
        )

        self.assertEqual(usage.input_tokens, 175)
        self.assertEqual(usage.uncached_input_tokens, 100)
        self.assertEqual(usage.cache_write_input_tokens, 50)
        self.assertEqual(usage.cached_input_tokens, 25)
        self.assertEqual(estimate["status"], "CALCULATED")
        self.assertAlmostEqual(estimate["total_cost_usd"], 0.000795)

    def test_unknown_model_never_invents_a_price(self) -> None:
        estimate = self.catalog.estimate(
            provider="openai_compatible",
            model="private-model",
            usage=TokenUsage(
                input_tokens=100,
                uncached_input_tokens=100,
                output_tokens=50,
                total_tokens=150,
            ),
        )
        self.assertEqual(estimate["status"], "PRICE_UNAVAILABLE")
        self.assertIsNone(estimate["total_cost_usd"])

    def test_long_context_multiplier_is_recorded(self) -> None:
        estimate = self.catalog.estimate(
            provider="openai",
            model="gpt-5.4",
            usage=TokenUsage(
                input_tokens=300000,
                uncached_input_tokens=300000,
                output_tokens=1000,
                total_tokens=301000,
            ),
        )
        self.assertTrue(estimate["long_context_applied"])
        self.assertEqual(
            estimate["components"]["uncached_input"]["rate_per_million"], 5.0
        )
        self.assertEqual(
            estimate["components"]["output"]["rate_per_million"], 22.5
        )

    def test_client_wires_usage_and_cost_into_llm_result(self) -> None:
        class FakeClient(_LangChainChatClient):
            provider_name = "openai"

            def _invoke(self, system_prompt: str, user_prompt: str):
                return SimpleNamespace(
                    content="reactiveclass A(1) {}",
                    id="response-1",
                    usage_metadata={
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                    },
                    response_metadata={},
                )

        client = FakeClient(
            model="gpt-5.1-2025-11-13",
            config=GenerationConfig(),
            pricing_catalog=self.catalog,
        )
        result = client.generate("system", "user")

        self.assertEqual(result.cost_status, "CALCULATED")
        self.assertAlmostEqual(result.cost_usd, 0.000325)
        self.assertEqual(
            result.cost_details["matched_pricing_id"],
            "openai-gpt-5.1-standard-2026-08-06",
        )


if __name__ == "__main__":
    unittest.main()
