import asyncio
from typing import Any

import httpx

from ..config import get_settings


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Only retry if the server says we can retry within this many seconds.
# A larger Retry-After means a daily/long-term quota — don't burn time waiting.
_MAX_RETRY_AFTER = 12
_MAX_RETRIES = 2


async def chat(
    messages: list[dict[str, str]],
    *,
    response_format_json: bool = False,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 4000,
) -> str:
    s = get_settings()
    headers = {
        "Authorization": f"Bearer {s.openrouter_api_key}",
        "HTTP-Referer": s.openrouter_referer,
        "X-Title": s.openrouter_title,
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model or s.openrouter_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(_MAX_RETRIES + 1):
            r = await client.post(OPENROUTER_URL, headers=headers, json=body)
            if r.status_code != 429:
                r.raise_for_status()
                break
            retry_after = int(r.headers.get("Retry-After", _MAX_RETRY_AFTER + 1))
            if attempt < _MAX_RETRIES and retry_after <= _MAX_RETRY_AFTER:
                await asyncio.sleep(retry_after)
                continue
            # Daily/long-term quota exhausted — fail immediately with a clear message.
            raise RuntimeError(
                f"OpenRouter rate limit exceeded for model '{body['model']}'. "
                "The free-tier daily quota is likely used up. "
                "Set OPENROUTER_MODEL to a different free model in your .env "
                "(e.g. deepseek/deepseek-chat-v3-0324:free) or add credits to your account."
            )

    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response: {r.json()}") from e
