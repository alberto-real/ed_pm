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
- Managing card labels, priorities, and due dates

Current board state (JSON):
{board_json}

Available labels for this board:
{labels_json}

When responding, you MUST return valid JSON matching this exact schema:
{{
  "message": "your response to the user",
  "actions": [
    {{
      "type": "create_card",
      "columnId": "col-<id>",
      "title": "card title",
      "details": "short summary",
      "description": "longer description (optional)",
      "due_date": "YYYY-MM-DD (optional, null to clear)",
      "priority": "low|medium|high (optional, defaults to medium)"
    }},
    {{
      "type": "update_card",
      "cardId": "card-<id>",
      "title": "new title",
      "details": "new summary",
      "description": "new description (optional)",
      "due_date": "YYYY-MM-DD (optional)",
      "priority": "low|medium|high (optional)"
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
    }},
    {{
      "type": "add_label_to_card",
      "cardId": "card-<id>",
      "labelId": "label-<id>"
    }},
    {{
      "type": "remove_label_from_card",
      "cardId": "card-<id>",
      "labelId": "label-<id>"
    }}
  ]
}}

Rules:
- "message" is always required
- "actions" is an array that can be empty if no board changes are needed
- Use the exact column, card, and label IDs from the board state above
- Only include actions that the user explicitly or implicitly requests
- Return ONLY the JSON object, no markdown fences or extra text\
"""

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=60)
    return _client


async def _openrouter_request(messages: list[dict], **extra_json) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    resp = await get_client().post(
        OPENROUTER_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={"model": MODEL, "messages": messages, **extra_json},
    )
    resp.raise_for_status()
    return resp.json()


async def chat_with_board(board: dict, conversation: list[dict], labels: list[dict] | None = None) -> dict:
    """Chat with board context. Returns {"message": str, "actions": list}."""
    board_json = json.dumps(board, indent=2)
    labels_json = json.dumps(labels or [], indent=2)
    system_msg = {"role": "system", "content": SYSTEM_PROMPT.format(
        board_json=board_json, labels_json=labels_json,
    )}

    data = await _openrouter_request(
        [system_msg] + conversation,
        response_format={"type": "json_object"},
    )
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
