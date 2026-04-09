import type { BoardData, Card } from "./kanban";

async function request(url: string, options?: RequestInit) {
  const resp = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  return resp.json();
}

export async function fetchBoard(): Promise<BoardData> {
  return request("/api/board");
}

export async function addCard(
  columnId: string,
  title: string,
  details: string
): Promise<Card> {
  return request("/api/cards", {
    method: "POST",
    body: JSON.stringify({ columnId, title, details }),
  });
}

export async function updateCard(
  cardId: string,
  title: string,
  details: string
): Promise<void> {
  await request(`/api/cards/${cardId}`, {
    method: "PUT",
    body: JSON.stringify({ title, details }),
  });
}

export async function deleteCard(cardId: string): Promise<void> {
  await request(`/api/cards/${cardId}`, { method: "DELETE" });
}

export async function moveCard(
  cardId: string,
  columnId: string,
  position: number
): Promise<void> {
  await request(`/api/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ columnId, position }),
  });
}

export async function renameColumn(
  columnId: string,
  title: string
): Promise<void> {
  await request(`/api/columns/${columnId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}
