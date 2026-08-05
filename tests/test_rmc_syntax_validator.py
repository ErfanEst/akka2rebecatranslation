import tempfile
import unittest
from pathlib import Path

from src.syntax.rmc_compiler import CommandResult, RmcCompiler
from src.syntax.syntax_validator import SyntaxValidator


class FakeRunner:
    def run(self, command, *, cwd, timeout_seconds):
        generated = cwd / "rmc-output"
        generated.mkdir()
        (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")
        return CommandResult(
            command=command,
            return_code=0,
            stdout="generated",
            stderr="",
            duration_seconds=0.01,
        )


class ParserErrorRunner:
    def run(self, command, *, cwd, timeout_seconds):
        return CommandResult(
            command=command,
            return_code=0,
            stdout=(
                f"{cwd / 'candidate.rebeca'}\n"
                "Errors:\n"
                "line:1, column:19, mismatched input '{' "
                "expecting {'extends', 'implements', '('}\n"
                "line:31, column:19, mismatched input '{' "
                "expecting {'extends', 'implements', '('}\n"
            ),
            stderr=(
                'SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".\n'
                "SLF4J: Defaulting to no-operation (NOP) logger implementation\n"
                "SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder "
                "for further details.\n"
                "java.lang.reflect.InvocationTargetException\n"
                "\tat parent.First.call(First.java:1)\n"
                "\tat parent.Second.call(Second.java:2)\n"
                "Caused by: java.lang.NullPointerException: INTLITERAL() is null\n"
                "\tat child.Parser.parse(Parser.java:3)\n"
                "\t... 2 more\n"
            ),
            duration_seconds=0.01,
        )


class NoArtifactRunner:
    def run(self, command, *, cwd, timeout_seconds):
        return CommandResult(
            command=command,
            return_code=0,
            stdout="",
            stderr=(
                'SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".\n'
                "SLF4J: Defaulting to no-operation (NOP) logger implementation\n"
                "SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder "
                "for further details.\n"
            ),
            duration_seconds=0.01,
        )


class RmcSyntaxValidatorTests(unittest.TestCase):
    @staticmethod
    def _files(root: Path) -> tuple[Path, Path, Path]:
        jar = root / "rmc.jar"
        java = root / "java"
        candidate = root / "candidate.rebeca"
        jar.write_bytes(b"fake")
        java.write_text("fake", encoding="utf-8")
        candidate.write_text("main {}", encoding="utf-8")
        return jar, java, candidate

    def test_pass_requires_rmc_and_generated_cpp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = root / "rmc.jar"
            java = root / "java"
            candidate = root / "candidate.rebeca"
            jar.write_bytes(b"fake")
            java.write_text("fake", encoding="utf-8")
            candidate.write_text("main {}", encoding="utf-8")

            validator = SyntaxValidator(
                RmcCompiler(jar_path=jar, java_bin=java, runner=FakeRunner())
            )
            result = validator.validate(candidate, root)

            self.assertTrue(result.executed)
            self.assertTrue(result.execution_success)
            self.assertTrue(result.passed)
            self.assertTrue((root / "generated_cpp" / "model.cpp").is_file())
            self.assertTrue((root / "rmc_stdout.log").is_file())

    def test_retry_feedback_uses_both_logs_and_removes_slf4j(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar, java, candidate = self._files(root)
            validator = SyntaxValidator(
                RmcCompiler(jar_path=jar, java_bin=java, runner=ParserErrorRunner())
            )

            result = validator.validate(candidate, root)

            self.assertFalse(result.passed)
            self.assertEqual(result.error_category, "COMPILER_REJECTED")
            self.assertIn("line:1, column:19", result.error_message)
            self.assertIn("line:31, column:19", result.error_message)
            self.assertIn("InvocationTargetException", result.error_message)
            self.assertNotIn("... 2 more", result.error_message)
            self.assertIn("at parent.First.call(First.java:1)", result.error_message)
            self.assertIn("at parent.Second.call(Second.java:2)", result.error_message)
            self.assertNotIn("SLF4J", result.error_message)
            self.assertIn("SLF4J", (root / "rmc_stderr.log").read_text())
            self.assertNotIn("... 2 more", (root / "rmc_stderr.log").read_text())

    def test_success_without_cpp_or_diagnostics_is_internal_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar, java, candidate = self._files(root)
            validator = SyntaxValidator(
                RmcCompiler(jar_path=jar, java_bin=java, runner=NoArtifactRunner())
            )

            result = validator.validate(candidate, root)

            self.assertEqual(result.error_category, "RMC_INTERNAL_ERROR")
            self.assertEqual(
                result.error_message,
                "RMC returned success but generated no C++ files.",
            )


if __name__ == "__main__":
    unittest.main()
