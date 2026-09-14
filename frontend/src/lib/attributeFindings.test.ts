import { describe, expect, it } from "vitest";
import { attributeFindings } from "./attributeFindings";

function agent(issues: string[]) {
  return { summary: "", verdict: "APPROVE" as const, issues, suggestions: [] };
}

describe("attributeFindings", () => {
  it("attributes each merged issue to the agent whose list contains it verbatim", () => {
    const result = attributeFindings(["sec issue", "qua issue"], {
      security: agent(["sec issue"]),
      quality: agent(["qua issue"]),
      test: agent([]),
    });

    expect(result).toEqual([
      { text: "sec issue", agent: "security" },
      { text: "qua issue", agent: "quality" },
    ]);
  });

  it("gives a null agent (no fabricated colour) when a merged issue matches no per-agent list", () => {
    const result = attributeFindings(["mystery issue"], {
      security: agent([]),
      quality: agent([]),
      test: agent([]),
    });

    expect(result).toEqual([{ text: "mystery issue", agent: null }]);
  });

  it("handles a truncated merged list (fewer entries than the per-agent total)", () => {
    const result = attributeFindings(["a"], {
      security: agent([]),
      quality: agent(["a", "b"]),
      test: agent(["c"]),
    });

    expect(result).toEqual([{ text: "a", agent: "quality" }]);
  });
});
