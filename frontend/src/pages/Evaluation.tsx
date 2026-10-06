import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, errorMessage, getEvaluation } from "../api/client";
import type { EvaluationResponse, EvaluationSeries, SeriesRow } from "../api/types";
import { ChartFigure, EmptyState, fmtNum, fmtPct, num, TableView, Tip, type SeriesDef } from "../components/charts";
import DefenceEvaluation, { DEFENCE_SERIES } from "../components/defence/DefenceEvaluation";
import ErrorBox from "../components/ErrorBox";
import PrototypeNotice from "../components/PrototypeNotice";
import { useThemeColors, type ThemeColors } from "../components/useThemeColors";
import { useConfig } from "../config";

// Fixed colour slots: quantum is always slot 1 and classical slot 2, everywhere in the app.
const QUANTUM = "--series-1";
const CLASSICAL = "--series-2";
const SLOTS = ["--series-1", "--series-2", "--series-3", "--series-4"] as const;

const CIPHER_NAME: Record<string, string> = { miniaes: "MiniAES · Grover", minirsa: "MiniRSA · Shor" };
const SIZE_NAME: Record<string, string> = { miniaes: "key bits", minirsa: "modulus N" };

const SECTIONS = [
  { id: "comparison", title: "Quantum vs classical" },
  { id: "scaling", title: "Scaling" },
  { id: "noise", title: "Noise" },
  { id: "iteration_curve", title: "Grover iteration curve" },
  { id: "success_rate", title: "Success rates" },
  { id: "counting", title: "Quantum counting" },
  { id: "defence", title: "Defence" },
] as const;

function groupBy<T>(rows: T[], key: (r: T) => string): [string, T[]][] {
  const m = new Map<string, T[]>();
  for (const r of rows) {
    const k = key(r);
    m.set(k, [...(m.get(k) ?? []), r]);
  }
  return [...m.entries()];
}

function sizeLabel(cipher: unknown, size: unknown): string {
  return cipher === "minirsa" ? `N = ${size}` : `${size}-bit key`;
}

function axis(c: ThemeColors) {
  return { tick: { fill: c["--text-muted"], fontSize: 12 }, stroke: c["--border"], tickLine: false } as const;
}

type TipProps = { active?: boolean; label?: string | number; payload?: { dataKey?: string | number; value?: number; payload: SeriesRow }[] };

/** Tooltip listing every series at the hovered x. */
function seriesTip(series: SeriesDef[], c: ThemeColors, title: (x: string | number | undefined) => string, fmt: (v: unknown) => string) {
  return function SeriesTip({ active, label, payload }: TipProps) {
    if (!active || !payload?.length) return null;
    return (
      <Tip
        title={title(label)}
        rows={series
          .filter((s) => payload[0].payload[s.key] != null)
          .map((s) => ({
            label: s.label,
            value: fmt(payload[0].payload[s.key]),
            color: c[s.color as keyof ThemeColors],
            dash: s.mark === "dash",
          }))}
      />
    );
  };
}

