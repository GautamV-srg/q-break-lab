import { useEffect, useRef, useState } from "react";
import { aesAttack, aesEncrypt, errorMessage, MOCK_MODE } from "../api/client";
import { MOCK_KEYS } from "../api/mocks/demo";
import { buildAesAttackRequest, type InterceptedAes } from "../api/payloads";
import type { AesAttackResponse, AesEncryptResponse, AttackCondition } from "../api/types";
import BitInput, { randomBits } from "../components/BitInput";
import BreachReport, { verdictOf } from "../components/BreachReport";
import CiphertextView from "../components/CiphertextView";
import DefenceAct from "../components/defence/DefenceAct";
import { useDefence } from "../components/defence/useDefence";
import Duo from "../components/Duo";
import ErrorBox from "../components/ErrorBox";
import InterceptionWall from "../components/InterceptionWall";
import OptionGroup, { type Option } from "../components/OptionGroup";
import PopTheHood from "../components/PopTheHood";
import PrototypeNotice from "../components/PrototypeNotice";
import RunProgress from "../components/RunProgress";
import ShotsSlider from "../components/ShotsSlider";
import StageCard from "../components/StageCard";
import Stepper from "../components/Stepper";
import TraceView from "../components/TraceView";
import { focusStage, randomSeed, sleep, useAliveRef, useScrollToStage } from "../components/flow";
import { useConfig } from "../config";

const ID = "sym";
const STEPS = [
  { label: "Configure", side: "Your organization", act: "attack" as const },
  { label: "Intercept", side: "The wall", act: "attack" as const },
  { label: "Breach test", side: "Quantum adversary", act: "attack" as const },
  { label: "Report", side: "Breach Report", act: "attack" as const },
  { label: "Protect", side: "Your organization", act: "defend" as const },
  { label: "Re-attack", side: "Quantum adversary", act: "defend" as const },
  { label: "Compare", side: "Defence Report", act: "defend" as const },
];
const DEMO_MESSAGE = "Hi judges!";
const DEMO_SUBSTRING = "judges";

/** Presentation copy for the known-text field, per attack mode. The modes themselves come from /api/config. */
const KNOWN_FIELD: Record<AttackCondition, { label: string; hint: string } | null> = {
  known_beginning: {
    label: "Known beginning (e.g. a standard greeting or header)",
    hint: "Real messages often start predictably: greetings, headers, file signatures.",
  },
  known_substring: {
    label: "Known text somewhere in the message (position unknown)",
    hint: "A name, a date, a boilerplate phrase: the adversary knows it appears, not where.",
  },
  ciphertext_only: null,
};

/** A sensible starting guess for the known text, taken from the message that was encrypted. */
function defaultKnown(condition: AttackCondition, msg: string, prefixChars: number): string {
  if (condition === "ciphertext_only") return "";
  if (condition === "known_beginning") return msg.slice(0, prefixChars);
  if (msg.includes(DEMO_SUBSTRING)) return DEMO_SUBSTRING;
  const words = msg.split(/\s+/).filter((w) => w.length >= 3);
  // Prefer a word that is not at the very start, so "position unknown" means something.
  return words[1] ?? words[0] ?? msg.slice(Math.floor(msg.length / 3), Math.floor(msg.length / 3) + 4);
}

