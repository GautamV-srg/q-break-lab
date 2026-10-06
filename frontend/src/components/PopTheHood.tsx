import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ReportInput } from "./BreachReport";
import CircuitViewer from "./CircuitViewer";
import Histogram from "./Histogram";
import MathPanel from "./MathPanel";
import VerificationChecklist from "./VerificationChecklist";

const SECTIONS = ["The idea", "The circuit", "The measurements", "The maths", "Verification", "Scale & honesty"] as const;

const GROVER_NOTES: Record<string, string> = {
  Full: "Hadamards put the key register into an equal superposition of every key; then Oracle and Diffuser alternate once per Grover iteration; finally the key register is measured.",
  iteration: "One Grover iteration = Oracle (mark the right key) followed by Diffuser (amplify the marked key).",
  Oracle:
    "The Oracle runs MiniAES reversibly on the known plaintext block for every key in superposition, compares the result with the intercepted ciphertext, flips the sign of matching keys, then un-computes so only that sign remains.",
  Diffuser:
    "The Diffuser reflects every amplitude about the average. Because the matching key has a flipped sign, it grows while all others shrink.",
};

const SHOR_NOTES: Record<string, string> = {
  Full: "Hadamards spread the counting register over all exponents x; the controlled U^(2^j) blocks write a^x mod N into the work register; the inverse QFT turns the repeating pattern into sharp peaks; the counting register is measured.",
  "U^(2^": "Each controlled U^(2^j) block multiplies the work register by a^(2^j) mod N when its counting qubit is 1. Together they compute a^x mod N for every x at once.",
  "Inverse QFT":
    "The inverse quantum Fourier transform converts the periodic pattern of a^x mod N into peaks at multiples of 2^t / r, where r is the period.",
  IQFT: "The inverse quantum Fourier transform converts the periodic pattern of a^x mod N into peaks at multiples of 2^t / r, where r is the period.",
};

export default function PopTheHood({ input, pulse }: { input: ReportInput; pulse: boolean }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [open]);

  return (
    <section className="hood">
      <button
        className={`btn hood-toggle ${pulse && !open ? "pulse" : ""}`}
        aria-expanded={open}
        aria-controls="hood-panel"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "Close the hood" : "Pop the Hood 🔧"}
        <span className="hood-toggle-sub">
          {open ? "" : "See the circuit, the measurements, the maths and every verification step"}
        </span>
      </button>

      {open && (
        <div id="hood-panel" className="hood-panel" ref={panelRef}>
          <div className="tabs hood-tabs" role="tablist" aria-label="Pop the Hood sections">
            {SECTIONS.map((s, i) => (
              <button
                key={s}
                role="tab"
                id={`hood-tab-${i}`}
                aria-selected={i === tab}
                aria-controls="hood-tabpanel"
                className={i === tab ? "tab tab-active" : "tab"}
                onClick={() => setTab(i)}
              >
                <span className="tab-n">{i + 1}</span> {s}
              </button>
            ))}
          </div>
          <div id="hood-tabpanel" role="tabpanel" aria-labelledby={`hood-tab-${tab}`} className="hood-body">
            {input.kind === "symmetric" ? <GroverSection input={input} tab={tab} /> : <ShorSection input={input} tab={tab} />}
          </div>
        </div>
      )}
    </section>
  );
}

function Lead({ children }: { children: ReactNode }) {
  return <p className="lead">{children}</p>;
}

