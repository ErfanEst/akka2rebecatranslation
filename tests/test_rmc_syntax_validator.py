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


class RmcSyntaxValidatorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
