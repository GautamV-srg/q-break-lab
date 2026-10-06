import { useState } from "react";
import type { QkdSummary } from "../../api/types";
import { glyph } from "./Bb84Visual";
import { CopyButton, KeyNumbers } from "./bits";

const SECTIONS = ["The bases", "Wrong basis", "Why Eve shows up", "Sifting to a key", "Example circuit", "ML-KEM & AES-256"] as const;

interface ExampleCircuit {
  title: string;
  drawing: string | null;
  qasm: string | null;
}

/** The example circuit from the BB84 evidence object, whichever shape the engine sends. */
function exampleCircuit(ev: Record<string, unknown> | undefined): ExampleCircuit | null {
  if (!ev) return null;
  const pick = (o: unknown): ExampleCircuit | null => {
    if (!o || typeof o !== "object") return null;
    const r = o as Record<string, unknown>;
    const drawings = Array.isArray(r.drawings) ? (r.drawings as { title?: string; text?: string }[]) : [];
    const drawing = (typeof r.drawing === "string" && r.drawing) || (typeof r.text === "string" && r.text) || drawings[0]?.text || null;
    const qasm = typeof r.qasm === "string" ? r.qasm : null;
    if (!drawing && !qasm) return null;
    return { title: (typeof r.title === "string" && r.title) || drawings[0]?.title || "Example circuit", drawing, qasm };
  };
  return pick(ev.example_circuit) ?? pick(ev.circuit) ?? pick(ev);
}

