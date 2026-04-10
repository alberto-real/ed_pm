import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "@/components/LoginForm";

vi.mock("@/lib/api", () => ({
  login: vi.fn(),
  register: vi.fn(),
}));

const mockOnLogin = vi.fn();

beforeEach(() => {
  mockOnLogin.mockClear();
  vi.clearAllMocks();
});

describe("LoginForm", () => {
  it("renders username and password fields", () => {
    render(<LoginForm onLogin={mockOnLogin} />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls onLogin after successful login", async () => {
    const { login } = await import("@/lib/api");
    (login as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ username: "user" });

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith("user", "password");
    expect(mockOnLogin).toHaveBeenCalledWith("user");
  });

  it("shows error on invalid credentials", async () => {
    const { login } = await import("@/lib/api");
    (login as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("401"));

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
    expect(mockOnLogin).not.toHaveBeenCalled();
  });

  it("toggles to register mode", async () => {
    render(<LoginForm onLogin={mockOnLogin} />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /register/i }));

    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByText("Get started")).toBeInTheDocument();
  });

  it("calls register on submit in register mode", async () => {
    const { register } = await import("@/lib/api");
    (register as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ username: "newuser" });

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.click(screen.getByRole("button", { name: /register/i }));

    await userEvent.type(screen.getByLabelText(/username/i), "newuser");
    await userEvent.type(screen.getByLabelText(/password/i), "secret123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(register).toHaveBeenCalledWith("newuser", "secret123");
    expect(mockOnLogin).toHaveBeenCalledWith("newuser");
  });

  it("shows error when username is taken", async () => {
    const { register } = await import("@/lib/api");
    (register as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("409"));

    render(<LoginForm onLogin={mockOnLogin} />);
    await userEvent.click(screen.getByRole("button", { name: /register/i }));

    await userEvent.type(screen.getByLabelText(/username/i), "taken");
    await userEvent.type(screen.getByLabelText(/password/i), "secret123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Username already taken");
    expect(mockOnLogin).not.toHaveBeenCalled();
  });
});
