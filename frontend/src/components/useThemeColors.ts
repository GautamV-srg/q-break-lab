import { useEffect, useState } from "react";

const NAMES = ["--accent", "--breach", "--text", "--text-muted", "--border", "--surface-2", "--bar"] as const;
export type ThemeColors = Record<(typeof NAMES)[number], string>;

function read(): ThemeColors {
  const cs = getComputedStyle(document.documentElement);
  const out = {} as ThemeColors;
  for (const n of NAMES) out[n] = cs.getPropertyValue(n).trim() || "#888";
  return out;
}

/** Resolved design-token colours for SVG charts; follows light/dark changes. */
export function useThemeColors(): ThemeColors {
  const [c, setC] = useState<ThemeColors>(read);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const on = () => setC(read());
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return c;
}
