import type { BoardData, Card, Label } from "./kanban";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type Board = {
  id: string;
  title: string;
};

export type AiChatResponse = {
  message: string;
  actions: unknown[];
  board: BoardData;
};

async function request(url: string, options?: RequestInit) {
  const resp = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  return resp.json();
}

// --- Auth ---

export async function register(
  username: string,
  password: string
): Promise<{ username: string }> {
  return request("/api/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function login(
  username: string,
  password: string
): Promise<{ username: string }> {
  return request("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await request("/api/logout", { method: "POST" });
}

export async function checkSession(): Promise<{ username: string } | null> {
  try {
    return await request("/api/me");
  } catch {
    return null;
  }
}

// --- Boards ---

export async function fetchBoards(): Promise<Board[]> {
  return request("/api/boards");
}

export async function createBoard(title: string): Promise<Board> {
  return request("/api/boards", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function renameBoard(
  boardId: string,
  title: string
): Promise<void> {
  await request(`/api/boards/${boardId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}

export async function deleteBoard(boardId: string): Promise<void> {
  await request(`/api/boards/${boardId}`, { method: "DELETE" });
}

// --- Board data ---

export async function fetchBoard(boardId: string): Promise<BoardData> {
  return request(`/api/boards/${boardId}`);
}

// --- Cards ---

export async function addCard(
  boardId: string,
  columnId: string,
  title: string,
  details: string
): Promise<Card> {
  return request(`/api/boards/${boardId}/cards`, {
    method: "POST",
    body: JSON.stringify({ columnId, title, details }),
  });
}

export async function deleteCard(
  boardId: string,
  cardId: string
): Promise<void> {
  await request(`/api/boards/${boardId}/cards/${cardId}`, { method: "DELETE" });
}

export async function moveCard(
  boardId: string,
  cardId: string,
  columnId: string,
  position: number
): Promise<void> {
  await request(`/api/boards/${boardId}/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ columnId, position }),
  });
}

export async function updateCard(
  boardId: string,
  cardId: string,
  data: {
    title: string;
    details: string;
    description?: string;
    due_date?: string | null;
    priority?: string;
  }
): Promise<void> {
  await request(`/api/boards/${boardId}/cards/${cardId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// --- Labels ---

export async function fetchLabels(boardId: string): Promise<Label[]> {
  return request(`/api/boards/${boardId}/labels`);
}

export async function createLabel(
  boardId: string,
  name: string,
  color: string
): Promise<Label> {
  return request(`/api/boards/${boardId}/labels`, {
    method: "POST",
    body: JSON.stringify({ name, color }),
  });
}

export async function updateLabel(
  boardId: string,
  labelId: string,
  name: string,
  color: string
): Promise<void> {
  await request(`/api/boards/${boardId}/labels/${labelId}`, {
    method: "PUT",
    body: JSON.stringify({ name, color }),
  });
}

export async function deleteLabel(
  boardId: string,
  labelId: string
): Promise<void> {
  await request(`/api/boards/${boardId}/labels/${labelId}`, {
    method: "DELETE",
  });
}

export async function addLabelToCard(
  boardId: string,
  cardId: string,
  labelId: string
): Promise<void> {
  await request(`/api/boards/${boardId}/cards/${cardId}/labels/${labelId}`, {
    method: "POST",
  });
}

export async function removeLabelFromCard(
  boardId: string,
  cardId: string,
  labelId: string
): Promise<void> {
  await request(`/api/boards/${boardId}/cards/${cardId}/labels/${labelId}`, {
    method: "DELETE",
  });
}

// --- Columns ---

export async function renameColumn(
  boardId: string,
  columnId: string,
  title: string
): Promise<void> {
  await request(`/api/boards/${boardId}/columns/${columnId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}

// --- AI ---

export async function aiChat(
  boardId: string,
  messages: ChatMessage[]
): Promise<AiChatResponse> {
  return request(`/api/boards/${boardId}/ai/chat`, {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}