export default function Evaluation() {
  const { config } = useConfig();
  const [data, setData] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    setMissing(false);
    getEvaluation()
      .then(setData)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setMissing(true);
        else setError(errorMessage(e));
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const series = (name: string): EvaluationSeries | undefined => data?.data?.[name];

  return (
    <div className="page evaluation">
      <div className="page-head">
        <div>
          <div className="eyebrow">Evidence locker · stored experiment runs</div>
          <h1>Evaluation</h1>
          <p className="lede">
            How the two attacks behave across problem sizes, noise levels and random seeds, measured on the classical
            simulator. This page only reads results the experiments runner has already stored; nothing quantum runs
            when you open it.
          </p>
        </div>
        <button className="btn no-print" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "↻ Reload results"}
        </button>
      </div>

      <PrototypeNotice />

      <nav className="eval-nav no-print" aria-label="Evaluation sections">
        {SECTIONS.map((s) => {
          const has =
            s.id === "defence"
              ? DEFENCE_SERIES.some((d) => !!series(d) && !series(d)!.empty)
              : !!series(s.id) && !series(s.id)!.empty;
          return (
            <a key={s.id} href={`#eval-${s.id}`} className={has ? "eval-chip" : "eval-chip eval-chip-empty"}>
              <span aria-hidden="true">{loading ? "…" : has ? "●" : "∅"}</span> {s.title}
              <span className="sr-only">{loading ? " (loading)" : has ? " (has results)" : " (no results yet)"}</span>
            </a>
          );
        })}
      </nav>

      <ErrorBox message={error} onRetry={load} />
      {missing && (
        <div className="caution" role="status">
          <strong>This engine build does not serve evaluation data.</strong> The read-only evaluation endpoints ship
          with the Track 5 experiments runner. The sections below fill in once that build is deployed and experiments
          have been run.
        </div>
      )}

      <div className={loading && data ? "is-stale" : ""} aria-busy={loading}>
        <Section id="comparison" title="Quantum vs classical: queries, not time" series={series("comparison")} loading={loading}>
          {(rows) => <ComparisonCharts rows={rows} />}
        </Section>
        <Section id="scaling" title="Scaling: qubits and depth vs problem size" series={series("scaling")} loading={loading}>
          {(rows) => <ScalingCharts rows={rows} />}
        </Section>
        <Section id="noise" title="Noise: attack success vs error rate" series={series("noise")} loading={loading}>
          {(rows) => <NoiseCharts rows={rows} />}
        </Section>
        <Section id="iteration_curve" title="Grover iteration curve" series={series("iteration_curve")} loading={loading}>
          {(rows) => <IterationCharts rows={rows} />}
        </Section>
        <Section id="success_rate" title="Success rates across keys, seeds and bases" series={series("success_rate")} loading={loading}>
          {(rows) => <SuccessCharts rows={rows} conditionLabels={Object.fromEntries((config.aes_conditions ?? []).map((c) => [c.id, c.label]))} />}
        </Section>
        <Section id="counting" title="Quantum counting accuracy" series={series("counting")} loading={loading}>
          {(rows) => <CountingTable rows={rows} />}
        </Section>
        <section className="eval-section eval-section-def" id="eval-defence" aria-labelledby="eval-defence-title">
          <h2 id="eval-defence-title">Defence: BB84 under attack, and what protection costs</h2>
          <p className="muted">
            Stored runs of the defence experiments: the BB84 error rate as an eavesdropper intercepts more photons and as
            channel noise rises, the final key rate, and the measured overhead of the three defences.
          </p>
          {loading && !data ? (
            <div className="empty-state" role="status">
              <span className="empty-icon" aria-hidden="true">…</span> Loading stored results…
            </div>
          ) : (
            <DefenceEvaluation series={series} />
          )}
        </section>
      </div>

      <p className="small muted">
        Charts follow the same honesty rules as the tests: miniature ciphers, a classical simulator, and no
        speed-advantage claim. <Link to="/about">What this does and doesn't prove →</Link>
      </p>
    </div>
  );
}

function Section({
  id,
  title,
  series,
  loading,
  children,
}: {
  id: string;
  title: string;
  series: EvaluationSeries | undefined;
  loading: boolean;
  children: (rows: SeriesRow[]) => ReactNode;
}) {
  const rows = series?.rows ?? [];
  return (
    <section className="eval-section" id={`eval-${id}`} aria-labelledby={`eval-${id}-title`}>
      <h2 id={`eval-${id}-title`}>{title}</h2>
      {series?.description && <p className="muted">{series.description}</p>}
      {loading && !series ? (
        <div className="empty-state" role="status">
          <span className="empty-icon" aria-hidden="true">…</span> Loading stored results…
        </div>
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        children(rows)
      )}
    </section>
  );
}

// ---------- Quantum vs classical ----------

