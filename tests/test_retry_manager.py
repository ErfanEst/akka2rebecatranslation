import unittest

from src.artifacts.result_models import AttemptResult, LLMResult, SyntaxResult
from src.pipeline.retry_manager import RetryManager


def attempt(number: int, passed: bool) -> AttemptResult:
    return AttemptResult(
        attempt_number=number,
        started_at="start",
        finished_at="finish",
        prompt={},
        llm=LLMResult(model="fake"),
        generated_code_path=None,
        raw_response_path=None,
        syntax=SyntaxResult(executed=True, execution_success=True, passed=passed),
    )


class RetryManagerTests(unittest.TestCase):
    def test_stops_at_first_syntax_success(self) -> None:
        manager = RetryManager(max_attempts=5)
        outcome = manager.run(
            lambda number, previous: attempt(number, passed=number == 3)
        )
        self.assertEqual(len(outcome.attempts), 3)
        self.assertEqual(outcome.successful_attempt.attempt_number, 3)
        self.assertFalse(outcome.exhausted)

    def test_marks_exhaustion(self) -> None:
        outcome = RetryManager(2).run(
            lambda number, previous: attempt(number, passed=False)
        )
        self.assertEqual(len(outcome.attempts), 2)
        self.assertIsNone(outcome.successful_attempt)
        self.assertTrue(outcome.exhausted)


if __name__ == "__main__":
    unittest.main()
