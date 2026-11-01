import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setTheme = vi.fn();
let theme = "system";
vi.mock("next-themes", () => ({ useTheme: () => ({ theme, setTheme }) }));

import { nextTheme, ThemeToggle } from "@/components/layout/ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    setTheme.mockReset();
    theme = "system";
  });

  it("cycles system -> light -> dark -> system", () => {
    expect(nextTheme("system")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("system");
    expect(nextTheme(undefined)).toBe("light");
  });

  it("announces the current and next theme and switches on click", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Theme: system. Switch to light theme" });
    await user.click(button);
    expect(setTheme).toHaveBeenCalledWith("light");
  });

  it("reflects a stored dark theme and is keyboard operable", async () => {
    theme = "dark";
    const user = userEvent.setup();
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Theme: dark. Switch to system theme" });
    button.focus();
    await user.keyboard("{Enter}");
    expect(setTheme).toHaveBeenCalledWith("system");
  });
});
