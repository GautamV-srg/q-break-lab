import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage, getMoscaInfo, postMosca } from "../api/client";
import type { MoscaInfo, MoscaResult } from "../api/types";
import PrototypeNotice from "../components/PrototypeNotice";

type Inputs = { x: number; y: number; z: number };

// Used only when the engine has no Mosca endpoint; the engine's own defaults win when it does.
const FALLBACK_DEFAULTS: Inputs = { x: 10, y: 6, z: 15 };
const FALLBACK_MAX_YEARS = 200;
const INEQUALITY = "X + Y > Z";
const SLIDER_MAX = 50;
const DEBOUNCE_MS = 250;

const FIELDS: { key: keyof Inputs; symbol: string; title: string; help: string }[] = [
  { key: "x", symbol: "X", title: "Shelf life of your data", help: "Years the data must stay confidential." },
  { key: "y", symbol: "Y", title: "Migration time", help: "Years to move your systems to post-quantum cryptography." },
  { key: "z", symbol: "Z", title: "Time to a capable quantum computer", help: "Years until a cryptographically relevant quantum computer exists. Your assumption, not a forecast." },
];

function years(n: number): string {
  return `${Number(n.toFixed(2))} year${n === 1 ? "" : "s"}`;
}

/** The same inequality the engine evaluates, for when its endpoint is not deployed. */
function localMosca({ x, y, z }: Inputs): MoscaResult {
  const total = x + y;
  const margin = z - total;
  const at_risk = total > z;
  const verdict_text = at_risk
    ? `At risk: X + Y = ${years(total)} > Z = ${years(z)}. Traffic harvested now could be decrypted up to ${years(-margin)} before it stops being sensitive.`
    : margin === 0
      ? `On the boundary: X + Y = Z = ${years(z)}, so there is no margin.`
      : `Not at risk under these assumptions: X + Y = ${years(total)} ≤ Z = ${years(z)}, a margin of ${years(margin)}.`;
  return { at_risk, margin, verdict_text, inequality: INEQUALITY, x, y, z, exposure: Math.max(0, -margin) };
}

