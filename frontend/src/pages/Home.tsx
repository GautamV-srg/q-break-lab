import { Link } from "react-router-dom";
import PrototypeNotice from "../components/PrototypeNotice";

export default function Home() {
  return (
    <div className="page home">
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="eyebrow">Quantum red-team engine · working prototype</div>
        <h1 className="hero-title">Can your encrypted messages survive a quantum attacker?</h1>
        <p className="hero-lede">
          Q-Break shows how a quantum attacker would breach your encryption, then protects it with post-quantum and
          quantum methods, and compares them so you can choose the right defence.
        </p>
        <div className="hero-cta">
          <Link to="/test/symmetric" className="btn btn-attack-inline btn-large">
            Run a breach test
          </Link>
          <Link to="/protect" className="btn btn-defend btn-large">
            Protect a message
          </Link>
          <Link to="/about" className="btn btn-ghost btn-large">
            Rules of engagement
          </Link>
        </div>
      </section>

      <div className="wall-rule" aria-hidden="true">
        <span>YOUR ORGANIZATION</span>
        <span className="wall-rule-bricks" />
        <span>QUANTUM ADVERSARY</span>
      </div>

      <section className="test-cards" aria-label="Breach tests">
        <Link to="/test/symmetric" className="test-card card-sym">
          <div className="test-card-kicker">Engagement 01 · Symmetric breach test</div>
          <h2>Shared-key encryption like AES · Grover's algorithm</h2>
          <p>
            Grover's search can find a secret key in about the square root of the guesses a classical attacker needs,
            halving the effective strength of every symmetric key. Three attack modes: known beginning, known substring,
            ciphertext only.
          </p>
          <span className="card-go">Start engagement →</span>
        </Link>
        <Link to="/test/public-key" className="test-card card-pk">
          <div className="test-card-kicker">Engagement 02 · Public-key breach test</div>
          <h2>RSA · Shor's algorithm</h2>
          <p>
            Shor's period finding factors the public modulus and rebuilds the private key, including an iterative
            version that needs a single counting qubit. On large fault-tolerant hardware it breaks RSA at any key size.
          </p>
          <span className="card-go">Start engagement →</span>
        </Link>
        <Link to="/protect" className="test-card card-def">
          <div className="test-card-kicker">Engagement 03 · Protect, re-attack, compare</div>
          <h2>AES-256 · ML-KEM · BB84 QKD</h2>
          <p>
            Re-encrypt a message three ways, send the same quantum adversary after each one, and compare the defences.
            Both breach tests run this as Act II; open it here with a fresh message.
          </p>
          <span className="card-go">Start defending →</span>
        </Link>
      </section>

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title">The Q-Break loop</h2>
        <ol className="how-strip loop-strip">
          <li>
            <span className="how-n">1</span>
            <h3>Attack</h3>
            <p>
              Your organization encrypts a message with a miniature cipher. The quantum adversary intercepts only what an
              eavesdropper would and runs a genuine Grover or Shor circuit: the Breach Report says Breached.
            </p>
          </li>
          <li className="loop-def">
            <span className="how-n">2</span>
            <h3>Protect</h3>
            <p>
              The same message is re-encrypted with AES-256, ML-KEM-768 (the post-quantum standard) and BB84 quantum key
              distribution, simulated in Qiskit.
            </p>
          </li>
          <li className="loop-def">
            <span className="how-n">3</span>
            <h3>Re-attack</h3>
            <p>
              The same adversary attacks each protected version: AES-256 is infeasible, ML-KEM has no known quantum attack,
              and BB84 detects the eavesdropper.
            </p>
          </li>
          <li className="loop-def">
            <span className="how-n">4</span>
            <h3>Compare</h3>
            <p>A side-by-side comparison, measured overhead, and a recommendation you can print as a Defence Report.</p>
          </li>
        </ol>
        <p className="hero-cta">
          <Link to="/test/symmetric" className="btn btn-ghost">
            Symmetric test (Grover) →
          </Link>
          <Link to="/test/public-key" className="btn btn-ghost">
            Public-key test (Shor) →
          </Link>
          <Link to="/protect" className="btn btn-ghost">
            Protect only →
          </Link>
        </p>
      </section>

      <section className="evidence" aria-labelledby="evidence-title">
        <h2 id="evidence-title">Beyond a single test</h2>
        <div className="tiles">
          <Link to="/evaluation" className="tile tile-link">
            <h3>Evaluation</h3>
            <p>Scaling, noise, success rates and quantum-vs-classical query counts across stored experiment runs.</p>
            <span className="card-go">Open the evidence →</span>
          </Link>
          <Link to="/mosca" className="tile tile-link">
            <h3>Mosca risk calculator</h3>
            <p>X + Y &gt; Z: is data you encrypt today still sensitive when a capable quantum computer arrives?</p>
            <span className="card-go">Model your risk →</span>
          </Link>
          <a href="/presentation.html" className="tile tile-link">
            <h3>Presentation deck</h3>
            <p>The Track 5 talk: problem, approach, classical comparison, noise and scaling, limits.</p>
            <span className="card-go">Open the deck →</span>
          </a>
        </div>
      </section>

      <section className="audience" aria-labelledby="who-title">
        <h2 id="who-title">Who it's for</h2>
        <div className="tiles">
          <div className="tile">
            <h3>Enterprises</h3>
            <p>Find where shared-key and RSA encryption protect customer data, contracts and internal traffic.</p>
          </div>
          <div className="tile">
            <h3>Governments</h3>
            <p>Assess communications whose confidentiality must outlast the arrival of large quantum computers.</p>
          </div>
          <div className="tile">
            <h3>Secure-messaging providers</h3>
            <p>Show users, with evidence, how today's message encryption would hold up against a quantum adversary.</p>
          </div>
        </div>
        <p className="hndl">
          <strong>Harvest now, decrypt later:</strong> encrypted data intercepted today can be stored and decrypted
          once the quantum hardware exists.
        </p>
      </section>

      <PrototypeNotice variant="full" />
    </div>
  );
}
