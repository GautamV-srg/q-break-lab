import { useEffect, useState } from "react";
import { getAesResources, getRsaResourceEstimate } from "../api/client";
import type { AesResources, RsaResourceEstimate } from "../api/types";

function fmtBig(n: number): string {
  return n >= 1e6 ? n.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 }) : n.toLocaleString();
}

/**
 * Published real-scale resource estimates, served by the engine with their citations.
 * Nothing here is measured by Q-Break. Renders nothing when the engine does not expose
 * the estimator, so the report still stands on its own.
 */
export default function RealScaleEstimates({ kind }: { kind: "symmetric" | "public-key" }) {
  const [aes, setAes] = useState<AesResources | null>(null);
  const [rsa, setRsa] = useState<RsaResourceEstimate | null>(null);

  useEffect(() => {
    let live = true;
    if (kind === "symmetric") getAesResources().then((r) => live && setAes(r)).catch(() => {});
    else getRsaResourceEstimate(2048).then((r) => live && setRsa(r)).catch(() => {});
    return () => {
      live = false;
    };
  }, [kind]);

  if (kind === "symmetric" && aes?.estimates?.length) {
    const used = new Set(aes.estimates.flatMap((e) => [e.logical_qubits.source, e.t_gates.source, e.grover_iterations.source]));
    return (
      <div className="real-scale">
        <h4>Published estimates for real AES (not measured by Q-Break)</h4>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Cipher</th>
                <th scope="col">Grover iterations</th>
                <th scope="col">Classical tries</th>
                <th scope="col">Logical qubits</th>
                <th scope="col">T gates</th>
                <th scope="col">T-depth</th>
              </tr>
            </thead>
            <tbody>
              {aes.estimates.map((e) => (
                <tr key={e.cipher}>
                  <th scope="row">{e.cipher}</th>
                  <td className="mono">{e.grover_iterations.text}</td>
                  <td className="mono">{e.classical_tries.text}</td>
                  <td className="mono">{e.logical_qubits.value?.toLocaleString() ?? "—"}</td>
                  <td className="mono">{e.t_gates.text}</td>
                  <td className="mono">{e.t_depth.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small">{aes.takeaway}</p>
        <ul className="citations small muted">
          {Object.entries(aes.citations)
            .filter(([k]) => used.has(k))
            .map(([k, v]) => (
              <li key={k}>
                <span className="mono">[{k}]</span> {v}
              </li>
            ))}
        </ul>
      </div>
    );
  }

  if (kind === "public-key" && rsa?.figures?.length) {
    const used = new Set(rsa.figures.map((f) => f.citation));
    return (
      <div className="real-scale">
        <h4>Published estimates for RSA-{rsa.modulus_bits} (not measured by Q-Break)</h4>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Figure</th>
                <th scope="col">Value</th>
                <th scope="col">Basis</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {rsa.figures.map((f) => (
                <tr key={f.name}>
                  <th scope="row">{f.name}</th>
                  <td className="mono">
                    {fmtBig(f.value)} <span className="muted">{f.unit}</span>
                  </td>
                  <td>{f.kind === "published" ? "quoted from the paper" : `paper's formula${f.formula ? `: ${f.formula}` : ""}`}</td>
                  <td className="mono">[{f.citation}]</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small">{rsa.honesty_note}</p>
        <ul className="citations small muted">
          {Object.entries(rsa.citations)
            .filter(([k]) => used.has(k))
            .map(([k, c]) => (
              <li key={k}>
                <span className="mono">[{k}]</span> {c.authors}, “{c.title}”, {c.venue}.
              </li>
            ))}
        </ul>
      </div>
    );
  }

  return null;
}
