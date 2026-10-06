export interface StepDef {
  label: string;
  side: string;
  /** Which act the stage belongs to; drives the group labels and the palette. */
  act?: "attack" | "defend";
}

const ACT_LABEL = { attack: "Attack", defend: "Defend" } as const;

/** Numbered stages that unlock in order. `active` is 1-based; stages < active are done. */
export default function Stepper({ steps, active, idPrefix }: { steps: StepDef[]; active: number; idPrefix: string }) {
  // Consecutive runs of the same act become labelled groups ("Attack" over 1–4, "Defend" over 5–7).
  const groups: { act: "attack" | "defend"; from: number; to: number }[] = [];
  steps.forEach((s, i) => {
    if (!s.act) return;
    const last = groups[groups.length - 1];
    if (last && last.act === s.act && last.to === i) last.to = i + 1;
    else groups.push({ act: s.act, from: i, to: i + 1 });
  });

  return (
    <nav className="stepper-wrap no-print" aria-label="Test progress" style={{ ["--steps" as string]: steps.length }}>
      {groups.length > 0 && (
        <div className="stepper-acts" aria-hidden="true">
          {groups.map((g) => (
            <span key={g.act + g.from} className={`stepper-act stepper-act-${g.act}`} style={{ gridColumn: `${g.from + 1} / ${g.to + 1}` }}>
              {ACT_LABEL[g.act]}
            </span>
          ))}
        </div>
      )}
      <ol className={`stepper ${groups.length > 0 ? "stepper-grouped" : ""}`}>
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
            <li
              key={s.label}
              className={`step step-${state} ${s.act ? `step-act-${s.act}` : ""}`}
              aria-current={state === "active" ? "step" : undefined}
            >
              {s.act && <span className="sr-only">{ACT_LABEL[s.act]}: </span>}
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
    </nav>
  );
}
