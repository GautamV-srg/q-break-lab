import type { PhotonRow, QkdSummary } from "../../api/types";

/** Polarisation glyph for a bit sent in a basis: Z is rectilinear (— |), X is diagonal (/ \). */
export function glyph(basis: string | null, bit: number | null): string {
  if (!basis) return "·";
  if (bit === null) return basis === "Z" ? "+" : "×";
  if (basis === "Z") return bit ? "|" : "—";
  return bit ? "\\" : "/";
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

/**
 * The photon stream: Alice → (Eve) → Bob. Each photon in the preview flies along the channel
 * as its polarisation glyph; a photon Eve measured in the wrong basis arrives disturbed.
 * Under prefers-reduced-motion the photons are laid out statically.
 */
export function PhotonStream({ photons, eve }: { photons: PhotonRow[]; eve: boolean }) {
  const shown = photons.slice(0, 12);
  return (
    <figure className="photon-stream" aria-label={`Photon stream from Alice${eve ? " through Eve" : ""} to Bob`}>
      <div className={`ps-row ${eve ? "ps-with-eve" : ""}`}>
        <div className="ps-node ps-alice">
          <span className="ps-avatar" aria-hidden="true">A</span>
          <span className="ps-name">Alice</span>
          <span className="ps-role small muted">prepares</span>
        </div>
        <div className="ps-track" aria-hidden="true">
          {shown.map((p, i) => (
            <span
              key={i}
              className={`photon ${eve && p.eve_basis ? "photon-to-eve" : ""}`}
              style={{ animationDelay: `${i * 0.28}s` }}
              title={`Alice: bit ${p.alice_bit} in ${p.alice_basis}`}
            >
              {glyph(p.alice_basis, p.alice_bit)}
            </span>
          ))}
        </div>
        {eve && (
          <>
            <div className="ps-node ps-eve">
              <span className="ps-avatar" aria-hidden="true">E</span>
              <span className="ps-name">Eve</span>
              <span className="ps-role small muted">measures, re-sends</span>
            </div>
            <div className="ps-track" aria-hidden="true">
              {shown.map((p, i) => {
                const intercepted = !!p.eve_basis;
                const disturbed = intercepted && p.eve_basis !== p.alice_basis;
                return (
                  <span
                    key={i}
                    className={`photon photon-leg2 ${disturbed ? "photon-disturbed" : ""}`}
                    style={{ animationDelay: `${i * 0.28 + 1.2}s` }}
                  >
                    {intercepted ? glyph(p.eve_basis, disturbed ? null : p.alice_bit) : glyph(p.alice_basis, p.alice_bit)}
                  </span>
                );
              })}
            </div>
          </>
        )}
        <div className="ps-node ps-bob">
          <span className="ps-avatar" aria-hidden="true">B</span>
          <span className="ps-name">Bob</span>
          <span className="ps-role small muted">measures</span>
        </div>
      </div>
      <figcaption className="small muted">
        Glyphs: <span className="mono">— |</span> are bits 0/1 in the Z basis, <span className="mono">/ \</span> are bits
        0/1 in the X basis.{" "}
        {eve && (
          <>
            <span className="mono">+ ×</span> mark a photon Eve measured in the wrong basis and re-sent with a random bit.
          </>
        )}
      </figcaption>
    </figure>
  );
}

export function PhotonTable({ photons, eve }: { photons: PhotonRow[]; eve: boolean }) {
  const rows = photons.slice(0, 16);
  const errors = rows.filter((r) => r.error).length;
  return (
    <div className="photon-table-wrap">
      <table className="data-table stack-table photon-table">
        <caption className="small muted">
          First {rows.length} photons. Kept = Alice and Bob used the same basis.{" "}
          {errors > 0 ? `${errors} kept photon${errors === 1 ? "" : "s"} disagree (marked ✗ error).` : "No kept photon disagrees."}
        </caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Alice bit</th>
            <th scope="col">Alice basis</th>
            {eve && <th scope="col">Eve basis</th>}
            <th scope="col">Bob basis</th>
            <th scope="col">Bob bit</th>
            <th scope="col">Kept</th>
            <th scope="col">Error</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.error ? "row-error" : r.kept ? "row-kept" : "row-dropped"}>
              <td data-label="#" className="mono">{i}</td>
              <td data-label="Alice bit" className="mono">
                {r.alice_bit} <span className="muted">{glyph(r.alice_basis, r.alice_bit)}</span>
              </td>
              <td data-label="Alice basis" className="mono">{r.alice_basis}</td>
              {eve && (
                <td data-label="Eve basis" className="mono">
                  {r.eve_basis ?? <span className="muted">—</span>}
                </td>
              )}
              <td data-label="Bob basis" className="mono">{r.bob_basis}</td>
              <td data-label="Bob bit" className="mono">{r.bob_bit}</td>
              <td data-label="Kept">{r.kept ? "✓ kept" : <span className="muted">– sifted out</span>}</td>
              <td data-label="Error">{r.error ? <strong className="err-text">✗ error</strong> : <span className="muted">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SiftingFunnel({ qkd }: { qkd: QkdSummary }) {
  const steps = [
    { k: "Raw qubits sent", v: qkd.raw_bits, note: "every photon Alice prepared" },
    { k: "Sifted", v: qkd.sifted_bits, note: "bases matched (about half)" },
    { k: "Public sample", v: qkd.sample_bits, note: "sacrificed to estimate the QBER" },
    {
      k: "Final key",
      v: qkd.final_key_bits,
      note: qkd.accepted ? "after reconciliation and privacy amplification" : "discarded: no key",
    },
  ];
  const max = Math.max(1, qkd.raw_bits);
  return (
    <ol className="funnel" aria-label="Sifting funnel">
      {steps.map((s, i) => (
        <li key={s.k} className={`funnel-step ${i === 3 && !qkd.accepted ? "funnel-discarded" : ""}`}>
          <div className="funnel-label">
            <span className="strong">{s.k}</span> <span className="small muted">{s.note}</span>
          </div>
          <div className="funnel-bar-track">
            <div className="funnel-bar" style={{ width: `${Math.max(s.v > 0 ? 1.5 : 0, (s.v / max) * 100)}%` }} />
            <span className="funnel-value mono">
              {i === 3 && !qkd.accepted ? "✗ 0 bits" : `${s.v.toLocaleString()} bits`}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function QberGauge({ qber, threshold }: { qber: number; threshold: number }) {
  const scale = Math.max(0.3, threshold * 2, qber + 0.05);
  const over = qber > threshold;
  return (
    <div className={`qber-gauge ${over ? "qber-over" : "qber-under"}`}>
      <div className="qber-head">
        <span className="strong">QBER (quantum bit error rate)</span>
        <span className="qber-reading mono">
          <span aria-hidden="true">{over ? "✗ " : "✓ "}</span>
          {pct(qber)} {over ? "above" : "within"} the {pct(threshold)} threshold
        </span>
      </div>
      <div
        className="qber-track"
        role="meter"
        aria-label="QBER"
        aria-valuemin={0}
        aria-valuemax={Number((scale * 100).toFixed(1))}
        aria-valuenow={Number((qber * 100).toFixed(1))}
        aria-valuetext={`${pct(qber)}, ${over ? "above" : "within"} the ${pct(threshold)} threshold`}
      >
        <div className="qber-fill" style={{ width: `${Math.min(100, (qber / scale) * 100)}%` }} />
        <div className="qber-threshold" style={{ left: `${(threshold / scale) * 100}%` }}>
          <span className="qber-threshold-label small">threshold {pct(threshold)}</span>
        </div>
        <div className="qber-eve-mark" style={{ left: `${(0.25 / scale) * 100}%` }} aria-hidden="true">
          <span className="small muted">25%: full intercept</span>
        </div>
      </div>
      <div className="qber-scale small muted mono" aria-hidden="true">
        <span>0%</span>
        <span>{pct(scale)}</span>
      </div>
    </div>
  );
}

/** Accept/abort verdict for the key exchange, announced to screen readers. */
export function Bb84Verdict({ qkd }: { qkd: QkdSummary }) {
  const eveDetected = !qkd.accepted && qkd.qber > qkd.qber_threshold;
  return (
    <div aria-live="polite" aria-atomic="true">
      {qkd.accepted ? (
        <div className="verdict verdict-def verdict-def-ok">
          <span className="verdict-icon" aria-hidden="true">✓</span>
          <div>
            <div className="verdict-title">Key accepted</div>
            <div className="verdict-sub">{qkd.reason}</div>
          </div>
        </div>
      ) : (
        <div className="verdict verdict-def verdict-def-abort">
          <span className="verdict-icon" aria-hidden="true">✗</span>
          <div>
            <div className="verdict-title">{eveDetected ? "Key discarded: eavesdropper detected" : "Key discarded"}</div>
            <div className="verdict-sub">{qkd.reason}</div>
            <p className="small no-ct">
              <strong>No ciphertext exists for BB84.</strong> Alice never encrypted the message, so there is nothing on the
              wire for the adversary to attack.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
