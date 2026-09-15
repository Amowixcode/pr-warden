import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReviewDetail } from "./ReviewDetail";
import { ApiError } from "../api/client";
import * as client from "../api/client";

const agent = { summary: "ok", verdict: "APPROVE" as const, issues: [], suggestions: [] };

describe("ReviewDetail", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state, then the full review with per-agent tabs", async () => {
    vi.spyOn(client, "getReviewDetail").mockResolvedValue({
      id: 1,
      repo: "octocat/Hello-World",
      pr_number: 7,
      head_sha: "deadbeef",
      verdict: "APPROVE",
      summary: "Looks good",
      issues: [],
      suggestions: [],
      security_result: agent,
      quality_result: agent,
      test_result: agent,
      created_at: "2024-06-01T00:00:00Z",
    });

    render(<ReviewDetail id={1} />);

    expect(screen.getByText("Loading review…")).toBeInTheDocument();
    expect(await screen.findByText("Looks good")).toBeInTheDocument();
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("shows a not-found state on a 404", async () => {
    vi.spyOn(client, "getReviewDetail").mockRejectedValue(new ApiError(404, "review not found"));

    render(<ReviewDetail id={999} />);

    expect(await screen.findByText(/Review not found/)).toBeInTheDocument();
  });

  it("passes null per-agent results through without fabricating them", async () => {
    vi.spyOn(client, "getReviewDetail").mockResolvedValue({
      id: 1,
      repo: "octocat/Hello-World",
      pr_number: 7,
      head_sha: "deadbeef",
      verdict: "REQUEST_CHANGES",
      summary: "Needs work",
      issues: [],
      suggestions: [],
      security_result: null,
      quality_result: null,
      test_result: null,
      created_at: "2024-06-01T00:00:00Z",
    });

    render(<ReviewDetail id={1} />);

    expect(
      await screen.findAllByText("Per-agent detail not available for this review."),
    ).toHaveLength(3);
  });
});
