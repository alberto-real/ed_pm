import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "@/components/LoginForm";

const mockOnLogin = vi.fn();

beforeEach(() => {
  mockOnLogin.mockClear();
  vi.restoreAllMocks();
});

describe("LoginForm", () => {
  it("renders username and password fields", () => {
    render(<LoginForm onLogin={mockOnLogin} />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls onLogin after successful login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({ username: "user" }),
    } as Response);

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/login", expect.objectContaining({
      method: "POST",
    }));
    expect(mockOnLogin).toHaveBeenCalledWith("user");
  });

  it("shows error on invalid credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ error: "Invalid credentials" }),
    } as Response);

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
    expect(mockOnLogin).not.toHaveBeenCalled();
  });
});
