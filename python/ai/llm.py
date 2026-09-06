"""Single entry point to the local LLM (Ollama via its OpenAI-compatible API).

Every AI feature in the project goes through `complete` / `complete_json`,
so swapping the model or provider is a one-file change.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import cast

from openai import Omit, OpenAI, omit
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONObject

PROMPTS_DIR = Path(__file__).parent / "prompts"


class LLMUnavailable(RuntimeError):
    """The configured model cannot be reached, or is not installed.

    Raised only by `require_available`, which the *explicitly requested* AI
    entry points call — `pytest -m ai_judge` and `ai/api_fuzzer.py`. Asking for
    the AI and silently getting nothing is worse than an error: the run goes
    green having checked nothing.

    The ambient features are the opposite case and keep degrading quietly:
    AI_ANALYSIS annotates a report and SELF_HEAL retries a locator, both inside
    runs that gate merges, and neither may fail a build because a side feature
    is offline.
    """


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.1:8b"


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
        api_key="ollama",  # required by the SDK, ignored by Ollama
    )


def complete(
    system_prompt: str, user_message: str, max_tokens: int = 1024, json_mode: bool = False
) -> str:
    client = _client()
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    # json_mode maps to Ollama's format=json: constrains decoding to valid JSON,
    # which an instruction in the prompt alone does not guarantee.
    response_format: ResponseFormatJSONObject | Omit = (
        {"type": "json_object"} if json_mode else omit
    )
    response = client.chat.completions.create(
        model=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        max_tokens=max_tokens,
        temperature=0,
        messages=messages,
        response_format=response_format,
    )
    return response.choices[0].message.content or ""


def complete_json(system_prompt: str, user_message: str, max_tokens: int = 2048) -> dict | list:
    """Like `complete`, but parses the response as JSON.

    Local models sometimes wrap JSON in a markdown code fence despite
    instructions, so the fence is stripped before parsing.
    """
    raw = complete(system_prompt, user_message, max_tokens, json_mode=True).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return cast(dict | list, json.loads(raw))


def require_available() -> None:
    """Raise `LLMUnavailable` unless the configured model is ready to answer.

    Checks both ways this fails in practice: Ollama not running at all, and
    Ollama running without the model pulled. Listing models is cheap (~0.2s)
    and fails immediately on a closed port, so this is a preflight, not a
    tax on the run.
    """
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    client = _client()
    # Off the client, not the environment: `_client` is cached, so a process
    # that changed OLLAMA_BASE_URL after first use would otherwise be told to
    # go start a server at an address nothing ever contacted.
    base_url = str(client.base_url)
    try:
        installed = [m.id for m in client.models.list().data]
    except Exception as exc:
        raise LLMUnavailable(
            f"No LLM at {base_url} ({type(exc).__name__}: {exc}). Start one with "
            f"`ollama serve`, then `ollama pull {model}`."
        ) from exc

    if model not in installed:
        raise LLMUnavailable(
            f"{base_url} is up but {model!r} is not installed "
            f"(available: {', '.join(installed) or 'none'}). Run `ollama pull {model}`."
        )
