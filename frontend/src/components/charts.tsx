import type { ReactNode } from "react";
import type { SeriesRow } from "../api/types";

/** One plotted series: a fixed colour slot and how its legend key is drawn. */
export interface SeriesDef {
  key: string;
  label: string;
  /** CSS custom property name, e.g. "--series-1". Colour follows the entity, never its rank. */
  color: string;
  mark?: "line" | "dash" | "bar";
}

export function num(row: SeriesRow, key: string): number | null {
  const v = row[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function fmtNum(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v !== "number") return String(v);
  if (Number.isInteger(v)) return v.toLocaleString();
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function fmtPct(v: unknown): string {
  return typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";
}

/** Legend with text in ink colours; the coloured key beside it carries identity. */
export function Legend({ series }: { series: SeriesDef[] }) {
  return (
    <ul className="chart-legend small">
      {series.map((s) => (
        <li key={s.key}>
          <span
            className={`legend-key legend-key-${s.mark ?? "line"}`}
            style={s.mark === "dash" ? { borderColor: `var(${s.color})` } : { background: `var(${s.color})` }}
            aria-hidden="true"
          />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

export interface Column {
  key: string;
  label: string;
  format?: (v: unknown) => string;
}

/** The table view behind every chart: every plotted value is reachable without hovering. */
export function TableView({ rows, columns, caption }: { rows: SeriesRow[]; columns: Column[]; caption: string }) {
  return (
    <details className="disclosure chart-table">
      <summary>Table view ({rows.length} rows)</summary>
      <div className="table-scroll">
        <table className="data-table">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th scope="col" key={c.key}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td className="mono" key={c.key}>
                    {(c.format ?? fmtNum)(r[c.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

interface TipRow {
  label: string;
  value: string;
  color?: string;
  dash?: boolean;
}

/** Shared tooltip body: the value leads, the series name follows. */
export function Tip({ title, rows }: { title: string; rows: TipRow[] }) {
  return (
    <div className="chart-tooltip">
      <div className="muted small">{title}</div>
      {rows.map((r) => (
        <div className="tip-row" key={r.label}>
          {r.color && (
            <span
              className={`legend-key ${r.dash ? "legend-key-dash" : "legend-key-line"}`}
              style={r.dash ? { borderColor: r.color } : { background: r.color }}
              aria-hidden="true"
            />
          )}
          <span className="mono strong">{r.value}</span>
          <span className="muted">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

/** A titled figure. `takeaway` states what the data supports, in one sentence. */
export function ChartFigure({
  title,
  note,
  legend,
  ariaLabel,
  children,
  table,
}: {
  title: string;
  note?: ReactNode;
  legend?: SeriesDef[];
  ariaLabel: string;
  children: ReactNode;
  table?: ReactNode;
}) {
  return (
    <figure className="chart-figure">
      <figcaption className="chart-title">{title}</figcaption>
      {note && <div className="small muted chart-note">{note}</div>}
      {legend && legend.length > 1 && <Legend series={legend} />}
      <div className="chart-box" role="img" aria-label={ariaLabel}>
        {children}
      </div>
      {table}
    </figure>
  );
}

export function EmptyState({ children }: { children?: ReactNode }) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-icon" aria-hidden="true">∅</span>
      <div>
        <strong>No results yet.</strong>{" "}
        {children ?? "This experiment has not been run on this engine, or its results are being regenerated."}
      </div>
    </div>
  );
}
