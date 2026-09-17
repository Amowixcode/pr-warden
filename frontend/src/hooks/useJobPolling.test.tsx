import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useJobPolling } from "./useJobPolling";
import * as client from "../api/client";
import type { Job } from "../api/types";

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

async function _flushMicrotasks() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useJobPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("stays idle when there is no job to poll", () => {
    const { result } = renderHook(() => useJobPolling(undefined));

    expect(result.current.status).toBeNull();
  });

  it("polls immediately on mount and reflects the running stage", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(_job({ stage: "retrieving context" }));

    const { result } = renderHook(() => useJobPolling("job-1", 2000));
    await _flushMicrotasks();

    expect(result.current.status).toBe("running");
    expect(result.current.stage).toBe("retrieving context");
  });

  it("stops polling and captures the result once the job succeeds", async () => {
    const getJob = vi
      .spyOn(client, "getJob")
      .mockResolvedValueOnce(_job({ status: "running" }))
      .mockResolvedValueOnce(
        _job({ status: "succeeded", stage: "done", result: { pr_number: 7 } as never }),
      );

    const { result } = renderHook(() => useJobPolling("job-1", 2000));
    await _flushMicrotasks();
    expect(result.current.status).toBe("running");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(result.current.status).toBe("succeeded");
    expect(result.current.result).toEqual({ pr_number: 7 });

    const callsAfterTerminal = getJob.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(getJob.mock.calls.length).toBe(callsAfterTerminal);
  });

  it("stops polling and captures the error once the job fails", async () => {
    const getJob = vi
      .spyOn(client, "getJob")
      .mockResolvedValueOnce(_job({ status: "running" }))
      .mockResolvedValueOnce(_job({ status: "failed", stage: "running review agents", error: "boom" }));

    const { result } = renderHook(() => useJobPolling("job-1", 2000));
    await _flushMicrotasks();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.error).toBe("boom");

    const callsAfterTerminal = getJob.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(getJob.mock.calls.length).toBe(callsAfterTerminal);
  });

  it("resets to idle when jobId is cleared", async () => {
    vi.spyOn(client, "getJob").mockResolvedValue(_job());

    const { result, rerender } = renderHook(
      ({ jobId }: { jobId: string | undefined }) => useJobPolling(jobId),
      { initialProps: { jobId: "job-1" as string | undefined } },
    );
    await _flushMicrotasks();
    expect(result.current.status).toBe("running");

    act(() => {
      rerender({ jobId: undefined });
    });

    expect(result.current.status).toBeNull();
  });

  it("keeps polling through a transient fetch error", async () => {
    const getJob = vi
      .spyOn(client, "getJob")
      .mockRejectedValueOnce(new Error("network blip"))
      .mockResolvedValueOnce(_job({ status: "succeeded", stage: "done" }));

    const { result } = renderHook(() => useJobPolling("job-1", 2000));
    await _flushMicrotasks();
    expect(result.current.status).toBe("running");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(getJob.mock.calls.length).toBe(2);
    expect(result.current.status).toBe("succeeded");
  });
});
