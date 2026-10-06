import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getConfig, errorMessage } from "./api/client";
import type { ConfigResponse } from "./api/types";

/** Used until /api/config answers (and if it never does), so the UI still renders. */
export const FALLBACK_CONFIG: ConfigResponse = {
  aes_key_bits: [],
  rsa_moduli: [],
  max_shots: 0,
  max_aes_text_chars: 0,
  max_rsa_text_chars: 0,
  default_known_prefix_chars: 3,
};

interface ConfigState {
  config: ConfigResponse;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const ConfigContext = createContext<ConfigState>({
  config: FALLBACK_CONFIG,
  loading: true,
  error: null,
  reload: () => {},
});

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<ConfigResponse>(FALLBACK_CONFIG);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getConfig()
      .then((c) => setConfig(c))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  return (
    <ConfigContext.Provider value={{ config, loading, error, reload: load }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig(): ConfigState {
  return useContext(ConfigContext);
}
