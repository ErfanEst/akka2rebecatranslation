"""Extract Rebeca source without damaging braces or fenced code."""

from __future__ import annotations

import re


class OutputCleaner:
    _FENCE = re.compile(
        r"```[ \t]*(?P<label>[A-Za-z0-9_+-]*)[ \t]*\r?\n(?P<body>.*?)```",
        re.DOTALL,
    )
    _START = re.compile(
        r"^\s*(reactiveclass\b|main\b|env\b|package\b|import\b)",
        re.IGNORECASE,
    )

    def clean(self, response: str) -> str:
        text = response.strip()
        fenced = list(self._FENCE.finditer(text))
        if fenced:
            preferred = next(
                (
                    match
                    for match in fenced
                    if match.group("label").lower() in {"rebeca", "rebec"}
                ),
                fenced[0],
            )
            text = preferred.group("body").strip()

        lines = text.splitlines()
        start = next(
            (index for index, line in enumerate(lines) if self._START.search(line)),
            0,
        )
        lines = lines[start:]

        end = len(lines)
        for index in range(len(lines) - 1, -1, -1):
            stripped = lines[index].strip()
            if stripped.endswith("}") or stripped.endswith(";"):
                end = index + 1
                break

        return "\n".join(lines[:end]).strip()
