import { useState } from "react";
import { Link } from "react-router-dom";

// Static, rule-based guidance. No API calls, no cryptography.

type Threat = "shor" | "grover-weak" | "grover-ok" | "pq";

interface Algo {
  id: string;
  name: string;
  family: string;
  threat: Threat;
}

const ALGOS: Algo[] = [
  { id: "rsa2048", name: "RSA-2048", family: "Public-key (encryption, signatures)", threat: "shor" },
  { id: "rsa4096", name: "RSA-3072 / RSA-4096", family: "Public-key (encryption, signatures)", threat: "shor" },
  { id: "ecc", name: "ECC P-256 (ECDH / ECDSA)", family: "Elliptic-curve key exchange, signatures", threat: "shor" },
  { id: "aes128", name: "AES-128", family: "Symmetric encryption", threat: "grover-weak" },
  { id: "aes256", name: "AES-256", family: "Symmetric encryption", threat: "grover-ok" },
  { id: "mlkem", name: "ML-KEM (FIPS 203)", family: "Post-quantum key establishment", threat: "pq" },
  { id: "mldsa", name: "ML-DSA (FIPS 204)", family: "Post-quantum signatures", threat: "pq" },
];

const LIFETIMES = [
  { id: "lt1", label: "Less than 1 year", long: false },
  { id: "1to5", label: "1 to 5 years", long: false },
  { id: "5to10", label: "5 to 10 years", long: true },
  { id: "gt10", label: "More than 10 years", long: true },
];

function assess(a: Algo, longLived: boolean) {
  switch (a.threat) {
    case "shor":
      return {
        status: "Vulnerable to Shor",
        level: "high" as const,
        action: longLived
          ? "Migrate first: long-lived data is exposed to harvest-now, decrypt-later. Move to ML-KEM / ML-DSA."
          : "Plan migration to ML-KEM / ML-DSA; inventory where it is used.",
        test: { to: "/test/public-key", label: "See Shor break RSA at miniature scale" },
      };
    case "grover-weak":
      return {
        status: "Weakened by Grover; upgrade",
        level: "medium" as const,
        action: longLived
          ? "Upgrade to AES-256 for data that must stay confidential for years."
          : "Upgrade to AES-256 as part of routine key rotation.",
        test: { to: "/test/symmetric", label: "See Grover recover a key at miniature scale" },
      };
    case "grover-ok":
      return {
        status: "Considered quantum-resistant",
        level: "low" as const,
        action: "Keep. Grover leaves about 128-bit security, which is still considered strong.",
        test: { to: "/test/symmetric", label: "See why Grover only halves key strength" },
      };
    default:
      return {
        status: "Post-quantum",
        level: "low" as const,
        action: "Keep. Designed to resist known quantum attacks; follow NIST guidance and updates.",
        test: { to: "/about", label: "Read about post-quantum standards" },
      };
  }
}

export default function Readiness() {
  const [selected, setSelected] = useState<Set<string>>(new Set(["rsa2048", "aes128"]));
  const [lifetime, setLifetime] = useState("5to10");
  const longLived = LIFETIMES.find((l) => l.id === lifetime)?.long ?? false;
  const rows = ALGOS.filter((a) => selected.has(a.id));

  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  return (
    <div className="page prose-page readiness">
      <div className="eyebrow">Risk framing · General guidance</div>
      <h1>Quantum Readiness Check</h1>
      <p className="lede">
        Pick the algorithms your organization uses and how long its data must stay confidential. You get a
        rule-based risk table, with a link to see each attack happen at miniature scale.
      </p>
      <div className="caution">
        <strong>General guidance, not a certification.</strong> This page runs no tests and no cryptography; it applies
        simple published rules of thumb. A real assessment needs an inventory of your systems.
      </div>

      <div className="readiness-form">
        <fieldset>
          <legend>Algorithms in use</legend>
          <div className="algo-grid">
            {ALGOS.map((a) => (
              <label key={a.id} className={`algo-opt ${selected.has(a.id) ? "algo-on" : ""}`}>
                <input type="checkbox" checked={selected.has(a.id)} onChange={() => toggle(a.id)} />
                <span>
                  <span className="algo-name">{a.name}</span>
                  <span className="small muted">{a.family}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>How long must your data stay confidential?</legend>
          <div className="segmented">
            {LIFETIMES.map((l) => (
              <label key={l.id} className={l.id === lifetime ? "seg seg-on" : "seg"}>
                <input
                  type="radio"
                  name="lifetime"
                  className="sr-only"
                  checked={l.id === lifetime}
                  onChange={() => setLifetime(l.id)}
                />
                {l.label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {rows.length === 0 ? (
        <p className="muted">Select at least one algorithm to see its risk.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table risk-table">
            <thead>
              <tr>
                <th scope="col">Algorithm</th>
                <th scope="col">Quantum status</th>
                <th scope="col">Recommended action</th>
                <th scope="col">See it happen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => {
                const r = assess(a, longLived);
                return (
                  <tr key={a.id}>
                    <td>
                      <strong>{a.name}</strong>
                      <div className="small muted">{a.family}</div>
                    </td>
                    <td>
                      <span className={`risk risk-${r.level}`}>
                        {r.level === "high" ? "▲ " : r.level === "medium" ? "◆ " : "● "}
                        {r.status}
                      </span>
                    </td>
                    <td>{r.action}</td>
                    <td>
                      <Link to={r.test.to}>{r.test.label} →</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {longLived && rows.some((a) => a.threat === "shor") && (
        <p className="hndl">
          <strong>Harvest now, decrypt later:</strong> because your data must stay confidential for years, traffic
          protected by RSA or ECC today could be recorded now and decrypted once large quantum computers exist.
        </p>
      )}
      <p>
        <Link to="/mosca">Put numbers on that timeline with the Mosca risk calculator →</Link>
      </p>
    </div>
  );
}
