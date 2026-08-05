import unittest

from prompts.researched_prompts import (
    HANDBOOK_ZERO_SHOT_V1,
    INITIAL_WITH_CONTEXT_V1,
    SYNTAX_REPAIR_V1,
)
from src.llm.prompt_builder import PromptBuilder


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PromptBuilder(
            system_prompt=HANDBOOK_ZERO_SHOT_V1,
            initial_template=INITIAL_WITH_CONTEXT_V1,
            retry_template=SYNTAX_REPAIR_V1,
            strategy="handbook_zero_shot_v1",
        )

    def test_initial_prompt_is_benchmark_independent(self) -> None:
        prompt = self.builder.build(
            attempt_number=1,
            akka_code="class Ping extends Actor",
        )

        self.assertIn("extension: CORE_REBECA", prompt.user)
        self.assertIn("<akka_source>\nclass Ping extends Actor", prompt.user)
        self.assertNotIn("simple_ping_pong", prompt.user)
        self.assertNotIn("exactly 10 PingMessage/PongMessage pairs", prompt.user)
        self.assertNotIn("<semantic_contract", prompt.user)

    def test_retry_keeps_source_candidate_categories_and_both_logs(self) -> None:
        prompt = self.builder.build(
            attempt_number=2,
            akka_code="class Ping extends Actor",
            previous_code="reactiveclass Ping {}",
            compiler_error="parser rejected candidate",
            error_categories="COMPILER_REJECTED",
            rmc_stdout="line: 1, column: 20",
            rmc_stderr="NullPointerException: INTLITERAL is null",
        )

        for expected in (
            "class Ping extends Actor",
            "reactiveclass Ping {}",
            "COMPILER_REJECTED",
            "line: 1, column: 20",
            "NullPointerException: INTLITERAL is null",
        ):
            self.assertIn(expected, prompt.user)
        self.assertNotIn("<semantic_contract", prompt.user)


if __name__ == "__main__":
    unittest.main()
