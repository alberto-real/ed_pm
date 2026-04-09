"use client";

import { useRef, useState, type FormEvent } from "react";
import { aiChat, type AiChatResponse, type ChatMessage } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type ChatSidebarProps = {
  onBoardUpdate: (board: BoardData) => void;
};

export const ChatSidebar = ({ onBoardUpdate }: ChatSidebarProps) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const result: AiChatResponse = await aiChat(updatedMessages);
      const assistantMsg: ChatMessage = { role: "assistant", content: result.message };
      setMessages((prev) => [...prev, assistantMsg]);
      if (result.actions.length > 0) {
        onBoardUpdate(result.board);
      }
    } catch {
      const errorMsg: ChatMessage = { role: "assistant", content: "Sorry, something went wrong." };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--secondary-purple)] text-white shadow-lg transition hover:brightness-110"
        aria-label="Open AI chat"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </button>
    );
  }

  return (
    <aside className="fixed bottom-0 right-0 top-0 z-50 flex w-[400px] flex-col border-l border-[var(--stroke)] bg-white shadow-[-8px_0_24px_rgba(3,33,71,0.08)]">
      <header className="flex items-center justify-between border-b border-[var(--stroke)] px-5 py-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-[var(--navy-dark)]">
            AI Assistant
          </h2>
          <p className="text-xs text-[var(--gray-text)]">
            Ask me to manage your board
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
          aria-label="Close chat"
        >
          Close
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <p className="text-center text-sm text-[var(--gray-text)]">
            Try: &quot;Add a card called Planning to Backlog&quot; or &quot;Move all Review cards to Done&quot;
          </p>
        )}
        <div className="space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-[var(--secondary-purple)] text-white"
                    : "border border-[var(--stroke)] bg-[var(--surface)] text-[var(--navy-dark)]"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--gray-text)]">
                Thinking...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="border-t border-[var(--stroke)] px-5 py-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the AI..."
            disabled={loading}
            className="flex-1 rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)] disabled:opacity-50"
            aria-label="Chat message"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-xl bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
};
