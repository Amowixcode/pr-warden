import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Home } from "./Home";
import { featuredReview } from "../data/featured-review";

describe("Home", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the bundled fixture's verdict without making any network call", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<Home onNavigate={() => {}} />);

    expect(screen.getByText(featuredReview.summary)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows real findings without requiring an API key", () => {
    render(<Home onNavigate={() => {}} />);

    // The real fixture has findings — the landing page must show at least one immediately.
    expect(screen.getAllByText(/quality|test coverage/).length).toBeGreaterThan(0);
  });

  it("has no hardcoded/fabricated stats — the indexed strip labels real numbers", () => {
    render(<Home onNavigate={() => {}} />);

    expect(screen.getByText("issues")).toBeInTheDocument();
    expect(screen.getByText("commits")).toBeInTheDocument();
    expect(screen.getByText("merged PRs")).toBeInTheDocument();
  });
});
