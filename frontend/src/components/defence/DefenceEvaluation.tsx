import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EvaluationSeries, SeriesRow } from "../../api/types";
import { ChartFigure, EmptyState, fmtNum, fmtPct, num, TableView, Tip, type SeriesDef } from "../charts";
import { useThemeColors, type ThemeColors } from "../useThemeColors";
import { METHOD_FALLBACK_NAME } from "./settings";

export const DEFENCE_SERIES = ["bb84_qber_vs_eve", "bb84_qber_vs_noise", "bb84_key_rate", "defence_overhead"] as const;

/** The first key present in the rows, so a renamed engine field still plots. */
function pickKey(rows: SeriesRow[], candidates: string[]): string | null {
  return candidates.find((k) => rows.some((r) => num(r, k) !== null)) ?? null;
}

type TipProps = { active?: boolean; label?: string | number; payload?: { payload: SeriesRow }[] };

function axis(c: ThemeColors) {
  return { tick: { fill: c["--text-muted"], fontSize: 12 }, stroke: c["--border"], tickLine: false } as const;
}

function Sub({ title, series, children }: { title: string; series: EvaluationSeries | undefined; children: (rows: SeriesRow[]) => ReactNode }) {
  const rows = series?.rows ?? [];
  return (
    <div className="eval-sub">
      {rows.length === 0 ? (
        <>
          <h3>{title}</h3>
          <EmptyState>The defence experiments have not been run on this engine yet, or their results are being regenerated.</EmptyState>
        </>
      ) : (
        children(rows)
      )}
    </div>
  );
}

