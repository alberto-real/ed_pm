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
    "10": { id: "10", title: "Card A", details: "Details A" },
    "11": { id: "11", title: "Card B", details: "Details B" },
  },
};

vi.mock("@/lib/api", () => ({
  fetchBoard: vi.fn(() => Promise.resolve(structuredClone(mockBoard))),
  addCard: vi.fn((_col: string, title: string, details: string) =>
    Promise.resolve({ id: "99", title, details })
  ),
  deleteCard: vi.fn(() => Promise.resolve()),
  moveCard: vi.fn(() => Promise.resolve()),
  renameColumn: vi.fn(() => Promise.resolve()),
  updateCard: vi.fn(() => Promise.resolve()),
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
    const { renameColumn } = await import("@/lib/api");
    await renderBoard();
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
    expect(renameColumn).toHaveBeenCalledWith("1", "New Name");
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
    expect(addCard).toHaveBeenCalledWith("1", "New card", "Notes");

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    expect(deleteCard).toHaveBeenCalledWith("99");
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
});
