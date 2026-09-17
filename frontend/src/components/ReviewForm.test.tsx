import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewForm } from "./ReviewForm";
import * as client from "../api/client";
import type { AgentResult, Job, ReviewResponse } from "../api/types";

function _agentResult(overrides: Partial<AgentResult> = {}): AgentResult {
  return { summary: "Looks fine", verdict: "APPROVE", issues: [], suggestions: [], ...overrides };
}

function _reviewResponse(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
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
    ...overrides,
  };
}

function _job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    kind: "review",
    status: "running",
    stage: "running review agents",
    result: null,
    error: null,
    created_at: "2024-06-01T00:00:00Z",
    updated_at: "2024-06-01T00:00:00Z",
    ...overrides,
  };
}

async function _flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("ReviewForm", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("submitting the form starts a job and navigates to include its id", async () => {
    vi.spyOn(client, "reviewPr").mockResolvedValue({ job_id: "new-job-id" });
    const onNavigate = vi.fn();

    render(<ReviewForm onNavigate={onNavigate} />);

    fireEvent.change(screen.getByLabelText("Repository"), {
      target: { value: "octocat/Hello-World" },
    });
    fireEvent.change(screen.getByLabelText("PR number"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Review PR" }));
    await _flush();

    expect(client.reviewPr).toHaveBeenCalledWith(
      "octocat/Hello-World",
      7,
      expect.any(String),
      false,
    );
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringMatching(/^#\/review\?repo=octocat%2FHello-World&pr=7&job=.+$/),
    );
  });

  it("resuming from a jobId prop polls and shows the running stage, without a fresh submit", async () => {
    const getJob = vi.spyOn(client, "getJob").mockResolvedValue(_job());
    const reviewPr = vi.spyOn(client, "reviewPr");

    render(<ReviewForm jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(getJob).toHaveBeenCalledWith("job-1");
    expect(reviewPr).not.toHaveBeenCalled();
    expect(screen.getByText("running review agents")).toBeInTheDocument();
  });

  it("shows the review results once the job succeeds", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(
      _job({ status: "succeeded", stage: "done", result: _reviewResponse() }),
    );

    render(<ReviewForm prefillRepo="octocat/Hello-World" jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(
      screen.getByText("No blocking concerns from security, quality, or test coverage review."),
    ).toBeInTheDocument();
  });

  it("shows an error banner once the job fails", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(
      _job({ status: "failed", error: "GitHub API error: Not Found" }),
    );

    render(<ReviewForm jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(screen.getByText("GitHub API error: Not Found")).toBeInTheDocument();
  });
});
