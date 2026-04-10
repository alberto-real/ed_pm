"use client";

import { useRef, useState, type FormEvent } from "react";
import type { Board } from "@/lib/api";

type BoardSwitcherProps = {
  boards: Board[];
  activeBoardId: string;
  onSwitch: (boardId: string) => void;
  onCreate: (title: string) => void;
  onRename: (boardId: string, title: string) => void;
  onDelete: (boardId: string) => void;
};

export const BoardSwitcher = ({
  boards,
  activeBoardId,
  onSwitch,
  onCreate,
  onRename,
  onDelete,
}: BoardSwitcherProps) => {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeBoard = boards.find((b) => b.id === activeBoardId);

  const handleCreate = (e: FormEvent) => {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    onCreate(title);
    setNewTitle("");
    setCreating(false);
  };

  const handleRename = (boardId: string) => {
    const title = editTitle.trim();
    if (!title) return;
    onRename(boardId, title);
    setEditingId(null);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-xl border border-[var(--stroke)] px-3 py-1.5 text-sm font-semibold text-[var(--navy-dark)] transition hover:bg-[var(--surface)]"
        aria-label="Switch board"
      >
        {activeBoard?.title ?? "Select board"}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 w-64 rounded-2xl border border-[var(--stroke)] bg-white p-2 shadow-[var(--shadow)]">
          <div className="max-h-60 overflow-y-auto">
            {boards.map((board) => (
              <div key={board.id} className="group flex items-center gap-1">
                {editingId === board.id ? (
                  <input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => handleRename(board.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleRename(board.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    className="flex-1 rounded-lg border border-[var(--primary-blue)] px-2 py-1.5 text-sm font-medium text-[var(--navy-dark)] outline-none"
                    autoFocus
                    aria-label="Board name"
                  />
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        onSwitch(board.id);
                        setOpen(false);
                      }}
                      className={`flex-1 rounded-lg px-2 py-1.5 text-left text-sm font-medium transition ${
                        board.id === activeBoardId
                          ? "bg-[var(--surface)] text-[var(--navy-dark)]"
                          : "text-[var(--gray-text)] hover:bg-[var(--surface)] hover:text-[var(--navy-dark)]"
                      }`}
                    >
                      {board.title}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(board.id);
                        setEditTitle(board.title);
                      }}
                      className="shrink-0 rounded-lg p-1 text-[var(--gray-text)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[var(--navy-dark)]"
                      aria-label={`Rename ${board.title}`}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                      </svg>
                    </button>
                    {boards.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          onDelete(board.id);
                          setOpen(false);
                        }}
                        className="shrink-0 rounded-lg p-1 text-[var(--gray-text)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-500"
                        aria-label={`Delete ${board.title}`}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M3 6h18" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                        </svg>
                      </button>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>

          <div className="mt-1 border-t border-[var(--stroke)] pt-2">
            {creating ? (
              <form onSubmit={handleCreate} className="flex gap-1">
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Board name"
                  className="flex-1 rounded-lg border border-[var(--stroke)] px-2 py-1.5 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                  autoFocus
                  aria-label="New board name"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-[var(--secondary-purple)] px-2 py-1.5 text-xs font-semibold text-white transition hover:brightness-110"
                >
                  Add
                </button>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-semibold text-[var(--primary-blue)] transition hover:bg-[var(--surface)]"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5v14" />
                  <path d="M5 12h14" />
                </svg>
                New board
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
