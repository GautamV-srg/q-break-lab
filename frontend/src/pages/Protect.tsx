import { useState } from "react";
import { MOCK_MESSAGE } from "../api/mocks/demo";
import DefenceAct from "../components/defence/DefenceAct";
import { useDefence } from "../components/defence/useDefence";
import PrototypeNotice from "../components/PrototypeNotice";
import Stepper from "../components/Stepper";
import { sleep, useAliveRef, useScrollToStage } from "../components/flow";

const ID = "def";
const STEPS = [
  { label: "Protect", side: "Your organization", act: "defend" as const },
  { label: "Re-attack", side: "Quantum adversary", act: "defend" as const },
  { label: "Compare", side: "Defence Report", act: "defend" as const },
];

/** Act II on its own: protect a fresh message, re-attack it, compare the defences. */
export default function Protect() {
  const d = useDefence();
  const alive = useAliveRef();
  const [message, setMessage] = useState(MOCK_MESSAGE);
  const [demoRunning, setDemoRunning] = useState(false);

  const stage = d.reattack ? 3 : d.protect ? 2 : 1;
  useScrollToStage(ID, stage);

  async function runDemo() {
    const s = d.settings;
    if (!s) return;
    setDemoRunning(true);
    try {
      setMessage(MOCK_MESSAGE);
      const bb84 = { ...s.defaults, eve: true };
      d.setMethods(s.methods);
      d.setBb84(bb84);
      await sleep(900);
      if (!alive.current) return;
      const p = await d.runProtect(MOCK_MESSAGE, { bb84, methods: s.methods });
      if (!p || !alive.current) return;
      await sleep(4500);
      if (!alive.current) return;
      const attack = { eve_intercept_fraction: s.defaults.eve_intercept_fraction, channel_noise: s.defaults.channel_noise };
      d.setAttack(attack);
      await d.runReattack(p, { attack });
    } finally {
      if (alive.current) setDemoRunning(false);
    }
  }

  return (
    <div className="page test-page protect-page">
      <div className="page-head">
        <div>
          <div className="eyebrow eyebrow-def">Blue-team engagement · AES-256 · ML-KEM · BB84 QKD</div>
          <h1>Protect a message</h1>
          <p className="lede">
            Re-encrypt a message three ways, send the same quantum adversary after each protected version, and compare
            the defences side by side. The breach tests run this as Act II, after the toy cipher falls.
          </p>
        </div>
        <button className="btn btn-demo btn-demo-def no-print" onClick={() => void runDemo()} disabled={demoRunning || d.busy || !d.settings}>
          {demoRunning ? "Demo running…" : "▶ Run demo"}
        </button>
      </div>

      <PrototypeNotice />
      <Stepper steps={STEPS} active={stage} idPrefix={ID} />

      <DefenceAct
        d={d}
        idPrefix={ID}
        startN={1}
        unlocked
        message={message}
        onMessageChange={(m) => {
          setMessage(m);
        }}
        origin="Standalone protect flow"
        demoRunning={demoRunning}
      />
    </div>
  );
}
