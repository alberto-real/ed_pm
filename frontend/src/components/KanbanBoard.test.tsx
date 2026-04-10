import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardData } from "@/lib/kanban";

const mockBoard: BoardData = {
  columns: [
    { id: "1", title: "Backlog", cardIds: ["10", "11"] },
    { id: "2", title: "Discovery", cardIds: [] },
    { id: "3", title: "In Progress", cardIds: [] },
    { id: "4", title: "Review", cardIds: [] },
    { id: "5", title: "Done", cardIds: [] },
  ],
  cards: {
    "10": { id: "10", title: "Card A", details: "Details A", description: "", due_date: null, priority: "medium", labels: [] },
    "11": { id: "11", title: "Card B", details: "Details B", description: "", due_date: "2026-04-15", priority: "high", labels: [{ id: "label-1", name: "Bug", color: "#e74c3c" }] },
  },
};

const mockBoards = [
  { id: "board-1", title: "My Board" },
];

vi.mock("@/lib/api", () => ({
  fetchBoards: vi.fn(() => Promise.resolve(structuredClone(mockBoards))),
  fetchBoard: vi.fn(() => Promise.resolve(structuredClone(mockBoard))),
  fetchLabels: vi.fn(() => Promise.resolve([{ id: "label-1", name: "Bug", color: "#e74c3c" }])),
  createBoard: vi.fn((title: string) =>
    Promise.resolve({ id: "board-2", title })
  ),
  renameBoard: vi.fn(() => Promise.resolve()),
  deleteBoard: vi.fn(() => Promise.resolve()),
  addCard: vi.fn((_boardId: string, _col: string, title: string, details: string) =>
    Promise.resolve({ id: "99", title, details, description: "", due_date: null, priority: "medium", labels: [] })
  ),
  updateCard: vi.fn(() => Promise.resolve()),
  deleteCard: vi.fn(() => Promise.resolve()),
  moveCard: vi.fn(() => Promise.resolve()),
  renameColumn: vi.fn(() => Promise.resolve()),
  aiChat: vi.fn(() => Promise.resolve({ message: "", actions: [], board: {} })),
  addLabelToCard: vi.fn(() => Promise.resolve()),
  removeLabelFromCard: vi.fn(() => Promise.resolve()),
}));

const mockLogout = vi.fn();

const renderBoard = async (props?: { username?: string; onLogout?: () => void }) => {
  render(<KanbanBoard {...props} />);
  await waitFor(() => {
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });
};

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders five columns from API", async () => {
    await renderBoard();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
    expect(screen.getByText("Card A")).toBeInTheDocument();
    expect(screen.getByText("Card B")).toBeInTheDocument();
  });

  it("renames a column", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { renameColumn } = await import("@/lib/api");
    render(<KanbanBoard />);
    await waitFor(() => {
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
    });
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await user.clear(input);
    await user.type(input, "New Name");
    expect(input).toHaveValue("New Name");
    vi.advanceTimersByTime(500);
    expect(renameColumn).toHaveBeenCalledWith("board-1", "1", "New Name");
    vi.useRealTimers();
  });

  it("adds and removes a card", async () => {
    const { addCard, deleteCard } = await import("@/lib/api");
    await renderBoard();
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(
      within(column).getByRole("button", { name: /add card/i })
    );

    await waitFor(() => {
      expect(within(column).getByText("New card")).toBeInTheDocument();
    });
    expect(addCard).toHaveBeenCalledWith("board-1", "1", "New card", "Notes");

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    expect(deleteCard).toHaveBeenCalledWith("board-1", "99");
  });

  it("shows sign out button when username is provided", async () => {
    await renderBoard({ username: "user", onLogout: mockLogout });
    expect(screen.getByText("user")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign out/i })
    ).toBeInTheDocument();
  });

  it("calls onLogout when sign out is clicked", async () => {
    await renderBoard({ username: "user", onLogout: mockLogout });
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(mockLogout).toHaveBeenCalled();
  });

  it("reloads board when addCard fails", async () => {
    const { addCard, fetchBoard } = await import("@/lib/api");
    (addCard as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("500"));
    await renderBoard();
    const column = getFirstColumn();
    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i })
    );
    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "Fail card");
    await userEvent.click(
      within(column).getByRole("button", { name: /add card/i })
    );
    await waitFor(() => {
      expect(fetchBoard).toHaveBeenCalledTimes(2);
    });
  });

  it("reloads board when deleteCard fails", async () => {
    const { deleteCard, fetchBoard } = await import("@/lib/api");
    (deleteCard as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("500"));
    await renderBoard();
    const column = getFirstColumn();
    const deleteButton = within(column).getAllByRole("button", {
      name: /delete/i,
    })[0];
    await userEvent.click(deleteButton);
    await waitFor(() => {
      expect(fetchBoard).toHaveBeenCalledTimes(2);
    });
  });

  it("shows board switcher with board name", async () => {
    await renderBoard();
    expect(screen.getByRole("button", { name: /switch board/i })).toHaveTextContent("My Board");
  });

  it("displays labels and priority on cards", async () => {
    await renderBoard();
    // Card B has a Bug label and high priority
    expect(screen.getByText("Bug")).toBeInTheDocument();
    // Card B has a due date
    expect(screen.getByText("2026-04-15")).toBeInTheDocument();
  });

  it("opens card detail modal on click", async () => {
    await renderBoard();
    const cardA = screen.getByTestId("card-10");
    await userEvent.click(cardA);
    // Modal should appear with card title in an input
    expect(screen.getByDisplayValue("Card A")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});
