import { useEffect, useRef, useState } from "react";
import { aesAttack, aesEncrypt, errorMessage, MOCK_MODE } from "../api/client";
import { buildAesAttackRequest, type InterceptedAes } from "../api/payloads";
import type { AesAttackResponse, AesEncryptResponse } from "../api/types";
import BitInput, { randomBits } from "../components/BitInput";
import BreachReport from "../components/BreachReport";
import CiphertextView from "../components/CiphertextView";
import Duo from "../components/Duo";
import ErrorBox from "../components/ErrorBox";
import InterceptionWall from "../components/InterceptionWall";
import PopTheHood from "../components/PopTheHood";
import PrototypeNotice from "../components/PrototypeNotice";
import RunProgress from "../components/RunProgress";
import ShotsSlider from "../components/ShotsSlider";
import StageCard from "../components/StageCard";
import Stepper from "../components/Stepper";
import TraceView from "../components/TraceView";
import { randomSeed, sleep, useAliveRef, useScrollToStage } from "../components/flow";
import { useConfig } from "../config";

const ID = "sym";
const STEPS = [
  { label: "Configure", side: "Your organization" },
  { label: "Intercept", side: "The wall" },
  { label: "Breach test", side: "Quantum adversary" },
  { label: "Report", side: "Breach Report" },
];

