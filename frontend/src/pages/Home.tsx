import { Link } from "react-router-dom";
import PrototypeNotice from "../components/PrototypeNotice";

export default function Home() {
  return (
    <div className="page home">
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="eyebrow">Quantum breach testing · working prototype</div>
        <h1 className="hero-title">Can your encrypted messages survive a quantum attacker?</h1>
        <p className="hero-lede">
          Q-Break lets organizations test whether their encrypted communications could be breached by a quantum
          attacker. Submit an encrypted message, and Q-Break runs real quantum attack circuits against it, then hands
          you a Breach Report with a verdict, the evidence, and what it means for your real keys.
        </p>
        <div className="hero-cta">
          <Link to="/test/symmetric" className="btn btn-primary btn-large">
            Run a breach test
          </Link>
          <Link to="/about" className="btn btn-ghost btn-large">
            How it works
          </Link>
        </div>
      </section>

      <section className="test-cards" aria-label="Breach tests">
        <Link to="/test/symmetric" className="test-card card-sym">
          <div className="test-card-kicker">Symmetric breach test</div>
          <h2>Shared-key encryption like AES · Grover's algorithm</h2>
          <p>
            Grover's search can find a secret key in about the square root of the guesses a classical attacker needs,
            halving the effective strength of every symmetric key.
          </p>
          <span className="card-go">Start test →</span>
        </Link>
        <Link to="/test/public-key" className="test-card card-pk">
          <div className="test-card-kicker">Public-key breach test</div>
          <h2>RSA · Shor's algorithm</h2>
          <p>
            Shor's period finding factors the public modulus and rebuilds the private key. On large fault-tolerant
            hardware it breaks RSA at any key size.
          </p>
          <span className="card-go">Start test →</span>
        </Link>
      </section>

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title">How a Q-Break test works</h2>
        <ol className="how-strip">
          <li>
            <span className="how-n">1</span>
            <h3>Configure</h3>
            <p>Your organization encrypts a message with its own key.</p>
          </li>
          <li>
            <span className="how-n">2</span>
            <h3>Intercept</h3>
            <p>The quantum adversary captures only what an eavesdropper would: never your key.</p>
          </li>
          <li>
            <span className="how-n">3</span>
            <h3>Breach test</h3>
            <p>Q-Break runs a genuine Grover or Shor circuit against the intercepted data.</p>
          </li>
          <li>
            <span className="how-n">4</span>
            <h3>Report</h3>
            <p>A verdict, the recovered secret, the evidence, and a recommendation. Then pop the hood.</p>
          </li>
        </ol>
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
