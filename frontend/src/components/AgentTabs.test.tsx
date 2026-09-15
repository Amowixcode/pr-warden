import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AgentTabs, type AgentResults } from "./AgentTabs";

function makeResults(overrides: Partial<AgentResults> = {}): AgentResults {
  return {
    security: { summary: "No security concerns found.", verdict: "APPROVE", issues: [], suggestions: [] },
    quality: {
      summary: "Minor issues.",
      verdict: "COMMENT",
      issues: ["file.py:1 - a quality issue"],
      suggestions: [],
    },
    test: {
      summary: "Missing coverage.",
      verdict: "REQUEST_CHANGES",
      issues: ["file.py:2 - a test issue"],
      suggestions: [],
    },
    ...overrides,
  };
}

describe("AgentTabs", () => {
  it("renders a tablist with the right roles and finding counts", () => {
    render(<AgentTabs results={makeResults()} />);

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveAttribute("aria-selected", "false");
  });

  it("switches the active tab and panel on click", async () => {
    const user = userEvent.setup();
    render(<AgentTabs results={makeResults()} />);

    await user.click(screen.getByRole("tab", { name: /Quality/ }));

    expect(screen.getByRole("tab", { name: /Quality/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: /Quality/ })).not.toHaveAttribute("hidden");
  });

  it("moves selection with the right/left arrow keys", async () => {
    const user = userEvent.setup();
    render(<AgentTabs results={makeResults()} />);

    screen.getByRole("tab", { name: /Security/ }).focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: /Quality/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Quality/ })).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: /Security/ })).toHaveAttribute("aria-selected", "true");
  });

  it("renders a clean, finished zero-issues state — not an apology", () => {
    render(<AgentTabs results={makeResults()} />);

    expect(screen.getByText("No security concerns found.")).toBeInTheDocument();
    expect(screen.getByText("No issues found.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Security/ })).toHaveTextContent("0");
  });

  it("shows an unavailable message when a per-agent result is null", async () => {
    const user = userEvent.setup();
    render(<AgentTabs results={makeResults({ quality: null })} />);

    await user.click(screen.getByRole("tab", { name: /Quality/ }));

    expect(screen.getByText("Per-agent detail not available for this review.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Quality/ })).toHaveTextContent("—");
  });
});