export default function Mosca() {
  const id = useId();
  const [info, setInfo] = useState<MoscaInfo | null>(null);
  const [inputs, setInputs] = useState<Inputs>(FALLBACK_DEFAULTS);
  const [result, setResult] = useState<MoscaResult | null>(null);
  /** "engine" = verdict from the backend endpoint; "local" = endpoint absent, computed here. */
  const [source, setSource] = useState<"engine" | "local" | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const touched = useRef(false);
  const seq = useRef(0);

  const maxYears = info?.max_years ?? FALLBACK_MAX_YEARS;
  const defaults = info?.defaults ?? FALLBACK_DEFAULTS;

  // Defaults, explanation and citation come from the engine when it has the endpoint.
  useEffect(() => {
    let live = true;
    getMoscaInfo()
      .then((i) => {
        if (!live) return;
        setInfo(i);
        if (!touched.current) {
          setInputs(i.defaults);
          setResult(i.default_result);
          setSource("engine");
        }
      })
      .catch(() => {
        if (live && !touched.current) {
          setResult(localMosca(FALLBACK_DEFAULTS));
          setSource("local");
        }
      });
    return () => {
      live = false;
    };
  }, []);

  const valid = FIELDS.every(({ key }) => Number.isFinite(inputs[key]) && inputs[key] >= 0 && inputs[key] <= maxYears);

  // Ask the engine for the verdict (debounced); fall back to the same inequality if it has no endpoint.
  useEffect(() => {
    if (!touched.current || !valid) return;
    const mine = ++seq.current;
    setPending(true);
    const t = setTimeout(() => {
      postMosca(inputs)
        .then((r) => {
          if (mine !== seq.current) return;
          setResult(r);
          setSource("engine");
          setError(null);
        })
        .catch((e) => {
          if (mine !== seq.current) return;
          setResult(localMosca(inputs));
          setSource("local");
          // A missing endpoint is expected on older engines; anything else is worth showing.
          setError(e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === null) ? null : errorMessage(e));
        })
        .finally(() => {
          if (mine === seq.current) setPending(false);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [inputs, valid]);

  function set(key: keyof Inputs, raw: string) {
    touched.current = true;
    setInputs((prev) => ({ ...prev, [key]: raw === "" ? NaN : Number(raw) }));
  }

  function reset() {
    touched.current = true;
    setInputs(defaults);
  }

  // The picture always reflects the current inputs, even while the engine's verdict is on its way.
  const live = valid ? localMosca(inputs) : null;
  const shown = result && live && result.x === live.x && result.y === live.y && result.z === live.z ? result : live;
  const scale = live ? Math.max(live.x + live.y, live.z, 1) * 1.08 : 1;
  const pct = (v: number) => `${(v / scale) * 100}%`;

  return (
    <div className="page prose-page mosca">
      <div className="eyebrow">Risk framing · Mosca's inequality</div>
      <h1>Mosca risk calculator</h1>
      <p className="lede">
        The breach tests show <em>how</em> a quantum attack works. This calculator asks <em>when it matters to you</em>:
        if your data must stay secret for longer than you have left before a capable quantum computer arrives, traffic
        recorded today is already at risk.
      </p>

      <div className="mosca-inequality" aria-label={`Mosca's inequality: you are at risk when ${info?.inequality ?? INEQUALITY}`}>
        <span className="mosca-formula mono">{info?.inequality ?? INEQUALITY}</span>
        <span className="muted">means at risk</span>
      </div>

      <form className="mosca-form" onSubmit={(e) => e.preventDefault()}>
        {FIELDS.map(({ key, symbol, title, help }) => {
          const v = inputs[key];
          const bad = !Number.isFinite(v) || v < 0 || v > maxYears;
          return (
            <div className={`mosca-field mosca-field-${key}`} key={key}>
              <label htmlFor={`${id}-${key}`} className="field-label">
                <span className="mosca-symbol mono">{symbol}</span> {title}
              </label>
              <div className="mosca-input-row">
                <input
                  id={`${id}-${key}`}
                  className={`input mono input-short ${bad ? "input-invalid" : ""}`}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={maxYears}
                  step={0.5}
                  value={Number.isFinite(v) ? v : ""}
                  onChange={(e) => set(key, e.target.value)}
                  aria-invalid={bad}
                  aria-describedby={`${id}-${key}-help`}
                />
                <span className="muted">years</span>
              </div>
              <input
                type="range"
                min={0}
                max={Math.min(SLIDER_MAX, maxYears)}
                step={0.5}
                value={Number.isFinite(v) ? Math.min(v, SLIDER_MAX) : 0}
                onChange={(e) => set(key, e.target.value)}
                aria-label={`${symbol}: ${title}, in years`}
              />
              <div id={`${id}-${key}-help`} className={`field-hint ${bad ? "field-error" : ""}`}>
                {bad ? `Enter a number of years from 0 to ${maxYears}.` : help}
              </div>
            </div>
          );
        })}
        <button type="button" className="btn btn-ghost btn-small" onClick={reset}>
          Reset to defaults ({defaults.x}, {defaults.y}, {defaults.z})
        </button>
      </form>

      {live && shown ? (
        <section className="mosca-result" aria-live="polite" aria-busy={pending}>
          <div className={`verdict ${shown.at_risk ? "verdict-breached" : shown.margin === 0 ? "verdict-ambiguous" : "verdict-ok"}`} role="status">
            <span className="verdict-icon" aria-hidden="true">{shown.at_risk ? "⚠" : shown.margin === 0 ? "≈" : "✓"}</span>
            <div>
              <div className="verdict-title">{shown.at_risk ? "AT RISK" : shown.margin === 0 ? "ON THE BOUNDARY" : "NOT AT RISK"}</div>
              <div className="verdict-sub mono">
                {live.x} + {live.y} = {Number((live.x + live.y).toFixed(2))} {shown.at_risk ? ">" : shown.margin === 0 ? "=" : "≤"} {live.z}
                {" · "}
                {shown.at_risk
                  ? `exposed for ${years(shown.exposure)}`
                  : `margin ${years(Math.max(0, shown.margin))}`}
              </div>
            </div>
          </div>

          <figure className="mosca-timeline">
            <div
              className="timeline"
              role="img"
              aria-label={`Timeline in years from today. Data must stay secret for ${live.x}, migration takes ${live.y}, together ${live.x + live.y}. A capable quantum computer is assumed in ${live.z}.`}
            >
              <div className="timeline-row">
                <span className="timeline-seg timeline-x" style={{ width: pct(live.x) }}>
                  {live.x > 0 && <span>X</span>}
                </span>
                <span className="timeline-seg timeline-y" style={{ width: pct(live.y) }}>
                  {live.y > 0 && <span>Y</span>}
                </span>
              </div>
              <div className="timeline-row">
                <span className="timeline-seg timeline-z" style={{ width: pct(live.z) }}>
                  {live.z > 0 && <span>Z</span>}
                </span>
                {shown.at_risk && (
                  <span className="timeline-seg timeline-gap" style={{ width: pct(live.x + live.y - live.z) }} title="Exposed window">
                    {(live.x + live.y - live.z) / scale > 0.12 && <span>exposed</span>}
                  </span>
                )}
              </div>
            </div>
            <figcaption className="small muted">
              Years from today, on one scale. Top: how long your data needs protecting plus how long migration takes
              (X + Y). Bottom: how long until the quantum computer (Z). If the top bar is longer, the hatched difference
              is the window in which harvested traffic can be read while it is still sensitive.
            </figcaption>
          </figure>

          <p className="mosca-text">{shown.verdict_text}</p>
          <p className="small muted">
            {source === "engine" && shown === result
              ? "Verdict computed by the Q-Break engine."
              : "Verdict computed in your browser with the same inequality (the engine's risk endpoint is not available or has not answered yet)."}
          </p>
          {error && <p className="field-error small">{error}</p>}
        </section>
      ) : (
        <p className="field-error" role="alert">
          Enter all three values as years from 0 to {maxYears} to see the verdict.
        </p>
      )}

      <section>
        <h2>How to read it</h2>
        <p>
          {info?.explanation ??
            "Mosca's inequality: if X (how many years your data must stay confidential) plus Y (how many years it takes to migrate your systems to quantum-safe cryptography) is greater than Z (how many years until a cryptographically relevant quantum computer exists), you are at risk: traffic harvested and stored today could be decrypted while it still has to be secret. Z is uncertain, so the inputs are your assumptions; this calculator does not forecast them."}
        </p>
        {info?.citation && (
          <p className="small muted">
            Source: {String(info.citation.authors)}, “{String(info.citation.title)}”, {String(info.citation.venue)}.
          </p>
        )}
        <div className="caution">
          <strong>A framing tool, not a forecast.</strong> Q-Break does not predict when a cryptographically relevant
          quantum computer will exist, and the miniature breach tests are not evidence about Z. The three numbers are
          your own planning assumptions.
        </div>
        <p>
          <Link to="/readiness">Check which of your algorithms are exposed →</Link> ·{" "}
          <Link to="/test/public-key">See Shor's attack at miniature scale →</Link>
        </p>
      </section>

      <PrototypeNotice />
    </div>
  );
}
