import { useEffect } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComparisonRow, DefenceMethod, ProtectResult } from "../../api/types";
import { ChartFigure, TableView, Tip, type SeriesDef } from "../charts";
import PrototypeNotice from "../PrototypeNotice";
import StageCard from "../StageCard";
import { useThemeColors, type ThemeColors } from "../useThemeColors";
import { fmtMs, VerdictBadge } from "./bits";
import type { BeforeResult } from "./ReattackStage";
import { ALL_METHODS, methodName, verdictMeta } from "./settings";
import type { DefenceState } from "./useDefence";

interface Props {
  d: DefenceState;
  id: string;
  n: number;
  locked: boolean;
  lockedHint?: string;
  original?: BeforeResult;
  /** Where the message came from, for the report header. */
  origin: string;
}

/** Prints the full loop: the Breach Report (when there is one) followed by the Defence Report. */
export function printDefenceReport() {
  const root = document.documentElement;
  root.classList.add("print-defence");
  const done = () => {
    root.classList.remove("print-defence");
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  window.print();
}

const VERDICT_WORDS = Object.keys({ infeasible: 1, not_applicable: 1, detected: 1, undetected_low_intercept: 1 });

/** A table cell with an icon for the common yes/no answers and verdict words. Text always stays. */
function Cell({ text }: { text: string }) {
  const verdictKey = VERDICT_WORDS.find((v) => verdictMeta(v).label.toLowerCase() === text.trim().toLowerCase());
  if (verdictKey) return <VerdictBadge verdict={verdictKey} />;
  const yes = /^yes\b/i.test(text);
  const no = /^no\b/i.test(text);
  return (
    <span className={yes ? "cell-yes" : no ? "cell-no" : undefined}>
      {yes && <span aria-hidden="true">✓ </span>}
      {no && <span aria-hidden="true">✗ </span>}
      {text}
    </span>
  );
}

function ComparisonTable({ rows, names }: { rows: ComparisonRow[]; names: Record<DefenceMethod, string> }) {
  return (
    <table className="data-table stack-table compare-table">
      <caption className="sr-only">Comparison of the three defences</caption>
      <thead>
        <tr>
          <th scope="col">Property</th>
          {ALL_METHODS.map((m) => (
            <th scope="col" key={m}>
              {names[m]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}>
            <th scope="row" data-label="">
              {r.label}
            </th>
            {ALL_METHODS.map((m) => (
              <td key={m} data-label={names[m]}>
                <Cell text={r[m] ?? "—"} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const BYTE_FIELDS: { field: string; key: string; label: string; color: string }[] = [
  { field: "ciphertext_b64", key: "ciphertext", label: "Message ciphertext", color: "--series-1" },
  { field: "nonce_b64", key: "nonce", label: "Nonce", color: "--series-3" },
  { field: "encapsulation_key_b64", key: "encapsulation_key", label: "Encapsulation (public) key", color: "--series-2" },
  { field: "kem_ciphertext_b64", key: "kem_ciphertext", label: "KEM ciphertext", color: "--series-4" },
];

function b64Len(v: unknown): number {
  if (typeof v !== "string") return 0;
  try {
    return atob(v).length;
  } catch {
    return 0;
  }
}

type TipProps = { active?: boolean; label?: string; payload?: { payload: Record<string, number | string> }[] };

function OverheadCharts({ results, names }: { results: ProtectResult[]; names: Record<DefenceMethod, string> }) {
  const c = useThemeColors();
  const axis = { tick: { fill: c["--text-muted"], fontSize: 12 }, stroke: c["--border"], tickLine: false } as const;

  // Bytes on the wire, measured from the public bundles of this run.
  const bytes = results.map((r) => {
    const row: Record<string, number | string> = { method: names[r.method] };
    for (const f of BYTE_FIELDS) row[f.key] = b64Len(r.bundle?.[f.field]);
    row.total = BYTE_FIELDS.reduce((s, f) => s + (row[f.key] as number), 0);
    return row;
  });
  const byteSeries: SeriesDef[] = BYTE_FIELDS.filter((f) => bytes.some((b) => (b[f.key] as number) > 0)).map((f) => ({
    key: f.key,
    label: f.label,
    color: f.color,
    mark: "bar",
  }));
  // Time per method, measured: the sum of the engine's timed phases.
  const times = results.map((r) => {
    const phases = Object.entries(r.timings_ms).filter((e): e is [string, number] => typeof e[1] === "number");
    return { method: names[r.method], total_ms: phases.reduce((s, [, v]) => s + v, 0), breakdown: phases.map(([k, v]) => `${k.replace(/_/g, " ")} ${fmtMs(v)}`).join(", ") };
  });
  const bb84 = results.find((r) => r.method === "bb84");

  const ByteTip = ({ active, label, payload }: TipProps) =>
    active && payload?.length ? (
      <Tip
        title={String(label)}
        rows={[
          ...byteSeries
            .filter((s) => (payload[0].payload[s.key] as number) > 0)
            .map((s) => ({ label: s.label, value: `${(payload[0].payload[s.key] as number).toLocaleString()} B`, color: c[s.color as keyof ThemeColors] })),
          { label: "total", value: `${(payload[0].payload.total as number).toLocaleString()} B` },
        ]}
      />
    ) : null;
  const TimeTip = ({ active, label, payload }: TipProps) =>
    active && payload?.length ? (
      <Tip title={String(label)} rows={[{ label: String(payload[0].payload.breakdown), value: fmtMs(payload[0].payload.total_ms as number), color: c["--series-1"] }]} />
    ) : null;

  return (
    <div className="chart-grid">
      <ChartFigure
        title="Bytes on the wire, per method"
        note={
          <>
            Measured from this run's public bundles.
            {bb84 && bb84.sizes.raw_qubits != null && <> BB84 also sent {String(bb84.sizes.raw_qubits)} qubits over the quantum channel.</>}
            {bb84 && !bb84.bundle && <> BB84 aborted, so it put no ciphertext on the wire.</>}
          </>
        }
        legend={byteSeries}
        ariaLabel={`Bytes on the wire: ${bytes.map((b) => `${b.method} ${b.total} bytes`).join("; ")}`}
        table={
          <TableView
            rows={bytes}
            caption="Bytes on the wire per method"
            columns={[{ key: "method", label: "method" }, ...byteSeries.map((s) => ({ key: s.key, label: s.label })), { key: "total", label: "total bytes" }]}
          />
        }
      >
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={bytes} margin={{ top: 12, right: 16, bottom: 8, left: 4 }}>
            <CartesianGrid vertical={false} stroke={c["--grid"]} />
            <XAxis dataKey="method" {...axis} />
            <YAxis {...axis} width={56} tickFormatter={(v: number) => `${v.toLocaleString()}`} />
            <Tooltip content={<ByteTip />} cursor={{ fill: c["--surface-2"] }} />
            {byteSeries.map((s) => (
              <Bar key={s.key} dataKey={s.key} stackId="b" fill={c[s.color as keyof ThemeColors]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartFigure>
      <ChartFigure
        title="Time per method (log scale)"
        note="Sum of the engine's timed phases in this run. BB84 time is classical simulation of the quantum exchange, not a hardware figure."
        ariaLabel={`Time per method: ${times.map((t) => `${t.method} ${fmtMs(t.total_ms)}`).join("; ")}`}
        table={
          <TableView
            rows={times}
            caption="Time per method"
            columns={[
              { key: "method", label: "method" },
              { key: "total_ms", label: "total", format: (v) => fmtMs(typeof v === "number" ? v : null) },
              { key: "breakdown", label: "phases", format: (v) => String(v) },
            ]}
          />
        }
      >
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={times} margin={{ top: 12, right: 16, bottom: 8, left: 4 }}>
            <CartesianGrid vertical={false} stroke={c["--grid"]} />
            <XAxis dataKey="method" {...axis} />
            <YAxis scale="log" domain={[0.01, "auto"]} allowDataOverflow {...axis} width={56} tickFormatter={(v: number) => fmtMs(v)} />
            <Tooltip content={<TimeTip />} cursor={{ fill: c["--surface-2"] }} />
            <Bar dataKey="total_ms" fill={c["--series-1"]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </ChartFigure>
    </div>
  );
}

export default function CompareStage({ d, id, n, locked, lockedHint, original, origin }: Props) {
  const names = Object.fromEntries(ALL_METHODS.map((m) => [m, methodName(d.info, m)])) as Record<DefenceMethod, string>;
  const results = d.protect ? ALL_METHODS.map((m) => d.protect!.results[m]).filter((r): r is ProtectResult => !!r) : [];
  const verdicts = d.reattack ? ALL_METHODS.map((m) => d.reattack!.verdicts[m]).filter((v) => !!v) : [];
  const bb84 = d.protect?.results.bb84;
  const now = new Date().toLocaleString();

  // Leave print mode if the page changes under it.
  useEffect(() => () => document.documentElement.classList.remove("print-defence"), []);

  return (
    <StageCard id={id} n={n} title="Compare and choose" side="def" sideLabel="Blue team · Defence Report" locked={locked} lockedHint={lockedHint} className="stage-compare">
      {d.reattack && (
        <article className="report defence-report" aria-labelledby={`${id}-report-title`}>
          <header className="report-head">
            <div>
              <div className="report-eyebrow">Q-Break · Blue-team Defence Report</div>
              <h2 id={`${id}-report-title`}>Protect, re-attack, compare</h2>
              <div className="small muted">Generated {now} · {origin}</div>
            </div>
            <div className="report-actions no-print">
              <button className="btn btn-defend" onClick={printDefenceReport}>
                ⎙ Download Defence Report
              </button>
            </div>
          </header>

          <dl className="engagement">
            <div>
              <dt>Message</dt>
              <dd>{d.protectedText.length} characters</dd>
            </div>
            <div>
              <dt>Defences</dt>
              <dd>{results.map((r) => names[r.method]).join(", ")}</dd>
            </div>
            {bb84?.qkd && (
              <div>
                <dt>BB84 exchange</dt>
                <dd>
                  {bb84.qkd.raw_bits.toLocaleString()} qubits, Eve {bb84.qkd.photon_preview.some((p) => p.eve_basis) ? "on" : "off"}, QBER{" "}
                  {(bb84.qkd.qber * 100).toFixed(1)}%
                </dd>
              </div>
            )}
          </dl>

          <section className="report-section">
            <h3>Before → after</h3>
            <div className="ba-compact">
              {original && (
                <span>
                  {original.label}: <VerdictBadge verdict={original.verdict} />
                </span>
              )}
              {original && <span aria-hidden="true">→</span>}
              {verdicts.map((v) => (
                <span key={v!.method}>
                  {names[v!.method]}: <VerdictBadge verdict={v!.verdict} />
                </span>
              ))}
            </div>
          </section>

          <section className="report-section">
            <h3>Protection</h3>
            <table className="data-table stack-table">
              <thead>
                <tr>
                  <th scope="col">Method</th>
                  <th scope="col">Status</th>
                  <th scope="col">Round trip</th>
                  <th scope="col">Ciphertext</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.method}>
                    <th scope="row" data-label="">
                      {names[r.method]} {r.parameter_set && r.parameter_set !== names[r.method] && <span className="mono small">({r.parameter_set})</span>}
                    </th>
                    <td data-label="Status">{r.status === "protected" ? "🛡 protected" : `✗ ${r.status}`}</td>
                    <td data-label="Round trip">{r.status !== "protected" ? "— nothing encrypted" : r.roundtrip_ok ? "✓ matches" : "✗ failed"}</td>
                    <td data-label="Ciphertext" className="mono">
                      {r.bundle ? `${b64Len(r.bundle.ciphertext_b64).toLocaleString()} B` : "none"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="report-section">
            <h3>Re-attack verdicts</h3>
            <ul className="verdict-list">
              {verdicts.map((v) => (
                <li key={v!.method}>
                  <strong>{names[v!.method]}</strong> <VerdictBadge verdict={v!.verdict} />{" "}
                  <span className="small muted">
                    {v!.attack} · {v!.executed ? "executed" : "not executed"}
                  </span>
                  <div className="small">{v!.explanation}</div>
                </li>
              ))}
            </ul>
          </section>

          <section className="report-section">
            <h3>Comparison</h3>
            <ComparisonTable rows={d.reattack.comparison.rows} names={names} />
          </section>

          {results.length > 0 && (
            <section className="report-section">
              <h3>Measured overhead</h3>
              <OverheadCharts results={results} names={names} />
            </section>
          )}

          <section className="report-section recommendation reco-def" aria-live="polite">
            <h3>Recommendation</h3>
            <p className="reco">{d.reattack.recommendation.text}</p>
            <p className="small">
              <span className="muted">Rule that fired:</span> <code className="rule">{d.reattack.recommendation.rule}</code>
            </p>
          </section>

          {d.info?.honesty_notes && d.info.honesty_notes.length > 0 && (
            <section className="report-section">
              <h3>Honesty notes</h3>
              <ul className="small">
                {d.info.honesty_notes.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </section>
          )}

          <div className="report-notice">
            <PrototypeNotice />
          </div>
        </article>
      )}
    </StageCard>
  );
}
