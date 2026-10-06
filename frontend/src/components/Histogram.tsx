import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Measurement, MeasurementTop } from "../api/types";
import { useThemeColors } from "./useThemeColors";

interface Props {
  measurement: Measurement;
  /** Bitstrings to draw in the accent colour (recovered key / accepted peaks). */
  highlight: string[];
  /** Dashed "random guessing" line at this probability (symmetric test: 1/2^k). */
  uniform?: number;
  highlightLabel: string;
}

function TooltipBody({ active, payload }: { active?: boolean; payload?: { payload: MeasurementTop }[] }) {
  if (!active || !payload?.length) return null;
  const t = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="mono strong">{t.bitstring}</div>
      <div>{t.meaning}</div>
      <div className="mono muted">
        {t.count} shots · {(t.probability * 100).toFixed(1)}%
      </div>
    </div>
  );
}

export default function Histogram({ measurement, highlight, uniform, highlightLabel }: Props) {
  const c = useThemeColors();
  const data = measurement.top;
  const hl = new Set(highlight);
  const longLabels = (data[0]?.bitstring.length ?? 0) > 5 || data.length > 10;
  const maxP = Math.max(...data.map((d) => d.probability), uniform ?? 0);

  return (
    <figure className="histogram">
      <div className="chart-box" role="img" aria-label={`Measurement histogram of ${measurement.shots} shots. ${data
        .slice(0, 4)
        .map((d) => `${d.bitstring}: ${(d.probability * 100).toFixed(1)}%`)
        .join(", ")}`}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 16, right: 16, bottom: longLabels ? 36 : 8, left: 0 }}>
            <CartesianGrid vertical={false} stroke={c["--border"]} strokeDasharray="2 4" />
            <XAxis
              dataKey="bitstring"
              tick={{ fill: c["--text-muted"], fontFamily: "var(--font-mono)", fontSize: 12 }}
              angle={longLabels ? -45 : 0}
              textAnchor={longLabels ? "end" : "middle"}
              interval={0}
              stroke={c["--border"]}
            />
            <YAxis
              domain={[0, Math.min(1, Math.ceil(maxP * 10 + 0.5) / 10)]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fill: c["--text-muted"], fontSize: 12 }}
              stroke={c["--border"]}
              width={48}
            />
            <Tooltip content={<TooltipBody />} cursor={{ fill: c["--surface-2"] }} />
            {uniform !== undefined && (
              <ReferenceLine
                y={uniform}
                stroke={c["--text-muted"]}
                strokeDasharray="6 4"
                label={{
                  value: `random guessing (${(uniform * 100).toFixed(uniform < 0.01 ? 2 : 1)}%)`,
                  position: "insideTopRight",
                  fill: c["--text-muted"],
                  fontSize: 12,
                }}
              />
            )}
            <Bar dataKey="probability" radius={[4, 4, 0, 0]} isAnimationActive>
              {data.map((d) => (
                <Cell key={d.bitstring} fill={hl.has(d.bitstring) ? c["--accent"] : c["--bar"]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="legend small">
        <span className="legend-swatch" style={{ background: c["--accent"] }} /> {highlightLabel}
        <span className="legend-swatch" style={{ background: c["--bar"] }} /> other outcomes
        {uniform !== undefined && (
          <>
            <span className="legend-dash" /> uniform baseline
          </>
        )}
        <span className="muted"> · {measurement.shots} shots, top {data.length} outcomes</span>
      </figcaption>
    </figure>
  );
}
