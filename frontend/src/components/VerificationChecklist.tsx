import type { VerificationStep } from "../api/types";

export default function VerificationChecklist({ steps }: { steps: VerificationStep[] }) {
  const allPassed = steps.length > 0 && steps.every((s) => s.passed);
  const failed = steps.filter((s) => !s.passed).length;
  return (
    <div className="verification">
      <div className={`verify-summary ${allPassed ? "verify-ok" : "verify-warn"}`}>
        {allPassed ? (
          <>
            <span aria-hidden="true">✓</span> Independently verified by classical checks ({steps.length}/{steps.length})
          </>
        ) : steps.length === 0 ? (
          <>No verification steps were returned.</>
        ) : (
          <>
            <span aria-hidden="true">✗</span> {failed} of {steps.length} checks failed
          </>
        )}
      </div>
      <ul className="checklist">
        {steps.map((s, i) => (
          <li key={i} className={s.passed ? "check-pass" : "check-fail"}>
            <span className="check-icon" aria-hidden="true">
              {s.passed ? "✓" : "✗"}
            </span>
            <span className="check-body">
              <span className="check-name">
                {s.name}
                <span className="sr-only">{s.passed ? " passed" : " failed"}</span>
              </span>
              <span className="mono check-detail">{s.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