function ComparisonCharts({ rows }: { rows: SeriesRow[] }) {
  const c = useThemeColors();
  // Attack modes apply to the symmetric test only; rows without one (Shor) are always shown.
  const conditions = [...new Set(rows.filter((r) => r.condition).map((r) => String(r.condition)))];
  const [condition, setCondition] = useState(conditions.includes("known_beginning") ? "known_beginning" : conditions[0]);
  const shown = rows.filter((r) => !r.condition || String(r.condition) === condition);
  // The engine's record uses the same two fields for both attacks; what they count differs.
  const seriesFor = (cipher: string): SeriesDef[] =>
    cipher === "minirsa"
      ? [
          { key: "quantum_oracle_calls", label: "Shor circuit runs to factor (measured)", color: QUANTUM },
          { key: "classical_evaluations", label: "Classical trial divisions (measured)", color: CLASSICAL },
        ]
      : [
          { key: "quantum_oracle_calls", label: "Grover oracle calls (measured)", color: QUANTUM },
          { key: "classical_evaluations", label: "Classical tries (measured)", color: CLASSICAL },
          { key: "theory_grover", label: "Grover theory, π/4·√N", color: QUANTUM, mark: "dash" },
          { key: "theory_classical", label: "Classical theory, (N+1)/2", color: CLASSICAL, mark: "dash" },
        ];

  return (
    <>
      {conditions.length > 1 && (
        <div className="segmented eval-filter" role="radiogroup" aria-label="Symmetric attack mode">
          {conditions.map((k) => (
            <button
              type="button"
              role="radio"
              aria-checked={k === condition}
              key={k}
              className={k === condition ? "seg seg-on" : "seg"}
              onClick={() => setCondition(k)}
            >
              {k.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      )}
      <div className="chart-grid">
        {groupBy(shown, (r) => String(r.cipher)).map(([cipher, rs]) => {
          const data = [...rs].sort((a, b) => (num(a, "size") ?? 0) - (num(b, "size") ?? 0));
          const present = seriesFor(cipher).filter((s) => data.some((r) => (num(r, s.key) ?? 0) > 0));
          const hasTheory = present.some((s) => s.mark === "dash");
          const SeriesTip = seriesTip(present, c, (x) => sizeLabel(cipher, x), (v) => fmtNum(v, 1));
          return (
            <ChartFigure
              key={cipher}
              title={`${CIPHER_NAME[cipher] ?? cipher}: ${cipher === "minirsa" ? "runs and divisions" : "queries"} needed, by ${SIZE_NAME[cipher] ?? "size"}`}
              note={
                hasTheory
                  ? "Log scale. Solid lines are measured; dashed lines are the textbook predictions. Measured oracle calls include the extra controlled calls spent on quantum counting where it ran (small keys), which is why a measured point can sit above the Grover line."
                  : "Log scale. Averages over stored runs. At these toy moduli both counts are tiny; neither side is strained."
              }
              legend={present}
              ariaLabel={`Queries by size. ${data
                .map((r) => `${sizeLabel(cipher, r.size)}: quantum ${fmtNum(r.quantum_oracle_calls, 1)}, classical ${fmtNum(r.classical_evaluations, 1)}`)
                .join("; ")}`}
              table={
                <TableView
                  rows={rs}
                  caption="Quantum vs classical query counts"
                  columns={[
                    { key: "size", label: SIZE_NAME[cipher] ?? "size" },
                    { key: "condition", label: "attack mode" },
                    { key: "quantum_oracle_calls", label: cipher === "minirsa" ? "Shor circuit runs" : "quantum oracle calls" },
                    { key: "classical_evaluations", label: cipher === "minirsa" ? "trial divisions" : "classical tries" },
                    { key: "theory_grover", label: "Grover theory" },
                    { key: "theory_classical", label: "classical theory" },
                    { key: "runs", label: "runs" },
                  ]}
                />
              }
            >
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey="size" {...axis(c)} label={{ value: SIZE_NAME[cipher] ?? "size", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis scale="log" domain={[1, "auto"]} allowDataOverflow {...axis(c)} width={56} tickFormatter={(v: number) => fmtNum(v, 0)} />
                  <Tooltip content={<SeriesTip />} cursor={{ stroke: c["--border"] }} />
                  {present.map((s) => (
                    <Line
                      key={s.key}
                      dataKey={s.key}
                      stroke={c[s.color as keyof ThemeColors]}
                      strokeWidth={2}
                      strokeDasharray={s.mark === "dash" ? "6 5" : undefined}
                      dot={s.mark === "dash" ? false : { r: 4, fill: c[s.color as keyof ThemeColors], stroke: c["--surface"], strokeWidth: 2 }}
                      activeDot={s.mark === "dash" ? false : { r: 6 }}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        })}
      </div>
      <p className="takeaway">
        <strong>What this shows.</strong> Grover needs about √N oracle calls where brute force needs about N/2 tries, so
        the gap widens with every added key bit. At the very smallest sizes the two are close, and quantum counting can
        cost more calls than the search it tunes. The comparison is in queries: on wall-clock time the classical
        simulation of the quantum circuit is slower than brute force at these sizes, and no speed advantage is claimed.
      </p>
    </>
  );
}

// ---------- Scaling ----------

function ScalingCharts({ rows }: { rows: SeriesRow[] }) {
  const c = useThemeColors();
  const { config } = useConfig();
  // Qubits per construction, as the engine's configuration reports them for each enabled modulus.
  const byConstruction = (config.rsa_moduli_options ?? []).filter(
    (o) => o.enabled && o.qubits_register_2n != null && o.qubits_iterative != null,
  );
  const constructionSeries: SeriesDef[] = [
    { key: "qubits_register_2n", label: "2n counting register", color: SLOTS[0], mark: "bar" },
    { key: "qubits_iterative", label: "Iterative, 1 counting qubit", color: SLOTS[2], mark: "bar" },
  ];
  const CTip = seriesTip(constructionSeries, c, (x) => `N = ${x}`, (v) => `${fmtNum(v, 0)} qubits`);
  return (
    <>
      {groupBy(rows, (r) => String(r.cipher)).map(([cipher, rs]) => {
        // One series per construction when the engine reports it; otherwise a single series.
        const keys = [...new Set(rs.map((r) => String(r.construction ?? "all")))];
        const series = (suffix: string): SeriesDef[] =>
          keys.map((k, i) => ({ key: `${k}:${suffix}`, label: k === "all" ? suffix : k, color: SLOTS[i % SLOTS.length] }));
        const sizes = [...new Set(rs.map((r) => num(r, "size") ?? 0))].sort((a, b) => a - b);
        const data = sizes.map((size) => {
          const out: SeriesRow = { size };
          for (const r of rs.filter((x) => x.size === size)) {
            const k = String(r.construction ?? "all");
            out[`${k}:qubits`] = num(r, "qubits");
            out[`${k}:depth`] = num(r, "transpiled_depth") ?? num(r, "depth");
          }
          return out;
        });
        const qSeries = series("qubits");
        const dSeries = series("depth");
        // The stored series has one row per modulus; when it mixed several constructions, the
        // mean qubit count describes no real circuit, so show the per-construction counts instead.
        const mixed = cipher === "minirsa" && keys.length === 1 && rs.some((r) => (num(r, "runs") ?? 1) > 1);
        const splitQubits = mixed && byConstruction.length > 0;
        const QTip = seriesTip(qSeries, c, (x) => sizeLabel(cipher, x), (v) => `${fmtNum(v, 0)} qubits`);
        const DTip = seriesTip(dSeries, c, (x) => sizeLabel(cipher, x), (v) => `depth ${fmtNum(v, 0)}`);
        const table = (
          <TableView
            rows={rs}
            caption={`${CIPHER_NAME[cipher] ?? cipher} scaling`}
            columns={[
              { key: "size", label: SIZE_NAME[cipher] ?? "size" },
              ...(keys.length > 1 ? [{ key: "construction", label: "construction" }] : []),
              { key: "qubits", label: "qubits" },
              { key: "depth", label: "logical depth" },
              { key: "transpiled_depth", label: "transpiled depth" },
              { key: "iterations", label: "iterations" },
              { key: "runs", label: "runs" },
            ]}
          />
        );
        return (
          <div className="chart-grid" key={cipher}>
            {splitQubits ? (
              <ChartFigure
                title="MiniRSA · Shor: qubits by modulus and construction"
                note="From the engine's configuration. The iterative construction reuses one counting qubit."
                legend={constructionSeries}
                ariaLabel={`Qubits by modulus: ${byConstruction.map((o) => `N = ${o.n}: ${o.qubits_register_2n} with a 2n register, ${o.qubits_iterative} iterative`).join("; ")}`}
                table={
                  <TableView
                    rows={byConstruction as unknown as SeriesRow[]}
                    caption="Qubits by modulus and construction"
                    columns={[
                      { key: "n", label: "modulus N" },
                      { key: "qubits_register_2n", label: "2n counting register" },
                      { key: "qubits_iterative", label: "iterative" },
                    ]}
                  />
                }
              >
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={byConstruction} margin={{ top: 12, right: 16, bottom: 22, left: 0 }} barCategoryGap="30%" barGap={2}>
                    <CartesianGrid vertical={false} stroke={c["--grid"]} />
                    <XAxis dataKey="n" {...axis(c)} label={{ value: "modulus N", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                    <YAxis {...axis(c)} width={40} allowDecimals={false} />
                    <Tooltip content={<CTip />} cursor={{ fill: c["--surface-2"] }} />
                    {constructionSeries.map((s) => (
                      <Bar key={s.key} dataKey={s.key} fill={c[s.color as keyof ThemeColors]} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </ChartFigure>
            ) : (
            <ChartFigure
              title={`${CIPHER_NAME[cipher] ?? cipher}: qubits by ${SIZE_NAME[cipher] ?? "size"}`}
              note={mixed ? "Mean over the constructions stored for each modulus." : undefined}
              legend={qSeries}
              ariaLabel={`Qubits by size: ${rs.map((r) => `${sizeLabel(cipher, r.size)} ${fmtNum(r.qubits, 0)}`).join(", ")}`}
              table={table}
            >
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data} margin={{ top: 12, right: 16, bottom: 22, left: 0 }} barCategoryGap="30%" barGap={2}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey="size" {...axis(c)} label={{ value: SIZE_NAME[cipher] ?? "size", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis {...axis(c)} width={40} allowDecimals={false} />
                  <Tooltip content={<QTip />} cursor={{ fill: c["--surface-2"] }} />
                  {qSeries.map((s) => (
                    <Bar key={s.key} dataKey={s.key} fill={c[s.color as keyof ThemeColors]} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </ChartFigure>
            )}
            <ChartFigure
              title={`${CIPHER_NAME[cipher] ?? cipher}: transpiled depth by ${SIZE_NAME[cipher] ?? "size"}`}
              note={
                mixed
                  ? "Log scale. Mean over the constructions stored for each modulus (the stored series does not separate them)."
                  : "Log scale: depth grows much faster than the qubit count."
              }
              legend={dSeries}
              table={splitQubits ? table : undefined}
              ariaLabel={`Transpiled depth by size: ${rs.map((r) => `${sizeLabel(cipher, r.size)} ${fmtNum(r.transpiled_depth ?? r.depth, 0)}`).join(", ")}`}
            >
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey="size" {...axis(c)} label={{ value: SIZE_NAME[cipher] ?? "size", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis scale="log" domain={["auto", "auto"]} {...axis(c)} width={60} tickFormatter={(v: number) => fmtNum(v, 0)} />
                  <Tooltip content={<DTip />} cursor={{ stroke: c["--border"] }} />
                  {dSeries.map((s) => (
                    <Line
                      key={s.key}
                      dataKey={s.key}
                      stroke={c[s.color as keyof ThemeColors]}
                      strokeWidth={2}
                      dot={{ r: 4, fill: c[s.color as keyof ThemeColors], stroke: c["--surface"], strokeWidth: 2 }}
                      activeDot={{ r: 6 }}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </ChartFigure>
          </div>
        );
      })}
      <p className="takeaway">
        <strong>What this shows.</strong> Qubits grow steadily with the problem, but the circuit depth explodes, and the
        simulator's memory doubles with every qubit. That is why these are miniature ciphers.
      </p>
    </>
  );
}

// ---------- Noise ----------

function NoiseCharts({ rows }: { rows: SeriesRow[] }) {
  const c = useThemeColors();
  const sweeps = rows.filter((r) => r.model === "depolarizing" || (r.model === "ideal" && r.p != null));
  const fake = rows.filter((r) => r.model === "fake_backend");
  const series: SeriesDef[] = [{ key: "y", label: "attack success probability", color: QUANTUM }];

  return (
    <>
      {sweeps.length > 0 && (
        <div className="chart-grid">
          {/* One chart per circuit: Shor's constructions are different circuits with different noise behaviour. */}
          {groupBy(sweeps, (r) => `${r.cipher}|${r.size}|${r.construction ?? ""}`).map(([key, rs]) => {
            const cipher = String(rs[0].cipher);
            const construction = rs[0].construction != null ? `, ${String(rs[0].construction)} circuit` : "";
            const data = [...rs]
              .sort((a, b) => (num(a, "p") ?? 0) - (num(b, "p") ?? 0))
              .map((r) => ({ ...r, x: String(r.p ?? 0), y: num(r, "p_success") ?? num(r, "success_rate") }));
            const baseline = data.map((r) => num(r, "baseline")).find((b) => b !== null) ?? null;
            const NTip = seriesTip(series, c, (x) => `noise p = ${x}`, fmtPct);
            return (
              <ChartFigure
                key={key}
                title={`${CIPHER_NAME[cipher] ?? cipher}, ${sizeLabel(cipher, rs[0].size)}${construction}: success vs noise`}
                note="Depolarising error per two-qubit gate. The share of shots that land on the secret."
                ariaLabel={`Success probability by noise: ${data.map((r) => `p ${r.x}: ${fmtPct(r.y)}`).join(", ")}`}
                table={
                  <TableView
                    rows={rs}
                    caption="Noise sweep"
                    columns={[
                      { key: "p", label: "noise p", format: (v) => String(v ?? 0) },
                      { key: "p_success", label: "success probability", format: fmtPct },
                      { key: "success_rate", label: "runs that recovered the secret", format: fmtPct },
                      { key: "baseline", label: "guessing baseline", format: fmtPct },
                      { key: "transpiled_depth", label: "transpiled depth" },
                      { key: "runs", label: "runs" },
                    ]}
                  />
                }
              >
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 0 }}>
                    <CartesianGrid vertical={false} stroke={c["--grid"]} />
                    <XAxis dataKey="x" {...axis(c)} label={{ value: "noise p", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                    <YAxis domain={[0, 1]} {...axis(c)} width={48} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                    <Tooltip content={<NTip />} cursor={{ stroke: c["--border"] }} />
                    {baseline !== null && (
                      <ReferenceLine
                        y={baseline}
                        stroke={c["--text-muted"]}
                        strokeDasharray="6 5"
                        label={{ value: "guessing", position: "insideBottomRight", fill: c["--text-muted"], fontSize: 12 }}
                      />
                    )}
                    <Line
                      dataKey="y"
                      stroke={c["--series-1"]}
                      strokeWidth={2}
                      dot={{ r: 4, fill: c["--series-1"], stroke: c["--surface"], strokeWidth: 2 }}
                      activeDot={{ r: 6 }}
                      isAnimationActive={false}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartFigure>
            );
          })}
        </div>
      )}
      {fake.length > 0 && (
        <>
          <h3>Fake IBM backends (real chip layouts and calibrated noise)</h3>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Attack</th>
                  <th scope="col">Backend</th>
                  <th scope="col">Grover iterations</th>
                  <th scope="col">Success probability</th>
                  <th scope="col">Guessing baseline</th>
                  <th scope="col">Transpiled depth</th>
                  <th scope="col">Runs</th>
                </tr>
              </thead>
              <tbody>
                {fake.map((r, i) => (
                  <tr key={i}>
                    <th scope="row">
                      {CIPHER_NAME[String(r.cipher)] ?? String(r.cipher)}, {sizeLabel(r.cipher, r.size)}
                      {r.construction != null && `, ${String(r.construction)}`}
                    </th>
                    <td className="mono">{String(r.backend ?? "—")}</td>
                    <td className="mono">{fmtNum(r.iterations)}</td>
                    <td className="mono">{fmtPct(r.p_success)}</td>
                    <td className="mono">{fmtPct(r.baseline)}</td>
                    <td className="mono">{fmtNum(r.transpiled_depth, 0)}</td>
                    <td className="mono">{fmtNum(r.runs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <p className="takeaway">
        <strong>What this shows.</strong> On today's noisy hardware even this miniature breach fails: success falls to
        the guessing baseline at error rates far below what current devices achieve. Real breach testing needs fault
        tolerance.
      </p>
    </>
  );
}

// ---------- Iteration curve ----------

function IterationCharts({ rows }: { rows: SeriesRow[] }) {
  const c = useThemeColors();
  const series: SeriesDef[] = [
    { key: "p_success", label: "Measured success", color: QUANTUM },
    { key: "theory", label: "Theory, sin²((2j+1)θ)", color: QUANTUM, mark: "dash" },
  ];
  return (
    <>
      <div className="chart-grid">
        {groupBy(rows, (r) => String(r.key_bits)).map(([bits, rs]) => {
          const data = [...rs].sort((a, b) => (num(a, "iterations") ?? 0) - (num(b, "iterations") ?? 0));
          const ITip = seriesTip(series, c, (x) => `${x} iteration${x === 1 ? "" : "s"}`, fmtPct);
          return (
            <ChartFigure
              key={bits}
              title={`${bits}-bit key: success by number of Grover iterations`}
              legend={series}
              ariaLabel={`Success by iterations: ${data.map((r) => `${r.iterations}: measured ${fmtPct(r.p_success)}, theory ${fmtPct(r.theory)}`).join("; ")}`}
              table={
                <TableView
                  rows={data}
                  caption="Iteration curve"
                  columns={[
                    { key: "iterations", label: "iterations" },
                    { key: "p_success", label: "measured", format: fmtPct },
                    { key: "theory", label: "theory", format: fmtPct },
                    { key: "runs", label: "runs" },
                  ]}
                />
              }
            >
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey="iterations" {...axis(c)} label={{ value: "Grover iterations", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis domain={[0, 1]} {...axis(c)} width={48} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                  <Tooltip content={<ITip />} cursor={{ stroke: c["--border"] }} />
                  <Line dataKey="theory" stroke={c["--series-1"]} strokeWidth={2} strokeDasharray="6 5" dot={false} activeDot={false} isAnimationActive={false} connectNulls />
                  <Line
                    dataKey="p_success"
                    stroke={c["--series-1"]}
                    strokeWidth={2}
                    dot={{ r: 4, fill: c["--series-1"], stroke: c["--surface"], strokeWidth: 2 }}
                    activeDot={{ r: 6 }}
                    isAnimationActive={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        })}
      </div>
      <p className="takeaway">
        <strong>What this shows.</strong> Success rises and then falls again as iterations increase, tracking the
        textbook sin² curve: too many Grover iterations overshoot. That is why the iteration count is chosen from the
        estimated number of matching keys.
      </p>
    </>
  );
}

// ---------- Success rates ----------

function SuccessCharts({ rows, conditionLabels }: { rows: SeriesRow[]; conditionLabels: Record<string, string> }) {
  const c = useThemeColors();
  const sym = rows.filter((r) => r.cipher === "miniaes");
  const shorByBase = rows.filter((r) => r.cipher === "minirsa" && r.a != null);
  const shorRuns = rows.filter((r) => r.cipher === "minirsa" && num(r, "runs_to_success") !== null);

  // Symmetric: one bar per attack mode, grouped by key size. Colour follows the mode.
  const conditions = [...new Set(sym.map((r) => String(r.condition ?? "all")))].sort();
  const symSeries: SeriesDef[] = conditions.map((k, i) => ({
    key: k,
    label: conditionLabels[k] ?? k.replace(/_/g, " "),
    color: SLOTS[i % SLOTS.length],
    mark: "bar",
  }));
  const symData = [...new Set(sym.map((r) => num(r, "size") ?? 0))]
    .sort((a, b) => a - b)
    .map((size) => {
      const out: SeriesRow = { size };
      for (const r of sym.filter((x) => x.size === size)) out[String(r.condition ?? "all")] = num(r, "success_rate");
      return out;
    });
  const SymTip = seriesTip(symSeries, c, (x) => `${x}-bit key`, fmtPct);
  const baseSeries: SeriesDef[] = [{ key: "success_rate", label: "runs that factored N", color: QUANTUM, mark: "bar" }];

  return (
    <>
      {sym.length > 0 && (
        <ChartFigure
          title="MiniAES · Grover: runs that recovered the key, by key size and attack mode"
          note="Each bar averages runs across keys and seeds. An ambiguous result still counts as recovered here; the table shows how often the key was unique."
          legend={symSeries}
          ariaLabel={`Success rate: ${sym.map((r) => `${r.size}-bit ${r.condition}: ${fmtPct(r.success_rate)}`).join("; ")}`}
          table={
            <TableView
              rows={sym}
              caption="Symmetric success rates"
              columns={[
                { key: "size", label: "key bits" },
                { key: "condition", label: "attack mode" },
                { key: "success_rate", label: "recovered", format: fmtPct },
                { key: "unique_rate", label: "unique key", format: fmtPct },
                { key: "p_success", label: "shots on the key", format: fmtPct },
                { key: "runs", label: "runs" },
              ]}
            />
          }
        >
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={symData} margin={{ top: 12, right: 16, bottom: 22, left: 0 }} barCategoryGap="30%" barGap={2}>
              <CartesianGrid vertical={false} stroke={c["--grid"]} />
              <XAxis dataKey="size" {...axis(c)} label={{ value: "key bits", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
              <YAxis domain={[0, 1]} {...axis(c)} width={48} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
              <Tooltip content={<SymTip />} cursor={{ fill: c["--surface-2"] }} />
              {symSeries.map((s) => (
                <Bar key={s.key} dataKey={s.key} fill={c[s.color as keyof ThemeColors]} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartFigure>
      )}

      {shorByBase.length > 0 && (
        <>
          <h3>MiniRSA · Shor: success by base a</h3>
          <div className="chart-grid chart-grid-3">
            {groupBy(shorByBase, (r) => String(r.size)).map(([n, rs]) => {
              const data = [...rs].sort((a, b) => (num(a, "a") ?? 0) - (num(b, "a") ?? 0));
              const BTip = seriesTip(baseSeries, c, (x) => `N = ${n}, base a = ${x}`, fmtPct);
              return (
                <ChartFigure
                  key={n}
                  title={`N = ${n}`}
                  ariaLabel={`Success by base for N = ${n}: ${data.map((r) => `a ${r.a}: ${fmtPct(r.success_rate)}`).join(", ")}`}
                  table={
                    <TableView
                      rows={data}
                      caption={`Shor success by base, N = ${n}`}
                      columns={[
                        { key: "a", label: "base a" },
                        { key: "success_rate", label: "factored", format: fmtPct },
                        { key: "p_success", label: "useful shots", format: fmtPct },
                        { key: "runs", label: "runs" },
                      ]}
                    />
                  }
                >
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={data} margin={{ top: 8, right: 8, bottom: 20, left: 0 }} barCategoryGap="25%">
                      <CartesianGrid vertical={false} stroke={c["--grid"]} />
                      <XAxis dataKey="a" {...axis(c)} interval="preserveStartEnd" label={{ value: "base a", position: "insideBottom", offset: -10, fill: c["--text-muted"], fontSize: 12 }} />
                      <YAxis domain={[0, 1]} {...axis(c)} width={44} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                      <Tooltip content={<BTip />} cursor={{ fill: c["--surface-2"] }} />
                      <Bar dataKey="success_rate" fill={c["--series-1"]} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartFigure>
              );
            })}
          </div>
        </>
      )}

      {shorRuns.length > 0 && (
        <>
          <h3>MiniRSA · Shor: average circuit runs to factor</h3>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Modulus</th>
                  <th scope="col">Base a</th>
                  <th scope="col">Average runs to factor</th>
                  <th scope="col">Trials</th>
                </tr>
              </thead>
              <tbody>
                {shorRuns.map((r, i) => (
                  <tr key={i}>
                    <th scope="row">N = {String(r.size)}</th>
                    <td className="mono">{r.a != null ? String(r.a) : "random"}</td>
                    <td className="mono">{fmtNum(r.runs_to_success)}</td>
                    <td className="mono">{fmtNum(r.runs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {sym.length > 0 && shorByBase.length === 0 && shorRuns.length === 0 && (
        <EmptyState>No Shor per-base or runs-to-factor results are stored on this engine yet.</EmptyState>
      )}
      {sym.length === 0 && <EmptyState>No symmetric success-rate results are stored on this engine yet.</EmptyState>}
    </>
  );
}

// ---------- Counting ----------

function CountingTable({ rows }: { rows: SeriesRow[] }) {
  const correct = rows.filter((r) => r.correct === true).length;
  // One line per distinct outcome, with how many stored runs produced it.
  const grouped = groupBy(rows, (r) => [r.key_bits, r.condition, r.true_m, r.estimated_m, r.correct].join("|")).map(([, rs]): SeriesRow => ({
    ...rs[0],
    runs: rs.length,
    peak_m_estimate: rs.reduce((sum, r) => sum + (num(r, "peak_m_estimate") ?? 0), 0) / rs.length,
  }));
  return (
    <>
      <p>
        Quantum counting estimated the number of matching keys correctly in{" "}
        <strong className="mono">
          {correct} of {rows.length}
        </strong>{" "}
        stored runs. The true count is computed classically, which is only possible at these toy sizes.
      </p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Key bits</th>
              <th scope="col">Attack mode</th>
              <th scope="col">True M</th>
              <th scope="col">Estimated M</th>
              <th scope="col">Mean raw estimate</th>
              <th scope="col">Runs</th>
              <th scope="col">Match</th>
            </tr>
          </thead>
          <tbody>
            {grouped.map((r, i) => (
              <tr key={i}>
                <td className="mono">{fmtNum(r.key_bits)}</td>
                <td>{String(r.condition ?? "—").replace(/_/g, " ")}</td>
                <td className="mono">{fmtNum(r.true_m)}</td>
                <td className="mono">{fmtNum(r.estimated_m)}</td>
                <td className="mono">{fmtNum(r.peak_m_estimate)}</td>
                <td className="mono">{fmtNum(r.runs)}</td>
                <td>{r.correct === true ? "✓ correct" : r.correct === false ? "✗ off" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
