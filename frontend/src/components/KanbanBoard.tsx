"use client";

import { useCallback, useEffect, useState } from "react";
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
import { ChatSidebar } from "@/components/ChatSidebar";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { moveCard as localMoveCard, type BoardData } from "@/lib/kanban";
import * as api from "@/lib/api";

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
  const [board, setBoard] = useState<BoardData>(emptyBoard);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    api.fetchBoard().then(setBoard).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

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

    if (!over || active.id === over.id) {
      return;
    }

    // Optimistic local update
    const newColumns = localMoveCard(
      board.columns,
      active.id as string,
      over.id as string
    );
    setBoard((prev) => ({ ...prev, columns: newColumns }));

    // Find the target column and position for the API call
    const targetCol = newColumns.find((col) =>
      col.cardIds.includes(active.id as string)
    );
    if (targetCol) {
      const position = targetCol.cardIds.indexOf(active.id as string);
      api.moveCard(active.id as string, targetCol.id, position).catch(reload);
    }
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    setBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
    api.renameColumn(columnId, title).catch(reload);
  };

  const handleAddCard = async (
    columnId: string,
    title: string,
    details: string
  ) => {
    try {
      const card = await api.addCard(columnId, title, details || "No details yet.");
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
    // Optimistic update
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
    api.deleteCard(cardId).catch(reload);
  };

  const activeCard = activeCardId ? board.cards[activeCardId] : null;

  if (loading) return null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative flex min-h-screen flex-col gap-6 px-6 pb-8 pt-8">
        <header className="flex items-center justify-between rounded-2xl border border-[var(--stroke)] bg-white/80 px-6 py-4 shadow-[var(--shadow)] backdrop-blur">
          <div>
            <h1 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
              Kanban Studio
            </h1>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
              {board.columns.length} columns &middot; {Object.keys(board.cards).length} cards
            </p>
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
      <ChatSidebar onBoardUpdate={setBoard} />
    </div>
  );
};
