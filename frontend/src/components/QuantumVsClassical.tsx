import type { ReactNode } from "react";
import type { AesComparison, RsaComparison } from "../api/types";

type Props =
  | { kind: "symmetric"; comparison: AesComparison | null | undefined }
  | { kind: "public-key"; comparison: RsaComparison | null | undefined; constructionLabel?: string };

function fmt(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 1) return `${ms.toFixed(0)} ms`;
  return `${ms.toFixed(3)} ms`;
}

function Figure({ k, v, sub }: { k: string; v: ReactNode; sub?: ReactNode }) {
  return (
    <div className="qvc-figure">
      <dt>{k}</dt>
      <dd>
        <span className="qvc-value mono">{v}</span>
        {sub && <span className="qvc-sub small muted">{sub}</span>}
      </dd>
    </div>
  );
}

/** Paired bars on one shared scale: the fair comparison is the number of queries, not time. */
function QueryBars({ rows, unit }: { rows: { label: string; value: number; side: "q" | "c" }[]; unit: string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="qvc-bars" role="img" aria-label={`${unit}: ${rows.map((r) => `${r.label} ${fmt(r.value)}`).join(", ")}`}>
      {rows.map((r) => (
        <div className="qvc-bar-row" key={r.label}>
          <span className="qvc-bar-label">{r.label}</span>
          <span className="qvc-bar-track">
            <span className={`qvc-bar qvc-bar-${r.side}`} style={{ width: `${Math.max(1.5, (r.value / max) * 100)}%` }} />
          </span>
          <span className="qvc-bar-value mono">{fmt(r.value)}</span>
        </div>
      ))}
      <div className="small muted">{unit}, same scale. Fewer is cheaper.</div>
    </div>
  );
}

/**
 * The Breach Report's "Quantum vs classical" box, rendered from the engine's per-run
 * comparison record. The wall-clock note is the engine's own text, shown verbatim.
 */
export default function QuantumVsClassical(props: Props) {
  if (!props.comparison) {
    return (
      <section className="report-section">
        <h3>Quantum vs classical</h3>
        <p className="muted">This engine build did not return a classical-baseline comparison for this run.</p>
      </section>
    );
  }

  return (
    <section className="report-section qvc" aria-labelledby="qvc-title">
      <h3 id="qvc-title">Quantum vs classical</h3>
      {props.kind === "symmetric" ? <Symmetric c={props.comparison} /> : <PublicKey c={props.comparison} label={props.constructionLabel} />}
    </section>
  );
}

function Symmetric({ c }: { c: AesComparison }) {
  const q = c.quantum;
  const cl = c.classical;
  return (
    <>
      <p className="qvc-lede">
        Both sides solved the same problem from the same intercepted data. Neither saw the key.
      </p>
      <div className="qvc-grid">
        <div className="qvc-side qvc-quantum">
          <div className="qvc-side-title">
            <span className="qvc-key qvc-key-q" aria-hidden="true" /> Quantum adversary · Grover
          </div>
          <dl>
            <Figure
              k="Oracle calls"
              v={fmt(q.oracle_calls)}
              sub={
                q.counting_oracle_calls > 0
                  ? `${fmt(q.grover_oracle_calls)} in the search + ${fmt(q.counting_oracle_calls)} for quantum counting`
                  : `across ${fmt(q.circuit_runs)} circuit run${q.circuit_runs === 1 ? "" : "s"}`
              }
            />
            <Figure k="Grover iterations" v={fmt(q.grover_iterations)} sub={`theory optimum ≈ ${fmt(c.theory.grover_optimal_iterations)}`} />
            <Figure k="Qubits" v={fmt(q.qubits)} sub={`transpiled depth ${fmt(q.transpiled_depth)}`} />
          </dl>
        </div>
        <div className="qvc-side qvc-classical">
          <div className="qvc-side-title">
            <span className="qvc-key qvc-key-c" aria-hidden="true" /> Classical baseline · brute force
          </div>
          <dl>
            <Figure
              k="Cipher evaluations"
              v={fmt(cl.cipher_evaluations)}
              sub={`keys tried before the first fit; ${fmt(cl.exhaustive_evaluations)} to check every key`}
            />
            <Figure k="Expected tries" v={fmt(cl.expected_tries)} sub={`theory average ≈ ${fmt(c.theory.classical_average_tries)} of ${fmt(c.theory.search_space)} keys`} />
            <Figure k="Qubits" v="0" sub={`${fmt(cl.candidates)} key${cl.candidates === 1 ? "" : "s"} fit the data`} />
          </dl>
        </div>
      </div>
      <QueryBars
        unit="Queries to the cipher"
        rows={[
          { label: "Grover oracle calls", value: q.grover_oracle_calls, side: "q" },
          { label: "Classical cipher evaluations", value: cl.cipher_evaluations, side: "c" },
        ]}
      />
      <WallClock
        note={c.wallclock_note}
        extra={c.oracle_calls_note}
        times={[
          ["Quantum circuit, simulated classically", c.quantum_wallclock_ms],
          ["Classical brute force", c.classical_wallclock_ms],
        ]}
      />
    </>
  );
}

