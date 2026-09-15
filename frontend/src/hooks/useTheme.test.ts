import { describe, expect, it } from "vitest";
import { nextTheme } from "./useTheme";

describe("nextTheme", () => {
  it("flips an explicit light choice to dark", () => {
    expect(nextTheme("light", false)).toBe("dark");
    expect(nextTheme("light", true)).toBe("dark");
  });

  it("flips an explicit dark choice to light", () => {
    expect(nextTheme("dark", false)).toBe("light");
    expect(nextTheme("dark", true)).toBe("light");
  });

  it("with no explicit choice, flips away from the system preference", () => {
    expect(nextTheme(null, true)).toBe("light");
    expect(nextTheme(null, false)).toBe("dark");
  });
});
