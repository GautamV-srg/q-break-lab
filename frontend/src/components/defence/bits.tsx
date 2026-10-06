import { useState } from "react";
import type { Citation, DefenceBundle } from "../../api/types";
import { verdictMeta } from "./settings";

export function humanize(key: string): string {
  return key
    .replace(/_b64$/, "")
    .replace(/_ms$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase())
    .replace(/\bkem\b/i, "KEM")
    .replace(/\bqber\b/i, "QBER")
    .replace(/\bbb84\b/i, "BB84");
}

export function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return String(v);
    if (Math.abs(v) >= 1e9) return v.toExponential(2).replace("e+", " × 10^");
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 10) return `${ms.toFixed(0)} ms`;
  return `${ms.toFixed(2)} ms`;
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked; ignore */
    }
  }
  return (
    <button type="button" className="btn btn-small btn-copy" onClick={() => void copy()} aria-label={`Copy ${label}`}>
      <span aria-live="polite">{copied ? "✓ Copied" : "Copy"}</span>
    </button>
  );
}

function truncate(s: string, n = 44): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function b64Bytes(s: string): number | null {
  try {
    return atob(s).length;
  } catch {
    return null;
  }
}

/** Every field of a public bundle, truncated, with a copy button. Nested records are summarised. */
export function PublicBundleView({ bundle }: { bundle: DefenceBundle }) {
  return (
    <dl className="bundle">
      {Object.entries(bundle).map(([k, v]) => {
        if (typeof v === "string") {
          const size = k.endsWith("_b64") ? b64Bytes(v) : null;
          return (
            <div className="bundle-row" key={k}>
              <dt>
                {humanize(k)} {size !== null && <span className="muted small">({size.toLocaleString()} B)</span>}
              </dt>
              <dd>
                <code className="bundle-value" title={v}>
                  {truncate(v)}
                </code>
                <CopyButton text={v} label={humanize(k)} />
              </dd>
            </div>
          );
        }
        const text = JSON.stringify(v);
        return (
          <div className="bundle-row" key={k}>
            <dt>{humanize(k)}</dt>
            <dd>
              <details className="bundle-record">
                <summary>
                  {v && typeof v === "object" && !Array.isArray(v)
                    ? `Public record: ${Object.keys(v).map(humanize).join(", ")}`
                    : truncate(text)}
                </summary>
                <code className="bundle-value bundle-json">{truncate(text, 600)}</code>
              </details>
              <CopyButton text={text} label={humanize(k)} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function VerdictBadge({ verdict, big = false }: { verdict: string; big?: boolean }) {
  const m = verdictMeta(verdict);
  return (
    <span className={`vbadge vbadge-${m.tone} ${big ? "vbadge-big" : ""}`}>
      <span aria-hidden="true">{m.icon}</span> {m.label}
    </span>
  );
}

/** Numbers and short strings from an evidence object, as a compact key-value grid. */
export function KeyNumbers({ evidence, skip = [] }: { evidence: Record<string, unknown>; skip?: string[] }) {
  const entries = Object.entries(evidence).filter(
    ([k, v]) =>
      !skip.includes(k) &&
      (typeof v === "number" || typeof v === "boolean" || (typeof v === "string" && v.length <= 90)) &&
      k !== "note",
  );
  if (entries.length === 0) return null;
  return (
    <dl className="key-numbers">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt>{humanize(k)}</dt>
          <dd className="mono">{k.includes("qber") && typeof v === "number" ? `${(v * 100).toFixed(1)}%` : fmtValue(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function citationText(c: Citation): string {
  if (typeof c === "string") return c;
  return [c.authors, c.title && `"${c.title}"`, c.venue, c.year].filter(Boolean).join(", ");
}

export function Citations({ citations }: { citations: Citation[] | Record<string, Citation> | undefined }) {
  if (!citations) return null;
  const list = Array.isArray(citations) ? citations.map((c) => [null, c] as const) : Object.entries(citations);
  if (list.length === 0) return null;
  return (
    <ul className="citations small muted">
      {list.map(([k, c], i) => {
        const url = typeof c === "object" && typeof c.url === "string" ? c.url : null;
        return (
          <li key={k ?? i}>
            {k && <span className="mono">[{k}]</span>} {citationText(c)}{" "}
            {url && (
              <a href={url} target="_blank" rel="noreferrer">
                link
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}
