export interface StepDef {
  label: string;
  side: string;
}

/** Four numbered stages that unlock in order. `active` is 1-based; stages < active are done. */
export default function Stepper({ steps, active, idPrefix }: { steps: StepDef[]; active: number; idPrefix: string }) {
  return (
    <ol className="stepper no-print" aria-label="Test progress">
      {steps.map((s, i) => {
        const n = i + 1;
        const state = n < active ? "done" : n === active ? "active" : "locked";
        const content = (
          <>
            <span className="step-num" aria-hidden="true">
              {state === "done" ? "✓" : n}
            </span>
            <span className="step-text">
              <span className="step-label">{s.label}</span>
              <span className="step-side">{s.side}</span>
            </span>
          </>
        );
        return (
          <li key={s.label} className={`step step-${state}`} aria-current={state === "active" ? "step" : undefined}>
            {state === "locked" ? (
              <span className="step-inner">
                {content}
                <span className="sr-only"> (locked)</span>
              </span>
            ) : (
              <a className="step-inner" href={`#${idPrefix}-stage-${n}`}>
                {content}
                {state === "done" && <span className="sr-only"> (complete)</span>}
              </a>
            )}
          </li>
        );
      })}
    </ol>
  );
}