export default function DefenceEvaluation({ series }: { series: (name: string) => EvaluationSeries | undefined }) {
  const c = useThemeColors();
  const QBER = "--series-3";
  const THEORY = "--series-1";

  return (
    <div className="chart-grid">
      <Sub title="QBER vs intercept fraction" series={series("bb84_qber_vs_eve")}>
        {(rows) => {
          const x = pickKey(rows, ["eve_intercept_fraction", "intercept_fraction", "fraction"]) ?? "eve_intercept_fraction";
          const y = pickKey(rows, ["qber", "qber_mean", "mean_qber"]) ?? "qber";
          const thr = num(rows[0], "qber_threshold");
          // The theory line is fraction / 4 (intercept-resend); the engine's own value wins when it sends one.
          const data = [...rows]
            .sort((a, b) => (num(a, x) ?? 0) - (num(b, x) ?? 0))
            .map((r): SeriesRow => ({ ...r, theory_line: num(r, "theory") ?? num(r, "theory_qber") ?? (num(r, x) ?? 0) / 4 }));
          const defs: SeriesDef[] = [
            { key: y, label: "QBER (measured)", color: QBER },
            { key: "theory_line", label: "Theory: fraction / 4", color: THEORY, mark: "dash" },
          ];
          const T = ({ active, label, payload }: TipProps) =>
            active && payload?.length ? (
              <Tip
                title={`Intercept ${fmtPct(Number(label))}`}
                rows={defs.map((d) => ({ label: d.label, value: fmtPct(payload[0].payload[d.key]), color: c[d.color as keyof ThemeColors], dash: d.mark === "dash" }))}
              />
            ) : null;
          return (
            <ChartFigure
              title="BB84: QBER vs intercept fraction"
              note={`Eve intercept-resends a growing share of photons. Measured QBER tracks the fraction/4 theory, reaching about 25% at full intercept.${thr != null ? ` Dashed horizontal line: the ${fmtPct(thr)} abort threshold.` : ""}`}
              legend={defs}
              ariaLabel={`QBER by intercept fraction: ${data.map((r) => `${fmtPct(r[x])}: ${fmtPct(r[y])}`).join("; ")}`}
              table={<TableView rows={data} caption="QBER vs intercept fraction" columns={[{ key: x, label: "intercept fraction", format: fmtPct }, { key: y, label: "QBER", format: fmtPct }, { key: "theory_line", label: "theory", format: fmtPct }, { key: "runs", label: "runs" }]} />}
            >
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey={x} type="number" domain={[0, 1]} {...axis(c)} tickFormatter={(v: number) => fmtPct(v)} label={{ value: "intercept fraction", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis {...axis(c)} width={52} tickFormatter={(v: number) => fmtPct(v)} />
                  <Tooltip content={<T />} cursor={{ stroke: c["--border"] }} />
                  {thr != null && <ReferenceLine y={thr} stroke={c["--breach"]} strokeDasharray="4 4" label={{ value: `threshold ${fmtPct(thr)}`, fill: c["--text-muted"], fontSize: 11, position: "insideTopLeft" }} />}
                  <Line dataKey="theory_line" stroke={c[THEORY]} strokeWidth={2} strokeDasharray="6 5" dot={false} isAnimationActive={false} />
                  <Line dataKey={y} stroke={c[QBER]} strokeWidth={2} dot={{ r: 4, fill: c[QBER], stroke: c["--surface"], strokeWidth: 2 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        }}
      </Sub>

      <Sub title="QBER vs channel noise" series={series("bb84_qber_vs_noise")}>
        {(rows) => {
          const x = pickKey(rows, ["channel_noise", "noise", "p"]) ?? "channel_noise";
          const y = pickKey(rows, ["qber", "qber_mean", "mean_qber"]) ?? "qber";
          const thr = num(rows[0], "qber_threshold");
          const data = [...rows].sort((a, b) => (num(a, x) ?? 0) - (num(b, x) ?? 0));
          const T = ({ active, label, payload }: TipProps) =>
            active && payload?.length ? <Tip title={`Noise ${fmtPct(Number(label))}`} rows={[{ label: "QBER", value: fmtPct(payload[0].payload[y]), color: c[QBER] }]} /> : null;
          return (
            <ChartFigure
              title="BB84: QBER vs channel noise (no eavesdropper)"
              note={`Noise alone also raises the error rate. Past the threshold${thr != null ? ` (${fmtPct(thr)})` : ""} Alice and Bob abort, because they cannot tell noise from an eavesdropper.`}
              ariaLabel={`QBER by channel noise: ${data.map((r) => `${fmtPct(r[x])}: ${fmtPct(r[y])}`).join("; ")}`}
              table={<TableView rows={data} caption="QBER vs channel noise" columns={[{ key: x, label: "channel noise", format: fmtPct }, { key: y, label: "QBER", format: fmtPct }, { key: "runs", label: "runs" }]} />}
            >
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey={x} type="number" domain={[0, "auto"]} {...axis(c)} tickFormatter={(v: number) => fmtPct(v)} label={{ value: "channel noise", position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis {...axis(c)} width={52} tickFormatter={(v: number) => fmtPct(v)} />
                  <Tooltip content={<T />} cursor={{ stroke: c["--border"] }} />
                  {thr != null && <ReferenceLine y={thr} stroke={c["--breach"]} strokeDasharray="4 4" label={{ value: `threshold ${fmtPct(thr)}`, fill: c["--text-muted"], fontSize: 11, position: "insideTopLeft" }} />}
                  <Line dataKey={y} stroke={c[QBER]} strokeWidth={2} dot={{ r: 4, fill: c[QBER], stroke: c["--surface"], strokeWidth: 2 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        }}
      </Sub>

      <Sub title="Key rate" series={series("bb84_key_rate")}>
        {(rows) => {
          const x = pickKey(rows, ["raw_qubits", "raw_bits", "eve_intercept_fraction", "channel_noise"]) ?? "raw_qubits";
          const y = pickKey(rows, ["key_rate", "final_bits_per_raw_qubit"]) ?? "key_rate";
          const data = [...rows].sort((a, b) => (num(a, x) ?? 0) - (num(b, x) ?? 0));
          const T = ({ active, label, payload }: TipProps) =>
            active && payload?.length ? (
              <Tip
                title={`${x.replace(/_/g, " ")} ${fmtNum(label)}`}
                rows={[
                  { label: "final key bits per raw qubit", value: fmtNum(payload[0].payload[y], 4), color: c[QBER] },
                  { label: "final key bits", value: fmtNum(payload[0].payload.final_key_bits, 1) },
                ]}
              />
            ) : null;
          return (
            <ChartFigure
              title="BB84: key rate"
              note="Final key bits per raw qubit sent. Sifting keeps about half, sampling spends a quarter of those, and privacy amplification fixes the key at 256 bits, so too few raw qubits produce no key at all."
              ariaLabel={`Key rate: ${data.map((r) => `${fmtNum(r[x])}: ${fmtNum(r[y], 4)}`).join("; ")}`}
              table={<TableView rows={data} caption="Key rate" columns={[{ key: x, label: x.replace(/_/g, " ") }, { key: "sifted_bits", label: "sifted bits" }, { key: "final_key_bits", label: "final key bits" }, { key: y, label: "key rate" }, { key: "runs", label: "runs" }]} />}
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data} margin={{ top: 12, right: 24, bottom: 22, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey={x} {...axis(c)} label={{ value: x.replace(/_/g, " "), position: "insideBottom", offset: -12, fill: c["--text-muted"], fontSize: 12 }} />
                  <YAxis {...axis(c)} width={52} tickFormatter={(v: number) => fmtNum(v, 3)} />
                  <Tooltip content={<T />} cursor={{ fill: c["--surface-2"] }} />
                  <Bar dataKey={y} fill={c[QBER]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        }}
      </Sub>

      <Sub title="Defence overhead" series={series("defence_overhead")}>
        {(rows) => {
          const data = rows.map((r): SeriesRow => ({ ...r, name: METHOD_FALLBACK_NAME[String(r.method) as keyof typeof METHOD_FALLBACK_NAME] ?? String(r.method) }));
          const bytes = ["ciphertext_bytes", "public_bytes", "key_bytes"].filter((k) => rows.some((r) => num(r, k) !== null));
          const time = pickKey(rows, ["total_ms", "time_ms", "wallclock_ms"]);
          const defs: SeriesDef[] = bytes.map((k, i) => ({ key: k, label: k.replace(/_/g, " "), color: ["--series-1", "--series-2", "--series-4"][i], mark: "bar" }));
          const T = ({ active, label, payload }: TipProps) =>
            active && payload?.length ? (
              <Tip
                title={String(label)}
                rows={[
                  ...defs.map((d) => ({ label: d.label, value: `${fmtNum(payload[0].payload[d.key])} B`, color: c[d.color as keyof ThemeColors] })),
                  ...(time ? [{ label: "time", value: `${fmtNum(payload[0].payload[time], 1)} ms` }] : []),
                ]}
              />
            ) : null;
          return (
            <ChartFigure
              title="Defence overhead: bytes per method"
              note="Averaged over stored runs. ML-KEM's public key and KEM ciphertext add about 2.3 kB per exchange; BB84 instead spends raw qubits on the quantum channel."
              legend={defs}
              ariaLabel={`Overhead: ${data.map((r) => `${r.name}: ${bytes.map((k) => `${k} ${fmtNum(r[k])}`).join(", ")}`).join("; ")}`}
              table={<TableView rows={data} caption="Defence overhead" columns={[{ key: "name", label: "method" }, ...bytes.map((k) => ({ key: k, label: k.replace(/_/g, " ") })), ...(time ? [{ key: time, label: "time (ms)" }] : []), { key: "raw_qubits", label: "raw qubits" }, { key: "runs", label: "runs" }]} />}
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data} margin={{ top: 12, right: 24, bottom: 8, left: 4 }}>
                  <CartesianGrid vertical={false} stroke={c["--grid"]} />
                  <XAxis dataKey="name" {...axis(c)} />
                  <YAxis {...axis(c)} width={56} tickFormatter={(v: number) => fmtNum(v, 0)} />
                  <Tooltip content={<T />} cursor={{ fill: c["--surface-2"] }} />
                  {defs.map((d) => (
                    <Bar key={d.key} dataKey={d.key} stackId="b" fill={c[d.color as keyof ThemeColors]} isAnimationActive={false} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </ChartFigure>
          );
        }}
      </Sub>
    </div>
  );
}
