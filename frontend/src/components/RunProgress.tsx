import { useEffect, useState } from "react";

/**
 * Scanning-style progress panel while the breach test runs. The backend answers in one
 * request, so stages advance on a timer and the last one holds until the response lands.
 */
export default function RunProgress({ stages, stepMs = 900 }: { stages: string[]; stepMs?: number }) {
  const [i, setI] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t0 = performance.now();
    const step = setInterval(() => setI((x) => Math.min(x + 1, stages.length - 1)), stepMs);
    const clock = setInterval(() => setElapsed(performance.now() - t0), 100);
    return () => {
      clearInterval(step);
      clearInterval(clock);
    };
  }, [stages.length, stepMs]);

  return (
    <div className="run-progress" role="status" aria-live="polite">
      <div className="scanline" aria-hidden="true" />
      <ol className="run-stages">
        {stages.map((s, n) => (
          <li key={s} className={n < i ? "rs-done" : n === i ? "rs-active" : "rs-pending"}>
            <span className="rs-icon" aria-hidden="true">
              {n < i ? "✓" : n === i ? "◉" : "○"}
            </span>
            {s}
            {n === i && "…"}
          </li>
        ))}
      </ol>
      <div className="mono muted small">{(elapsed / 1000).toFixed(1)} s elapsed</div>
    </div>
  );
}
