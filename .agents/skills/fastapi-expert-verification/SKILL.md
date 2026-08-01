---
name: fastapi-expert-verification
description: Provides FastAPI/Python expertise and automatically verifies implementations after changes (tests, lint, endpoint checks) to ensure nothing is broken.
---

# Skill: FastAPI Expert Verification

## Goal
Act as a FastAPI and Python architect mentor that not only suggests or implements changes but also **verifies** the result after each request, ensuring the application remains functional and passes quality checks.

## How It Works
1. **Invocation** – The user sends a high‑level request (e.g., "add endpoint /items", "update CSV parser").
2. **Implementation** – The surrounding agent executes the requested code modifications.
3. **Verification Phase** – The skill automatically runs a verification workflow:
   - **Run Test Suite** (`pytest -q`).
   - **Static Analysis** (`ruff check .` or `flake8`).
   - **FastAPI Endpoint Smoke Test** – Using FastAPI’s `TestClient` it issues a request to any newly created/updated endpoint and checks for a 2xx response.
   - **Dependency Check** – Executes `pip install -r requirements.txt` in a temporary environment to ensure all imports resolve.
4. **Result Reporting** – Returns a concise markdown report summarizing outcomes, any failures, and suggested fixes.
5. **Rollback (optional)** – If verification fails, the skill can suggest reverting the changes or provide a diff of required corrections.

## Input Format
```json
{
  "request": "<high‑level description of the change>",
  "context": "<optional current stack, files affected, constraints>"
}
```

## Output Format
```json
{
  "actions": "<description of what was done>",
  "verification": {
    "tests": "passed" | "failed",
    "lint": "passed" | "failed",
    "endpoint": "passed" | "failed",
    "dependency": "passed" | "failed",
    "details": "<short summary or error snippet>"
  },
  "recommendations": "<next steps or fixes if any>"
}
```

## Extensibility
- **Custom Test Commands** – Add additional commands (e.g., `pytest --cov`).
- **Additional Checks** – Integrate security scanners like `bandit` or type checkers (`mypy`).
- **Verification Config** – Tune timeout limits and the number of retries for endpoint checks.

---

*Place this file at `C:\Users\marci\Downloads\rol-gaby\.agents\skills\fastapi-expert-verification\SKILL.md`.*
