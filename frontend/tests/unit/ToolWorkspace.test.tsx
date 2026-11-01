import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToolWorkspace } from "@/components/tools/ToolWorkspace";

const base = {
  toolSlug: "merge-pdf",
  title: "Merge PDF",
  inputKinds: ["file" as const],
  accepts: ["application/pdf"],
  minInputs: 2,
  maxInputs: 5,
  maxFileBytes: 25 * 1024 * 1024,
  requiresAiConsent: false,
};

describe("ToolWorkspace", () => {
  it("disables every input and labels the tool as coming soon", () => {
    render(<ToolWorkspace {...base} status="coming_soon" />);
    expect(screen.getByText(/coming soon/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeDisabled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("enables the dropzone when the tool is available", () => {
    render(<ToolWorkspace {...base} status="available" />);
    expect(screen.queryByText(/Coming soon/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeEnabled();
  });

  it("renders URL inputs and AI consent for URL/AI tools", () => {
    render(
      <ToolWorkspace
        {...base}
        title="Compare webpages"
        inputKinds={["url"]}
        accepts={[]}
        maxInputs={2}
        requiresAiConsent
        status="coming_soon"
      />,
    );
    expect(screen.getByLabelText("First page URL")).toBeDisabled();
    expect(screen.getByLabelText("Second page URL")).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /AI provider/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Choose files" })).not.toBeInTheDocument();
  });
});
