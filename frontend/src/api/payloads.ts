// Builders for the ADVERSARY's requests.
//
// Integrity rule: the attacker payload is built ONLY from what crossed the interception
// wall (ciphertext, public parameters, known plaintext). These builders take narrow
// "intercepted" types that have no slot for a secret, copy fields explicitly (no spread
// of organization state), and then assert at runtime that no secret-named field exists.

import type {
  AesAttackRequest,
  AttackCondition,
  DefenceBundle,
  DefenceMethod,
  ProtectResponse,
  ReattackRequest,
  RsaAttackRequest,
} from "./types";

/** What the adversary captured in the symmetric test. No key. */
export interface InterceptedAes {
  key_bits: number;
  ciphertext_nibbles: number[];
  /** Empty when the attack mode is ciphertext-only. */
  known_plaintext: string;
  /** The attack mode. Absent for engines that predate the mode selector. */
  condition?: AttackCondition;
}

/** What the adversary captured in the public-key test. No p, q, phi, d. */
export interface InterceptedRsa {
  n: number;
  e: number;
  ciphertext: number[];
  bit_length: number;
}

export const FORBIDDEN_ATTACK_FIELDS = [
  "key",
  "secret",
  "victim_secret",
  "p",
  "q",
  "d",
  "phi",
  "factors",
] as const;

export class SecretLeakError extends Error {}

/** Throws if any forbidden (secret) field name is present in an attacker payload. */
export function assertNoSecrets(payload: object): void {
  const present = Object.keys(payload).filter((k) =>
    (FORBIDDEN_ATTACK_FIELDS as readonly string[]).includes(k),
  );
  if (present.length > 0) {
    throw new SecretLeakError(
      `Attacker payload must not contain secrets; found: ${present.join(", ")}`,
    );
  }
}

export function buildAesAttackRequest(
  intercepted: InterceptedAes,
  opts: { shots: number; seed: number | null; noise_p?: number },
): AesAttackRequest {
  const ciphertextOnly = intercepted.condition === "ciphertext_only";
  const req: AesAttackRequest = {
    key_bits: intercepted.key_bits,
    known_plaintext: ciphertextOnly ? null : intercepted.known_plaintext,
    ciphertext_nibbles: [...intercepted.ciphertext_nibbles],
    shots: opts.shots,
    seed: opts.seed,
  };
  // Optional fields are added only when set, so engines that predate them still accept the request.
  if (intercepted.condition !== undefined) req.condition = intercepted.condition;
  if (opts.noise_p !== undefined) req.noise_p = opts.noise_p;
  assertNoSecrets(req);
  return req;
}

export function buildRsaAttackRequest(
  intercepted: InterceptedRsa,
  opts: { a: number | null; shots: number; seed: number | null; construction?: string; noise_p?: number },
): RsaAttackRequest {
  const req: RsaAttackRequest = {
    n: intercepted.n,
    e: intercepted.e,
    ciphertext: [...intercepted.ciphertext],
    bit_length: intercepted.bit_length,
    a: opts.a,
    shots: opts.shots,
    seed: opts.seed,
  };
  if (opts.construction !== undefined) req.construction = opts.construction;
  if (opts.noise_p !== undefined) req.noise_p = opts.noise_p;
  assertNoSecrets(req);
  return req;
}

// ---------- Defence re-attack ----------
//
// The re-attack is the same blind adversary: it receives ONLY the public `bundle` of each
// protect result. Sizes, timings, steps, the QKD summary and evidence stay on the
// organization's side, and any secret-looking field inside a bundle is stripped.

/** Field names that must never reach /api/defence/reattack, at any depth. */
export const FORBIDDEN_BUNDLE_FIELDS = [
  ...FORBIDDEN_ATTACK_FIELDS,
  "plaintext",
  "message",
  "aes_key",
  "key_b64",
  "key_hex",
  "shared_secret",
  "shared_secret_b64",
  "decapsulation_key",
  "decapsulation_key_b64",
  "private_key",
  "secret_key",
  "final_key",
  "sifted_key",
  "raw_key",
  "alice_bits",
  "bob_bits",
  "bb84_key",
] as const;

function isForbidden(field: string): boolean {
  return (FORBIDDEN_BUNDLE_FIELDS as readonly string[]).includes(field.toLowerCase());
}

/** Deep copy of `value` with every forbidden field removed. Records which ones were dropped. */
function stripSecrets(value: unknown, path: string, dropped: string[]): unknown {
  if (Array.isArray(value)) return value.map((v, i) => stripSecrets(v, `${path}[${i}]`, dropped));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      if (isForbidden(k)) {
        dropped.push(`${path}.${k}`);
        continue;
      }
      out[k] = stripSecrets(v, `${path}.${k}`, dropped);
    }
    return out;
  }
  return value;
}

/** Throws if a forbidden field name appears anywhere in the payload. */
export function assertNoSecretsDeep(payload: unknown, path = "payload"): void {
  const found: string[] = [];
  stripSecrets(payload, path, found);
  if (found.length > 0) throw new SecretLeakError(`Re-attack payload must not contain secrets; found: ${found.join(", ")}`);
}

export const DEFENCE_METHODS: readonly DefenceMethod[] = ["aes256", "mlkem", "bb84"];

/**
 * Builds the blind re-attack request from a protect response: copies each result's `bundle`
 * (and nothing else), strips secret-named fields, then asserts none survived.
 */
export function buildReattackRequest(
  protect: ProtectResponse,
  opts: {
    bb84_attack: ReattackRequest["bb84_attack"];
    original_attack?: ReattackRequest["original_attack"];
  },
): { request: ReattackRequest; dropped: string[] } {
  const dropped: string[] = [];
  const bundles: ReattackRequest["bundles"] = {};
  for (const m of DEFENCE_METHODS) {
    const result = protect.results[m];
    if (!result) continue;
    bundles[m] = result.bundle ? (stripSecrets(result.bundle, `bundles.${m}`, dropped) as DefenceBundle) : null;
  }
  const request: ReattackRequest = {
    bundles,
    bb84_attack: {
      eve_intercept_fraction: opts.bb84_attack.eve_intercept_fraction,
      channel_noise: opts.bb84_attack.channel_noise,
      seed: opts.bb84_attack.seed,
    },
  };
  if (opts.original_attack) request.original_attack = { cipher: opts.original_attack.cipher, verdict: opts.original_attack.verdict };
  assertNoSecretsDeep(request);
  return { request, dropped };
}
