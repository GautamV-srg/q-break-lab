import { describe, expect, it } from "vitest";
import {
  assertNoSecrets,
  buildAesAttackRequest,
  buildRsaAttackRequest,
  FORBIDDEN_ATTACK_FIELDS,
  SecretLeakError,
} from "./payloads";

describe("attacker payloads contain no secrets", () => {
  it("AES attack request has exactly the contract fields and no key", () => {
    // Intercepted object is (wrongly) carrying extra organization state on purpose:
    // the builder must not copy it through.
    const leaky = {
      key_bits: 4,
      ciphertext_nibbles: [3, 8, 14, 13],
      known_plaintext: "Hi ",
      key: "1001",
    };
    const req = buildAesAttackRequest(leaky, { shots: 1024, seed: null });
    expect(Object.keys(req).sort()).toEqual(
      ["ciphertext_nibbles", "key_bits", "known_plaintext", "seed", "shots"].sort(),
    );
    expect(JSON.stringify(req)).not.toContain('"key"');
  });

  it("RSA attack request has exactly the contract fields and no p, q, d, phi", () => {
    const leaky = {
      n: 15,
      e: 3,
      ciphertext: [8, 8, 0, 6, 4, 4],
      bit_length: 16,
      p: 3,
      q: 5,
      d: 3,
      phi: 8,
    };
    const req = buildRsaAttackRequest(leaky, { a: 7, shots: 1024, seed: 1 });
    expect(Object.keys(req).sort()).toEqual(
      ["a", "bit_length", "ciphertext", "e", "n", "seed", "shots"].sort(),
    );
    for (const f of FORBIDDEN_ATTACK_FIELDS) expect(req).not.toHaveProperty(f);
  });

  it("AES attack request carries the attack mode and noise, and still no key", () => {
    const leaky = {
      key_bits: 4,
      ciphertext_nibbles: [3, 8, 14, 13],
      known_plaintext: "ignored",
      condition: "ciphertext_only" as const,
      key: "1001",
    };
    const req = buildAesAttackRequest(leaky, { shots: 256, seed: 7, noise_p: 0.01 });
    expect(Object.keys(req).sort()).toEqual(
      ["ciphertext_nibbles", "condition", "key_bits", "known_plaintext", "noise_p", "seed", "shots"].sort(),
    );
    // Ciphertext-only sends no known plaintext at all.
    expect(req.known_plaintext).toBeNull();
    expect(req.condition).toBe("ciphertext_only");
    for (const f of FORBIDDEN_ATTACK_FIELDS) expect(req).not.toHaveProperty(f);

    const substring = buildAesAttackRequest(
      { key_bits: 4, ciphertext_nibbles: [3, 8], known_plaintext: "jud", condition: "known_substring" },
      { shots: 1024, seed: null },
    );
    expect(substring.known_plaintext).toBe("jud");
    expect(substring).not.toHaveProperty("noise_p");
  });

  it("RSA attack request carries construction and noise, and still no p, q, d, phi", () => {
    const leaky = { n: 15, e: 3, ciphertext: [8, 8], bit_length: 6, p: 3, q: 5, d: 3, phi: 8 };
    const req = buildRsaAttackRequest(leaky, { a: null, shots: 512, seed: 2, construction: "iterative", noise_p: 0.02 });
    expect(Object.keys(req).sort()).toEqual(
      ["a", "bit_length", "ciphertext", "construction", "e", "n", "noise_p", "seed", "shots"].sort(),
    );
    for (const f of FORBIDDEN_ATTACK_FIELDS) expect(req).not.toHaveProperty(f);
  });

  it("assertNoSecrets rejects payloads with secret fields", () => {
    expect(() => assertNoSecrets({ n: 15, d: 3 })).toThrow(SecretLeakError);
    expect(() => assertNoSecrets({ key_bits: 4, key: "1001" })).toThrow(SecretLeakError);
    expect(() => assertNoSecrets({ key_bits: 4 })).not.toThrow();
  });
});
