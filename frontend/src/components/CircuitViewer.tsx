import { useState } from "react";
import type { CircuitInfo } from "../api/types";

interface Props {
  circuit: CircuitInfo;
  /** One sentence per boxed block, shown under the tabs when the drawing title contains the key. */
  blockNotes?: Record<string, string>;
  filename: string;
}

const FONT_SIZES = [10, 12, 14, 16];

export default function CircuitViewer({ circuit, blockNotes = {}, filename }: Props) {
  const [tab, setTab] = useState(0);
  const [fs, setFs] = useState(1);
  const [copied, setCopied] = useState(false);
  const drawings = circuit.drawings;
  const current = drawings[Math.min(tab, drawings.length - 1)];
  // Notes are matched by substring so "U^(2^" covers every controlled-power block.
  const note = current
    ? Object.entries(blockNotes).find(([k]) => current.title.toLowerCase().includes(k.toLowerCase()))?.[1]
    : undefined;

  const topGates = Object.entries(circuit.gate_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  async function copy() {
    if (!current) return;
    try {
      await navigator.clipboard.writeText(current.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked; ignore */
    }
  }

  function downloadQasm() {
    if (!circuit.qasm) return;
    const blob = new Blob([circuit.qasm], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="circuit-viewer">
      <div className="stat-chips">
        <span className="stat-chip">
          <span className="stat-k">qubits</span> <span className="mono">{circuit.num_qubits}</span>
        </span>
        <span className="stat-chip">
          <span className="stat-k">classical bits</span> <span className="mono">{circuit.num_clbits}</span>
        </span>
        <span className="stat-chip">
          <span className="stat-k">logical depth</span> <span className="mono">{circuit.depth}</span>
        </span>
        <span className="stat-chip">
          <span className="stat-k">transpiled depth</span> <span className="mono">{circuit.transpiled_depth}</span>
        </span>
        {topGates.map(([g, n]) => (
          <span className="stat-chip stat-chip-gate" key={g}>
            <span className="mono">{g}</span> <span className="mono">×{n}</span>
          </span>
        ))}
      </div>

      {circuit.registers.length > 0 && (
        <table className="register-legend">
          <caption className="sr-only">Quantum registers</caption>
          <thead>
            <tr>
              <th scope="col">Register</th>
              <th scope="col">Qubits</th>
              <th scope="col">Role</th>
            </tr>
          </thead>
          <tbody>
            {circuit.registers.map((r) => (
              <tr key={r.name}>
                <td className="mono">{r.name}</td>
                <td className="mono">{r.size}</td>
                <td>{r.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {drawings.length > 0 ? (
        <>
          <div className="tabs" role="tablist" aria-label="Circuit drawings">
            {drawings.map((d, i) => (
              <button
                key={d.title}
                role="tab"
                aria-selected={i === tab}
                className={i === tab ? "tab tab-active" : "tab"}
                onClick={() => setTab(i)}
              >
                {d.title}
              </button>
            ))}
          </div>
          {note && <p className="block-note">{note}</p>}
          <div className="pre-toolbar">
            <span className="muted small">Font size</span>
            <button className="btn btn-ghost btn-small" onClick={() => setFs((f) => Math.max(0, f - 1))} aria-label="Smaller font">
              A−
            </button>
            <button
              className="btn btn-ghost btn-small"
              onClick={() => setFs((f) => Math.min(FONT_SIZES.length - 1, f + 1))}
              aria-label="Larger font"
            >
              A+
            </button>
            <button className="btn btn-ghost btn-small" onClick={copy}>
              {copied ? "Copied ✓" : "Copy"}
            </button>
            {circuit.qasm && (
              <button className="btn btn-ghost btn-small" onClick={downloadQasm}>
                Download OpenQASM
              </button>
            )}
          </div>
          <pre className="circuit-pre" style={{ fontSize: FONT_SIZES[fs] }} tabIndex={0} aria-label={current?.title}>
            {current?.text}
          </pre>
        </>
      ) : (
        <p className="muted">No drawings were returned for this circuit.</p>
      )}
    </div>
  );
}
