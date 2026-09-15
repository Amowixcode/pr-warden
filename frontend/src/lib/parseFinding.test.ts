import { describe, expect, it } from "vitest";
import { parseFinding } from "./parseFinding";

describe("parseFinding", () => {
  it("splits a plain-hyphen location", () => {
    expect(parseFinding("api/routes/health.py:6 - external calls in a polled endpoint")).toEqual(
      {
        location: "api/routes/health.py:6",
        body: "external calls in a polled endpoint",
      },
    );
  });

  it("splits an em-dash-separated location with a line range", () => {
    // Real pipeline output: the range hyphen ("245-314") has no surrounding spaces, the
    // separator dash does — that's what tells them apart.
    expect(
      parseFinding(
        "packages/react-devtools-shared/src/backend/views/canvas.js:245-314 — No explicit new or updated tests",
      ),
    ).toEqual({
      location: "packages/react-devtools-shared/src/backend/views/canvas.js:245-314",
      body: "No explicit new or updated tests",
    });
  });

  it("splits an en-dash-separated location", () => {
    expect(parseFinding("config/settings.py:37 – module-scope instantiation")).toEqual({
      location: "config/settings.py:37",
      body: "module-scope instantiation",
    });
  });

  it("falls back to the full text with no location when there's no file:line prefix", () => {
    const text = "Removal of Overlay.js (329 lines) — no regression tests added";
    expect(parseFinding(text)).toEqual({ location: null, body: text });
  });
});
