import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-oss-120b:free"


async def chat(messages: list[dict]) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"model": MODEL, "messages": messages},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
