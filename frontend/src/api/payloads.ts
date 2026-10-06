// Builders for the ADVERSARY's requests.
//
// Integrity rule: the attacker payload is built ONLY from what crossed the interception
// wall (ciphertext, public parameters, known plaintext). These builders take narrow
// "intercepted" types that have no slot for a secret, copy fields explicitly (no spread
// of organization state), and then assert at runtime that no secret-named field exists.

import type { AesAttackRequest, AttackCondition, RsaAttackRequest } from "./types";

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