export default function SymmetricTest() {
  const { config } = useConfig();
  const alive = useAliveRef();

  // ---- Organization (victim) state. Never read when building the attack request. ----
  const [message, setMessage] = useState("Hi judges!");
  const [keyBits, setKeyBits] = useState(config.aes_key_bits[0] ?? 4);
  const [orgKey, setOrgKey] = useState("1001");
  const [enc, setEnc] = useState<AesEncryptResponse | null>(null);
  const [encMessage, setEncMessage] = useState("");
  const [encrypting, setEncrypting] = useState(false);
  const [encError, setEncError] = useState<string | null>(null);

  // ---- Wall: known plaintext is chosen here, as part of what the adversary has. ----
  const [knownPlaintext, setKnownPlaintext] = useState("");

  // ---- Adversary state. Holds only what crossed the wall. ----
  const [intercepted, setIntercepted] = useState<InterceptedAes | null>(null);
  const [shots, setShots] = useState(1024);
  const [attack, setAttack] = useState<AesAttackResponse | null>(null);
  const [attacking, setAttacking] = useState(false);
  const [attackError, setAttackError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const [demoRunning, setDemoRunning] = useState(false);
  const [completedOnce, setCompletedOnce] = useState(false);

  // Keep key size valid when /api/config arrives.
  useEffect(() => {
    if (!config.aes_key_bits.includes(keyBits)) {
      const kb = config.aes_key_bits[0] ?? 4;
      setKeyBits(kb);
      setOrgKey(randomBits(kb));
    }
  }, [config.aes_key_bits, keyBits]);

  const stage = attack ? 4 : intercepted ? 3 : enc ? 2 : 1;
  useScrollToStage(ID, stage);

  const keyValid = orgKey.length === keyBits && /^[01]+$/.test(orgKey);
  const messageValid = message.length > 0 && message.length <= config.max_aes_text_chars;
  const busy = encrypting || attacking || demoRunning;

  function resetFromEncrypt() {
    setEnc(null);
    setIntercepted(null);
    setAttack(null);
    setAttackError(null);
  }

  function onOrgChange<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      if (enc) resetFromEncrypt();
    };
  }

  async function doEncrypt(msg = message, key = orgKey, kb = keyBits): Promise<AesEncryptResponse | null> {
    setEncrypting(true);
    setEncError(null);
    try {
      const r = await aesEncrypt({ plaintext: msg, key, key_bits: kb });
      if (!alive.current) return null;
      resetFromEncrypt();
      setEnc(r);
      setEncMessage(msg);
      setKnownPlaintext(msg.slice(0, config.default_known_prefix_chars));
      return r;
    } catch (e) {
      if (alive.current) setEncError(errorMessage(e));
      return null;
    } finally {
      if (alive.current) setEncrypting(false);
    }
  }

  function handOff(r: AesEncryptResponse | null = enc, known = knownPlaintext) {
    if (!r || !known) return;
    // Only public material crosses the wall: ciphertext, key size, known plaintext.
    setIntercepted({ key_bits: r.key_bits, ciphertext_nibbles: [...r.ciphertext_nibbles], known_plaintext: known });
    setAttack(null);
    setAttackError(null);
  }

  async function runAttack(target: InterceptedAes | null = intercepted, seed: number | null = null) {
    if (!target || inFlight.current) return; // never fire twice
    inFlight.current = true;
    setAttacking(true);
    setAttackError(null);
    try {
      // The request is built ONLY from the adversary's intercepted data (see api/payloads.ts).
      const req = buildAesAttackRequest(target, { shots, seed });
      const r = await aesAttack(req);
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
      const kb = config.aes_key_bits[0] ?? 4;
      // Mock fixtures were generated with key 1001, so keep the "matches" badge honest in mock mode.
      const key = MOCK_MODE ? "1001" : randomBits(kb);
      const msg = "Hi judges!";
      setKeyBits(kb);
      setOrgKey(key);
      setMessage(msg);
      setAttack(null);
      await sleep(700);
      if (!alive.current) return;
      const r = await doEncrypt(msg, key, kb);
      if (!r || !alive.current) return;
      await sleep(1600);
      if (!alive.current) return;
      const known = "Hi ";
      setKnownPlaintext(known);
      await sleep(700);
      if (!alive.current) return;
      handOff(r, known);
      await sleep(3200); // let the wall animation play
      if (!alive.current) return;
      await runAttack({ key_bits: r.key_bits, ciphertext_nibbles: r.ciphertext_nibbles, known_plaintext: known });
    } finally {
      if (alive.current) setDemoRunning(false);
    }
  }

  const showKeySelector = config.aes_key_bits.length > 1;

  return (
    <div className="page test-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Shared-key encryption like AES · Grover's algorithm</div>
          <h1>Symmetric breach test</h1>
          <p className="lede">
            Your organization encrypts a message with a secret key. A simulated quantum adversary intercepts the
            ciphertext and uses Grover's search to recover the key.
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
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (keyValid && messageValid && !busy) void doEncrypt();
              }}
            >
              <div className="field">
                <label htmlFor="sym-msg" className="field-label">
                  Message your organization sends
                </label>
                <textarea
                  id="sym-msg"
                  className="input"
                  rows={2}
                  value={message}
                  maxLength={config.max_aes_text_chars}
                  onChange={(e) => onOrgChange(setMessage)(e.target.value)}
                  disabled={busy}
                />
                <div className="field-hint">
                  {message.length}/{config.max_aes_text_chars} characters
                </div>
              </div>

              {showKeySelector && (
                <div className="field">
                  <span className="field-label" id="sym-kb-label">
                    Key size
                  </span>
                  <div className="segmented" role="radiogroup" aria-labelledby="sym-kb-label">
                    {config.aes_key_bits.map((kb) => (
                      <button
                        type="button"
                        role="radio"
                        aria-checked={kb === keyBits}
                        key={kb}
                        className={kb === keyBits ? "seg seg-on" : "seg"}
                        onClick={() => {
                          onOrgChange(setKeyBits)(kb);
                          setOrgKey(randomBits(kb));
                        }}
                        disabled={busy}
                      >
                        {kb}-bit <span className="muted small">({2 ** kb} keys)</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <BitInput
                label="Organization's secret key (hidden from adversary)"
                value={orgKey}
                bits={keyBits}
                onChange={onOrgChange(setOrgKey)}
                disabled={busy}
              />

              <button type="submit" className="btn btn-primary" disabled={!keyValid || !messageValid || busy}>
                {encrypting ? "Encrypting…" : "🔐 Encrypt message"}
              </button>
            </form>
            <ErrorBox message={encError} onRetry={() => void doEncrypt()} />
            {enc && (
              <div className="result-block">
                <CiphertextView nibbles={enc.ciphertext_nibbles} />
                <TraceView trace={enc.trace} />
              </div>
            )}
          </StageCard>
        }
        right={
          <div className="adv-listen">
            <span className="side-tag side-tag-adv">Quantum adversary (simulated)</span>
            {enc ? (
              <p>
                📡 A ciphertext is on the wire: <span className="mono">{enc.ciphertext_hex.slice(0, 12)}…</span>. The
                adversary does not know the key.
              </p>
            ) : (
              <p className="muted">📡 Listening on the channel. Nothing sent yet.</p>
            )}
            <p className="small muted">
              The adversary knows the cipher's public rules (MiniAES: S-box, RotateBits, key schedule), like any
              attacker who knows which algorithm you use.
            </p>
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
        locked={!enc}
        lockedHint="Encrypt a message first."
      >
        {enc && (
          <InterceptionWall
            key={enc.ciphertext_hex}
            secrets={["Secret key " + "•".repeat(enc.key_bits)]}
            captured={[
              { label: "Ciphertext", value: <span className="mono">{enc.ciphertext_hex}</span> },
              { label: "Cipher rules", value: `MiniAES, ${enc.key_bits}-bit key, public` },
              { label: "Known plaintext", value: <span className="mono">“{knownPlaintext}”</span> },
            ]}
          >
            <div className="field known-field">
              <label htmlFor="sym-known" className="field-label">
                Known plaintext (e.g. a standard greeting or header)
              </label>
              <input
                id="sym-known"
                className="input mono"
                value={knownPlaintext}
                onChange={(e) => {
                  setKnownPlaintext(e.target.value);
                  if (intercepted) {
                    setIntercepted(null);
                    setAttack(null);
                  }
                }}
                maxLength={encMessage.length || undefined}
                disabled={busy}
                spellCheck={false}
              />
              <div className="field-hint">
                Real messages often start predictably: greetings, headers, file signatures.
              </div>
            </div>
            {!intercepted && (
              <button className="btn btn-primary" onClick={() => handOff()} disabled={!knownPlaintext || busy}>
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
              <span aria-hidden="true">🔒</span> The secret key never leaves this side. The adversary's request
              contains only the ciphertext, the key size and the known plaintext.
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
            <ShotsSlider value={shots} max={config.max_shots} onChange={setShots} disabled={busy} />
            <button className="btn btn-attack" onClick={() => void runAttack()} disabled={busy || !intercepted}>
              {attacking ? "Breach test running…" : "⚛ Run quantum breach test"}
            </button>
            {attacking && intercepted && (
              <RunProgress
                stages={[
                  "Building oracle",
                  `Simulating ${intercepted.key_bits}-qubit key register in superposition`,
                  "Amplifying",
                  "Measuring",
                ]}
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
        locked={!attack}
        lockedHint="Run the breach test to produce a report."
        className="stage-report"
      >
        {attack && (
          <BreachReport
            input={{ kind: "symmetric", resp: attack, orgKey, knownPlaintext: intercepted?.known_plaintext ?? "" }}
            onRetry={() => void runAttack(intercepted, randomSeed())}
            retrying={attacking}
            popTheHood={
              <PopTheHood
                input={{ kind: "symmetric", resp: attack, orgKey, knownPlaintext: intercepted?.known_plaintext ?? "" }}
                pulse={completedOnce}
              />
            }
          />
        )}
      </StageCard>
    </div>
  );
}
