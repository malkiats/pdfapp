import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ProcessingStatus } from "@/components/tools/ProcessingStatus";

describe("ProcessingStatus (Phase 1 synchronous)", () => {
  it("is a polite live region", () => {
    render(<ProcessingStatus state={{ phase: "idle" }} />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText(/deleted automatically/)).toBeInTheDocument();
  });

  it("shows processing state with request ID", () => {
    render(<ProcessingStatus state={{ phase: "processing", requestId: "req_abc123" }} />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Working on it, this typically takes a few seconds.")).toBeInTheDocument();
    expect(screen.getByText("req_abc123")).toBeInTheDocument();
  });

  it("shows success with download action", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <ProcessingStatus state={{ phase: "succeeded", filename: "result.pdf" }} onDownload={onDownload} />,
    );
    expect(screen.getByText("Your result is ready")).toBeInTheDocument();
    expect(screen.getByText(/deleted automatically/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Download result" }));
    expect(onDownload).toHaveBeenCalledOnce();
  });

  it("maps error codes to friendly messages and offers retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ProcessingStatus
        state={{ phase: "failed", errorCode: "too_many_pages", requestId: "req_xyz" }}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("Processing failed")).toBeInTheDocument();
    expect(screen.getByText(/more pages than allowed/)).toBeInTheDocument();
    expect(screen.getByText("req_xyz")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("falls back to a generic message for unknown error codes", () => {
    render(<ProcessingStatus state={{ phase: "failed", errorCode: "unknown_future_code" }} />);
    expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
  });
});
