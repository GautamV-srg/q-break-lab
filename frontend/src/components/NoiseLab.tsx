import { useEffect, useId, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { aesAttack, errorMessage, rsaAttack } from "../api/client";
import { buildAesAttackRequest, buildRsaAttackRequest, type InterceptedAes, type InterceptedRsa } from "../api/payloads";
import type { AesAttackResponse, Measurement, RsaAttackResponse } from "../api/types";
import { useConfig } from "../config";
import { verdictOf, type ReportInput, type Verdict } from "./BreachReport";
import Histogram from "./Histogram";
import { useThemeColors } from "./useThemeColors";

/** What the adversary re-runs under noise: only intercepted data and run settings. No secrets. */
export type NoiseTarget =
  | { kind: "symmetric"; intercepted: InterceptedAes; shots: number }
  | { kind: "public-key"; intercepted: InterceptedRsa; shots: number; construction?: string };

interface Point {
  p: number;
  /** Slider position in [0, 1]; the chart's x-axis, so the low-noise end has room. */
  s: number;
  verdict: Verdict;
  /** Share of shots that landed on the secret (symmetric) or on the ideal period peaks (public-key). */
  confidence: number | null;
  measurement: Measurement;
  highlight: string[];
  warnings: string[];
  simMs: number;
}

const DEBOUNCE_MS = 450;
const LAB_SEED = 7; // fixed, so the only thing that changes between runs is the noise level
const SWEEP_POINTS = 6;
const SLIDER_STEP = 0.025;
/** Per-shot noisy simulation is slow; a small sample keeps the slider responsive. */
const LAB_SHOTS = 128;

const DECADES = 4;

/**
 * Slider position → noise rate. Logarithmic over four decades below the engine's maximum,
 * because these deep circuits already fail at error rates far below it. Position 0 is ideal.
 */
export function noiseAt(s: number, maxP: number): number {
  return s <= 0 ? 0 : Number((maxP * 10 ** (-DECADES * (1 - s))).toPrecision(3));
}

type Signal = "holds" | "degrading" | "lost";

/** How much of the ideal run's signal is left above pure guessing. */
function signalOf(confidence: number | null, ideal: number | null, uniform: number | null): Signal | null {
  if (confidence === null || ideal === null || uniform === null || ideal <= uniform) return null;
  const left = (confidence - uniform) / (ideal - uniform);
  return left >= 0.5 ? "holds" : left >= 0.1 ? "degrading" : "lost";
}

const SIGNAL_TEXT: Record<Signal, string> = {
  holds: "BREACH HOLDS",
  degrading: "BREACH DEGRADING",
  lost: "SIGNAL LOST",
};
const SIGNAL_SUB: Record<Signal, string> = {
  holds: "The quantum signal still stands clear of guessing.",
  degrading: "The quantum signal is sinking toward guessing.",
  lost: "No better than guessing: the quantum attack has failed.",
};

const VERDICT_TEXT: Record<Verdict, string> = {
  breached: "BREACHED",
  ambiguous: "AMBIGUOUS",
  safe: "NOT BREACHED",
};

function massOn(m: Measurement, bitstrings: string[]): number {
  return bitstrings.reduce((sum, b) => sum + (m.counts[b] ?? 0), 0) / Math.max(1, m.shots);
}

/** Counting-register readings that sit on a multiple of 2^t / r: where an ideal Shor run lands. */
function idealPeaks(t: number, r: number): string[] {
  const size = 2 ** t;
  const out: string[] = [];
  for (let y = 0; y < size; y++) {
    const nearest = (Math.round((y * r) / size) * size) / r;
    if (Math.abs(y - nearest) <= 0.5) out.push(y.toString(2).padStart(t, "0"));
  }
  return out;
}

function pct(x: number | null): string {
  return x === null ? "—" : `${(x * 100).toFixed(1)}%`;
}

function NoiseTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="mono strong">{pct(pt.confidence)}</div>
      <div className="muted">noise p = {pt.p}</div>
      <div>engine verdict: {VERDICT_TEXT[pt.verdict]}</div>
    </div>
  );
}

/**
 * Pop the Hood noise lab: re-runs the same attack under a depolarising noise model and
 * shows the breach degrade. Limits (max noise, sizes, shots) come from /api/config.
 */
