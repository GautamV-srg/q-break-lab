import type { ReactNode } from "react";

export interface WallItem {
  label: string;
  value: ReactNode;
}

interface Props {
  /** Things that cross the wall: what a real eavesdropper captures. */
  captured: WallItem[];
  /** Secrets that stay with the organization: shown as locked chips bouncing off the wall. */
  secrets: string[];
  children?: ReactNode;
}

/** Stage 2 visual: the hand-off across the interception wall. */
export default function InterceptionWall({ captured, secrets, children }: Props) {
  return (
    <div className="wall-scene">
      <div className="wall-side wall-org">
        <div className="wall-side-title">Your organization keeps</div>
        <ul className="secret-chips">
          {secrets.map((s, i) => (
            <li key={s} className="chip chip-secret" style={{ animationDelay: `${0.3 + i * 0.35}s` }}>
              <span aria-hidden="true">🔒</span> {s}
              <span className="sr-only"> (blocked by the wall; never sent to the adversary)</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="wall" aria-hidden="true">
        <div className="wall-bricks" />
        <span className="wall-label">INTERCEPTION WALL</span>
      </div>

      <div className="wall-side wall-adv">
        <div className="wall-side-title">Quantum adversary captures</div>
        <ul className="captured-list">
          {captured.map((c, i) => (
            <li key={c.label} className="chip chip-captured" style={{ animationDelay: `${0.2 + i * 0.3}s` }}>
              <span className="chip-label">{c.label}</span>
              <span className="chip-value">{c.value}</span>
            </li>
          ))}
        </ul>
        {children}
      </div>
    </div>
  );
}
