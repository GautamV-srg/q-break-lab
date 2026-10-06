import { useId } from "react";
import { Link } from "react-router-dom";
import type { DefenceVerdict } from "../../api/types";
import ErrorBox from "../ErrorBox";
import InterceptionWall from "../InterceptionWall";
import RunProgress from "../RunProgress";
import StageCard from "../StageCard";
import { Citations, KeyNumbers, VerdictBadge } from "./bits";
import { ALL_METHODS, methodName } from "./settings";
import type { DefenceState, OriginalAttack } from "./useDefence";

export interface BeforeResult extends OriginalAttack {
  /** e.g. "MiniAES, 4-bit key · Grover". */
  label: string;
}

interface Props {
  d: DefenceState;
  id: string;
  n: number;
  locked: boolean;
  lockedHint?: string;
  original?: BeforeResult;
  demoRunning?: boolean;
}

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ReattackStage({ d, id, n, locked, lockedHint, original, demoRunning }: Props) {
  const fid = useId();
  const s = d.settings;
  const busy = d.busy || !!demoRunning;
  const targets = d.protect ? ALL_METHODS.filter((m) => d.protect!.results[m]) : [];
  const verdicts = d.reattack ? ALL_METHODS.map((m) => d.reattack!.verdicts[m]).filter((v): v is DefenceVerdict => !!v) : [];

  function run() {
    void d.runReattack(d.protect, { original });
  }

  const wallTargets = targets.map((m) => {
    const r = d.protect!.results[m]!;
    return `${methodName(d.info, m)}${r.status === "protected" ? "" : " (key discarded)"}`;
  });
  const wallAttacks = d.reattack
    ? verdicts.map((v) => ({ label: `${v.attack} → ${methodName(d.info, v.method)}`, value: <VerdictBadge verdict={v.verdict} /> }))
    : targets.map((m) => ({ label: `Attack on ${methodName(d.info, m)}`, value: d.reattacking ? "launching…" : "ready" }));

  return (
    <StageCard
      id={id}
      n={n}
      title="Same quantum adversary, protected targets."
      side="adv"
      sideLabel="Red team returns · quantum adversary (simulated)"
      locked={locked}
      lockedHint={lockedHint}
      className="stage-reattack"
    >
      <div className="duo duo-def">
        <div className="duo-col">
          <div className="org-hold">
            <span className="side-tag side-tag-org">Your organization</span>
            <p>
              <span aria-hidden="true">🔒</span> Keys, shared secrets, the BB84 key and the plaintext stay on this side. The
              re-attack request carries only the public bundles the adversary could capture on the wire.
            </p>
            {d.dropped.length > 0 && (
              <p className="small caution">
                The client guard stripped {d.dropped.length} secret-looking field{d.dropped.length === 1 ? "" : "s"} before sending:{" "}
                <span className="mono">{d.dropped.join(", ")}</span>.
              </p>
            )}
          </div>
        </div>
        <div className="duo-wall" aria-hidden="true" />
        <div className="duo-col">
          <span className="side-tag side-tag-adv">Quantum adversary</span>
          {d.attack && s && (
            <fieldset className="bb84-panel bb84-attack" disabled={busy}>
              <legend>Eavesdropping on the BB84 exchange</legend>
              <div className="field">
                <label htmlFor={`${fid}-f`} className="field-label">
                  Intercept fraction: <span className="mono">{pct(d.attack.eve_intercept_fraction)}</span>
                </label>
                <input
                  id={`${fid}-f`}
                  type="range"
                  className="range-adv"
                  min={s.limits.eve_intercept_fraction_min}
                  max={s.limits.eve_intercept_fraction_max}
                  step={0.05}
                  value={d.attack.eve_intercept_fraction}
                  onChange={(e) => d.setAttack({ ...d.attack!, eve_intercept_fraction: Number(e.target.value) })}
                  aria-valuetext={pct(d.attack.eve_intercept_fraction)}
                />
                <div className="field-hint">A fresh BB84 exchange runs with Eve on. Lower fractions may slip under the threshold, and the verdict says so.</div>
              </div>
              <div className="field">
                <label htmlFor={`${fid}-n`} className="field-label">
                  Channel noise: <span className="mono">{pct1(d.attack.channel_noise)}</span>
                </label>
                <input
                  id={`${fid}-n`}
                  type="range"
                  className="range-adv"
                  min={s.limits.channel_noise_min}
                  max={s.limits.channel_noise_max}
                  step={0.005}
                  value={d.attack.channel_noise}
                  onChange={(e) => d.setAttack({ ...d.attack!, channel_noise: Number(e.target.value) })}
                  aria-valuetext={pct1(d.attack.channel_noise)}
                />
              </div>
            </fieldset>
          )}
          <button className="btn btn-attack" onClick={run} disabled={busy || !d.protect || !d.attack}>
            {d.reattacking ? "Re-attack running…" : d.reattack ? "↻ Re-attack again" : "⚛ Re-attack the protected messages"}
          </button>
          {d.reattacking && (
            <RunProgress
              stages={[
                "Grover feasibility check against AES-256",
                "Handing the ML-KEM bundle to Shor's input stage",
                "Running a fresh BB84 exchange with Eve on the channel",
                "Comparing the three defences",
              ]}
            />
          )}
          <ErrorBox message={d.reattackError} onRetry={busy ? undefined : run} />
        </div>
      </div>

      {targets.length > 0 && (
        <InterceptionWall key={d.reattack ? JSON.stringify(verdicts.map((v) => v.verdict)) : "pending"} variant="defend" secrets={wallTargets} captured={wallAttacks} />
      )}

      <div className="verdict-region" aria-live="polite">
        {verdicts.length > 0 && (
          <>
            <h3 className="sr-only">Re-attack verdicts</h3>
            <div className="verdict-cards">
              {verdicts.map((v) => (
                <VerdictCard key={v.method} v={v} name={methodName(d.info, v.method)} />
              ))}
            </div>
            <BeforeAfter original={original} verdicts={verdicts} names={(m) => methodName(d.info, m)} />
          </>
        )}
      </div>
    </StageCard>
  );
}