/** "BB84 under the hood": the Pop the Hood section for the defence flow. */
export default function DefenceHood({ evidence, qkd }: { evidence?: Record<string, unknown>; qkd: QkdSummary }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(0);
  const circuit = exampleCircuit(evidence);
  const p = qkd.photon_preview.find((r) => r.kept) ?? qkd.photon_preview[0];
  const wrong = qkd.photon_preview.find((r) => !r.kept);

  return (
    <section className="hood hood-def">
      <button className="btn hood-toggle" aria-expanded={open} aria-controls="def-hood-panel" onClick={() => setOpen((o) => !o)}>
        {open ? "Close the hood" : "Pop the Hood: BB84 under the hood 🔧"}
        <span className="hood-toggle-sub">{open ? "" : "Bases, Eve's 25%, sifting, privacy amplification, the circuit, and notes on ML-KEM and AES-256"}</span>
      </button>
      {open && (
        <div id="def-hood-panel" className="hood-panel">
          <div className="tabs hood-tabs" role="tablist" aria-label="BB84 under the hood">
            {SECTIONS.map((s, i) => (
              <button
                key={s}
                role="tab"
                id={`def-hood-tab-${i}`}
                aria-selected={i === tab}
                aria-controls="def-hood-tabpanel"
                className={i === tab ? "tab tab-active" : "tab"}
                onClick={() => setTab(i)}
              >
                <span className="tab-n">{i + 1}</span> {s}
              </button>
            ))}
          </div>
          <div id="def-hood-tabpanel" role="tabpanel" aria-labelledby={`def-hood-tab-${tab}`} className="hood-body">
            {tab === 0 && (
              <>
                <p className="lead">Alice encodes each bit in one of two bases, chosen at random per photon.</p>
                <div className="basis-grid">
                  <div className="basis-card">
                    <h4>Z basis (rectilinear)</h4>
                    <p className="basis-glyphs mono">
                      0 = {glyph("Z", 0)} &nbsp; 1 = {glyph("Z", 1)}
                    </p>
                    <p className="small">
                      Circuit: start in |0⟩, apply <span className="mono">X</span> for a 1.
                    </p>
                  </div>
                  <div className="basis-card">
                    <h4>X basis (diagonal)</h4>
                    <p className="basis-glyphs mono">
                      0 = {glyph("X", 0)} &nbsp; 1 = {glyph("X", 1)}
                    </p>
                    <p className="small">
                      Circuit: as for Z, then <span className="mono">H</span> rotates into |+⟩ or |−⟩.
                    </p>
                  </div>
                </div>
                <p>
                  Bob also picks a basis at random. Measuring in the same basis Alice used reads her bit exactly
                  {p && (
                    <>
                      {" "}
                      (photon {qkd.photon_preview.indexOf(p)} in this run: Alice sent {p.alice_bit} in {p.alice_basis}, Bob measured {p.bob_bit} in{" "}
                      {p.bob_basis})
                    </>
                  )}
                  .
                </p>
              </>
            )}
            {tab === 1 && (
              <>
                <p className="lead">Measuring in the wrong basis gives a coin flip, and destroys the original state.</p>
                <p>
                  A diagonal photon measured in the rectilinear basis lands on 0 or 1 with probability ½ each, whatever
                  bit Alice meant. That is why Alice and Bob throw away every position where their bases differ (about
                  half of them){wrong && <> — photon {qkd.photon_preview.indexOf(wrong)} here is one: Alice used {wrong.alice_basis}, Bob {wrong.bob_basis}</>}.
                </p>
                <p>
                  The measurement also collapses the photon into the basis it was measured in. That disturbance is the
                  physical fact BB84's security rests on: no one can read a photon without changing it, in general.
                </p>
              </>
            )}
            {tab === 2 && (
              <>
                <p className="lead">Intercept-resend: why a full-time eavesdropper causes about 25% QBER.</p>
                <ol>
                  <li>Eve does not know Alice's basis, so she guesses: wrong half the time.</li>
                  <li>When she guesses wrong, she re-sends a photon in her basis, not Alice's.</li>
                  <li>On positions Alice and Bob keep (same basis), Bob then reads a random bit: wrong half of those times.</li>
                  <li>
                    So the error rate on kept bits is ½ × ½ = <strong>25%</strong> at full intercept, or about{" "}
                    <span className="mono">fraction / 4</span> when Eve intercepts only some photons.
                  </li>
                </ol>
                <p>
                  The abort threshold here is <strong>{(qkd.qber_threshold * 100).toFixed(0)}%</strong>, the standard bound
                  below which BB84 can still distil a secure key. This run measured{" "}
                  <strong>{(qkd.qber * 100).toFixed(1)}%</strong>.
                </p>
              </>
            )}
            {tab === 3 && (
              <>
                <p className="lead">From {qkd.raw_bits.toLocaleString()} photons to a 256-bit key.</p>
                <ol>
                  <li>
                    <strong>Sifting.</strong> Bob announces his bases (not his results); Alice says which matched. {qkd.sifted_bits.toLocaleString()} positions
                    survive.
                  </li>
                  <li>
                    <strong>Error estimation.</strong> They reveal a random sample of {qkd.sample_bits.toLocaleString()} sifted bits and count disagreements: the QBER.
                    Those bits are now public, so they are discarded.
                  </li>
                  <li>
                    <strong>Information reconciliation.</strong> A simple block-parity / binary-search pass finds and fixes the
                    remaining errors. It leaks a few parity bits, and is disclosed as simplified.
                  </li>
                  <li>
                    <strong>Privacy amplification.</strong> Hashing the reconciled bits with SHA-256 to 256 bits removes what Eve
                    may have learned about individual bits.
                  </li>
                  <li>
                    <strong>Use.</strong> The 256-bit key encrypts the message with AES-256-GCM.
                  </li>
                </ol>
              </>
            )}
            {tab === 4 &&
              (circuit ? (
                <>
                  <p className="lead">{circuit.title}</p>
                  {evidence && <KeyNumbers evidence={evidence} skip={["example_circuit", "circuit"]} />}
                  {circuit.drawing && <pre className="circuit-pre" tabIndex={0} aria-label={circuit.title}>{circuit.drawing}</pre>}
                  {circuit.qasm && (
                    <details className="disclosure" open>
                      <summary>OpenQASM</summary>
                      <pre className="circuit-pre" tabIndex={0} aria-label="OpenQASM">{circuit.qasm}</pre>
                      <CopyButton text={circuit.qasm} label="OpenQASM" />
                    </details>
                  )}
                  {typeof evidence?.note === "string" && <p className="small muted">{evidence.note}</p>}
                </>
              ) : (
                <p className="muted">This engine did not include an example circuit in the BB84 evidence.</p>
              ))}
            {tab === 5 && (
              <>
                <h4>ML-KEM-768</h4>
                <p>
                  ML-KEM is a <strong>key-encapsulation mechanism</strong>: it does not encrypt the message itself. The
                  receiver publishes an encapsulation key; the sender uses it to create a shared secret and a KEM
                  ciphertext; HKDF turns the secret into an AES-256-GCM key that encrypts the message. Its security rests
                  on the Module-LWE lattice problem, for which no efficient quantum algorithm is known (FIPS 203). The
                  implementation here is educational, not a vetted production library.
                </p>
                <h4>AES-256</h4>
                <p>
                  Grover's search needs about √(2<sup>256</sup>) = 2<sup>128</sup> iterations to find a 256-bit key, so a
                  quantum attacker only halves its strength, to about 128 bits, which remains out of reach. AES-256 still
                  needs a way to share the key, which is what ML-KEM or BB84 provide.
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
