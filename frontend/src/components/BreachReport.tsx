import type { ReactNode } from "react";
import type { AesAttackResponse, AttackCondition, RsaAttackResponse, RsaVictimSecret } from "../api/types";
import PrototypeNotice from "./PrototypeNotice";
import QuantumVsClassical from "./QuantumVsClassical";
import RealScaleEstimates from "./RealScaleEstimates";

export type ReportInput =
  | {
      kind: "symmetric";
      resp: AesAttackResponse;
      /** Organization's key from Stage 1, used ONLY for the post-test "matches?" badge. */
      orgKey: string;
      knownPlaintext: string;
      /** Attack-mode label from /api/config, for the engagement summary. */
      conditionLabel?: string;
    }
  | {
      kind: "public-key";
      resp: RsaAttackResponse;
      e: number;
      /** Organization's secret from Stage 1, used ONLY for the post-test "matches?" badge. */
      orgSecret: RsaVictimSecret;
      /** Construction label from /api/config, for the engagement summary. */
      constructionLabel?: string;
    };

interface Props {
  input: ReportInput;
  onRetry: () => void;
  retrying: boolean;
  popTheHood: ReactNode;
  /** Opens Act II with the same message. */
  onProtect?: () => void;
}

export type Verdict = "breached" | "ambiguous" | "safe";

