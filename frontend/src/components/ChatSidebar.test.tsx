import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatSidebar } from "@/components/ChatSidebar";
import type { BoardData } from "@/lib/kanban";

const mockBoard: BoardData = {
  columns: [{ id: "col-1", title: "Backlog", cardIds: [] }],
  cards: {},
};

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual("@/lib/api");
  return {
    ...actual,
    aiChat: vi.fn(() =>
      Promise.resolve({
        message: "Done!",
        actions: [{ type: "create_card" }],
        board: mockBoard,
      })
    ),
  };
});

const mockOnBoardUpdate = vi.fn();

describe("ChatSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows chat button when closed", () => {
    render(<ChatSidebar onBoardUpdate={mockOnBoardUpdate} />);
    expect(screen.getByRole("button", { name: /open ai chat/i })).toBeInTheDocument();
  });

  it("opens sidebar when button is clicked", async () => {
    render(<ChatSidebar onBoardUpdate={mockOnBoardUpdate} />);
    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    expect(screen.getByText("AI Assistant")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toBeInTheDocument();
  });

  it("sends message and displays response", async () => {
    render(<ChatSidebar onBoardUpdate={mockOnBoardUpdate} />);
    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));

    const input = screen.getByLabelText("Chat message");
    await userEvent.type(input, "Add a card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    // User message appears
    expect(screen.getByText("Add a card")).toBeInTheDocument();

    // AI response appears
    await waitFor(() => {
      expect(screen.getByText("Done!")).toBeInTheDocument();
    });

    // Board update callback was called because actions were returned
    expect(mockOnBoardUpdate).toHaveBeenCalledWith(mockBoard);
  });

  it("closes sidebar when close is clicked", async () => {
    render(<ChatSidebar onBoardUpdate={mockOnBoardUpdate} />);
    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    expect(screen.getByText("AI Assistant")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /close chat/i }));
    expect(screen.queryByText("AI Assistant")).not.toBeInTheDocument();
  });
});
