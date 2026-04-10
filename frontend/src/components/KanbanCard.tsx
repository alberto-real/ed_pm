import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import type { Card } from "@/lib/kanban";

type KanbanCardProps = {
  card: Card;
  onClick: () => void;
  onDelete: (cardId: string) => void;
};

const PRIORITY_COLORS = {
  low: "#2ecc71",
  medium: "#ecad0a",
  high: "#e74c3c",
};

function getDueDateStatus(due_date: string | null): "overdue" | "today" | "upcoming" | null {
  if (!due_date) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(due_date + "T00:00:00");
  if (due < today) return "overdue";
  if (due.getTime() === today.getTime()) return "today";
  return "upcoming";
}

const DUE_DATE_STYLES = {
  overdue: "text-red-600 bg-red-50",
  today: "text-amber-600 bg-amber-50",
  upcoming: "text-[var(--gray-text)] bg-[var(--surface)]",
};

export const KanbanCard = ({ card, onClick, onDelete }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const dueDateStatus = getDueDateStatus(card.due_date);

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group cursor-pointer rounded-2xl border border-transparent bg-white px-4 py-4 shadow-[0_12px_24px_rgba(3,33,71,0.08)]",
        "transition-all duration-150",
        isDragging && "opacity-60 shadow-[0_18px_32px_rgba(3,33,71,0.16)]"
      )}
      {...attributes}
      {...listeners}
      onClick={onClick}
      data-testid={`card-${card.id}`}
    >
      {card.labels.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {card.labels.map((label) => (
            <span
              key={label.id}
              className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-white"
              style={{ backgroundColor: label.color }}
            >
              {label.name}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: PRIORITY_COLORS[card.priority] }}
              title={`${card.priority} priority`}
            />
            <h4 className="font-display text-sm font-semibold text-[var(--navy-dark)]">
              {card.title}
            </h4>
          </div>
          <p className="mt-1 text-xs leading-5 text-[var(--gray-text)]">
            {card.details}
          </p>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(card.id);
          }}
          className="shrink-0 rounded-lg p-1.5 text-[var(--gray-text)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-500"
          aria-label={`Delete ${card.title}`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18" />
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
          </svg>
        </button>
      </div>
      {dueDateStatus && (
        <div className="mt-2">
          <span className={clsx("rounded-md px-1.5 py-0.5 text-[10px] font-semibold", DUE_DATE_STYLES[dueDateStatus])}>
            {card.due_date}
          </span>
        </div>
      )}
    </article>
  );
};
