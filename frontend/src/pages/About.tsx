import { Link } from "react-router-dom";
import PrototypeNotice from "../components/PrototypeNotice";

export default function About() {
  return (
    <div className="page prose-page">
      <div className="eyebrow">Rules of engagement · About Q-Break</div>
      <h1>How Q-Break works, and what this prototype does and doesn't prove</h1>

      <PrototypeNotice variant="full" />

      <section>
        <h2>The vision</h2>
        <p>
          Q-Break is a quantum red-team engine for breach testing encrypted communications. A red team attacks a
          system the way a real adversary would, so its owners learn where it fails before someone else finds out.
          Once suitable quantum hardware exists, companies, governments and any organization that sends encrypted
          messages could run Q-Break to answer one question:{" "}
          <em>could a quantum attacker breach our encrypted messages?</em> This hackathon build is the working
          prototype at miniature scale. The “once scaled” story is a vision, not a current capability.
        </p>
        <p className="lede">
          Q-Break shows how a quantum attacker would breach your encryption, then protects it with post-quantum and
          quantum methods, and compares them so you can choose the right defence.
        </p>
      </section>

      <section>
        <h2>How a test works</h2>
        <ol>
          <li>
            <strong>Configure.</strong> Your organization encrypts a message: with a shared secret key (symmetric test)
            or with its RSA public key (public-key test).
          </li>
          <li>
            <strong>Intercept.</strong> Q-Break plays the quantum adversary. It receives only what a real eavesdropper
            would have: the ciphertext and public parameters. The symmetric test offers three attack modes: the
            adversary knows how the message begins, knows a piece of text that appears somewhere in it, or knows
            nothing but the ciphertext. It never receives the key, or p, q, φ, d.
          </li>
          <li>
            <strong>Breach test.</strong> A genuine quantum circuit runs: <em>Grover's search</em> over all keys, with
            the cipher evaluated reversibly inside its oracle; or <em>Shor's period finding</em>, followed by continued
            fractions and GCDs to recover the factors.
          </li>
          <li>
            <strong>Breach Report.</strong> A verdict (Breached, Ambiguous or Not breached), the recovered secret, the
            decrypted message, the attack's cost next to a classical baseline solving the same problem, and what it
            means at real scale. <strong>Pop the Hood</strong> shows the circuit, measurements, maths, every
            verification step, and a noise lab that re-runs the breach under simulated hardware noise. Every result
            is re-checked classically before it is reported.
          </li>
          <li>
            <strong>Protect.</strong> Act II re-encrypts the same message three ways: <em>AES-256</em> (AES-256-GCM),{" "}
            <em>ML-KEM-768</em> (the NIST post-quantum key-encapsulation standard, FIPS 203, then AES-256-GCM) and{" "}
            <em>BB84 quantum key distribution</em>, simulated in Qiskit, whose 256-bit key then drives AES-256-GCM. You can
            put an eavesdropper on the BB84 channel and watch the error rate give her away.
          </li>
          <li>
            <strong>Re-attack.</strong> The same blind adversary receives only the public bundles (ciphertexts, nonces,
            public keys, KEM ciphertexts, announced bases) and tries again. Each verdict says what was actually run:
            AES-256 is <em>infeasible</em> (a cited estimate, no circuit is run), ML-KEM is <em>not applicable</em> (Shor
            finds nothing to factor), and BB84 eavesdropping is <em>detected</em> (a fresh exchange really runs).
          </li>
          <li>
            <strong>Compare.</strong> A side-by-side table, measured overhead and a rule-based recommendation, printable as
            a Defence Report.
          </li>
        </ol>
      </section>

      <section>
        <h2>What this prototype does not claim</h2>
        <ul className="honesty">
          <li>
            <strong>Simulator, not quantum hardware.</strong> Circuits are built with Qiskit and executed on the Qiskit
            Aer simulator, on a classical computer. Q-Break does not claim a speed advantage today: at these sizes
            the simulation is slower than classical brute force, and each report compares query counts, not time.
          </li>
          <li>
            <strong>We never tested your real AES or RSA.</strong> This miniature test shows how such an attack works. At
            real key sizes the same attack would need large, fault-tolerant quantum hardware that does not exist yet.
          </li>
          <li>
            <strong>MiniAES is an AES-inspired toy cipher</strong>, not a reduced version of the real AES standard. It
            uses a 4-bit block, a single round, and independent ECB-style blocks, all insecure on purpose.
          </li>
          <li>
            <strong>MiniRSA uses genuine RSA arithmetic with numbers far too small to be secure.</strong> The moduli
            are products of two distinct odd primes up to 11. At several of them the public and private exponents are
            numerically equal (e = d), which key generation flags. These tests demonstrate Shor's factor-recovery
            workflow, not secure RSA examples.
          </li>
          <li>
            <strong>Modular multiplication is built from a classically computed permutation.</strong> The blocks in the
            Shor circuit implement the permutation that multiplication by a performs, computed classically when the
            circuit is built, and every report that uses them says so. This is the standard approach in small textbook
            demonstrations. For N = 15, a hand-built swap-gate version (the Qiskit textbook construction) is also
            available, and an iterative version reuses a single counting qubit.
          </li>
          <li>
            <strong>Textbook RSA, no padding.</strong> Text is encoded in 3-bit chunks, so every plaintext value is ≤ 7
            &lt; N. Equal chunks encrypt to equal ciphertexts. That is insecure, deliberately.
          </li>
          <li>
            <strong>Longer text does not mean a bigger circuit.</strong> Grover works only on a few known blocks, and
            classical decryption handles the rest of the message. The Shor circuit depends only on N.
          </li>
          <li>
            <strong>Ciphertext-only results are often ambiguous, on purpose.</strong> With a 4-bit block, many keys
            decrypt a message to plausible text. Quantum counting estimates how many, and the report says Ambiguous
            rather than picking one.
          </li>
          <li>
            <strong>Noise breaks even these miniature attacks.</strong> The reported runs use an ideal simulator. Under
            realistic hardware noise the signal sinks into random guessing, which the noise lab and the{" "}
            <Link to="/evaluation">Evaluation page</Link> show with data.
          </li>
        </ul>
        <h3>The defences</h3>
        <ul className="honesty">
          <li>
            <strong>AES-256 and ML-KEM really encrypt your message.</strong> The engine encrypts it, decrypts it again on
            the organization's side and reports whether the round trip matches. Keys and shared secrets never leave the
            server and never reach the re-attack.
          </li>
          <li>
            <strong>BB84 is a faithful simulation, not quantum hardware.</strong> Real QKD needs a photon source and a
            quantum channel (optical fibre or free space). Here every photon is a small Qiskit circuit on the Aer
            simulator, the eavesdropper is modelled as intercept-resend, and reconciliation is a simplified single pass.
          </li>
          <li>
            <strong>The ML-KEM implementation is educational, not production-grade.</strong> It follows FIPS 203, but a
            real system should use a vetted, constant-time library.
          </li>
          <li>
            <strong>“No known quantum attack” is not “proven unbreakable”.</strong> ML-KEM rests on the Module-LWE
            lattice problem, for which no efficient quantum algorithm is known. Nothing in Q-Break claims any defence is
            unbreakable.
          </li>
          <li>
            <strong>AES-256's verdict is an estimate, not a run.</strong> No simulator can hold a Grover search over 2
            <sup>256</sup> keys; the report quotes the cited resource estimate (Grassl et al., 2016) instead.
          </li>
        </ul>
      </section>

      <section>
        <h2>Why real keys are out of reach today</h2>
        <h3>AES-128 and Grover</h3>
        <p>
          Grover's search needs about √(2<sup>k</sup>) iterations for a k-bit key. For AES-128 that is on the order of 2
          <sup>64</sup> iterations, and they must run one after another, each evaluating the full AES cipher reversibly
          on error-corrected qubits. That is why AES-128 is said to drop to about 64-bit security against a quantum
          attacker, and why AES-256 (about 128-bit quantum security) is still considered strong.
        </p>
        <h3>RSA-2048 and Shor</h3>
        <p>
          Shor's algorithm factors any RSA modulus in polynomial time, so key length does not save you. But running it
          on a 2048-bit modulus needs a very large number of error-corrected (logical) qubits, each built from many
          physical qubits, and a very long, error-free computation. No machine is close to that today. The workflow,
          however, is exactly the one this prototype runs on its miniature moduli. Each Breach Report quotes published
          resource estimates, with their sources, next to the miniature result.
        </p>
      </section>

      <section>
        <h2>What to do about it</h2>
        <ul>
          <li>
            Shor breaks RSA and elliptic-curve cryptography at any key size, given enough fault-tolerant qubits. Plan
            migration to NIST post-quantum standards: <strong>ML-KEM (FIPS 203)</strong> for key establishment and{" "}
            <strong>ML-DSA (FIPS 204)</strong> for signatures.
          </li>
          <li>
            Grover roughly halves the effective security of a symmetric key. Use <strong>256-bit symmetric keys</strong>.
          </li>
          <li>
            Quantum key distribution (BB84) detects eavesdroppers through physics, but needs dedicated photon hardware
            and limited distances. <Link to="/protect">Compare all three defences →</Link>
          </li>
          <li>
            <strong>Harvest now, decrypt later:</strong> data intercepted today can be decrypted once the hardware
            exists, so prioritise data that must stay confidential for many years.
          </li>
        </ul>
        <p>
          <Link to="/mosca">Model your timeline with the Mosca risk calculator →</Link> ·{" "}
          <Link to="/readiness">Try the Quantum Readiness Check →</Link> ·{" "}
          <Link to="/evaluation">See the evaluation evidence →</Link>
        </p>
      </section>
    </div>
  );
}
