"""Turns a failed test (name + traceback) into a human-readable diagnosis.

Called from the `pytest_runtest_makereport` hook in conftest.py when
AI_ANALYSIS=true; the result is attached to the Allure report.
"""

from ai.llm import complete, load_prompt

# Keep the prompt within the local model's context window.
MAX_LOG_CHARS = 4000


def analyze_failure(test_name: str, error_log: str) -> str:
    """Return an AI diagnosis, or a fallback message if the LLM is unreachable.

    The fallback lives here rather than in the caller: an unreachable Ollama
    must skip the diagnosis, never fail the run.
    """
    user_message = (
        f"**Test:** {test_name}\n\n**Error log:**\n```\n{error_log[-MAX_LOG_CHARS:]}\n```"
    )
    try:
        return complete(load_prompt("analyze_failure"), user_message)
    except Exception as exc:
        return f"AI analysis unavailable: {exc}"
