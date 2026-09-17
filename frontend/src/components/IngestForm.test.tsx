import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IngestForm } from "./IngestForm";
import * as client from "../api/client";
import type { IngestResponse, Job } from "../api/types";

function _ingestResponse(overrides: Partial<IngestResponse> = {}): IngestResponse {
  return {
    issues_indexed: 3,
    prs_indexed: 2,
    commits_indexed: 10,
    total_newly_indexed: 15,
    incremental: false,
    ...overrides,
  };
}

function _job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    kind: "ingest",
    status: "running",
    stage: "fetching repository data",
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

describe("IngestForm", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("submitting the form starts a job and navigates to include its id", async () => {
    vi.spyOn(client, "ingestRepository").mockResolvedValue({ job_id: "new-job-id" });
    const onNavigate = vi.fn();

    render(<IngestForm onNavigate={onNavigate} />);

    fireEvent.change(screen.getByLabelText("Repository"), {
      target: { value: "octocat/Hello-World" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingest" }));
    await _flush();

    expect(client.ingestRepository).toHaveBeenCalledWith("octocat/Hello-World", expect.any(String));
    expect(onNavigate).toHaveBeenCalledWith(expect.stringMatching(/^#\/ingest\?job=.+$/));
  });

  it("resuming from a jobId prop polls and shows the running stage, without a fresh submit", async () => {
    const getJob = vi.spyOn(client, "getJob").mockResolvedValue(_job());
    const ingestRepository = vi.spyOn(client, "ingestRepository");

    render(<IngestForm jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(getJob).toHaveBeenCalledWith("job-1");
    expect(ingestRepository).not.toHaveBeenCalled();
    expect(screen.getByText("fetching repository data")).toBeInTheDocument();
  });

  it("shows the ingest summary once the job succeeds", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(
      _job({ status: "succeeded", stage: "done", result: _ingestResponse() }),
    );

    render(<IngestForm jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(screen.getByText(/Indexed 3 issues, 2 merged PRs, and 10 commits/)).toBeInTheDocument();
  });

  it("shows an error banner once the job fails", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(_job({ status: "failed", error: "boom" }));

    render(<IngestForm jobId="job-1" onNavigate={vi.fn()} />);
    await _flush();

    expect(screen.getByText("boom")).toBeInTheDocument();
  });
});
