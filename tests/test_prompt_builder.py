import unittest

from prompts.researched_prompts import (
    HANDBOOK_ZERO_SHOT_V1,
    CODEGEN_REPAIR_V1,
    INITIAL_WITH_CONTEXT_V1,
    SEMANTIC_REPAIR_V1,
    SIMPLE_PING_PONG_CONTRACT,
    SYNTAX_REPAIR_V1,
)
from src.llm.prompt_builder import PromptBuilder


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PromptBuilder(
            system_prompt=HANDBOOK_ZERO_SHOT_V1,
            initial_template=INITIAL_WITH_CONTEXT_V1,
            retry_template=SYNTAX_REPAIR_V1,
            codegen_retry_template=CODEGEN_REPAIR_V1,
            semantic_retry_template=SEMANTIC_REPAIR_V1,
            strategy="handbook_zero_shot_v1",
            semantic_contracts={"simple_ping_pong": SIMPLE_PING_PONG_CONTRACT},
        )

    def test_initial_prompt_contains_target_and_source_without_oracle_contract(self) -> None:
        prompt = self.builder.build(
            attempt_number=1,
            akka_code="class Ping extends Actor",
            benchmark="simple_ping_pong",
        )

        self.assertIn("extension: CORE_REBECA", prompt.user)
        self.assertIn("<akka_source>\nclass Ping extends Actor", prompt.user)
        self.assertNotIn("exactly 10 PingMessage/PongMessage pairs", prompt.user)
        self.assertFalse(prompt.metadata["benchmark_oracle_exposed"])

    def test_retry_keeps_source_candidate_categories_and_both_logs(self) -> None:
        prompt = self.builder.build(
            attempt_number=2,
            akka_code="class Ping extends Actor",
            benchmark="simple_ping_pong",
            previous_code="reactiveclass Ping {}",
            compiler_error="parser rejected candidate",
            error_categories="COMPILER_REJECTED",
            rmc_stdout="line: 1, column: 20",
            rmc_stderr="NullPointerException: INTLITERAL is null",
        )

        for expected in (
            "class Ping extends Actor",
            "reactiveclass Ping {}",
            "parser rejected candidate",
            "COMPILER_REJECTED",
            "line: 1, column: 20",
            "NullPointerException: INTLITERAL is null",
        ):
            self.assertIn(expected, prompt.user)

    def test_semantic_repair_is_explicitly_labelled_as_oracle_assisted(self) -> None:
        prompt = self.builder.build_semantic_repair(
            akka_code="class Ping extends Actor",
            previous_code="reactiveclass Ping(10) {}\nmain {}",
            semantic_diagnostic='{"observed": 9, "expected": 10}',
            benchmark="simple_ping_pong",
            repair_number=1,
        )

        self.assertEqual(prompt.phase, "semantic_repair")
        self.assertTrue(prompt.metadata["benchmark_oracle_exposed"])
        self.assertIn('"observed": 9', prompt.user)
        self.assertIn("class Ping extends Actor", prompt.user)

    def test_codegen_repair_contains_complete_backend_diagnostic_without_oracle(self) -> None:
        prompt = self.builder.build_codegen_repair(
            akka_code="class Ping extends Actor",
            previous_code="reactiveclass Ping(10) {}\nmain {}",
            codegen_diagnostic='{"stderr": "_ref_pong collision"}',
            benchmark="simple_ping_pong",
            repair_number=1,
        )

        self.assertEqual(prompt.phase, "codegen_repair")
        self.assertFalse(prompt.metadata["benchmark_oracle_exposed"])
        self.assertIn("_ref_pong collision", prompt.user)
        self.assertIn("reactiveclass Ping", prompt.user)


if __name__ == "__main__":
    unittest.main()