function PublicKey({ c, label }: { c: RsaComparison; label?: string }) {
  const q = c.quantum;
  const cl = c.classical;
  const by = q.qubits_by_construction;
  return (
    <>
      <p className="qvc-lede">
        Both sides worked from the public key only. Neither saw p, q, φ or d.
      </p>
      <div className="qvc-grid">
        <div className="qvc-side qvc-quantum">
          <div className="qvc-side-title">
            <span className="qvc-key qvc-key-q" aria-hidden="true" /> Quantum adversary · Shor
          </div>
          <dl>
            <Figure
              k="Shor circuit runs"
              v={fmt(q.circuit_runs)}
              sub={`${fmt(q.shots_per_run)} shots each · ${q.factors_found ? "factors found" : "no factors this run"}`}
            />
            <Figure k="Qubits" v={fmt(q.qubits)} sub={label ?? q.construction_name} />
            <Figure
              k="2n register vs iterative"
              v={`${fmt(by.register_2n)} vs ${fmt(by.iterative)}`}
              sub="qubits for this modulus, by construction"
            />
          </dl>
        </div>
        <div className="qvc-side qvc-classical">
          <div className="qvc-side-title">
            <span className="qvc-key qvc-key-c" aria-hidden="true" /> Classical baselines
          </div>
          <dl>
            <Figure k="Trial divisions" v={fmt(cl.trial_divisions)} sub="to factor N directly" />
            <Figure
              k="Order-finding multiplications"
              v={fmt(cl.order_finding_mults)}
              sub={`modular multiplications · ${fmt(cl.order_finding_bases_tried)} base${cl.order_finding_bases_tried === 1 ? "" : "s"} tried`}
            />
            <Figure k="Qubits" v="0" sub={cl.factors_found ? "factors found" : "no factors"} />
          </dl>
        </div>
      </div>
      <QueryBars
        unit="Runs and operations"
        rows={[
          { label: "Shor circuit runs", value: q.circuit_runs, side: "q" },
          { label: "Classical trial divisions", value: cl.trial_divisions, side: "c" },
          { label: "Classical order-finding multiplications", value: cl.order_finding_mults, side: "c" },
        ]}
      />
      <WallClock
        note={c.wallclock_note}
        times={[
          ["Quantum circuit, simulated classically", c.wallclock_ms.quantum_simulation],
          ["Trial division", c.wallclock_ms.trial_division],
          ["Classical order finding", c.wallclock_ms.order_finding],
        ]}
      />
    </>
  );
}

function WallClock({ note, extra, times }: { note: string; extra?: string; times: [string, number][] }) {
  return (
    <div className="qvc-note">
      <strong>About wall-clock time.</strong> {note}
      {extra && <span className="qvc-note-extra"> {extra}</span>}
      <ul className="qvc-times mono small">
        {times.map(([k, ms]) => (
          <li key={k}>
            <span className="qvc-time-k">{k}</span> {fmtMs(ms)}
          </li>
        ))}
      </ul>
    </div>
  );
}
