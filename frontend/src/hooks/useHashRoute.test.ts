import { describe, expect, it } from "vitest";
import { parseHash } from "./useHashRoute";

describe("parseHash", () => {
  it("treats an empty hash as home", () => {
    expect(parseHash("")).toEqual({ view: "home" });
    expect(parseHash("#")).toEqual({ view: "home" });
    expect(parseHash("#/")).toEqual({ view: "home" });
    expect(parseHash("#/home")).toEqual({ view: "home" });
  });

  it("parses a review-detail route", () => {
    expect(parseHash("#/review/42")).toEqual({ view: "review-detail", id: 42 });
  });

  it("parses a bare review-form route", () => {
    expect(parseHash("#/review")).toEqual({ view: "review-form", prefillRepo: undefined, prefillPr: undefined });
  });

  it("parses a review-form route with prefill query params", () => {
    expect(parseHash("#/review?repo=facebook%2Freact&pr=123")).toEqual({
      view: "review-form",
      prefillRepo: "facebook/react",
      prefillPr: 123,
    });
  });

  it("ignores a non-numeric pr in the prefill query", () => {
    expect(parseHash("#/review?repo=facebook%2Freact&pr=abc")).toEqual({
      view: "review-form",
      prefillRepo: "facebook/react",
      prefillPr: undefined,
    });
  });

  it("parses the plain section routes", () => {
    expect(parseHash("#/history")).toEqual({ view: "section", section: "history" });
    expect(parseHash("#/prs")).toEqual({ view: "section", section: "prs" });
  });

  it("falls back to home for anything unrecognized — never a dead route", () => {
    expect(parseHash("#/nonsense")).toEqual({ view: "home" });
    // /ingest is no longer a route at all — dropped from the public UI.
    expect(parseHash("#/ingest")).toEqual({ view: "home" });
    expect(parseHash("#/review/not-a-number")).toEqual({
      view: "review-form",
      prefillRepo: undefined,
      prefillPr: undefined,
    });
  });
});
