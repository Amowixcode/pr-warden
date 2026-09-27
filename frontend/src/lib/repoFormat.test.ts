import { describe, expect, it } from "vitest";
import { parseOwnerRepo } from "./repoFormat";

describe("parseOwnerRepo", () => {
  it("parses a valid owner/repo string", () => {
    expect(parseOwnerRepo("facebook/react")).toEqual(["facebook", "react"]);
  });

  it("rejects a string with no slash", () => {
    expect(parseOwnerRepo("facebook")).toBeNull();
  });

  it("rejects a string with too many slashes", () => {
    expect(parseOwnerRepo("facebook/react/extra")).toBeNull();
  });

  it("rejects an empty owner", () => {
    expect(parseOwnerRepo("/react")).toBeNull();
  });

  it("rejects an empty repo", () => {
    expect(parseOwnerRepo("facebook/")).toBeNull();
  });

  it("rejects an empty string", () => {
    expect(parseOwnerRepo("")).toBeNull();
  });
});