export default function SymmetricTest() {
  const { config, loading, error: configError } = useConfig();
  const alive = useAliveRef();

  // ---- Organization (victim) state. Never read when building the attack request. ----
  const [message, setMessage] = useState(DEMO_MESSAGE);
  const [keyBits, setKeyBits] = useState(config.aes_key_bits[0] ?? 4);
  const [orgKey, setOrgKey] = useState("1001");
  const [enc, setEnc] = useState<AesEncryptResponse | null>(null);
  const [encMessage, setEncMessage] = useState("");
  const [encrypting, setEncrypting] = useState(false);
  const [encError, setEncError] = useState<string | null>(null);

  // ---- Wall: what the adversary knows is chosen here, as part of what crosses. ----
  const [condition, setCondition] = useState<AttackCondition>("known_beginning");
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

  // ---- Act II (blue team): protect the same message, re-attack, compare. ----
  const defence = useDefence();
  const [actOpen, setActOpen] = useState(false);
  // A new breach (or none) starts Act II over.
  useEffect(() => {
    defence.reset();
    setActOpen(false);
  }, [attack]);

  // Everything selectable is driven by /api/config. Engines without the Track 5 fields
  // fall back to the plain list of enabled sizes and the single known-beginning mode.
  const conditions = config.aes_conditions ?? [];
  const modesExposed = conditions.length > 0;
  const activeCondition = modesExposed ? (conditions.find((c) => c.id === condition) ?? conditions[0]) : null;
  const needsKnown = activeCondition?.needs_known_text ?? true;
  const knownField = KNOWN_FIELD[activeCondition?.id ?? "known_beginning"];
  const keyOptions = config.aes_key_options?.length
    ? config.aes_key_options
    : config.aes_key_bits.map((bits) => ({ bits, enabled: true, simulated: true, reason: null }));

  // Keep the selections valid when /api/config arrives.
  useEffect(() => {
    if (config.aes_key_bits.length > 0 && !config.aes_key_bits.includes(keyBits)) {
      const kb = config.aes_key_bits[0];
      setKeyBits(kb);
      setOrgKey(randomBits(kb));
    }
  }, [config.aes_key_bits, keyBits]);
  useEffect(() => {
    if (activeCondition && activeCondition.id !== condition) setCondition(activeCondition.id);
  }, [activeCondition, condition]);

  const stage = attack
    ? defence.reattack
      ? 7
      : defence.protect || actOpen
        ? 5 + (defence.protect ? 1 : 0)
        : 4
    : intercepted
      ? 3
      : enc
        ? 2
        : 1;
  useScrollToStage(ID, stage);

  const configReady = !loading && !configError && config.aes_key_bits.length > 0;
  const keyValid = orgKey.length === keyBits && /^[01]+$/.test(orgKey);
  const messageValid = message.length > 0 && message.length <= config.max_aes_text_chars;
  const busy = encrypting || attacking || demoRunning || defence.busy || !configReady;
  const countingRuns = config.aes_counting_max_key_bits !== undefined && keyBits <= config.aes_counting_max_key_bits;

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

  /** Switching the attack mode changes what crosses the wall, so the hand-off is redone. */
  function chooseCondition(next: AttackCondition) {
    setCondition(next);
    setIntercepted(null);
    setAttack(null);
    setAttackError(null);
    if (enc) setKnownPlaintext(defaultKnown(next, encMessage, config.default_known_prefix_chars));
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
      setKnownPlaintext(defaultKnown(condition, msg, config.default_known_prefix_chars));
      return r;
    } catch (e) {
      if (alive.current) setEncError(errorMessage(e));
      return null;
    } finally {
      if (alive.current) setEncrypting(false);
    }
  }

  function interceptOf(r: AesEncryptResponse, known: string): InterceptedAes {
    // Only public material crosses the wall: ciphertext, key size, attack mode, known plaintext.
    return {
      key_bits: r.key_bits,
      ciphertext_nibbles: [...r.ciphertext_nibbles],
      known_plaintext: needsKnown ? known : "",
      ...(modesExposed ? { condition } : {}),
    };
  }

  function handOff(r: AesEncryptResponse | null = enc, known = knownPlaintext) {
    if (!r || (needsKnown && !known)) return;
    setIntercepted(interceptOf(r, known));
    setAttack(null);
    setAttackError(null);
  }

  async function runAttack(target: InterceptedAes | null = intercepted, seed: number | null = null): Promise<AesAttackResponse | null> {
    if (!target || inFlight.current) return null; // never fire twice
    inFlight.current = true;
    setAttacking(true);
    setAttackError(null);
    try {
      // The request is built ONLY from the adversary's intercepted data (see api/payloads.ts).
      const req = buildAesAttackRequest(target, { shots, seed });
      const r = await aesAttack(req);
      if (!alive.current) return null;
      setAttack(r);
      setCompletedOnce(true);
      return r;
    } catch (e) {
      if (alive.current) setAttackError(errorMessage(e));
      return null;
    } finally {
      inFlight.current = false;
      if (alive.current) setAttacking(false);
    }
  }

  /** Scripted run of the currently selected attack mode on the smallest enabled key. */
  async function runDemo() {
    setDemoRunning(true);
    try {
      const kb = config.aes_key_bits[0] ?? 4;
      // In mock mode, use the key the fixtures were recorded with so the demo replays a real run.
      const key = (MOCK_MODE && MOCK_KEYS[kb]) || randomBits(kb);
      const msg = DEMO_MESSAGE;
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
      const known = defaultKnown(condition, msg, config.default_known_prefix_chars);
      setKnownPlaintext(known);
      await sleep(700);
      if (!alive.current) return;
      handOff(r, known);
      await sleep(3200); // let the wall animation play
      if (!alive.current) return;
      const a = await runAttack(interceptOf(r, known));
      if (!a || !alive.current) return;
      await sleep(2500); // let the Breach Report land
      if (!alive.current) return;
      await runDefenceDemo(msg, originalOf(a));
    } finally {
      if (alive.current) setDemoRunning(false);
    }
  }

  function originalOf(a: AesAttackResponse) {
    const v = verdictOf({ kind: "symmetric", resp: a });
    return {
      cipher: "miniaes" as const,
      verdict: v === "safe" ? "not_breached" : v,
      label: `MiniAES, ${a.key_bits}-bit key · Grover`,
    };
  }

  /** Act II of the demo: protect with all three methods, Eve ON so the detection shows, re-attack, compare. */
  async function runDefenceDemo(msg: string, original: ReturnType<typeof originalOf>) {
    const s = defence.settings;
    if (!s) return;
    setActOpen(true);
    const bb84 = { ...s.defaults, eve: true };
    defence.setMethods(s.methods);
    defence.setBb84(bb84);
    await sleep(1500);
    if (!alive.current) return;
    const p = await defence.runProtect(msg, { bb84, methods: s.methods });
    if (!p || !alive.current) return;
    await sleep(4500); // let the photon stream and the QBER verdict play
    if (!alive.current) return;
    const attack = { eve_intercept_fraction: s.defaults.eve_intercept_fraction, channel_noise: s.defaults.channel_noise };
    defence.setAttack(attack);
    await defence.runReattack(p, { attack, original });
  }

  const keyChoices: Option<number>[] = keyOptions.map((o) => ({
    value: o.bits,
    name: `${o.bits}-bit`,
    label: `${o.bits}-bit`,
    sub: `${(2 ** o.bits).toLocaleString()} keys`,
    disabledReason: o.enabled ? null : (o.reason ?? "Not enabled on this instance."),
  }));
  const modeChoices: Option<AttackCondition>[] = conditions.map((c) => ({
    value: c.id,
    name: c.label,
    label: c.label,
    sub: c.description,
  }));
  const reportInput = attack && {
    kind: "symmetric" as const,
    resp: attack,
    orgKey,
    knownPlaintext: intercepted?.known_plaintext ?? "",
    conditionLabel: conditions.find((c) => c.id === (attack.condition ?? intercepted?.condition))?.label,
  };

  return (
    <div className="page test-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Red-team engagement · shared-key encryption like AES · Grover's algorithm</div>
          <h1>Symmetric breach test</h1>
          <p className="lede">
            Your organization encrypts a message with a secret key. A simulated quantum adversary intercepts the
            ciphertext and uses Grover's search to recover the key, under the attack mode you choose.
          </p>
        </div>
        <button className="btn btn-demo no-print" onClick={runDemo} disabled={busy}>
          {demoRunning ? "Demo running…" : "▶ Run full demo"}
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
                  rows={3}
                  value={message}
                  maxLength={config.max_aes_text_chars || undefined}
                  onChange={(e) => onOrgChange(setMessage)(e.target.value)}
                  disabled={busy}
                  aria-invalid={!messageValid}
                  aria-describedby="sym-msg-hint"
                />
                <div id="sym-msg-hint" className={`field-hint ${configReady && !messageValid ? "field-error" : ""}`}>
                  {configReady
                    ? `${message.length}/${config.max_aes_text_chars} characters${message.length === 0 ? " · enter a message" : ""}`
                    : "Waiting for the test engine's limits…"}
                </div>
              </div>

              <OptionGroup
                label="Key size"
                options={keyChoices}
                value={keyBits}
                busy={busy}
                onChange={(kb) => {
                  onOrgChange(setKeyBits)(kb);
                  setOrgKey(randomBits(kb));
                }}
                hint={
                  keyBits >= 10
                    ? "Larger keys take noticeably longer to simulate: every extra qubit doubles the simulator's work."
                    : undefined
                }
              />

              {modesExposed && (
                <OptionGroup
                  label="Attack mode: what the adversary knows"
                  variant="cards"
                  options={modeChoices}
                  value={condition}
                  busy={busy}
                  onChange={chooseCondition}
                />
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
            {activeCondition && (
              <p className="small">
                <strong>Attack mode: {activeCondition.label}.</strong> {activeCondition.description}
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
        locked={!enc}
        lockedHint="Encrypt a message first."
      >
        {enc && (
          <InterceptionWall
            key={enc.ciphertext_hex + condition}
            secrets={["Secret key " + "•".repeat(enc.key_bits)]}
            captured={[
              { label: "Ciphertext", value: <span className="mono chip-scroll">{enc.ciphertext_hex}</span> },
              { label: "Cipher rules", value: `MiniAES, ${enc.key_bits}-bit key, public` },
              needsKnown
                ? {
                    label: condition === "known_substring" ? "Known text (position unknown)" : "Known plaintext",
                    value: <span className="mono">“{knownPlaintext}”</span>,
                  }
                : { label: "Known plaintext", value: "None: ciphertext only" },
            ]}
          >
            {needsKnown && knownField ? (
              <div className="field known-field">
                <label htmlFor="sym-known" className="field-label">
                  {knownField.label}
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
                  aria-describedby="sym-known-hint"
                />
                <div id="sym-known-hint" className="field-hint">
                  {knownField.hint}
                </div>
              </div>
            ) : (
              <p className="known-field small">
                <strong>No known plaintext.</strong> The adversary only assumes the message is readable text, so
                several keys will usually fit.
              </p>
            )}
            {!intercepted && (
              <button className="btn btn-primary" onClick={() => handOff()} disabled={(needsKnown && !knownPlaintext) || busy}>
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
              contains only the ciphertext, the key size, the attack mode and any known plaintext.
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
                  ...(countingRuns ? ["Counting matching keys"] : []),
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
        {reportInput && (
          <BreachReport
            input={reportInput}
            onRetry={() => void runAttack(intercepted, randomSeed())}
            retrying={attacking}
            onProtect={() => {
              setActOpen(true);
              focusStage(ID, 5);
            }}
            popTheHood={
              <PopTheHood
                input={reportInput}
                noiseTarget={intercepted ? { kind: "symmetric", intercepted, shots } : undefined}
                pulse={completedOnce}
              />
            }
          />
        )}
      </StageCard>

      {/* ---------- Act II: stages 5–7 ---------- */}
      <DefenceAct
        d={defence}
        idPrefix={ID}
        startN={5}
        handOff
        unlocked={!!attack}
        lockedHint="Finish the breach test first: Act II protects the same message."
        message={encMessage}
        carriedFrom="Carried over from Act I, on the organization's side. It goes to the protect step only, never to the re-attack."
        original={attack ? originalOf(attack) : undefined}
        origin="Symmetric breach test, Act II"
        demoRunning={demoRunning}
      />
    </div>
  );
}
