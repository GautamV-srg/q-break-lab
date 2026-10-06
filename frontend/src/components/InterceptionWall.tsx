import type { ReactNode } from "react";

export interface WallItem {
  label: string;
  value: ReactNode;
}

interface Props {
  /** Things that cross the wall: what a real eavesdropper captures. In "defend", the attacks launched. */
  captured: WallItem[];
  /** Secrets that stay with the organization: shown as locked chips bouncing off the wall. In "defend", the protected targets. */
  secrets: string[];
  /**
   * "attack" (Act I): ciphertext crosses the wall to the adversary, secrets bounce off it.
   * "defend" (Act II): the animation reversed: the adversary's attacks fly at the wall and are repelled.
   */
  variant?: "attack" | "defend";
  children?: ReactNode;
}

/** The hand-off across the interception wall (stage 2), and its reversal in the re-attack (stage 6). */
export default function InterceptionWall({ captured, secrets, variant = "attack", children }: Props) {
  const defend = variant === "defend";
  return (
    <div className={`wall-scene ${defend ? "wall-scene-defend" : ""}`}>
      <div className="wall-side wall-org">
        <div className="wall-side-title">{defend ? "Your organization's protected messages" : "Your organization keeps"}</div>
        <ul className="secret-chips">
          {secrets.map((s, i) => (
            <li key={s} className={`chip ${defend ? "chip-shielded" : "chip-secret"}`} style={{ animationDelay: `${0.3 + i * 0.35}s` }}>
              <span aria-hidden="true">{defend ? "🛡" : "🔒"}</span> {s}
              <span className="sr-only">{defend ? " (protected)" : " (blocked by the wall; never sent to the adversary)"}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="wall" aria-hidden="true">
        <div className="wall-bricks" />
        <span className="wall-label">{defend ? "PROTECTED" : "INTERCEPTION WALL"}</span>
      </div>

      <div className="wall-side wall-adv">
        <div className="wall-side-title">{defend ? "Same quantum adversary attacks" : "Quantum adversary captures"}</div>
        <ul className="captured-list">
          {captured.map((c, i) => (
            <li
              key={c.label}
              className={`chip ${defend ? "chip-repelled" : "chip-captured"}`}
              style={{ animationDelay: `${0.2 + i * 0.3}s` }}
            >
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
