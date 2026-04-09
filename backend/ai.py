import json
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-oss-120b:free"

SYSTEM_PROMPT = """\
You are a helpful project management assistant. The user has a Kanban board with the current state shown below.

You can help the user by:
- Answering questions about their board
- Creating, updating, or deleting cards
- Moving cards between columns

Current board state (JSON):
{board_json}

When responding, you MUST return valid JSON matching this exact schema:
{{
  "message": "your response to the user",
  "actions": [
    {{
      "type": "create_card",
      "columnId": "col-<id>",
      "title": "card title",
      "details": "card details"
    }},
    {{
      "type": "update_card",
      "cardId": "card-<id>",
      "title": "new title",
      "details": "new details"
    }},
    {{
      "type": "delete_card",
      "cardId": "card-<id>"
    }},
    {{
      "type": "move_card",
      "cardId": "card-<id>",
      "columnId": "col-<id>",
      "position": 0
    }}
  ]
}}

Rules:
- "message" is always required
- "actions" is an array that can be empty if no board changes are needed
- Use the exact column and card IDs from the board state above
- Only include actions that the user explicitly or implicitly requests
- Return ONLY the JSON object, no markdown fences or extra text\
"""


async def chat(messages: list[dict]) -> str:
    """Simple chat for testing connectivity."""
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


async def chat_with_board(
    board: dict, conversation: list[dict]
) -> dict:
    """Chat with board context. Returns {"message": str, "actions": list}."""
    board_json = json.dumps(board, indent=2)
    system_msg = {"role": "system", "content": SYSTEM_PROMPT.format(board_json=board_json)}

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": MODEL,
                "messages": [system_msg] + conversation,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"message": content, "actions": []}

    if "message" not in parsed:
        parsed["message"] = content
    if "actions" not in parsed:
        parsed["actions"] = []

    return parsed
