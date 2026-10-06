import type { RsaAttackResponse } from "../api/types";

/**
 * Step-by-step Shor derivation, built only from fields of the attack response.
 * Nothing here recomputes cryptography; values are placed into formulas for display.
 */
export default function MathPanel({ resp, e }: { resp: RsaAttackResponse; e: number }) {
  const winning =
    resp.attempts.find((a) => a.ok && a.a === resp.a) ?? resp.attempts.find((a) => a.ok) ?? null;
  const t = resp.n_count;
  const half = resp.period !== null && resp.period % 2 === 0 ? resp.period / 2 : null;

  return (
    <div className="math-panel">
      <ol className="math-steps">
        <li>
          <h4>Measurement → phase → period</h4>
          {winning ? (
            <div className="math-chain mono">
              <span>
                measured <b>{winning.measured}</b>
              </span>
              <span className="arrow">→</span>
              <span>y = {winning.y}</span>
              <span className="arrow">→</span>
              <span>
                phase = y / 2<sup>{t}</sup> = {winning.y}/{2 ** t} = {winning.phase}
              </span>
              <span className="arrow">→</span>
              <span>continued fraction ≈ {winning.fraction}</span>
              <span className="arrow">→</span>
              <span>
                period <b>r = {resp.period ?? winning.r_candidate}</b>
              </span>
            </div>
          ) : (
            <p className="muted">No measurement produced an accepted period this run.</p>
          )}
          <p className="small muted">
            Base a = <span className="mono">{resp.a}</span>, modulus N = <span className="mono">{resp.n}</span>,{" "}
            {t} counting qubits. The period r is the smallest r with a<sup>r</sup> mod N = 1.
          </p>
        </li>

        <li>
          <h4>Period → factors</h4>
          {resp.factors && half !== null ? (
            <div className="math-chain mono">
              <span>
                a<sup>r/2</sup> = {resp.a}
                <sup>{half}</sup>
              </span>
              <span className="arrow">→</span>
              <span>
                gcd({resp.a}
                <sup>{half}</sup> − 1, {resp.n}) and gcd({resp.a}
                <sup>{half}</sup> + 1, {resp.n})
              </span>
              <span className="arrow">→</span>
              <span className="math-result">
                p × q = {resp.factors[0]} × {resp.factors[1]} = {resp.n}
              </span>
            </div>
          ) : (
            <p className="muted">No non-trivial factors were found this run.</p>
          )}
        </li>

        <li>
          <h4>Factors → private key → message</h4>
          {resp.factors && resp.phi !== null && resp.d !== null ? (
            <div className="math-chain mono">
              <span>
                φ = (p−1)(q−1) = ({resp.factors[0]}−1)({resp.factors[1]}−1) = {resp.phi}
              </span>
              <span className="arrow">→</span>
              <span>
                d = e<sup>−1</sup> mod φ = {e}
                <sup>−1</sup> mod {resp.phi} = <b>{resp.d}</b>
              </span>
              <span className="arrow">→</span>
              <span>
                m = c<sup>d</sup> mod N per chunk → “{resp.decrypted_text ?? "(not decodable)"}”
              </span>
            </div>
          ) : (
            <p className="muted">Without the factors, the private exponent cannot be rebuilt.</p>
          )}
        </li>
      </ol>

      <h4>Every measurement the adversary tried</h4>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">a</th>
              <th scope="col">measured</th>
              <th scope="col">y</th>
              <th scope="col">phase</th>
              <th scope="col">fraction</th>
              <th scope="col">r?</th>
              <th scope="col">result</th>
              <th scope="col">reason</th>
            </tr>
          </thead>
          <tbody>
            {resp.attempts.map((a, i) => (
              <tr key={i} className={a.ok ? "row-ok" : "row-rejected"}>
                <td className="mono">{a.a}</td>
                <td className="mono">{a.measured}</td>
                <td className="mono">{a.y}</td>
                <td className="mono">{a.phase}</td>
                <td className="mono">{a.fraction}</td>
                <td className="mono">{a.r_candidate ?? "—"}</td>
                <td>{a.ok ? "✓ accepted" : "✗ rejected"}</td>
                <td className="mono small">{a.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
