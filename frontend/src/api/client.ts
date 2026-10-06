import type {
  AesAttackRequest,
  AesAttackResponse,
  AesEncryptRequest,
  AesEncryptResponse,
  AesResources,
  ConfigResponse,
  EvaluationResponse,
  HealthResponse,
  MoscaInfo,
  MoscaRequest,
  MoscaResult,
  RsaAttackRequest,
  RsaAttackResponse,
  RsaEncryptRequest,
  RsaEncryptResponse,
  RsaKeygenRequest,
  RsaKeygenResponse,
  RsaResourceEstimate,
} from "./types";
import { assertNoSecrets } from "./payloads";

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

type MockEngine = typeof import("./mocks/engine");

/**
 * Mock mode answers from recorded engine responses. The fixtures are loaded on demand,
 * so a live deployment never downloads them.
 */
async function mock<T>(answer: (engine: MockEngine) => unknown, delayMs = MOCK_DELAY_MS): Promise<T> {
  const [engine] = await Promise.all([import("./mocks/engine"), new Promise((r) => setTimeout(r, delayMs))]);
  // Deep copy so callers can't mutate the fixtures.
  return JSON.parse(JSON.stringify(answer(engine))) as T;
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
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) {
    // A production build falls back to index.html for unknown paths: the endpoint is not there.
    throw new ApiError("This engine build does not provide this endpoint.", 404);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  if (MOCK_MODE) return mock(() => ({ status: "ok" }));
  return request("GET", "/health");
}

export function getConfig(): Promise<ConfigResponse> {
  if (MOCK_MODE) return mock((m) => m.config());
  return request("GET", "/config");
}

export function aesEncrypt(req: AesEncryptRequest): Promise<AesEncryptResponse> {
  if (MOCK_MODE) return mock((m) => m.aesEncrypt(req));
  return request("POST", "/aes/encrypt", req);
}

export function aesAttack(req: AesAttackRequest): Promise<AesAttackResponse> {
  assertNoSecrets(req); // last line of defence: never send a secret to /attack
  if (MOCK_MODE) return mock((m) => m.aesAttack(req));
  return request("POST", "/aes/attack", req);
}

export function rsaKeygen(req: RsaKeygenRequest): Promise<RsaKeygenResponse> {
  if (MOCK_MODE) return mock((m) => m.rsaKeygen(req));
  return request("POST", "/rsa/keygen", req);
}

export function rsaEncrypt(req: RsaEncryptRequest): Promise<RsaEncryptResponse> {
  if (MOCK_MODE) return mock((m) => m.rsaEncrypt(req));
  return request("POST", "/rsa/encrypt", req);
}

export function rsaAttack(req: RsaAttackRequest): Promise<RsaAttackResponse> {
  assertNoSecrets(req); // last line of defence: never send p, q, d, phi to /attack
  if (MOCK_MODE) return mock((m) => m.rsaAttack(req));
  return request("POST", "/rsa/attack", req);
}

/** Aggregated experiment series for the Evaluation page (read-only; runs no quantum work). */
export function getEvaluation(): Promise<EvaluationResponse> {
  if (MOCK_MODE) return mock((m) => m.evaluation());
  return request("GET", "/evaluation");
}

/** Defaults, explanation and citation for the Mosca calculator. */
export function getMoscaInfo(): Promise<MoscaInfo> {
  if (MOCK_MODE) return mock((m) => m.moscaInfo(), 200);
  return request("GET", "/risk/mosca");
}

export function postMosca(req: MoscaRequest): Promise<MoscaResult> {
  if (MOCK_MODE) return mock((m) => m.mosca(req), 150);
  return request("POST", "/risk/mosca", req);
}

/** Published, cited resource estimates for a Grover key search on real AES. */
export function getAesResources(): Promise<AesResources> {
  if (MOCK_MODE) return mock((m) => m.aesResources(), 200);
  return request("GET", "/aes/resources");
}

/** Published, cited resource estimates for factoring real-scale RSA. */
export function getRsaResourceEstimate(modulusBits: number): Promise<RsaResourceEstimate> {
  if (MOCK_MODE) return mock((m) => m.rsaResourceEstimate(), 200);
  return request("GET", `/rsa/resource-estimate?modulus_bits=${modulusBits}`);
}

/** Friendly message for any thrown value. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
