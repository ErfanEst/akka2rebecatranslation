# prompts/retry_prompts.py
"""
Retry prompt templates for error feedback.
"""

SIMPLE = """The following Rebeca code has compilation errors:

Code:
{previous_code}

Errors:
{errors}

Provide corrected Rebeca code. Output only the code."""

DETAILED = """COMPILATION FAILED

Your previous Rebeca code:
{previous_code}

Compilation errors:
{errors}

INSTRUCTIONS:
1. Read each error carefully
2. Identify the line and position
3. Fix ONLY the syntax errors
4. Maintain the same logic
5. Output corrected code only

Provide the corrected Rebeca code."""

# Will add TARGETED version on Day 5
