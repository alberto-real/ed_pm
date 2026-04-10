"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { BoardSwitcher } from "@/components/BoardSwitcher";
import { CardDetailModal } from "@/components/CardDetailModal";
import { ChatSidebar } from "@/components/ChatSidebar";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { moveCard as localMoveCard, type BoardData, type Label } from "@/lib/kanban";
import * as api from "@/lib/api";
import type { Board } from "@/lib/api";

type KanbanBoardProps = {
  username?: string;
  onLogout?: () => void;
};

const emptyBoard: BoardData = { columns: [], cards: {} };

const collisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args);
  if (pointerCollisions.length > 0) return pointerCollisions;
  return rectIntersection(args);
};

export const KanbanBoard = ({ username, onLogout }: KanbanBoardProps = {}) => {
  const [boards, setBoards] = useState<Board[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<string>("");
  const [board, setBoard] = useState<BoardData>(emptyBoard);
  const [labels, setLabels] = useState<Label[]>([]);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadBoard = useCallback((boardId: string) => {
    api.fetchBoard(boardId).then(setBoard);
    api.fetchLabels(boardId).then(setLabels);
  }, []);

  const reload = useCallback(() => {
    if (activeBoardId) {
      api.fetchBoard(activeBoardId).then(setBoard);
    }
  }, [activeBoardId]);

  useEffect(() => {
    api.fetchBoards().then((boardList) => {
      setBoards(boardList);
      if (boardList.length > 0) {
        const firstId = boardList[0].id;
        setActiveBoardId(firstId);
        loadBoard(firstId);
      }
      setLoading(false);
    });
  }, [loadBoard]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) return;

    const newColumns = localMoveCard(
      board.columns,
      active.id as string,
      over.id as string
    );
    setBoard((prev) => ({ ...prev, columns: newColumns }));

    const targetCol = newColumns.find((col) =>
      col.cardIds.includes(active.id as string)
    );
    if (targetCol) {
      const position = targetCol.cardIds.indexOf(active.id as string);
      api.moveCard(activeBoardId, active.id as string, targetCol.id, position).catch(reload);
    }
  };

  const renameTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const debouncedApiRename = useCallback(
    (columnId: string, title: string) => {
      const existing = renameTimers.current.get(columnId);
      if (existing) clearTimeout(existing);
      renameTimers.current.set(
        columnId,
        setTimeout(() => {
          renameTimers.current.delete(columnId);
          api.renameColumn(activeBoardId, columnId, title).catch(reload);
        }, 400)
      );
    },
    [activeBoardId, reload]
  );

  const handleRenameColumn = (columnId: string, title: string) => {
    setBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
    debouncedApiRename(columnId, title);
  };

  const handleAddCard = async (
    columnId: string,
    title: string,
    details: string
  ) => {
    try {
      const card = await api.addCard(activeBoardId, columnId, title, details || "No details yet.");
      setBoard((prev) => ({
        ...prev,
        cards: { ...prev.cards, [card.id]: card },
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? { ...column, cardIds: [...column.cardIds, card.id] }
            : column
        ),
      }));
    } catch {
      reload();
    }
  };

  const handleDeleteCard = async (columnId: string, cardId: string) => {
    setBoard((prev) => ({
      ...prev,
      cards: Object.fromEntries(
        Object.entries(prev.cards).filter(([id]) => id !== cardId)
      ),
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) }
          : column
      ),
    }));
    api.deleteCard(activeBoardId, cardId).catch(reload);
  };

  const handleSwitchBoard = (boardId: string) => {
    setActiveBoardId(boardId);
    loadBoard(boardId);
  };

  const handleCreateBoard = async (title: string) => {
    const newBoard = await api.createBoard(title);
    setBoards((prev) => [...prev, newBoard]);
    setActiveBoardId(newBoard.id);
    loadBoard(newBoard.id);
  };

  const handleRenameBoard = async (boardId: string, title: string) => {
    await api.renameBoard(boardId, title);
    setBoards((prev) =>
      prev.map((b) => (b.id === boardId ? { ...b, title } : b))
    );
  };

  const handleDeleteBoard = async (boardId: string) => {
    await api.deleteBoard(boardId);
    const remaining = boards.filter((b) => b.id !== boardId);
    setBoards(remaining);
    if (boardId === activeBoardId && remaining.length > 0) {
      setActiveBoardId(remaining[0].id);
      loadBoard(remaining[0].id);
    }
  };

  const handleCardClick = (cardId: string) => {
    setEditingCardId(cardId);
  };

  const handleSaveCard = async (data: {
    title: string;
    details: string;
    description: string;
    due_date: string | null;
    priority: string;
  }) => {
    if (!editingCardId) return;
    await api.updateCard(activeBoardId, editingCardId, data);
    setEditingCardId(null);
    reload();
  };

  const handleDeleteEditingCard = async () => {
    if (!editingCardId) return;
    const col = board.columns.find((c) => c.cardIds.includes(editingCardId));
    if (col) await handleDeleteCard(col.id, editingCardId);
    setEditingCardId(null);
  };

  const handleLabelAdd = async (labelId: string) => {
    if (!editingCardId) return;
    await api.addLabelToCard(activeBoardId, editingCardId, labelId);
    reload();
  };

  const handleLabelRemove = async (labelId: string) => {
    if (!editingCardId) return;
    await api.removeLabelFromCard(activeBoardId, editingCardId, labelId);
    reload();
  };

  const activeCard = activeCardId ? board.cards[activeCardId] : null;
  const editingCard = editingCardId ? board.cards[editingCardId] : null;

  if (loading) return null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative flex min-h-screen flex-col gap-6 px-6 pb-8 pt-8">
        <header className="flex items-center justify-between rounded-2xl border border-[var(--stroke)] bg-white/80 px-6 py-4 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-1 text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                {board.columns.length} columns &middot; {Object.keys(board.cards).length} cards
              </p>
            </div>
            <BoardSwitcher
              boards={boards}
              activeBoardId={activeBoardId}
              onSwitch={handleSwitchBoard}
              onCreate={handleCreateBoard}
              onRename={handleRenameBoard}
              onDelete={handleDeleteBoard}
            />
          </div>
          {username && (
            <div className="flex items-center gap-4">
              <span className="text-sm font-semibold text-[var(--navy-dark)]">
                {username}
              </span>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full border border-[var(--stroke)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
              >
                Sign out
              </button>
            </div>
          )}
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetection}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="flex gap-5 overflow-x-auto pb-2">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds.map((cardId) => board.cards[cardId]).filter(Boolean)}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onDeleteCard={handleDeleteCard}
                onCardClick={handleCardClick}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
      <ChatSidebar boardId={activeBoardId} onBoardUpdate={setBoard} />
      {editingCard && (
        <CardDetailModal
          card={editingCard}
          boardLabels={labels}
          onSave={handleSaveCard}
          onDelete={handleDeleteEditingCard}
          onClose={() => setEditingCardId(null)}
          onLabelAdd={handleLabelAdd}
          onLabelRemove={handleLabelRemove}
        />
      )}
    </div>
  );
};
