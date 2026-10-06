import { useEffect, useRef, useState } from "react";
import { errorMessage, rsaAttack, rsaEncrypt, rsaKeygen } from "../api/client";
import { buildRsaAttackRequest, type InterceptedRsa } from "../api/payloads";
import type { RsaAttackResponse, RsaEncryptResponse, RsaKeygenResponse } from "../api/types";
import BreachReport from "../components/BreachReport";
import ChunkTable from "../components/ChunkTable";
import Duo from "../components/Duo";
import ErrorBox from "../components/ErrorBox";
import InterceptionWall from "../components/InterceptionWall";
import PopTheHood from "../components/PopTheHood";
import PrototypeNotice from "../components/PrototypeNotice";
import RunProgress from "../components/RunProgress";
import ShotsSlider from "../components/ShotsSlider";
import StageCard from "../components/StageCard";
import Stepper from "../components/Stepper";
import { randomSeed, sleep, useAliveRef, useScrollToStage } from "../components/flow";
import { useConfig } from "../config";

const ID = "pk";
const STEPS = [
  { label: "Configure", side: "Your organization" },
  { label: "Intercept", side: "The wall" },
  { label: "Breach test", side: "Quantum adversary" },
  { label: "Report", side: "Breach Report" },
];

export default function PublicKeyTest() {
  const { config } = useConfig();
  const alive = useAliveRef();

  // ---- Organization (victim) state. Never read when building the attack request. ----
  const [n, setN] = useState(config.rsa_moduli[0] ?? 15);
  const [keys, setKeys] = useState<RsaKeygenResponse | null>(null);
  const [reveal, setReveal] = useState(false);
  const [keygenBusy, setKeygenBusy] = useState(false);
  const [keygenError, setKeygenError] = useState<string | null>(null);
  const [message, setMessage] = useState("Hi judges!");
  const [enc, setEnc] = useState<RsaEncryptResponse | null>(null);
  const [encMessage, setEncMessage] = useState("");
  const [encrypting, setEncrypting] = useState(false);
  const [encError, setEncError] = useState<string | null>(null);

  // ---- Adversary state. Holds only what crossed the wall. ----
  const [intercepted, setIntercepted] = useState<InterceptedRsa | null>(null);
  const [baseA, setBaseA] = useState("");
  const [shots, setShots] = useState(1024);
  const [attack, setAttack] = useState<RsaAttackResponse | null>(null);
  const [attacking, setAttacking] = useState(false);
  const [attackError, setAttackError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const [demoRunning, setDemoRunning] = useState(false);
  const [completedOnce, setCompletedOnce] = useState(false);

  useEffect(() => {
    if (!config.rsa_moduli.includes(n)) setN(config.rsa_moduli[0] ?? 15);
  }, [config.rsa_moduli, n]);

  const stage = attack ? 4 : intercepted ? 3 : enc ? 2 : 1;
  useScrollToStage(ID, stage);

  const busy = keygenBusy || encrypting || attacking || demoRunning;
  const messageValid = message.length > 0 && message.length <= config.max_rsa_text_chars;

  const aTrim = baseA.trim();
  const aNum = aTrim === "" ? null : Number(aTrim);
  const aValid = aNum === null || (Number.isInteger(aNum) && aNum >= 2 && aNum < (intercepted?.n ?? n));

  function resetAfterEncrypt() {
    setIntercepted(null);
    setAttack(null);
    setAttackError(null);
  }

  function resetAfterKeygen() {
    setEnc(null);
    resetAfterEncrypt();
  }

  async function doKeygen(modulus = n): Promise<RsaKeygenResponse | null> {
    setKeygenBusy(true);
    setKeygenError(null);
    try {
      const r = await rsaKeygen({ n: modulus });
      if (!alive.current) return null;
      resetAfterKeygen();
      setKeys(r);
      setReveal(false);
      return r;
    } catch (e) {
      if (alive.current) setKeygenError(errorMessage(e));
      return null;
    } finally {
      if (alive.current) setKeygenBusy(false);
    }
  }

  async function doEncrypt(k: RsaKeygenResponse | null = keys, msg = message): Promise<RsaEncryptResponse | null> {
    if (!k) return null;
    setEncrypting(true);
    setEncError(null);
    try {
      // Encryption uses only the PUBLIC key (n, e).
      const r = await rsaEncrypt({ plaintext: msg, n: k.n, e: k.e });
      if (!alive.current) return null;
      resetAfterEncrypt();
      setEnc(r);
      setEncMessage(msg);
      return r;
    } catch (e) {
      if (alive.current) setEncError(errorMessage(e));
      return null;
    } finally {
      if (alive.current) setEncrypting(false);
    }
  }

  function handOff(k: RsaKeygenResponse | null = keys, r: RsaEncryptResponse | null = enc) {
    if (!k || !r) return;
    // Only public material crosses the wall: n, e, ciphertext, bit_length.
    setIntercepted({ n: k.n, e: k.e, ciphertext: [...r.ciphertext], bit_length: r.bit_length });
    setAttack(null);
    setAttackError(null);
  }

  async function runAttack(target: InterceptedRsa | null = intercepted, a: number | null = aNum, seed: number | null = null) {
    if (!target || inFlight.current) return; // never fire twice
    inFlight.current = true;
    setAttacking(true);
    setAttackError(null);
    try {
      // The request is built ONLY from the adversary's intercepted data (see api/payloads.ts).
      const req = buildRsaAttackRequest(target, { a, shots, seed });
      const r = await rsaAttack(req);
      if (!alive.current) return;
      setAttack(r);
      setCompletedOnce(true);
    } catch (e) {
      if (alive.current) setAttackError(errorMessage(e));
    } finally {
      inFlight.current = false;
      if (alive.current) setAttacking(false);
    }
  }

  async function runDemo() {
    setDemoRunning(true);
    try {
      const modulus = config.rsa_moduli.includes(15) ? 15 : (config.rsa_moduli[0] ?? 15);
      const msg = "Hi judges!";
      setN(modulus);
      setMessage(msg);
      setBaseA("");
      setAttack(null);
      await sleep(600);
      if (!alive.current) return;
      const k = await doKeygen(modulus);
      if (!k || !alive.current) return;
      await sleep(1200);
      if (!alive.current) return;
      const r = await doEncrypt(k, msg);
      if (!r || !alive.current) return;
      await sleep(1800);
      if (!alive.current) return;
      handOff(k, r);
      await sleep(3200); // let the wall animation play
      if (!alive.current) return;
      const a = modulus === 15 ? 7 : null;
      setBaseA(a === null ? "" : String(a));
      await sleep(500);
      if (!alive.current) return;
      await runAttack({ n: k.n, e: k.e, ciphertext: r.ciphertext, bit_length: r.bit_length }, a);
    } finally {
      if (alive.current) setDemoRunning(false);
    }
  }

  return (
    <div className="page test-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">RSA · Shor's algorithm</div>
          <h1>Public-key breach test</h1>
          <p className="lede">
            Your organization publishes an RSA public key and receives encrypted messages. A simulated quantum
            adversary sees only the public key and the ciphertext, and uses Shor's period finding to factor N and
            rebuild the private key.
          </p>
        </div>
        <button className="btn btn-demo no-print" onClick={runDemo} disabled={busy}>
          {demoRunning ? "Demo running…" : "▶ Run demo test"}
        </button>
      </div>

      <PrototypeNotice />
      <Stepper steps={STEPS} active={stage} idPrefix={ID} />

      {/* ---------- Stage 1 ---------- */}
      <Duo
        left={
          <StageCard id={`${ID}-stage-1`} n={1} title="Configure the test" side="org" sideLabel="Your organization" locked={false}>
            <div className="field">
              <span className="field-label" id="pk-n-label">
                RSA modulus N
              </span>
              <div className="segmented" role="radiogroup" aria-labelledby="pk-n-label">
                {config.rsa_moduli.map((m) => (
                  <button
                    type="button"
                    role="radio"
                    aria-checked={m === n}
                    key={m}
                    className={m === n ? "seg seg-on" : "seg"}
                    onClick={() => {
                      setN(m);
                      if (keys && keys.n !== m) {
                        setKeys(null);
                        resetAfterKeygen();
                      }
                    }}
                    disabled={busy}
                  >
                    N = {m}
                  </button>
                ))}
              </div>
            </div>
            <button className="btn btn-primary" onClick={() => void doKeygen()} disabled={busy}>
              {keygenBusy ? "Generating…" : keys ? "↻ Regenerate key pair" : "🔑 Generate key pair"}
            </button>
            <ErrorBox message={keygenError} onRetry={() => void doKeygen()} />

            {keys && (
              <div className="result-block">
                <div className="keypair">
                  <div className="key-public">
                    <div className="ct-label">Public key (shared openly)</div>
                    <div className="mono big-mono">
                      n = {keys.n}, e = {keys.e}
                    </div>
                  </div>
                  <div className="key-private">
                    <div className="ct-label">
                      Organization's private key <span className="lock-tag">🔒 hidden from the adversary</span>
                    </div>
                    {reveal ? (
                      <div className="mono big-mono">
                        p = {keys.victim_secret.p}, q = {keys.victim_secret.q}, φ = {keys.victim_secret.phi}, d ={" "}
                        {keys.victim_secret.d}
                      </div>
                    ) : (
                      <div className="mono big-mono redacted" aria-label="hidden">
                        p = ••, q = ••, φ = ••, d = ••
                      </div>
                    )}
                    <button className="btn btn-ghost btn-small" onClick={() => setReveal((r) => !r)} aria-pressed={reveal}>
                      {reveal ? "Hide" : "Reveal (organization view only)"}
                    </button>
                  </div>
                </div>
                {keys.warnings.length > 0 && (
                  <div className="caution">
                    <strong>Caution</strong>
                    <ul>
                      {keys.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (messageValid && !busy) void doEncrypt();
                  }}
                >
                  <div className="field">
                    <label htmlFor="pk-msg" className="field-label">
                      Message encrypted with the public key
                    </label>
                    <input
                      id="pk-msg"
                      className="input"
                      value={message}
                      maxLength={config.max_rsa_text_chars}
                      onChange={(e) => {
                        setMessage(e.target.value);
                        if (enc) {
                          setEnc(null);
                          resetAfterEncrypt();
                        }
                      }}
                      disabled={busy}
                    />
                    <div className="field-hint">
                      {message.length}/{config.max_rsa_text_chars} characters
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={!messageValid || busy}>
                    {encrypting ? "Encrypting…" : "🔐 Encrypt with public key"}
                  </button>
                </form>
                <ErrorBox message={encError} onRetry={() => void doEncrypt()} />
                {enc && <ChunkTable message={encMessage} enc={enc} n={keys.n} e={keys.e} />}
              </div>
            )}
          </StageCard>
        }
        right={
          <div className="adv-listen">
            <span className="side-tag side-tag-adv">Quantum adversary (simulated)</span>
            {keys ? (
              <p>
                🌐 The public key <span className="mono">(n = {keys.n}, e = {keys.e})</span> is published. Anyone,
                including the adversary, can read it.
              </p>
            ) : (
              <p className="muted">📡 Listening on the channel. No public key published yet.</p>
            )}
            {enc && (
              <p>
                📡 Ciphertext on the wire: <span className="mono">[{enc.ciphertext.slice(0, 8).join(", ")}…]</span>
              </p>
            )}
          </div>
        }
      />

      {/* ---------- Stage 2 ---------- */}
      <StageCard
        id={`${ID}-stage-2`}
        n={2}
        title="Interception: what crosses the wall"
        side="wall"
        sideLabel="The interception wall"
        locked={!enc || !keys}
        lockedHint="Generate a key pair and encrypt a message first."
      >
        {enc && keys && (
          <InterceptionWall
            key={enc.ciphertext.join(",") + keys.n}
            secrets={["p", "q", "φ", "d"]}
            captured={[
              { label: "Modulus n", value: <span className="mono">{keys.n}</span> },
              { label: "Public exponent e", value: <span className="mono">{keys.e}</span> },
              { label: "Ciphertext", value: <span className="mono">[{enc.ciphertext.join(", ")}]</span> },
              { label: "bit_length", value: <span className="mono">{enc.bit_length}</span> },
            ]}
          >
            {!intercepted && (
              <button className="btn btn-primary" onClick={() => handOff()} disabled={busy}>
                Hand intercept to the adversary →
              </button>
            )}
            {intercepted && <p className="ok-line">✓ Intercept handed to the quantum adversary.</p>}
          </InterceptionWall>
        )}
      </StageCard>

      {/* ---------- Stage 3 ---------- */}
      <Duo
        left={
          <div className="org-hold">
            <span className="side-tag side-tag-org">Your organization</span>
            <p>
              <span aria-hidden="true">🔒</span> p, q, φ and d never leave this side. The adversary's request contains
              only n, e, the ciphertext and its bit length.
            </p>
          </div>
        }
        right={
          <StageCard
            id={`${ID}-stage-3`}
            n={3}
            title="Run the breach test"
            side="adv"
            sideLabel="Quantum adversary (simulated)"
            locked={!intercepted}
            lockedHint="Hand the intercept to the adversary first."
          >
            <div className="field">
              <label htmlFor="pk-a" className="field-label">
                Base a (optional)
              </label>
              <input
                id="pk-a"
                className={`input mono input-short ${aValid ? "" : "input-invalid"}`}
                inputMode="numeric"
                placeholder="random"
                value={baseA}
                onChange={(e) => setBaseA(e.target.value.replace(/[^0-9]/g, ""))}
                disabled={busy}
                aria-invalid={!aValid}
              />
              <div className={`field-hint ${aValid ? "" : "field-error"}`}>
                {aValid
                  ? "Leave empty for random. Shor picks a base a and finds the period of aˣ mod N."
                  : `a must be a whole number from 2 to ${(intercepted?.n ?? n) - 1}.`}
              </div>
            </div>
            <ShotsSlider value={shots} max={config.max_shots} onChange={setShots} disabled={busy} />
            <button className="btn btn-attack" onClick={() => void runAttack()} disabled={busy || !intercepted || !aValid}>
              {attacking ? "Breach test running…" : "⚛ Run quantum breach test"}
            </button>
            {attacking && (
              <RunProgress
                stages={["Building period-finding circuit", "Simulating", "Inverse QFT", "Reading period"]}
              />
            )}
            <ErrorBox message={attackError} onRetry={busy ? undefined : () => void runAttack()} />
          </StageCard>
        }
      />

      {/* ---------- Stage 4 ---------- */}
      <StageCard
        id={`${ID}-stage-4`}
        n={4}
        title="Breach Report"
        side="report"
        sideLabel="Result"
        locked={!attack || !keys}
        lockedHint="Run the breach test to produce a report."
        className="stage-report"
      >
        {attack && keys && intercepted && (
          <BreachReport
            input={{ kind: "public-key", resp: attack, e: intercepted.e, orgSecret: keys.victim_secret }}
            onRetry={() => void runAttack(intercepted, null, randomSeed())}
            retrying={attacking}
            popTheHood={
              <PopTheHood
                input={{ kind: "public-key", resp: attack, e: intercepted.e, orgSecret: keys.victim_secret }}
                pulse={completedOnce}
              />
            }
          />
        )}
      </StageCard>
    </div>
  );
}
