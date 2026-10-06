import { useEffect, useRef, useState } from "react";
import { errorMessage, rsaAttack, rsaEncrypt, rsaKeygen } from "../api/client";
import { buildRsaAttackRequest, type InterceptedRsa } from "../api/payloads";
import type { RsaAttackResponse, RsaEncryptResponse, RsaKeygenResponse } from "../api/types";
import BreachReport, { verdictOf } from "../components/BreachReport";
import ChunkTable from "../components/ChunkTable";
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
import { focusStage, randomSeed, sleep, useAliveRef, useScrollToStage } from "../components/flow";
import { useConfig } from "../config";

const ID = "pk";
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
/** "" lets the engine choose the construction (the field is then left out of the request). */
const AUTO = "";

export default function PublicKeyTest() {
  const { config, loading, error: configError } = useConfig();
  const alive = useAliveRef();

  // Everything selectable is driven by /api/config. Engines without the Track 5 fields
  // fall back to the plain list of enabled moduli and no construction selector.
  const modulusOptions = config.rsa_moduli_options?.length
    ? config.rsa_moduli_options
    : config.rsa_moduli.map((m) => ({
        n: m, label: `N = ${m}`, enabled: true, kind: "supported", reason: null, qubits_register_2n: null, qubits_iterative: null,
      }));
  const constructions = config.rsa_constructions ?? [];

  // ---- Organization (victim) state. Never read when building the attack request. ----
  const [n, setN] = useState(config.rsa_moduli[0] ?? 15);
  const [keys, setKeys] = useState<RsaKeygenResponse | null>(null);
  const [reveal, setReveal] = useState(false);
  const [keygenBusy, setKeygenBusy] = useState(false);
  const [keygenError, setKeygenError] = useState<string | null>(null);
  const [message, setMessage] = useState(DEMO_MESSAGE);
  const [enc, setEnc] = useState<RsaEncryptResponse | null>(null);
  const [encMessage, setEncMessage] = useState("");
  const [encrypting, setEncrypting] = useState(false);
  const [encError, setEncError] = useState<string | null>(null);

  // ---- Adversary state. Holds only what crossed the wall. ----
  const [intercepted, setIntercepted] = useState<InterceptedRsa | null>(null);
  const [baseA, setBaseA] = useState("");
  const [construction, setConstruction] = useState(AUTO);
  const [shots, setShots] = useState(1024);
  const [attack, setAttack] = useState<RsaAttackResponse | null>(null);
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

  // Keep the selections valid when /api/config arrives or the modulus changes.
  useEffect(() => {
    if (config.rsa_moduli.length > 0 && !config.rsa_moduli.includes(n)) setN(config.rsa_moduli[0]);
  }, [config.rsa_moduli, n]);
  useEffect(() => {
    if (construction !== AUTO && !config.rsa_constructions?.some((c) => c.key === construction && c.moduli.includes(n)))
      setConstruction(AUTO);
  }, [n, construction, config.rsa_constructions]);

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
  useScrollToStage(ID, stage, [6]); // stay on the Protect results; no jump to Re-attack

  const configReady = !loading && !configError && config.rsa_moduli.length > 0;
  const busy = keygenBusy || encrypting || attacking || demoRunning || defence.busy || !configReady;
  const messageValid = message.length > 0 && message.length <= config.max_rsa_text_chars;
  const selectedModulus = modulusOptions.find((o) => o.n === n);
  const chosen = constructions.find((c) => c.key === construction);

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

  async function runAttack(
    target: InterceptedRsa | null = intercepted,
    a: number | null = aNum,
    seed: number | null = null,
  ): Promise<RsaAttackResponse | null> {
    if (!target || inFlight.current) return null; // never fire twice
    inFlight.current = true;
    setAttacking(true);
    setAttackError(null);
    try {
      // The request is built ONLY from the adversary's intercepted data (see api/payloads.ts).
      const req = buildRsaAttackRequest(target, { a, shots, seed, ...(construction !== AUTO ? { construction } : {}) });
      const r = await rsaAttack(req);
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

  async function runDemo() {
    setDemoRunning(true);
    try {
      // The demo runs the modulus and construction currently selected.
      const modulus = config.rsa_moduli.includes(n) ? n : (config.rsa_moduli[0] ?? 15);
      const msg = DEMO_MESSAGE;
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
      const res = await runAttack({ n: k.n, e: k.e, ciphertext: r.ciphertext, bit_length: r.bit_length }, a);
      if (!res || !alive.current) return;
      await sleep(2500); // let the Breach Report land
      if (!alive.current) return;
      await runDefenceDemo(msg, originalOf(res));
    } finally {
      if (alive.current) setDemoRunning(false);
    }
  }

  function originalOf(a: RsaAttackResponse) {
    const v = verdictOf({ kind: "public-key", resp: a });
    return {
      cipher: "minirsa" as const,
      verdict: v === "safe" ? "not_breached" : v,
      label: `MiniRSA, N = ${a.n} · Shor`,
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

  const modulusChoices: Option<number>[] = modulusOptions.map((o) => ({
    value: o.n,
    name: o.label,
    label: o.label,
    disabledReason: o.enabled ? null : (o.reason ?? "Not enabled on this instance."),
  }));
  const constructionChoices: Option<string>[] = [
    { value: AUTO, name: "Engine default", label: "Engine default", sub: "Let the engine pick the construction for this modulus." },
    ...constructions.map((c) => ({
      value: c.key,
      name: c.label,
      label: c.label,
      sub: c.description,
      badge: c.headline ? "Headline · fewest qubits" : undefined,
      disabledReason: c.moduli.includes(intercepted?.n ?? n)
        ? null
        : `This construction is offered for N = ${c.moduli.join(", ") || "no enabled modulus"} only.`,
    })),
  ];
  const usedConstruction =
    attack && constructions.find((c) => c.key === attack.construction_key || c.name === attack.construction);
  const reportInput = attack &&
    keys &&
    intercepted && {
      kind: "public-key" as const,
      resp: attack,
      e: intercepted.e,
      orgSecret: keys.victim_secret,
      constructionLabel: usedConstruction?.label,
    };

  return (
    <div className="page test-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Red-team engagement · RSA · Shor's algorithm</div>
          <h1>Public-key breach test</h1>
          <p className="lede">
            Your organization publishes an RSA public key and receives encrypted messages. A simulated quantum
            adversary sees only the public key and the ciphertext, and uses Shor's period finding to factor N and
            rebuild the private key.
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
            <OptionGroup
              label="RSA modulus N"
              options={modulusChoices}
              value={n}
              busy={busy}
              onChange={(m) => {
                setN(m);
                if (keys && keys.n !== m) {
                  setKeys(null);
                  resetAfterKeygen();
                }
              }}
              hint={
                selectedModulus?.qubits_register_2n != null && selectedModulus.qubits_iterative != null
                  ? `N = ${n}: ${selectedModulus.qubits_register_2n} qubits with a 2n counting register, ${selectedModulus.qubits_iterative} with iterative Shor.`
                  : undefined
              }
            />
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
                    <textarea
                      id="pk-msg"
                      className="input"
                      rows={2}
                      value={message}
                      maxLength={config.max_rsa_text_chars || undefined}
                      onChange={(e) => {
                        setMessage(e.target.value);
                        if (enc) {
                          setEnc(null);
                          resetAfterEncrypt();
                        }
                      }}
                      disabled={busy}
                      aria-invalid={!messageValid}
                      aria-describedby="pk-msg-hint"
                    />
                    <div id="pk-msg-hint" className={`field-hint ${messageValid ? "" : "field-error"}`}>
                      {message.length}/{config.max_rsa_text_chars} characters{message.length === 0 ? " · enter a message" : ""}
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
              { label: "Ciphertext", value: <span className="mono chip-scroll">[{enc.ciphertext.join(", ")}]</span> },
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
              only n, e, the ciphertext, its bit length and the attack settings.
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
            {constructions.length > 0 && (
              <OptionGroup
                label="Shor construction"
                variant="cards"
                options={constructionChoices}
                value={construction}
                busy={busy}
                onChange={(key) => {
                  setConstruction(key);
                  setAttack(null);
                }}
                hint={chosen ? `Counting qubits: ${chosen.counting_qubits}.` : undefined}
              />
            )}
            <p className="caution">
              <strong>Classical pre-computation is disclosed.</strong> Except for the textbook swap circuit at N = 15,
              the modular-multiplication blocks are permutations computed classically when the circuit is built. The
              period itself is read from the quantum measurement, and each report states which construction ran.
            </p>
            <ShotsSlider value={shots} max={config.max_shots} onChange={setShots} disabled={busy} />
            <button className="btn btn-attack" onClick={() => void runAttack()} disabled={busy || !intercepted || !aValid}>
              {attacking ? "Breach test running…" : "⚛ Run quantum breach test"}
            </button>
            {attacking && (
              <RunProgress
                stages={[
                  "Building period-finding circuit",
                  "Simulating",
                  construction === "iterative" ? "Measuring and resetting the counting qubit" : "Inverse QFT",
                  "Reading period",
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
        locked={!attack || !keys}
        lockedHint="Run the breach test to produce a report."
        className="stage-report"
      >
        {reportInput && intercepted && (
          <BreachReport
            input={reportInput}
            onRetry={() => void runAttack(intercepted, null, randomSeed())}
            retrying={attacking}
            onProtect={() => {
              setActOpen(true);
              focusStage(ID, 5);
            }}
            popTheHood={
              <PopTheHood
                input={reportInput}
                noiseTarget={{ kind: "public-key", intercepted, shots, construction: reportInput.resp.construction_key }}
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
        origin="Public-key breach test, Act II"
        demoRunning={demoRunning}
      />
    </div>
  );
}
