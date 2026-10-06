import type { ReactNode } from "react";

interface Props {
  id: string;
  n: number;
  title: string;
  side: "org" | "adv" | "wall" | "report";
  sideLabel: string;
  locked: boolean;
  lockedHint?: string;
  className?: string;
  children: ReactNode;
}

/** One numbered stage of a breach test. Locked stages are dimmed and inert. */
export default function StageCard({ id, n, title, side, sideLabel, locked, lockedHint, className, children }: Props) {
  return (
    <section
      id={id}
      className={`stage stage-${side} ${locked ? "stage-locked" : ""} ${className ?? ""}`}
      aria-labelledby={`${id}-title`}
      aria-disabled={locked || undefined}
    >
      <header className="stage-head">
        <span className="stage-n" aria-hidden="true">
          {n}
        </span>
        <div>
          <span className={`side-tag side-tag-${side}`}>{sideLabel}</span>
          <h2 id={`${id}-title`}>
            <span className="sr-only">Stage {n}: </span>
            {title}
          </h2>
        </div>
      </header>
      {locked ? (
        <p className="stage-locked-hint">🔒 {lockedHint ?? `Complete stage ${n - 1} first.`}</p>
      ) : (
        <div className="stage-body">{children}</div>
      )}
    </section>
  );
}
