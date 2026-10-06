import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { MOCK_MODE } from "../api/client";
import { useConfig } from "../config";

const NAV = [
  { to: "/test/symmetric", label: "Symmetric test" },
  { to: "/test/public-key", label: "Public-key test" },
  { to: "/evaluation", label: "Evaluation" },
  { to: "/mosca", label: "Mosca risk" },
  { to: "/readiness", label: "Readiness" },
  { to: "/about", label: "About" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { error, reload, loading } = useConfig();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      {/* Exercise banner: the red-team dressing carries the honesty statement on every page. */}
      <div className="exercise-strip no-print" role="note">
        <span className="exercise-tag">Simulated exercise</span>
        <span>miniature ciphers · classical simulator · does not break real AES or RSA · no speed-advantage claim</span>
      </div>

      <header className="topnav no-print">
        <div className="topnav-inner">
          <Link to="/" className="brand" onClick={() => setMenuOpen(false)}>
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" width="30" height="30">
                <circle cx="16" cy="16" r="10" fill="none" stroke="currentColor" strokeWidth="2.5" />
                <circle cx="16" cy="16" r="3" fill="currentColor" />
                <path d="M16 2v7M16 23v7M2 16h7M23 16h7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            </span>
            <span className="brand-text">
              <span className="brand-name">
                Q-Break <span className="brand-kind">quantum red-team engine</span>
              </span>
              <span className="brand-tagline">Can your encrypted messages survive a quantum attacker?</span>
            </span>
          </Link>
          <button
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="main-nav"
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
          <nav id="main-nav" className={menuOpen ? "nav-links open" : "nav-links"} aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} onClick={() => setMenuOpen(false)}>
                {n.label}
              </NavLink>
            ))}
            {MOCK_MODE && (
              <span className="mock-badge" title="Responses come from recorded fixtures, not the live test engine">
                MOCK DATA
              </span>
            )}
          </nav>
        </div>
      </header>

      {error && (
        <div className="engine-banner no-print" role="alert">
          <span>
            <strong>Test engine unreachable.</strong> {error} Test controls stay locked until its configuration loads.
          </span>
          <button className="btn btn-small" onClick={reload} disabled={loading}>
            {loading ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}

      <main className="main" id="main">
        {children}
      </main>

      <footer className="footer no-print">
        <p>
          Q-Break is a prototype quantum red-team engine for breach testing encrypted communications. Genuine Grover
          and Shor circuits, run on the Qiskit Aer simulator, against miniature ciphers.{" "}
          <Link to="/about">What this does and doesn't prove →</Link> ·{" "}
          <a href="/presentation.html">Presentation deck</a>
        </p>
      </footer>
    </div>
  );
}
