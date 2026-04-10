"use client";

import { useState, type FormEvent } from "react";
import type { Card, Label } from "@/lib/kanban";

type CardDetailModalProps = {
  card: Card;
  boardLabels: Label[];
  onSave: (data: {
    title: string;
    details: string;
    description: string;
    due_date: string | null;
    priority: string;
  }) => void;
  onDelete: () => void;
  onClose: () => void;
  onLabelAdd: (labelId: string) => void;
  onLabelRemove: (labelId: string) => void;
};

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low", color: "#2ecc71" },
  { value: "medium", label: "Medium", color: "#ecad0a" },
  { value: "high", label: "High", color: "#e74c3c" },
];

export const CardDetailModal = ({
  card,
  boardLabels,
  onSave,
  onDelete,
  onClose,
  onLabelAdd,
  onLabelRemove,
}: CardDetailModalProps) => {
  const [title, setTitle] = useState(card.title);
  const [details, setDetails] = useState(card.details);
  const [description, setDescription] = useState(card.description);
  const [dueDate, setDueDate] = useState(card.due_date ?? "");
  const [priority, setPriority] = useState(card.priority);

  const assignedLabelIds = new Set(card.labels.map((l) => l.id));
  const unassignedLabels = boardLabels.filter((l) => !assignedLabelIds.has(l.id));

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSave({
      title: title.trim(),
      details: details.trim(),
      description: description.trim(),
      due_date: dueDate || null,
      priority,
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(3,33,71,0.4)] backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg rounded-3xl border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]">
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-transparent font-display text-xl font-semibold text-[var(--navy-dark)] outline-none"
            placeholder="Card title"
            required
            aria-label="Card title"
          />

          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
              Summary
            </label>
            <input
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              placeholder="Short summary"
            />
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="mt-1 w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              placeholder="Detailed description..."
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                Due date
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as "low" | "medium" | "high")}
                className="mt-1 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                aria-label="Priority"
              >
                {PRIORITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
              Labels
            </label>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {card.labels.map((label) => (
                <button
                  key={label.id}
                  type="button"
                  onClick={() => onLabelRemove(label.id)}
                  className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold text-white transition hover:brightness-90"
                  style={{ backgroundColor: label.color }}
                  aria-label={`Remove label ${label.name}`}
                >
                  {label.name}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                    <path d="M18 6L6 18" />
                    <path d="M6 6l12 12" />
                  </svg>
                </button>
              ))}
              {unassignedLabels.map((label) => (
                <button
                  key={label.id}
                  type="button"
                  onClick={() => onLabelAdd(label.id)}
                  className="rounded-full border border-dashed border-[var(--stroke)] px-2.5 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--navy-dark)]"
                  aria-label={`Add label ${label.name}`}
                >
                  + {label.name}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--stroke)] pt-4">
            <button
              type="button"
              onClick={onDelete}
              className="rounded-full border border-red-200 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-red-500 transition hover:bg-red-50"
            >
              Delete card
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-full border border-[var(--stroke)] px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-full bg-[var(--secondary-purple)] px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
              >
                Save
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
