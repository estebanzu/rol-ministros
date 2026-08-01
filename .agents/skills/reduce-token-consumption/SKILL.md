---
name: reduce-token-consumption
description: Reduce token usage by suppressing intermediate outputs and only returning final results.
---

# Skill: Reduce Token Consumption

## Goal
Minimize token consumption during automated workflows by:
- Hiding verbose intermediate outputs.
- Returning only the final result or a concise summary.

## How to Use
Provide a JSON payload with the command to run and optionally a summary prompt.
```json
{
  "command": "python generate_report.py",
  "summary_prompt": "Summarize the report in one sentence"
}
```
The skill executes the command, captures full output internally, filters out lines matching common verbose patterns (e.g., lines starting with `DEBUG:`), and replies with the final output or the supplied summary. If the output still exceeds token limits, it is truncated with a brief notice.

## Implementation Details
- Executes via the underlying `run_command` tool with a reasonable `WaitMsBeforeAsync` to run synchronously.
- Applies a default token limit of 500 tokens to the response.
- If the command fails, returns a concise error message without exposing the full stack trace.

## Extensibility
- Add additional regex filters to the `verbose_patterns` list to customize what is considered intermediate.
- Adjust `summary_prompt` to control summarization depth.
