import { useEffect, useRef } from "react";

export const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export function randomSeed(): number {
  return Math.floor(Math.random() * 2 ** 31);
}

/**
 * Scrolls the active stage into view whenever it advances (not on first render).
 * Stages in `noAutoScroll` are not jumped to: e.g. after Protect the user stays on the
 * protection results (round trips, sizes, BB84 visuals) and scrolls on when ready.
 */
export function useScrollToStage(idPrefix: string, stage: number, noAutoScroll: number[] = []) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (noAutoScroll.includes(stage)) return;
    const el = document.getElementById(`${idPrefix}-stage-${stage}`);
    if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idPrefix, stage]);
}

/** A token that flips on unmount so long async flows (demo mode) can stop early. */
export function useAliveRef() {
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  return alive;
}

/** Scrolls to a stage and moves keyboard focus to its heading (for CTAs that jump ahead). */
export function focusStage(idPrefix: string, n: number) {
  setTimeout(() => {
    const el = document.getElementById(`${idPrefix}-stage-${n}`);
    if (!el) return;
    el.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    const h = document.getElementById(`${idPrefix}-stage-${n}-title`);
    if (h) {
      h.setAttribute("tabindex", "-1");
      h.focus({ preventScroll: true });
    }
  }, 80);
}
