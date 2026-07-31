"""Initial and compiler-feedback retry prompt construction."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SYSTEM_PROMPT = (
    "You are an expert in Akka and Rebeca. Translate the supplied Akka program "
    "to compilable Rebeca while preserving actor behavior. Output only Rebeca code."
)
DEFAULT_INITIAL_TEMPLATE = """Translate this Akka program to Rebeca:\n\n{akka_code}"""
DEFAULT_RETRY_TEMPLATE = """The previous Rebeca candidate did not compile.

Previous candidate:
{previous_code}

RMC compiler error:
{compiler_error}

Correct the candidate while preserving its intended behavior. Output only Rebeca code."""


@dataclass(frozen=True)
class BuiltPrompt:
    system: str
    user: str
    strategy: str
    version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "system": self.system,
            "user": self.user,
            "strategy": self.strategy,
            "version": self.version,
        }


class PromptBuilder:
    def __init__(
        self,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        initial_template: str = DEFAULT_INITIAL_TEMPLATE,
        retry_template: str = DEFAULT_RETRY_TEMPLATE,
        strategy: str = "default",
        version: str = "v1",
    ) -> None:
        self.system_prompt = system_prompt
        self.initial_template = initial_template
        self.retry_template = retry_template
        self.strategy = strategy
        self.version = version

    def build(
        self,
        *,
        attempt_number: int,
        akka_code: str,
        previous_code: str | None = None,
        compiler_error: str | None = None,
    ) -> BuiltPrompt:
        if attempt_number == 1:
            user = self.initial_template.format(akka_code=akka_code)
        else:
            user = self.retry_template.format(
                previous_code=previous_code or "<no candidate was produced>",
                compiler_error=compiler_error or "Unknown previous-attempt error",
                errors=compiler_error or "Unknown previous-attempt error",
            )
        return BuiltPrompt(
            system=self.system_prompt,
            user=user,
            strategy=self.strategy,
            version=self.version,
        )
