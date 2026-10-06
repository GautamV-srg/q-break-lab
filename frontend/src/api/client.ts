import type {
  AesAttackRequest,
  AesAttackResponse,
  AesEncryptRequest,
  AesEncryptResponse,
  ConfigResponse,
  HealthResponse,
  RsaAttackRequest,
  RsaAttackResponse,
  RsaEncryptRequest,
  RsaEncryptResponse,
  RsaKeygenRequest,
  RsaKeygenResponse,
} from "./types";
import { assertNoSecrets } from "./payloads";

import mockConfig from "./mocks/config.json";
import mockAesEncrypt from "./mocks/aes_encrypt.json";
import mockAesAttack from "./mocks/aes_attack.json";
import mockRsaKeygen from "./mocks/rsa_keygen.json";
import mockRsaEncrypt from "./mocks/rsa_encrypt.json";
import mockRsaAttack from "./mocks/rsa_attack.json";

export class ApiError extends Error {
  status: number | null;
  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Decided once at load so client-side navigation keeps the mode. */
export const MOCK_MODE: boolean = (() => {
  if (import.meta.env.VITE_USE_MOCKS === "true") return true;
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("mock") === "1";
})();

const MOCK_DELAY_MS = 800;

function mock<T>(data: unknown): Promise<T> {
  // Deep copy so callers can't mutate the fixtures.
  const copy = JSON.parse(JSON.stringify(data)) as T;
  return new Promise((resolve) => setTimeout(() => resolve(copy), MOCK_DELAY_MS));
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : null))
      .filter((m): m is string => !!m);
    return msgs.length ? msgs.join("; ") : null;
  }
  return null;
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(
      "The Q-Break test engine is unreachable. Check your connection and try again.",
      null,
    );
  }
  if (!res.ok) {
    let message: string | null = null;
    try {
      const data = await res.json();
      message = detailToMessage(data?.detail);
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 503) {
      message = message ?? "The quantum simulator is busy running another test.";
      message += " Please retry in a few seconds.";
    }
    throw new ApiError(message ?? `Request failed (HTTP ${res.status}).`, res.status);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  if (MOCK_MODE) return mock({ status: "ok" });
  return request("GET", "/health");
}

export function getConfig(): Promise<ConfigResponse> {
  if (MOCK_MODE) return mock(mockConfig);
  return request("GET", "/config");
}

export function aesEncrypt(req: AesEncryptRequest): Promise<AesEncryptResponse> {
  if (MOCK_MODE) return mock(mockAesEncrypt);
  return request("POST", "/aes/encrypt", req);
}

export function aesAttack(req: AesAttackRequest): Promise<AesAttackResponse> {
  assertNoSecrets(req); // last line of defence: never send a secret to /attack
  if (MOCK_MODE) return mock(mockAesAttack);
  return request("POST", "/aes/attack", req);
}

export function rsaKeygen(req: RsaKeygenRequest): Promise<RsaKeygenResponse> {
  if (MOCK_MODE) return mock(mockRsaKeygen);
  return request("POST", "/rsa/keygen", req);
}

export function rsaEncrypt(req: RsaEncryptRequest): Promise<RsaEncryptResponse> {
  if (MOCK_MODE) return mock(mockRsaEncrypt);
  return request("POST", "/rsa/encrypt", req);
}

export function rsaAttack(req: RsaAttackRequest): Promise<RsaAttackResponse> {
  assertNoSecrets(req); // last line of defence: never send p, q, d, phi to /attack
  if (MOCK_MODE) return mock(mockRsaAttack);
  return request("POST", "/rsa/attack", req);
}

/** Friendly message for any thrown value. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
