import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "pr-warden-theme";

function readStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  } catch {
    return null;
  }
}

function writeStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private browsing / storage disabled — the toggle still works for this session.
  }
}

/**
 * The next theme after a toggle. Pure so it's unit-testable without a DOM: an explicit
 * `current` choice flips; with no explicit choice yet, the toggle flips away from whatever
 * the system preference currently resolves to.
 */
export function nextTheme(current: Theme | null, systemPrefersDark: boolean): Theme {
  const currentlyDark = current ? current === "dark" : systemPrefersDark;
  return currentlyDark ? "light" : "dark";
}

export function useTheme(): { theme: Theme | null; toggle: () => void } {
  const [theme, setTheme] = useState<Theme | null>(() => readStoredTheme());

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    if (theme) {
      root.classList.add(theme);
    }
  }, [theme]);

  const toggle = useCallback(() => {
    const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme((current) => {
      const next = nextTheme(current, systemPrefersDark);
      writeStoredTheme(next);
      return next;
    });
  }, []);

  return { theme, toggle };
}
