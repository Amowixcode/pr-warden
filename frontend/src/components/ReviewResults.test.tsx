import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewResults } from "./ReviewResults";
import type { AgentResult, ReviewResponse } from "../api/types";

function _agentResult(overrides: Partial<AgentResult> = {}): AgentResult {
  return { summary: "Looks fine", verdict: "APPROVE", issues: [], suggestions: [], ...overrides };
}

function _result(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    pr_number: 7,
    summary: "No blocking concerns from security, quality, or test coverage review.",
    verdict: "APPROVE",
    issues: [],
    suggestions: [],
    security_result: _agentResult(),
    quality_result: _agentResult(),
    test_result: _agentResult(),
    incremental: false,
    cached: false,
    prior_verdict: null,
    prior_head_sha: null,
    status: "reviewed",
    not_reviewed: [],
    ...overrides,
  };
}

describe("ReviewResults", () => {
  it("shows no Re-run button for a fresh review", () => {
    render(<ReviewResults result={_result()} repo="octocat/Hello-World" onRerun={() => {}} />);

    expect(screen.queryByText("Re-run")).not.toBeInTheDocument();
  });

  it("shows no Re-run button for an incremental (non-cached) review", () => {
    render(
      <ReviewResults
        result={_result({ incremental: true, cached: false })}
        repo="octocat/Hello-World"
        onRerun={() => {}}
      />,
    );

    expect(screen.queryByText("Re-run")).not.toBeInTheDocument();
  });

  it("shows a Re-run button next to the cached tag, and calls onRerun on click", () => {
    const onRerun = vi.fn();
    render(
      <ReviewResults
        result={_result({ incremental: true, cached: true })}
        repo="octocat/Hello-World"
        onRerun={onRerun}
      />,
    );

    const button = screen.getByText("Re-run");
    expect(button).toBeInTheDocument();

    fireEvent.click(button);

    expect(onRerun).toHaveBeenCalledOnce();
  });

  it("lists files that were not reviewed", () => {
    render(
      <ReviewResults
        result={_result({ not_reviewed: ["logo.png", "dist/bundle.js"] })}
        repo="octocat/Hello-World"
      />,
    );

    expect(screen.getByText("Not reviewed: logo.png, dist/bundle.js")).toBeInTheDocument();
  });

  it("shows no Not reviewed line when every file was reviewed", () => {
    render(<ReviewResults result={_result()} repo="octocat/Hello-World" />);

    expect(screen.queryByText(/Not reviewed/)).not.toBeInTheDocument();
  });

  it("shows the nothing-new message without a Re-run button", () => {
    render(
      <ReviewResults
        result={_result({
          status: "nothing_new",
          incremental: true,
          summary: "Nothing new to review since abc1234.",
          prior_verdict: "APPROVE",
          prior_head_sha: "abc1234def",
        })}
        repo="octocat/Hello-World"
        onRerun={() => {}}
      />,
    );

    expect(screen.getAllByText("Nothing new to review since abc1234.").length).toBeGreaterThan(0);
    expect(screen.queryByText("Re-run")).not.toBeInTheDocument();
  });
});
