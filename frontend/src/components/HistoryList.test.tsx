import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HistoryList } from "./HistoryList";
import * as client from "../api/client";

describe("HistoryList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("links each row's PR number to the review-detail hash route", async () => {
    vi.spyOn(client, "getReviewHistory").mockResolvedValue([
      {
        id: 42,
        repo: "octocat/Hello-World",
        pr_number: 7,
        head_sha: "deadbeef",
        verdict: "APPROVE",
        summary: "Looks good",
        issues: [],
        suggestions: [],
        created_at: "2024-06-01T00:00:00Z",
      },
    ]);

    render(<HistoryList />);

    const link = await screen.findByRole("link", { name: "#7" });
    expect(link).toHaveAttribute("href", "#/review/42");
  });

  it("also links each row to the PR on GitHub", async () => {
    vi.spyOn(client, "getReviewHistory").mockResolvedValue([
      {
        id: 42,
        repo: "octocat/Hello-World",
        pr_number: 7,
        head_sha: "deadbeef",
        verdict: "APPROVE",
        summary: "Looks good",
        issues: [],
        suggestions: [],
        created_at: "2024-06-01T00:00:00Z",
      },
    ]);

    render(<HistoryList />);

    const githubLink = await screen.findByRole("link", { name: /View PR/ });
    expect(githubLink).toHaveAttribute("href", "https://github.com/octocat/Hello-World/pull/7");
  });

  it("uses the quiet StatusTag treatment for row verdicts, not the filled pill", async () => {
    vi.spyOn(client, "getReviewHistory").mockResolvedValue([
      {
        id: 1,
        repo: "octocat/Hello-World",
        pr_number: 1,
        head_sha: "sha",
        verdict: "REQUEST_CHANGES",
        summary: "Needs work",
        issues: [],
        suggestions: [],
        created_at: "2024-06-01T00:00:00Z",
      },
    ]);

    render(<HistoryList />);

    const badge = await screen.findByText("Request changes");
    expect(badge.closest(".tag")).toBeInTheDocument();
    expect(badge.closest(".verdict-pill")).toBeNull();
  });
});
