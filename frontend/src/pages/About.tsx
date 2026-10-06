import { Link } from "react-router-dom";
import PrototypeNotice from "../components/PrototypeNotice";

export default function About() {
  return (
    <div className="page prose-page">
      <div className="eyebrow">About Q-Break</div>
      <h1>How Q-Break works, and what this prototype does and doesn't prove</h1>

      <PrototypeNotice variant="full" />

      <section>
        <h2>The vision</h2>
        <p>
          Q-Break is a quantum breach-testing tool. Once suitable quantum hardware exists, companies, governments and
          any organization that sends encrypted messages could run Q-Break to answer one question:{" "}
          <em>could a quantum attacker breach our encrypted messages?</em> This hackathon build is the working
          prototype at miniature scale. The “once scaled” story is a vision, not a current capability.
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
            would have: the ciphertext and public parameters (and, for the symmetric test, a short known plaintext such
            as a standard greeting). It never receives the key, or p, q, φ, d.
          </li>
          <li>
            <strong>Breach test.</strong> A genuine quantum circuit runs: <em>Grover's search</em> over all keys, with
            the cipher evaluated reversibly inside its oracle; or <em>Shor's period finding</em>, followed by continued
            fractions and GCDs to recover the factors.
          </li>
          <li>
            <strong>Breach Report.</strong> A verdict, the recovered secret, the decrypted message, the attack's cost,
            and what it means at real scale. <strong>Pop the Hood</strong> shows the circuit, measurements, maths and
            every verification step. Every result is re-checked classically before it is reported.
          </li>
        </ol>
      </section>

      <section>
        <h2>What this prototype does not claim</h2>
        <ul className="honesty">
          <li>
            <strong>Simulator, not quantum hardware.</strong> Circuits are built with Qiskit and executed on the Qiskit
            Aer simulator, on a classical computer. Q-Break does not claim a speed advantage today.
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
            <strong>MiniRSA uses genuine RSA arithmetic with numbers far too small to be secure.</strong> At N = 15, 21
            and 35, the public and private exponents are numerically equal (e = d). These tests demonstrate Shor's
            factor-recovery workflow, not secure RSA examples.
          </li>
          <li>
            <strong>Modular multiplication is built from a classically computed permutation.</strong> The blocks in the
            Shor circuit implement the permutation that multiplication by a performs, computed classically when the
            circuit is built. This is the standard approach in small textbook demonstrations. For N = 15, a hand-built
            swap-gate version (the Qiskit textbook construction) is also shown.
          </li>
          <li>
            <strong>Textbook RSA, no padding.</strong> Text is encoded in 3-bit chunks, so every plaintext value is ≤ 7
            &lt; N. Equal chunks encrypt to equal ciphertexts. That is insecure, deliberately.
          </li>
          <li>
            <strong>Longer text does not mean a bigger circuit.</strong> Grover works only on a few known blocks, and
            classical decryption handles the rest of the message. The Shor circuit depends only on N.
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
          however, is exactly the one this prototype runs on N = 15.
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
            <strong>Harvest now, decrypt later:</strong> data intercepted today can be decrypted once the hardware
            exists, so prioritise data that must stay confidential for many years.
          </li>
        </ul>
        <p>
          <Link to="/readiness">Try the Quantum Readiness Check →</Link>
        </p>
      </section>
    </div>
  );
}
