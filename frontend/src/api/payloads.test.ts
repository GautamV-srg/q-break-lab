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

  it("assertNoSecrets rejects payloads with secret fields", () => {
    expect(() => assertNoSecrets({ n: 15, d: 3 })).toThrow(SecretLeakError);
    expect(() => assertNoSecrets({ key_bits: 4, key: "1001" })).toThrow(SecretLeakError);
    expect(() => assertNoSecrets({ key_bits: 4 })).not.toThrow();
  });
});
