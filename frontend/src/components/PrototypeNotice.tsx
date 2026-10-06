import { Link } from "react-router-dom";

export const PROTOTYPE_CLAIM =
  "Q-Break is a prototype of a quantum red-team engine for breach testing encrypted communications. Today it runs genuine Grover and Shor circuits, on a classical simulator, against miniature versions of symmetric and RSA encryption. It does not break real AES or RSA: breaching real AES or production RSA keys requires large, fault-tolerant quantum hardware that does not exist yet. Q-Break demonstrates exactly how such a test would work, and does not claim a speed advantage today.";

/** Compact banner (test pages, reports) or the full claim box (Home, About). */
export default function PrototypeNotice({ variant = "compact" }: { variant?: "compact" | "full" }) {
  if (variant === "full") {
    return (
      <aside className="notice notice-full" aria-label="Prototype notice">
        <div className="notice-icon" aria-hidden="true">ⓘ</div>
        <div>
          <div className="notice-kicker">Rules of engagement</div>
          <h3>A working prototype, at miniature scale</h3>
          <p>{PROTOTYPE_CLAIM}</p>
          <Link to="/about" className="no-print">
            What this prototype does and doesn't prove →
          </Link>
        </div>
      </aside>
    );
  }
  return (
    <aside className="notice notice-compact" aria-label="Prototype notice">
      <span className="notice-icon" aria-hidden="true">ⓘ</span>
      <span>
        <strong>Rules of engagement: prototype at miniature scale.</strong> Genuine Grover and Shor circuits on a
        classical simulator, against miniature ciphers. This does not break real AES or RSA, and claims no speed
        advantage; real-size keys need future fault-tolerant hardware.{" "}
        <Link to="/about" className="no-print">
          Learn more
        </Link>
      </span>
    </aside>
  );
}
