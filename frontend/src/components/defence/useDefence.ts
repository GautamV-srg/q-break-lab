import { useEffect, useRef, useState } from "react";
import { defenceProtect, defenceReattack, errorMessage } from "../../api/client";
import { buildReattackRequest } from "../../api/payloads";
import type { Bb84Options, DefenceMethod, ProtectResponse, ReattackRequest, ReattackResponse } from "../../api/types";
import { useConfig } from "../../config";
import { useAliveRef } from "../flow";
import { defenceSettings, useDefenceInfo, type DefenceSettings } from "./settings";

export type OriginalAttack = NonNullable<ReattackRequest["original_attack"]>;

export interface Bb84Attack {
  eve_intercept_fraction: number;
  channel_noise: number;
}

/**
 * State and actions for Act II (Protect → Re-attack → Compare), shared by both breach tests
 * and the standalone Protect page. Actions take explicit arguments so demo mode can chain them.
 */
export function useDefence() {
  const { config } = useConfig();
  const infoState = useDefenceInfo();
  const settings: DefenceSettings | null = defenceSettings(config, infoState.info);
  const alive = useAliveRef();

  const [methods, setMethods] = useState<DefenceMethod[]>(["aes256", "mlkem", "bb84"]);
  const [bb84, setBb84] = useState<Bb84Options | null>(null);
  const [attack, setAttack] = useState<Bb84Attack | null>(null);
  const [autoRun, setAutoRun] = useState(false);

  const [protect, setProtect] = useState<ProtectResponse | null>(null);
  const [protectedText, setProtectedText] = useState("");
  const [protecting, setProtecting] = useState(false);
  const [protectError, setProtectError] = useState<string | null>(null);

  const [reattack, setReattack] = useState<ReattackResponse | null>(null);
  const [reattacking, setReattacking] = useState(false);
  const [reattackError, setReattackError] = useState<string | null>(null);
  const [dropped, setDropped] = useState<string[]>([]);
  const inFlight = useRef(false);

  // Seed the controls from the engine's defaults once they arrive.
  useEffect(() => {
    if (!settings) return;
    setMethods((m) => m.filter((x) => settings.methods.includes(x)));
    setBb84((b) => b ?? { ...settings.defaults });
    setAttack((a) => a ?? { eve_intercept_fraction: settings.defaults.eve_intercept_fraction, channel_noise: settings.defaults.channel_noise });
  }, [settings?.defaults.raw_qubits, settings?.methods.join()]);

  function reset() {
    setProtect(null);
    setProtectError(null);
    setReattack(null);
    setReattackError(null);
  }

  async function runProtect(
    plaintext: string,
    opts: { bb84?: Bb84Options; methods?: DefenceMethod[] } = {},
  ): Promise<ProtectResponse | null> {
    const b = opts.bb84 ?? bb84;
    const ms = opts.methods ?? methods;
    if (!b || ms.length === 0 || inFlight.current) return null;
    inFlight.current = true;
    setProtecting(true);
    setProtectError(null);
    try {
      // Organization side: the plaintext goes to /protect, never to /reattack.
      const r = await defenceProtect({ plaintext, methods: ms, bb84: b });
      if (!alive.current) return null;
      setProtect(r);
      setProtectedText(plaintext);
      setReattack(null);
      setReattackError(null);
      return r;
    } catch (e) {
      if (alive.current) setProtectError(errorMessage(e));
      return null;
    } finally {
      inFlight.current = false;
      if (alive.current) setProtecting(false);
    }
  }

  async function runReattack(
    target: ProtectResponse | null = protect,
    opts: { attack?: Bb84Attack; original?: OriginalAttack; seed?: number | null } = {},
  ): Promise<ReattackResponse | null> {
    const a = opts.attack ?? attack;
    if (!target || !a || inFlight.current) return null;
    inFlight.current = true;
    setReattacking(true);
    setReattackError(null);
    try {
      // Adversary side: only the public bundles cross (see buildReattackRequest).
      const { request, dropped: d } = buildReattackRequest(target, {
        bb84_attack: { ...a, seed: opts.seed ?? null },
        original_attack: opts.original,
      });
      setDropped(d);
      const r = await defenceReattack(request);
      if (!alive.current) return null;
      setReattack(r);
      return r;
    } catch (e) {
      if (alive.current) setReattackError(errorMessage(e));
      return null;
    } finally {
      inFlight.current = false;
      if (alive.current) setReattacking(false);
    }
  }

  return {
    info: infoState.info,
    infoError: infoState.error,
    infoLoading: infoState.loading,
    reloadInfo: infoState.reload,
    settings,
    methods,
    setMethods,
    bb84,
    setBb84,
    attack,
    setAttack,
    autoRun,
    setAutoRun,
    protect,
    protectedText,
    protecting,
    protectError,
    reattack,
    reattacking,
    reattackError,
    dropped,
    busy: protecting || reattacking,
    runProtect,
    runReattack,
    reset,
  };
}

export type DefenceState = ReturnType<typeof useDefence>;
