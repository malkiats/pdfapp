import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToolSearch } from "@/components/tools/ToolSearch";
import { getToolSummaries } from "@/services/catalog";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

describe("ToolSearch", () => {
  beforeEach(() => push.mockReset());

  it("filters the catalog as the user types and links to tool pages", async () => {
    const user = userEvent.setup();
    render(<ToolSearch tools={getToolSummaries()} />);
    await user.type(screen.getByRole("searchbox", { name: "Search tools" }), "merge");
    const results = screen.getByRole("list", { name: "Search results" });
    const first = results.querySelector("a");
    expect(first).toHaveAttribute("href", "/tools/merge-pdf");
    expect(screen.getByRole("status")).toHaveTextContent(/tools? found/);
  });

  it("opens the top result on Enter", async () => {
    const user = userEvent.setup();
    render(<ToolSearch tools={getToolSummaries()} />);
    await user.type(screen.getByRole("searchbox"), "merge{Enter}");
    expect(push).toHaveBeenCalledWith("/tools/merge-pdf");
  });

  it("supports arrow-key navigation and Escape", async () => {
    const user = userEvent.setup();
    render(<ToolSearch tools={getToolSummaries()} />);
    const input = screen.getByRole("searchbox");
    await user.type(input, "pdf");
    await user.keyboard("{ArrowDown}");
    const links = screen.getByRole("list", { name: "Search results" }).querySelectorAll("a");
    expect(links[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(links[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(input).toHaveFocus();
    await user.keyboard("{ArrowDown}{Escape}");
    expect(input).toHaveFocus();
    expect(input).toHaveValue("");
    expect(screen.queryByRole("list", { name: "Search results" })).not.toBeInTheDocument();
  });

  it("shows a helpful empty state", async () => {
    const user = userEvent.setup();
    render(<ToolSearch tools={getToolSummaries()} />);
    await user.type(screen.getByRole("searchbox"), "qqqqzzzz");
    expect(screen.getByText(/No tools match “qqqqzzzz”/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("No tools match your search.");
    expect(screen.getByRole("link", { name: "Browse all tools" })).toHaveAttribute("href", "/tools");
  });
});