function GroverSection({ input, tab }: { input: Extract<ReportInput, { kind: "symmetric" }>; tab: number }) {
  const r = input.resp;
  const N = r.search_space;
  const keyBits = r.key_bits;
  const highlight = r.recovered_keys;
  const uniform = 1 / N;
  const target = r.key ?? r.recovered_keys[0] ?? null;
  const targetTop = target ? r.measurement.top.find((t) => t.bitstring === target) : undefined;
  const M = Math.max(1, r.recovered_keys.length);
  // Textbook success probability after j iterations: sin²((2j+1)θ), sin θ = √(M/N).
  const theta = Math.asin(Math.sqrt(M / N));
  const theory = Math.sin((2 * r.iterations + 1) * theta) ** 2;

  switch (tab) {
    case 0:
      return (
        <>
          <Lead>
            Instead of trying keys one by one, the quantum adversary holds <em>all {N} keys at once</em> in
            superposition. An <strong>oracle</strong> runs the cipher on every key simultaneously and flips the sign of
            any key that turns the known plaintext into the intercepted ciphertext. A <strong>diffuser</strong> then
            converts that invisible sign flip into a higher probability. Repeating this about √{N} times makes the
            right key the most likely measurement, instead of needing about {N / 2} classical guesses on average.
          </Lead>
          <ol className="idea-flow">
            <li>
              <b>Superposition</b> over all 2<sup>{keyBits}</sup> = {N} keys
            </li>
            <li>
              <b>Oracle</b>: encrypt the known block under every key, flip the sign where it matches
            </li>
            <li>
              <b>Diffusion</b>: reflect about the average, so marked keys gain probability
            </li>
            <li>
              Repeat <b>{r.iterations}×</b>, then <b>measure</b> the key register
            </li>
          </ol>
        </>
      );
    case 1:
      return (
        <>
          <Lead>
            This is the actual circuit the simulator ran. The key register starts in superposition; each boxed Oracle
            and Diffuser is one half of a Grover iteration. The registers below list what every group of qubits does.
            The transpiled depth is much larger because the boxes are expanded into elementary gates.
          </Lead>
          <CircuitViewer circuit={r.circuit} blockNotes={GROVER_NOTES} filename={`qbreak-grover-${keyBits}bit.qasm`} />
        </>
      );
    case 2:
      return (
        <>
          <Lead>
            The circuit was run {r.measurement.shots} times and the key register measured each time. If the adversary
            were guessing, every key would appear about {(uniform * 100).toFixed(1)}% of the time (dashed line). The
            tall bar is the key that Grover amplified: the one that fits the known plaintext.
          </Lead>
          <Histogram measurement={r.measurement} highlight={highlight} uniform={uniform} highlightLabel="recovered key" />
        </>
      );
    case 3:
      return (
        <>
          <Lead>
            Grover's algorithm needs about π/4 · √(N/M) iterations to find one of M marked items among N. Too few or too
            many iterations both lower the success probability, so the iteration count is chosen from the formula.
          </Lead>
          <div className="math-chain mono">
            <span>N = 2^{keyBits} = {N}</span>
            <span className="arrow">→</span>
            <span>iterations: {r.optimal_iterations_formula}</span>
          </div>
          <div className="stats-grid">
            <div className="stat">
              <div className="stat-k">Measured probability on the key</div>
              <div className="stat-v mono">{targetTop ? `${(targetTop.probability * 100).toFixed(1)}%` : "—"}</div>
              <div className="stat-sub small muted">{target ? `key ${target}` : "no key found"}</div>
            </div>
            <div className="stat">
              <div className="stat-k">Random guess baseline</div>
              <div className="stat-v mono">{(uniform * 100).toFixed(2)}%</div>
              <div className="stat-sub small muted">1 / 2^{keyBits}</div>
            </div>
            <div className="stat">
              <div className="stat-k">Amplification</div>
              <div className="stat-v mono">{targetTop ? `${(targetTop.probability / uniform).toFixed(1)}×` : "—"}</div>
              <div className="stat-sub small muted">vs uniform</div>
            </div>
            <div className="stat">
              <div className="stat-k">Theory for {r.iterations} iterations</div>
              <div className="stat-v mono">{(theory * 100).toFixed(1)}%</div>
              <div className="stat-sub small muted">sin²((2j+1)θ), sin θ = √({M}/{N})</div>
            </div>
          </div>
          <h4>Known blocks used inside the oracle</h4>
          <ul className="pair-list mono">
            {r.pairs_used.map((p, i) => (
              <li key={i}>
                P = 0x{p.plain.toString(16)} ({p.plain.toString(2).padStart(4, "0")}) → C = 0x{p.cipher.toString(16)} (
                {p.cipher.toString(2).padStart(4, "0")})
              </li>
            ))}
          </ul>
          {r.attempts.length > 1 && (
            <>
              <h4>Attempts</h4>
              <ul className="pair-list mono">
                {r.attempts.map((a, i) => (
                  <li key={i}>
                    {a.iterations} iteration(s) → verified: {a.verified_keys.length ? a.verified_keys.join(", ") : "none"}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      );
    case 4:
      return (
        <>
          <Lead>
            A quantum measurement is only a candidate. Before anything is reported, the recovered key is re-checked on a
            classical computer: it must re-encrypt every known block to the intercepted ciphertext, and the decrypted
            message must make sense.
          </Lead>
          <p className="strong">Every result is re-checked classically before it is reported.</p>
          <VerificationChecklist steps={r.verification} />
        </>
      );
    default:
      return (
        <>
          <Lead>
            This test searched a {keyBits}-bit key using {r.circuit.num_qubits} simulated qubits. Real AES uses 128- or
            256-bit keys: Grover would need on the order of 2<sup>64</sup> or 2<sup>128</sup> sequential iterations,
            each running the full cipher reversibly on fault-tolerant hardware. The mechanism is identical; the scale is
            not.
          </Lead>
          <ul className="honesty">
            <li>
              <b>MiniAES is an AES-inspired toy cipher</b>, not a reduced version of the AES standard: a 4-bit block,
              one round, and independent (ECB-style) blocks, all insecure on purpose.
            </li>
            <li>
              <b>Simulator only.</b> The circuit is genuine Qiskit, executed on the Qiskit Aer simulator running on a
              classical computer. No speed advantage is claimed today.
            </li>
            <li>
              <b>Known plaintext.</b> The adversary relied on a guessed prefix of the message. Only a few known blocks go
              into the circuit; the rest of the message is decrypted classically once the key is found.
            </li>
            <li>
              <b>At real scale</b> Grover roughly halves effective key length: AES-128 → about 64-bit security, AES-256 →
              about 128-bit, which is still considered strong.
            </li>
          </ul>
        </>
      );
  }
}

function ShorSection({ input, tab }: { input: Extract<ReportInput, { kind: "public-key" }>; tab: number }) {
  const r = input.resp;
  const accepted = r.attempts.filter((a) => a.ok && a.a === r.a).map((a) => a.measured);

  switch (tab) {
    case 0:
      return (
        <>
          <Lead>
            RSA is safe only as long as nobody can split the public number N into its two secret primes. Shor's insight
            is that factoring reduces to finding a <strong>period</strong>: how often the sequence a, a², a³, … mod N
            repeats. A quantum computer explores every exponent at once, and the inverse quantum Fourier transform turns
            that repetition into sharp, readable peaks. A little classical arithmetic then turns the period into the
            factors, and the factors into the private key.
          </Lead>
          <ol className="idea-flow">
            <li>
              <b>Counting register</b> in superposition over all exponents x
            </li>
            <li>
              <b>Modular exponentiation</b>: compute a<sup>x</sup> mod N for every x at once
            </li>
            <li>
              <b>Inverse QFT</b>: periodicity becomes peaks at multiples of 2<sup>t</sup>/r
            </li>
            <li>
              <b>Continued fractions</b> read r; <b>GCDs</b> give p and q; p and q rebuild d
            </li>
          </ol>
        </>
      );
    case 1:
      return (
        <>
          <Lead>
            This is the period-finding circuit the simulator ran for N = {r.n} with base a = {r.a}: {r.n_count} counting
            qubits and {r.n_work} work qubits. Each controlled U<sup>2^j</sup> block multiplies by a power of a; the IQFT
            block reads out the period.{" "}
            {r.construction === "textbook-swaps"
              ? "For N = 15 the multiplication blocks are the hand-built swap-gate construction from the Qiskit textbook."
              : "The multiplication blocks are built from the permutation that multiplication by a performs, computed classically when the circuit is built (standard for small demonstrations)."}
          </Lead>
          <CircuitViewer circuit={r.circuit} blockNotes={SHOR_NOTES} filename={`qbreak-shor-N${r.n}.qasm`} />
        </>
      );
    case 2:
      return (
        <>
          <Lead>
            Each bar is a reading of the counting register over {r.measurement.shots} runs. The readings cluster on
            multiples of 2<sup>{r.n_count}</sup>/r: with period r = {r.period ?? "?"}, that is {r.period ?? "a few"}{" "}
            evenly spaced peaks. Highlighted bars are the readings that led to an accepted period.
          </Lead>
          <Histogram measurement={r.measurement} highlight={accepted} highlightLabel="accepted peaks" />
        </>
      );
    case 3:
      return (
        <>
          <Lead>
            The measurement is a fraction of 2<sup>{r.n_count}</sup>. Continued fractions find the simplest fraction
            s/r close to it, which reveals the period r. If r is even, a<sup>r/2</sup> ± 1 shares a factor with N, and a
            greatest-common-divisor computation pulls the primes out. Every value below comes straight from the test.
          </Lead>
          <MathPanel resp={r} e={input.e} />
        </>
      );
    case 4:
      return (
        <>
          <Lead>
            A quantum measurement can mislead: some peaks give a wrong or partial period. So every candidate is
            re-checked classically: the period must satisfy a<sup>r</sup> mod N = 1, the factors must multiply back to N,
            and the rebuilt private key must decrypt the message correctly.
          </Lead>
          <p className="strong">Every result is re-checked classically before it is reported.</p>
          <VerificationChecklist steps={r.verification} />
        </>
      );
    default:
      return (
        <>
          <Lead>
            This test factored N = {r.n} using {r.circuit.num_qubits} simulated qubits. A real RSA-2048 modulus has 617
            decimal digits; factoring it with Shor's algorithm would need a very large number of error-corrected qubits,
            far beyond any machine that exists today. The workflow shown here is exactly the one that would be used.
          </Lead>
          <ul className="honesty">
            <li>
              <b>Real RSA arithmetic, tiny numbers.</b> At N = 15, 21 and 35 the public and private exponents are equal
              (e = d). This demonstrates the factor-recovery workflow, not a secure RSA example.
            </li>
            <li>
              <b>Classically computed permutation blocks.</b> The modular-multiplication blocks are built from the
              permutation that multiplication by a performs, computed classically when the circuit is built. This is the
              standard approach for small textbook demonstrations. For N = 15 a hand-built swap-gate version is used.
            </li>
            <li>
              <b>Textbook RSA, no padding.</b> Text is split into 3-bit chunks (each ≤ 7 &lt; N), so equal chunks encrypt
              to equal ciphertexts. That is insecure on purpose.
            </li>
            <li>
              <b>Simulator only.</b> Genuine Qiskit circuits, executed on the Qiskit Aer simulator on a classical
              computer. No speed advantage is claimed today.
            </li>
            <li>
              <b>At real scale</b> Shor breaks RSA and elliptic-curve cryptography at any key size, given enough
              fault-tolerant qubits.
            </li>
          </ul>
        </>
      );
  }
}
