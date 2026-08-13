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


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
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
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
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