export function verdictOf(input: { kind: "symmetric"; resp: AesAttackResponse } | { kind: "public-key"; resp: RsaAttackResponse }): Verdict {
  if (input.kind === "symmetric") {
    // The engine's own verdict wins; older engines are read from the recovered keys.
    if (input.resp.verdict) return input.resp.verdict === "not_breached" ? "safe" : input.resp.verdict;
    if (input.resp.key !== null) return "breached";
    if (!input.resp.unique && input.resp.recovered_keys.length > 1) return "ambiguous";
    return "safe";
  }
  return input.resp.factors !== null ? "breached" : "safe";
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(0)} ms`;
}

/** Character ranges of `text` the adversary already knew, for the given attack mode. */
function knownRanges(text: string, known: string, condition: AttackCondition | undefined): [number, number][] {
  if (!known || condition === "ciphertext_only") return [];
  if (condition === "known_substring") {
    const out: [number, number][] = [];
    for (let i = text.indexOf(known); i !== -1; i = text.indexOf(known, i + known.length)) out.push([i, i + known.length]);
    return out;
  }
  return text.startsWith(known) ? [[0, known.length]] : [];
}

/** Decrypted text with the part the adversary did NOT know highlighted. */
function Decrypted({ text, known, condition }: { text: string; known: string; condition?: AttackCondition }) {
  const ranges = knownRanges(text, known, condition);
  const parts: { s: string; known: boolean }[] = [];
  let pos = 0;
  for (const [a, b] of ranges) {
    if (a > pos) parts.push({ s: text.slice(pos, a), known: false });
    parts.push({ s: text.slice(a, b), known: true });
    pos = b;
  }
  if (pos < text.length || parts.length === 0) parts.push({ s: text.slice(pos) || " ", known: false });

  return (
    <div className="decrypted">
      <p className="decrypted-text mono" aria-label={`Decrypted message: ${text}`}>
        {parts.map((p, i) =>
          p.known ? (
            <span className="dec-known" key={i} title="Known to the adversary in advance">
              {p.s}
            </span>
          ) : (
            <mark className="dec-recovered" key={i} title="Recovered beyond the known plaintext">
              {p.s}
            </mark>
          ),
        )}
      </p>
      <p className="small muted">
        {ranges.length > 0 ? (
          <>
            <span className="dec-known-swatch">Grey</span>: plaintext the adversary already knew.{" "}
            <mark className="dec-recovered">Highlighted</mark>: recovered beyond the known plaintext.
          </>
        ) : (
          <>
            <mark className="dec-recovered">Highlighted</mark>: everything recovered; the adversary knew none of the
            message in advance.
          </>
        )}
      </p>
    </div>
  );
}

function Stat({ k, v, sub }: { k: string; v: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-k">{k}</div>
      <div className="stat-v mono">{v}</div>
      {sub && <div className="stat-sub small muted">{sub}</div>}
    </div>
  );
}

function ProtectCta({ onProtect, verdict }: { onProtect: () => void; verdict: Verdict }) {
  return (
    <div className="protect-cta no-print">
      <div>
        <strong>{verdict === "breached" ? "Now fight back." : "Fight back anyway."}</strong>{" "}
        <span className="muted">
          Re-encrypt this same message with AES-256, ML-KEM and BB84, then send the same quantum adversary after it.
        </span>
      </div>
      <button type="button" className="btn btn-defend btn-large" onClick={onProtect}>
        Protect this message →
      </button>
    </div>
  );
}

export default function BreachReport({ input, onRetry, retrying, popTheHood, onProtect }: Props) {
  const verdict = verdictOf(input);
  const testName = input.kind === "symmetric" ? "Symmetric breach test (Grover)" : "Public-key breach test (Shor)";
  const now = new Date().toLocaleString();
  const engineVerdict = input.kind === "symmetric" ? input.resp.verdict_text : undefined;

  const engagement: [string, ReactNode][] =
    input.kind === "symmetric"
      ? [
          ["Target", `MiniAES, ${input.resp.key_bits}-bit key`],
          ["Attack mode", input.conditionLabel ?? "Known beginning"],
          ["Shots", input.resp.measurement.shots],
        ]
      : [
          ["Target", `MiniRSA, N = ${input.resp.n}`],
          ["Construction", input.constructionLabel ?? input.resp.construction],
          ["Shots", input.resp.measurement.shots],
        ];
  if (input.resp.noise_p) engagement.push(["Noise", `depolarising p = ${input.resp.noise_p}`]);

  return (
    <article className="report" aria-labelledby="report-title">
      <header className="report-head">
        <div>
          <div className="report-eyebrow">Q-Break · Red-team Breach Report</div>
          <h2 id="report-title">{testName}</h2>
          <div className="small muted">Generated {now} · simulated exercise on a miniature cipher</div>
        </div>
        <div className="report-actions no-print">
          <button className="btn btn-ghost" onClick={() => window.print()}>
            ⎙ Export report
          </button>
        </div>
      </header>

      <dl className="engagement">
        {engagement.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>

      {/* ---------- Verdict ---------- */}
      {verdict === "breached" && (
        <div className="verdict verdict-breached" role="status">
          <span className="verdict-icon" aria-hidden="true">⚠</span>
          <div>
            <div className="verdict-title">BREACHED</div>
            <div className="verdict-sub">
              {input.kind === "symmetric"
                ? "The red team recovered the key and decrypted the intercepted message."
                : "The red team factored the modulus, rebuilt the private key and decrypted the message."}
            </div>
            {engineVerdict && <div className="verdict-engine small">Engine verdict: {engineVerdict}</div>}
          </div>
        </div>
      )}
      {verdict === "ambiguous" && input.kind === "symmetric" && (
        <div className="verdict verdict-ambiguous" role="status">
          <span className="verdict-icon" aria-hidden="true">≈</span>
          <div>
            <div className="verdict-title">AMBIGUOUS: {input.resp.recovered_keys.length} candidate keys</div>
            <div className="verdict-sub">
              {input.resp.condition === "ciphertext_only"
                ? "Several keys decrypt the message to plausible text. With no known plaintext, the red team cannot tell which one is real."
                : "Several keys fit the known plaintext. Compare the decryptions below to see which one reads correctly."}
            </div>
            {engineVerdict && <div className="verdict-engine small">Engine verdict: {engineVerdict}</div>}
          </div>
        </div>
      )}
      {verdict === "safe" && (
        <div className="verdict verdict-safe" role="status">
          <span className="verdict-icon" aria-hidden="true">○</span>
          <div>
            <div className="verdict-title">NOT BREACHED this run</div>
            <div className="verdict-sub">
              Quantum attacks are probabilistic: a single run can miss. This is not evidence of safety; retry with a
              new random seed.
            </div>
            {engineVerdict && <div className="verdict-engine small">Engine verdict: {engineVerdict}</div>}
          </div>
          <button className="btn btn-primary no-print" onClick={onRetry} disabled={retrying}>
            {retrying ? "Running…" : "↻ Retry with a new seed"}
          </button>
        </div>
      )}

      {onProtect && <ProtectCta onProtect={onProtect} verdict={verdict} />}

      {input.resp.warnings.length > 0 && (
        <div className="caution">
          <strong>Notes from the test engine</strong>
          <ul>
            {input.resp.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* ---------- Recovered secret + decrypted message ---------- */}
      {input.kind === "symmetric" && <SymmetricFindings input={input} />}
      {input.kind === "public-key" && <PublicKeyFindings input={input} />}

      {/* ---------- Cost ---------- */}
      <section className="report-section">
        <h3>Attack cost</h3>
        {input.kind === "symmetric" ? (
          <div className="stats-grid">
            <Stat k="Search space" v={`2^${input.resp.key_bits} = ${input.resp.search_space}`} sub="possible keys" />
            {input.resp.counting && (
              <Stat
                k="Estimated matching keys"
                v={input.resp.estimated_matching_keys != null ? `M ≈ ${input.resp.estimated_matching_keys}` : "not estimated"}
                sub={
                  input.resp.counting.ran
                    ? `quantum counting, ${input.resp.counting.counting_qubits ?? "?"}-qubit counting register`
                    : "quantum counting was skipped for this key size (see Pop the Hood)"
                }
              />
            )}
            <Stat
              k="Grover iterations"
              v={input.resp.iterations}
              sub={<span className="mono">{input.resp.optimal_iterations_formula}</span>}
            />
            <Stat k="Qubits" v={input.resp.circuit.num_qubits} sub={`${input.resp.pairs_used.length} known block(s) in the oracle`} />
            <Stat k="Run time" v={fmtMs(input.resp.sim_time_ms)} sub="simulated on a classical computer" />
          </div>
        ) : (
          <div className="stats-grid">
            <Stat
              k="Qubits"
              v={input.resp.circuit.num_qubits}
              sub={`${input.resp.counting_qubits ?? input.resp.n_count} counting + ${input.resp.n_work} work`}
            />
            <Stat
              k="Construction"
              v={<span className="stat-v-text">{input.constructionLabel ?? input.resp.construction}</span>}
              sub={`${input.resp.n_count} bits of phase precision`}
            />
            <Stat k="Period r" v={input.resp.period ?? "—"} sub={`of ${input.resp.a}^x mod ${input.resp.n}`} />
            <Stat
              k="Bases tried"
              v={new Set(input.resp.attempts.map((a) => a.a)).size || 1}
              sub={`a ∈ {${[...new Set(input.resp.attempts.map((a) => a.a))].join(", ") || input.resp.a}}`}
            />
            <Stat k="Run time" v={fmtMs(input.resp.sim_time_ms)} sub="simulated on a classical computer" />
          </div>
        )}
        {input.kind === "public-key" && (
          <p className="small muted disclosure-line">
            {/* The engine's own disclosure text when it sends one; otherwise the same statement in our words. */}
            {input.resp.classical_precomputation_note ?? (
              <>
                <strong>Classical pre-computation is disclosed.</strong>{" "}
                {input.resp.construction === "textbook-swaps"
                  ? "This run used the hand-built textbook swap circuit for N = 15; no permutation was pre-computed."
                  : "The modular-multiplication blocks are permutations computed classically when the circuit is built; the period itself is read from the quantum measurement."}
              </>
            )}
          </p>
        )}
      </section>

      {/* ---------- Quantum vs classical ---------- */}
      {input.kind === "symmetric" ? (
        <QuantumVsClassical kind="symmetric" comparison={input.resp.comparison} />
      ) : (
        <QuantumVsClassical kind="public-key" comparison={input.resp.comparison} constructionLabel={input.constructionLabel} />
      )}

      {/* ---------- Real scale ---------- */}
      <section className="report-section">
        <h3>What this means at real scale</h3>
        {input.kind === "symmetric" ? (
          <p>
            Grover's speed-up is quadratic: searching 2<sup>k</sup> keys takes about √(2<sup>k</sup>) = 2
            <sup>k/2</sup> quantum steps, so a k-bit key offers roughly k/2 bits of security against a quantum
            attacker. AES-128 drops to about 64-bit security; AES-256 drops to about 128-bit, which remains strong.
            This miniature test shows the mechanism on a {input.resp.key_bits}-bit key; real AES keys would need large,
            fault-tolerant quantum hardware that does not exist yet.
          </p>
        ) : (
          <p>
            Shor's algorithm breaks RSA at <strong>any</strong> key size, given a large fault-tolerant quantum
            computer: key length does not save you. The same family of algorithms also breaks elliptic-curve
            cryptography. This miniature test factored N = {input.resp.n}; factoring RSA-2048 would need a very large
            number of error-corrected qubits that no machine has today. Data intercepted now can be stored and
            decrypted later (“harvest now, decrypt later”).
          </p>
        )}
        <RealScaleEstimates kind={input.kind} />
      </section>

      <section className="report-section recommendation">
        <h3>Recommendation</h3>
        {input.kind === "symmetric" ? (
          <p className="reco">Use 256-bit symmetric keys (e.g. AES-256) for data that must stay confidential.</p>
        ) : (
          <ul className="reco">
            <li>Plan migration to post-quantum algorithms (NIST ML-KEM, FIPS 203; ML-DSA, FIPS 204).</li>
            <li>Inventory where RSA and ECC are used across your systems.</li>
            <li>Prioritise data with long confidentiality lifetimes (harvest now, decrypt later).</li>
          </ul>
        )}
      </section>

      <div className="report-notice">
        <PrototypeNotice />
      </div>

      {onProtect && <ProtectCta onProtect={onProtect} verdict={verdict} />}

      <div className="no-print">{popTheHood}</div>
    </article>
  );
}

function SymmetricFindings({ input }: { input: Extract<ReportInput, { kind: "symmetric" }> }) {
  const { resp, orgKey, knownPlaintext } = input;
  // Post-test, browser-side comparison only. The key was never sent to /attack.
  const matches = resp.key !== null && resp.key === orgKey;
  const shown = resp.candidate_decryptions.length;

  return (
    <>
      {resp.key !== null && (
        <section className="report-section">
          <h3>Recovered secret key</h3>
          <div className="secret-row">
            <span className="big-secret mono">{resp.key}</span>
            {matches ? (
              <span className="badge badge-ok">✓ matches organization's key</span>
            ) : (
              <span className="badge badge-warn">✗ does not match organization's key ({orgKey})</span>
            )}
          </div>
        </section>
      )}

      {resp.decrypted_text !== null && (
        <section className="report-section">
          <h3>Decrypted message</h3>
          <Decrypted text={resp.decrypted_text} known={knownPlaintext} condition={resp.condition} />
        </section>
      )}

      {resp.key === null && shown > 1 && (
        <section className="report-section">
          <h3>Candidate keys and their decryptions</h3>
          <div className="candidates">
            {resp.candidate_decryptions.map((c) => (
              <div className="candidate" key={c.key}>
                <div className="mono big-secret small-secret">{c.key}</div>
                <div className="mono candidate-text">{c.text ?? <span className="muted">(not valid text)</span>}</div>
                {c.key === orgKey && <span className="badge badge-ok">✓ organization's key</span>}
              </div>
            ))}
          </div>
          <p className="small muted">
            {resp.recovered_keys.length > shown && `Showing ${shown} of ${resp.recovered_keys.length} candidate keys. `}
            {resp.condition === "ciphertext_only"
              ? "Every candidate decrypts the whole message to plausible text, so the ciphertext alone cannot single one out. Even a short piece of known plaintext usually does."
              : "A longer known plaintext usually pins down a single key. Try adding more known characters in stage 2."}
          </p>
        </section>
      )}
    </>
  );
}

function PublicKeyFindings({ input }: { input: Extract<ReportInput, { kind: "public-key" }> }) {
  const { resp, orgSecret } = input;
  if (!resp.factors) return null;
  // Post-test, browser-side comparison only. p, q, d were never sent to /attack.
  const [f1, f2] = resp.factors;
  const factorsMatch =
    (f1 === orgSecret.p && f2 === orgSecret.q) || (f1 === orgSecret.q && f2 === orgSecret.p);
  const dMatches = resp.d === orgSecret.d;

  return (
    <>
      <section className="report-section">
        <h3>Recovered secret</h3>
        <div className="secret-row">
          <span className="big-secret mono">
            {f1} × {f2} = {resp.n}
          </span>
          {resp.d !== null && (
            <span className="big-secret mono secondary">
              d = {resp.d}
            </span>
          )}
        </div>
        <div className="secret-row">
          {factorsMatch && dMatches ? (
            <span className="badge badge-ok">✓ matches organization's private key</span>
          ) : (
            <span className="badge badge-warn">✗ does not match organization's private key</span>
          )}
        </div>
      </section>
      {resp.decrypted_text !== null && (
        <section className="report-section">
          <h3>Decrypted message</h3>
          <Decrypted text={resp.decrypted_text} known="" />
        </section>
      )}
    </>
  );
}
