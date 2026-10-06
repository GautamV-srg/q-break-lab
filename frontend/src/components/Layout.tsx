import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { MOCK_MODE } from "../api/client";
import { useConfig } from "../config";

const NAV = [
  { to: "/test/symmetric", label: "Symmetric test" },
  { to: "/test/public-key", label: "Public-key test" },
  { to: "/readiness", label: "Readiness check" },
  { to: "/about", label: "About" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { error, reload, loading } = useConfig();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app">
      <header className="topnav no-print">
        <div className="topnav-inner">
          <Link to="/" className="brand" onClick={() => setMenuOpen(false)}>
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" width="28" height="28">
                <circle cx="15" cy="15" r="9" fill="none" stroke="currentColor" strokeWidth="3" />
                <path d="M21 21l6 6" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </span>
            <span className="brand-text">
              <span className="brand-name">Q-Break</span>
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
              <span className="mock-badge" title="Responses come from bundled fixtures, not the test engine">
                MOCK DATA
              </span>
            )}
          </nav>
        </div>
      </header>

      {error && (
        <div className="engine-banner no-print" role="alert">
          <strong>Test engine unreachable.</strong> {error} Limits shown are defaults.
          <button className="btn btn-small" onClick={reload} disabled={loading}>
            {loading ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}

      <main className="main">{children}</main>

      <footer className="footer no-print">
        <p>
          Q-Break is a prototype quantum breach-testing tool. Genuine Grover and Shor circuits, run on the
          Qiskit Aer simulator, against miniature ciphers. <Link to="/about">What this does and doesn't prove →</Link>
        </p>
      </footer>
    </div>
  );
}
