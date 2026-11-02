"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";

/**
 * Light / dark / follow-the-system.
 *
 * The choice lives in localStorage and the OS preference lives in
 * matchMedia — both are external stores, so this reads them with
 * `useSyncExternalStore` rather than copying them into state from an effect.
 * That keeps the server and client snapshots explicit and avoids a cascading
 * re-render on every mount.
 *
 * The resolved theme is written to `data-theme` on <html>, which is what
 * globals.css keys the light palette off. The same write happens in an inline
 * script in layout.tsx before first paint, so the page never flashes the
 * wrong theme.
 */
export type ThemeChoice = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "tj:theme";

type ThemeContextValue = {
  /** What the owner picked. */
  choice: ThemeChoice;
  /** What is actually on screen once "system" is resolved. */
  resolved: "light" | "dark";
  setChoice: (choice: ThemeChoice) => void;
};

const ThemeContext = createContext<ThemeContextValue>({
  choice: "dark",
  resolved: "dark",
  setChoice: () => {},
});

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

const LIGHT_QUERY = "(prefers-color-scheme: light)";

/** Listeners for changes this tab makes; `storage` only fires in other tabs. */
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  const media = window.matchMedia(LIGHT_QUERY);
  media.addEventListener("change", onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    media.removeEventListener("change", onChange);
    window.removeEventListener("storage", onChange);
  };
}

function readChoice(): ThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    // Private mode or blocked site data: fall back to the system preference.
  }
  return "system";
}

/**
 * The snapshot is a plain string so it compares by value — returning an object
 * here would allocate a new one per call and loop forever.
 */
function getSnapshot(): string {
  const choice = readChoice();
  const resolved =
    choice === "system" ? (window.matchMedia(LIGHT_QUERY).matches ? "light" : "dark") : choice;
  return `${choice}:${resolved}`;
}

function getServerSnapshot(): string {
  // Matches the `data-theme="dark"` the document ships with.
  return "system:dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const [choice, resolved] = snapshot.split(":") as [ThemeChoice, "light" | "dark"];

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolved;
    // Keeps form controls, scrollbars and the address bar in step.
    root.style.colorScheme = resolved;
  }, [resolved]);

  const setChoice = useCallback((next: ThemeChoice) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Not fatal, but without storage the choice cannot outlive the tab.
    }
    emit();
  }, []);

  return (
    <ThemeContext.Provider value={{ choice, resolved, setChoice }}>
      {children}
    </ThemeContext.Provider>
  );
}
