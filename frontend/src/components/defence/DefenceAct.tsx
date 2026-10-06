import CompareStage from "./CompareStage";
import ProtectStage from "./ProtectStage";
import ReattackStage, { type BeforeResult } from "./ReattackStage";
import type { DefenceState } from "./useDefence";

interface Props {
  d: DefenceState;
  idPrefix: string;
  /** Stage number of Protect: 5 after a breach test, 1 in the standalone flow. */
  startN: number;
  /** False until the Breach Report exists (Act II unlocks after Act I). */
  unlocked: boolean;
  lockedHint?: string;
  message: string;
  onMessageChange?: (m: string) => void;
  carriedFrom?: string;
  original?: BeforeResult;
  origin: string;
  demoRunning?: boolean;
  /** Show the "now we fight back" hand-off banner (after Act I). */
  handOff?: boolean;
}

/** Act II, the blue team: Protect → Re-attack → Compare, in the defence palette. */
export default function DefenceAct({ d, idPrefix, startN, unlocked, lockedHint, message, onMessageChange, carriedFrom, original, origin, demoRunning, handOff }: Props) {
  const n = (k: number) => startN + k;
  const sid = (k: number) => `${idPrefix}-stage-${n(k)}`;
  return (
    <div className="act act-defend">
      {handOff && (
        <div className={`act-divider ${unlocked ? "act-divider-on" : ""}`} role="presentation">
          <span className="act-divider-red">Act I · Red team · breached</span>
          <span className="act-divider-line" aria-hidden="true" />
          <span className="act-divider-blue">Act II · Blue team · now we fight back</span>
        </div>
      )}
      <ProtectStage
        d={d}
        id={sid(0)}
        n={n(0)}
        locked={!unlocked}
        lockedHint={lockedHint}
        message={message}
        onMessageChange={onMessageChange}
        carriedFrom={carriedFrom}
        demoRunning={demoRunning}
      />
      <ReattackStage
        d={d}
        id={sid(1)}
        n={n(1)}
        locked={!unlocked || !d.protect}
        lockedHint="Protect the message first."
        original={original}
        demoRunning={demoRunning}
      />
      <CompareStage
        d={d}
        id={sid(2)}
        n={n(2)}
        locked={!unlocked || !d.reattack}
        lockedHint="Re-attack the protected messages to compare the defences."
        original={original}
        origin={origin}
      />
    </div>
  );
}
