import unittest

from src.llm.output_cleaner import OutputCleaner


class OutputCleanerTests(unittest.TestCase):
    def test_extracts_rebeca_fence_and_discards_explanation(self) -> None:
        response = """Here is the model:
```rebeca
reactiveclass Counter(5) {
  msgsrv inc() {}
}
main { Counter c():(); }
```
This preserves the behavior."""
        cleaned = OutputCleaner().clean(response)
        self.assertTrue(cleaned.startswith("reactiveclass Counter"))
        self.assertTrue(cleaned.endswith("}"))
        self.assertNotIn("```", cleaned)
        self.assertNotIn("Here is", cleaned)

    def test_keeps_plain_rebeca(self) -> None:
        code = "reactiveclass A(1) {\n  msgsrv go() {}\n}\nmain { A a():(); }"
        self.assertEqual(OutputCleaner().clean(code), code)


if __name__ == "__main__":
    unittest.main()