function VerdictCard({ v, name }: { v: DefenceVerdict; name: string }) {
  return (
    <article className={`verdict-card vc-${v.verdict}`} aria-labelledby={`vc-${v.method}`}>
      <header className="vc-head">
        <h4 id={`vc-${v.method}`}>{name}</h4>
        <VerdictBadge verdict={v.verdict} big />
      </header>
      <p className="vc-attack small">
        <span className="muted">Attack:</span> <strong>{v.attack}</strong>{" "}
        {v.executed ? (
          <span className="exec-chip exec-yes">
            <span aria-hidden="true">⚛</span> executed
          </span>
        ) : (
          <span className="exec-chip exec-no">
            <span aria-hidden="true">∑</span> not executed: checked, not run
          </span>
        )}
      </p>
      <p className="vc-explain">{v.explanation}</p>
      <KeyNumbers evidence={v.evidence ?? {}} />
      {typeof v.evidence?.note === "string" && <p className="small muted">{v.evidence.note}</p>}
      <Citations citations={v.citations} />
    </article>
  );
}

function BeforeAfter({ original, verdicts, names }: { original?: BeforeResult; verdicts: DefenceVerdict[]; names: (m: DefenceVerdict["method"]) => string }) {
  return (
    <section className="before-after" aria-label="Before and after protection">
      <div className="ba-before">
        <div className="ba-k">Before</div>
        {original ? (
          <>
            <div className="ba-name">{original.label}</div>
            <VerdictBadge verdict={original.verdict} />
          </>
        ) : (
          <p className="small muted">
            Toy ciphers fall to the same adversary: see the <Link to="/test/symmetric">symmetric</Link> and{" "}
            <Link to="/test/public-key">public-key</Link> breach tests.
          </p>
        )}
      </div>
      <div className="ba-arrow" aria-hidden="true">
        →
      </div>
      <div className="ba-after">
        <div className="ba-k">After protection</div>
        <ul>
          {verdicts.map((v) => (
            <li key={v.method}>
              <span className="ba-name">{names(v.method)}</span> <VerdictBadge verdict={v.verdict} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
