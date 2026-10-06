import type { ReactNode } from "react";

/** "Your organization | Quantum adversary" columns with the wall between them. Stacks under 900px. */
export default function Duo({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="duo">
      <div className="duo-col duo-org">{left}</div>
      <div className="duo-wall" aria-hidden="true" />
      <div className="duo-col duo-adv">{right}</div>
    </div>
  );
}
