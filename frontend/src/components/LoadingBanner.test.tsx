import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoadingBanner } from "./LoadingBanner";

describe("LoadingBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when idle", () => {
    const { container } = render(<LoadingBanner phase="idle" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows "Waking up the server" only in the waking phase', () => {
    render(<LoadingBanner phase="waking" />);
    expect(screen.getByText(/Waking up the server/)).toBeInTheDocument();
  });

  it('"Waking up the server" is absent once the phase moves to running — an elapsed timer shows instead', () => {
    render(<LoadingBanner phase="running" runningLabel="Running review" />);

    expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
    expect(screen.getByText(/Running review… 0s/)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByText(/Running review… 3s/)).toBeInTheDocument();
  });
});
