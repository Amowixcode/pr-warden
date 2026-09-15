import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useHealthAwareLoading } from "./useHealthAwareLoading";
import * as client from "../api/client";

describe("useHealthAwareLoading", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts at idle, and returns to idle once the task settles", async () => {
    vi.spyOn(client, "getHealth").mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useHealthAwareLoading());

    expect(result.current.phase).toBe("idle");

    await act(async () => {
      await result.current.run(() => Promise.resolve("done"));
    });

    expect(result.current.phase).toBe("idle");
  });

  it("is 'waking' before /health answers, then 'running' once it does — while the task is still in flight", async () => {
    let resolveHealth!: () => void;
    vi.spyOn(client, "getHealth").mockReturnValue(
      new Promise((resolve) => {
        resolveHealth = () => resolve({ status: "ok" });
      }),
    );
    let resolveTask!: (v: string) => void;
    const { result } = renderHook(() => useHealthAwareLoading());

    act(() => {
      void result.current.run(() => new Promise((resolve) => (resolveTask = resolve)));
    });
    expect(result.current.phase).toBe("waking");

    await act(async () => {
      resolveHealth();
      await Promise.resolve();
    });
    expect(result.current.phase).toBe("running");

    await act(async () => {
      resolveTask("done");
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.phase).toBe("idle"));
  });

  it("a failed health check doesn't change the phase — stays 'waking' until the real request settles", async () => {
    vi.spyOn(client, "getHealth").mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useHealthAwareLoading());

    let resolveTask!: (v: string) => void;
    act(() => {
      void result.current.run(() => new Promise((resolve) => (resolveTask = resolve)));
    });

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.phase).toBe("waking");

    await act(async () => {
      resolveTask("done");
    });
    await waitFor(() => expect(result.current.phase).toBe("idle"));
  });
});