export default function NoiseLab({ target, baseline }: { target: NoiseTarget | undefined; baseline: ReportInput }) {
  const { config } = useConfig();
  const c = useThemeColors();
  const id = useId();

  // ---- What the engine allows, from /api/config ----
  let maxP = 0;
  let unavailable: string | null = null;
  let shots = target?.shots ?? 0;
  if (!target) {
    unavailable = "The intercepted data for this run is no longer available. Run the breach test again.";
  } else if (target.kind === "symmetric") {
    if (config.aes_max_noise_p === undefined || config.aes_noise_max_key_bits === undefined) {
      unavailable = "This engine build does not expose a noise model for the symmetric test.";
    } else if (target.intercepted.key_bits > config.aes_noise_max_key_bits) {
      unavailable = `Noisy runs simulate every shot separately, so this instance enables them for keys up to ${config.aes_noise_max_key_bits} bits. This run used a ${target.intercepted.key_bits}-bit key.`;
    } else {
      maxP = config.aes_max_noise_p;
      shots = Math.min(shots, config.aes_max_noisy_shots ?? shots, LAB_SHOTS);
    }
  } else if (!config.rsa_noise_moduli || config.rsa_max_noise_p === undefined) {
    unavailable = "This engine build does not expose a noise model for the public-key test.";
  } else if (!config.rsa_noise_moduli.includes(target.intercepted.n)) {
    unavailable = `Noisy runs need gate-level circuits, so this instance enables them only for N = ${config.rsa_noise_moduli.join(", ") || "(none)"}. This run used N = ${target.intercepted.n}.`;
  } else {
    maxP = config.rsa_max_noise_p;
  }

  // ---- What "the breach" means for this run, taken from the ideal result ----
  const r = baseline.resp;
  let secretBits: string[] = [];
  let uniform: number | null = null;
  let metricName = "";
  if (baseline.kind === "symmetric") {
    secretBits = baseline.resp.key !== null ? [baseline.resp.key] : baseline.resp.recovered_keys;
    uniform = secretBits.length / baseline.resp.search_space;
    metricName = secretBits.length === 1 ? "Shots on the recovered key" : "Shots on the candidate keys";
  } else if (baseline.resp.period) {
    const t = Object.keys(baseline.resp.measurement.counts)[0]?.length ?? baseline.resp.n_count;
    secretBits = idealPeaks(t, baseline.resp.period);
    uniform = secretBits.length / 2 ** t;
    metricName = "Shots on the ideal period peaks";
  }
  const hasMetric = secretBits.length > 0;
  const idealConfidence = hasMetric ? massOn(r.measurement, secretBits) : null;

  const [pos, setPos] = useState(0);
  const p = noiseAt(pos, maxP);
  const [points, setPoints] = useState<Record<string, Point>>({});
  const [current, setCurrent] = useState<Point | null>(null);
  const [running, setRunning] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queue = useRef<{ s: number; p: number }[]>([]);
  const inFlight = useRef(false);
  const alive = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      queue.current = [];
      clearTimeout(timer.current);
    };
  }, []);

  async function runOne(s: number, noise: number): Promise<Point> {
    if (!target) throw new Error("No intercepted data.");
    let resp: AesAttackResponse | RsaAttackResponse;
    let verdict: Verdict;
    if (target.kind === "symmetric") {
      // Built ONLY from the adversary's intercepted data (see api/payloads.ts).
      const a = await aesAttack(buildAesAttackRequest(target.intercepted, { shots, seed: LAB_SEED, noise_p: noise }));
      verdict = verdictOf({ kind: "symmetric", resp: a });
      resp = a;
    } else {
      const base = baseline.kind === "public-key" ? baseline.resp.a : null; // same base as the ideal run
      const b = await rsaAttack(
        buildRsaAttackRequest(target.intercepted, {
          a: base,
          shots,
          seed: LAB_SEED,
          noise_p: noise,
          ...(target.construction ? { construction: target.construction } : {}),
        }),
      );
      verdict = verdictOf({ kind: "public-key", resp: b });
      resp = b;
    }
    return {
      p: noise,
      s,
      verdict,
      confidence: hasMetric ? massOn(resp.measurement, secretBits) : null,
      measurement: resp.measurement,
      highlight: secretBits,
      warnings: resp.warnings,
      simMs: resp.sim_time_ms,
    };
  }

  /** One request at a time: the simulator is single-file, and stale levels are dropped. */
  async function pump() {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      while (queue.current.length > 0 && alive.current) {
        const { s, p: noise } = queue.current.shift()!;
        setRunning(noise);
        setError(null);
        try {
          const pt = await runOne(s, noise);
          if (!alive.current) return;
          setPoints((prev) => ({ ...prev, [String(noise)]: pt }));
          setCurrent(pt);
        } catch (e) {
          if (!alive.current) return;
          setError(errorMessage(e));
          queue.current = [];
        }
      }
    } finally {
      inFlight.current = false;
      if (alive.current) setRunning(null);
    }
  }

  function onSlide(s: number) {
    setPos(s);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      queue.current = [{ s, p: noiseAt(s, maxP) }]; // a newer level replaces anything still waiting
      void pump();
    }, DEBOUNCE_MS);
  }

  function sweep() {
    clearTimeout(timer.current);
    queue.current = Array.from({ length: SWEEP_POINTS }, (_, i) => {
      const s = i / (SWEEP_POINTS - 1);
      return { s, p: noiseAt(s, maxP) };
    });
    setPos(1);
    void pump();
  }

  const series = Object.values(points).sort((a, b) => a.p - b.p);
  const signal = current ? signalOf(current.confidence, idealConfidence, uniform) : null;
  const rescued = signal === "lost" && current?.verdict === "breached";
  const busy = running !== null;
  const waiting = current !== null && current.p !== p && !busy;

  return (
    <div className="noise-lab">
      <div className="field">
        <label htmlFor={`${id}-p`} className="field-label">
          Depolarising noise per two-qubit gate: <span className="mono">p = {p}</span>
        </label>
        <input
          id={`${id}-p`}
          type="range"
          min={0}
          max={1}
          step={SLIDER_STEP}
          value={pos}
          onChange={(e) => onSlide(Number(e.target.value))}
          disabled={!!unavailable}
          aria-valuetext={`noise p = ${p}`}
          aria-describedby={`${id}-help`}
        />
        <div className="range-ends mono muted small">
          <span>0 (ideal)</span>
          <span>{maxP ? `${maxP} (log scale)` : "—"}</span>
        </div>
        <div id={`${id}-help`} className={`field-hint ${unavailable ? "option-reasons" : ""}`}>
          {unavailable ? (
            <>
              <strong>Noise slider unavailable.</strong> {unavailable}
            </>
          ) : (
            <>
              Each change re-runs the same attack on the engine under that noise level ({shots} shots, fixed seed), using
              only the intercepted data. The slider is logarithmic: each quarter of its travel is ten times more noise.
              A noisy run is simulated shot by shot, so it can take the engine up to a minute.
            </>
          )}
        </div>
      </div>

      {!unavailable && (
        <div className="noise-actions">
          <button type="button" className="btn btn-small" onClick={sweep} disabled={busy}>
            ▶ Sweep {SWEEP_POINTS} noise levels
          </button>
          <span className="noise-status" role="status" aria-live="polite">
            {busy ? (
              <span className="noise-running">
                <span className="rs-icon" aria-hidden="true">◉</span> Running under noise p = {running}…
              </span>
            ) : waiting ? (
              "Waiting for the slider to settle…"
            ) : current ? (
              `Showing the run at p = ${current.p} (${(current.simMs / 1000).toFixed(2)} s simulated).`
            ) : (
              "Move the slider to re-run the breach under noise."
            )}
          </span>
        </div>
      )}

      {error && (
        <div className="error-box" role="alert">
          <span aria-hidden="true">⚠</span>
          <span className="error-text">{error}</span>
        </div>
      )}

      <div className={`noise-result ${busy ? "is-stale" : ""}`}>
        <div className="noise-tiles">
          <div className="noise-tile">
            <div className="stat-k">Verdict without noise</div>
            <div className={`noise-verdict noise-verdict-${verdictOf(baseline)}`}>{VERDICT_TEXT[verdictOf(baseline)]}</div>
            {hasMetric && (
              <div className="small muted">
                {metricName.toLowerCase()}: {pct(idealConfidence)}
              </div>
            )}
          </div>
          <div className="noise-tile">
            <div className="stat-k">Under noise{current ? ` p = ${current.p}` : ""}</div>
            {current ? (
              <>
                <div className={`noise-verdict noise-signal-${signal ?? (current.verdict === "safe" ? "lost" : "holds")}`}>
                  {current.verdict === "safe" ? "NOT BREACHED" : signal ? SIGNAL_TEXT[signal] : VERDICT_TEXT[current.verdict]}
                </div>
                <div className="small muted">
                  {signal && `${SIGNAL_SUB[signal]} `}Engine verdict: {VERDICT_TEXT[current.verdict].toLowerCase()}.
                </div>
              </>
            ) : (
              <div className="noise-verdict noise-verdict-none">not run yet</div>
            )}
          </div>
          {hasMetric && (
            <div className="noise-tile noise-tile-wide">
              <div className="stat-k">Confidence in the recovered secret</div>
              <div
                className="meter"
                role="meter"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round((current?.confidence ?? idealConfidence ?? 0) * 100)}
                aria-label={metricName}
              >
                <span className="meter-fill" style={{ width: `${(current?.confidence ?? idealConfidence ?? 0) * 100}%` }} />
                {uniform !== null && <span className="meter-mark" style={{ left: `${uniform * 100}%` }} title="pure guessing" />}
              </div>
              <div className="small muted">
                {metricName}: <span className="mono">{pct(current?.confidence ?? idealConfidence)}</span>
                {uniform !== null && (
                  <>
                    {" "}
                    · pure guessing would give <span className="mono">{pct(uniform)}</span> (tick)
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {hasMetric && series.length > 0 && (
          <figure className="chart-figure">
            <figcaption className="chart-title">{metricName} as noise rises</figcaption>
            <div
              className="chart-box"
              role="img"
              aria-label={`${metricName} by noise level: ${series.map((s) => `p ${s.p}: ${pct(s.confidence)}, ${VERDICT_TEXT[s.verdict]}`).join("; ")}`}
            >
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={series} margin={{ top: 12, right: 24, bottom: 18, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis
                    dataKey="s"
                    type="number"
                    domain={[0, 1]}
                    ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                    tickFormatter={(s: number) => String(noiseAt(s, maxP))}
                    tick={{ fill: c["--text-muted"], fontSize: 12 }}
                    stroke={c["--border"]}
                    label={{ value: "noise p (log scale)", position: "insideBottom", offset: -10, fill: c["--text-muted"], fontSize: 12 }}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    tick={{ fill: c["--text-muted"], fontSize: 12 }}
                    stroke={c["--border"]}
                    width={48}
                  />
                  <Tooltip content={<NoiseTooltip />} cursor={{ stroke: c["--border"] }} />
                  {uniform !== null && (
                    <ReferenceLine
                      y={uniform}
                      stroke={c["--text-muted"]}
                      strokeDasharray="6 4"
                      label={{ value: "pure guessing", position: "insideBottomRight", fill: c["--text-muted"], fontSize: 12 }}
                    />
                  )}
                  <Line
                    type="linear"
                    dataKey="confidence"
                    stroke={c["--series-1"]}
                    strokeWidth={2}
                    dot={{ r: 4, fill: c["--series-1"], stroke: c["--surface"], strokeWidth: 2 }}
                    activeDot={{ r: 6 }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <details className="disclosure chart-table">
              <summary>Table view</summary>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Noise p</th>
                      <th scope="col">{metricName}</th>
                      <th scope="col">Engine verdict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.map((s) => (
                      <tr key={s.p}>
                        <td className="mono">{s.p}</td>
                        <td className="mono">{pct(s.confidence)}</td>
                        <td>{VERDICT_TEXT[s.verdict]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </figure>
        )}

        {rescued && (
          <div className="caution">
            <strong>Why the engine still says “breached”.</strong> The quantum signal is gone, but the engine re-checks
            every measured key classically, and with a keyspace this small random readings stumble on the right key.
            That is brute force by luck, not a quantum attack: it stops working as soon as the keyspace outgrows the
            number of shots.
          </div>
        )}

        {current && (
          <>
            <h4>Measurements under noise p = {current.p}</h4>
            <Histogram
              measurement={current.measurement}
              highlight={current.highlight}
              uniform={baseline.kind === "symmetric" ? 1 / baseline.resp.search_space : undefined}
              highlightLabel={baseline.kind === "symmetric" ? "the key the ideal run recovered" : "ideal period peaks"}
            />
            {current.warnings.length > 0 && (
              <ul className="small muted noise-warnings">
                {current.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <p className="takeaway">
        <strong>The takeaway.</strong> On noisy hardware even this miniature breach fails: as the error rate rises the
        quantum signal sinks into random guessing, long before the error rates of today's devices. Real breach testing
        needs fault-tolerant, error-corrected quantum hardware, which does not exist yet.
      </p>
    </div>
  );
}
