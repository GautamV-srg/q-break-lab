import { useCallback, useEffect, useState } from "react";
import { errorMessage, getDefenceInfo } from "../../api/client";
import type { Bb84Limits, Bb84Options, ConfigResponse, DefenceInfo, DefenceMethod } from "../../api/types";

export const ALL_METHODS: DefenceMethod[] = ["aes256", "mlkem", "bb84"];

/** Display name per method, used until /api/defence/info answers. */
export const METHOD_FALLBACK_NAME: Record<DefenceMethod, string> = { aes256: "AES-256", mlkem: "ML-KEM", bb84: "BB84 QKD" };

export interface DefenceSettings {
  methods: DefenceMethod[];
  maxTextChars: number;
  defaults: Bb84Options;
  limits: Required<Bb84Limits>;
}

/**
 * Defence limits and defaults, read from /api/config (preferred) and /api/defence/info.
 * Returns null until one of them has supplied the BB84 defaults: no number is invented here.
 */
export function defenceSettings(config: ConfigResponse, info: DefenceInfo | null): DefenceSettings | null {
  const d = { ...(info?.bb84?.defaults ?? {}), ...(config.defence?.bb84_defaults ?? {}) } as Partial<Bb84Options>;
  const l = { ...(info?.bb84?.limits ?? {}), ...(config.defence?.bb84_limits ?? {}) } as Bb84Limits;
  if (d.raw_qubits == null || d.qber_threshold == null) return null;
  const defaults: Bb84Options = {
    eve: d.eve ?? false,
    eve_intercept_fraction: d.eve_intercept_fraction ?? l.eve_intercept_fraction_max ?? 1,
    channel_noise: d.channel_noise ?? l.channel_noise_min ?? 0,
    raw_qubits: d.raw_qubits,
    qber_threshold: d.qber_threshold,
    seed: d.seed ?? null,
  };
  const methods = (config.defence?.methods ?? info?.methods?.map((m) => m.id) ?? ALL_METHODS).filter((m) =>
    ALL_METHODS.includes(m),
  );
  return {
    methods,
    maxTextChars: config.defence?.max_text_chars ?? info?.max_text_chars ?? config.max_aes_text_chars,
    defaults,
    limits: {
      // A missing bound collapses onto the default, so a slider never offers a value the engine did not state.
      raw_qubits_min: l.raw_qubits_min ?? defaults.raw_qubits,
      raw_qubits_max: l.raw_qubits_max ?? defaults.raw_qubits,
      eve_intercept_fraction_min: l.eve_intercept_fraction_min ?? 0,
      eve_intercept_fraction_max: l.eve_intercept_fraction_max ?? 1,
      channel_noise_min: l.channel_noise_min ?? 0,
      channel_noise_max: l.channel_noise_max ?? defaults.channel_noise,
      qber_threshold_min: l.qber_threshold_min ?? defaults.qber_threshold,
      qber_threshold_max: l.qber_threshold_max ?? defaults.qber_threshold,
    },
  };
}

let infoPromise: Promise<DefenceInfo> | null = null;

/** /api/defence/info, fetched once per page load and shared by every defence view. */
export function useDefenceInfo() {
  const [info, setInfo] = useState<DefenceInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback((force = false) => {
    if (force || !infoPromise) infoPromise = getDefenceInfo();
    const p = infoPromise;
    setLoading(true);
    setError(null);
    p.then(setInfo)
      .catch((e) => {
        if (infoPromise === p) infoPromise = null;
        setError(errorMessage(e));
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);
  return { info, error, loading, reload: () => load(true) };
}

export function methodName(info: DefenceInfo | null, m: DefenceMethod): string {
  return info?.methods?.find((x) => x.id === m)?.name ?? METHOD_FALLBACK_NAME[m];
}

// ---------- Verdict presentation (text + icon: never colour alone) ----------

export interface VerdictMeta {
  label: string;
  icon: string;
  tone: "safe" | "warn" | "breach" | "neutral";
}

const VERDICTS: Record<string, VerdictMeta> = {
  infeasible: { label: "Infeasible", icon: "⛨", tone: "safe" },
  not_applicable: { label: "Not applicable", icon: "∅", tone: "safe" },
  detected: { label: "Detected", icon: "◉", tone: "safe" },
  undetected_low_intercept: { label: "Undetected (low intercept)", icon: "◌", tone: "warn" },
  breached: { label: "Breached", icon: "⚠", tone: "breach" },
  ambiguous: { label: "Ambiguous", icon: "≈", tone: "warn" },
  not_breached: { label: "Not breached", icon: "○", tone: "neutral" },
};

/** Badge copy for an engine verdict. Unknown verdicts are shown as the engine wrote them. */
export function verdictMeta(v: string): VerdictMeta {
  return VERDICTS[v] ?? { label: v.replace(/_/g, " "), icon: "•", tone: "neutral" };
}
