import { describe, expect, it } from "vitest";
import { assertNoSecretsDeep, buildReattackRequest, SecretLeakError } from "./payloads";
import type { ProtectResponse } from "./types";

const base = {
  sizes: { plaintext_bytes: 10, ciphertext_bytes: 26 },
  timings_ms: { encrypt: 0.1 },
  roundtrip_ok: true,
  steps: ["Encrypted with AES-256-GCM"],
};

/** A protect response that (wrongly) carries secrets in and around its bundles. */
const leaky = {
  results: {
    aes256: {
      ...base,
      method: "aes256",
      status: "protected",
      bundle: { ciphertext_b64: "Y3Q=", nonce_b64: "bm9uY2U=", aes_key: "SECRET", key: "SECRET" },
    },
    mlkem: {
      ...base,
      method: "mlkem",
      status: "protected",
      parameter_set: "ML-KEM-768",
      bundle: {
        ciphertext_b64: "Y3Q=",
        nonce_b64: "bm9uY2U=",
        encapsulation_key_b64: "ZWs=",
        kem_ciphertext_b64: "a2N0",
        shared_secret: "SECRET",
        decapsulation_key_b64: "SECRET",
      },
    },
    bb84: {
      ...base,
      method: "bb84",
      status: "aborted",
      bundle: null,
      qkd: { final_key_bits: 0, qber: 0.25, accepted: false },
      plaintext: "SECRET",
    },
  },
} as unknown as ProtectResponse;

describe("re-attack payload is blind", () => {
  it("sends only the bundle objects and strips secret fields at any depth", () => {
    const { request, dropped } = buildReattackRequest(leaky, {
      bb84_attack: { eve_intercept_fraction: 1, channel_noise: 0, seed: null },
      original_attack: { cipher: "miniaes", verdict: "breached" },
    });
    expect(Object.keys(request).sort()).toEqual(["bb84_attack", "bundles", "original_attack"]);
    expect(request.bundles.aes256).toEqual({ ciphertext_b64: "Y3Q=", nonce_b64: "bm9uY2U=" });
    expect(request.bundles.mlkem).toEqual({
      ciphertext_b64: "Y3Q=",
      nonce_b64: "bm9uY2U=",
      encapsulation_key_b64: "ZWs=",
      kem_ciphertext_b64: "a2N0",
    });
    expect(request.bundles.bb84).toBeNull();
    expect(dropped.sort()).toEqual(
      ["bundles.aes256.aes_key", "bundles.aes256.key", "bundles.mlkem.decapsulation_key_b64", "bundles.mlkem.shared_secret"].sort(),
    );
    const wire = JSON.stringify(request);
    expect(wire).not.toContain("SECRET");
    for (const f of ["sizes", "timings_ms", "steps", "qkd", "roundtrip_ok", "plaintext"]) expect(wire).not.toContain(`"${f}"`);
  });

  it("strips nested secrets inside the BB84 channel record", () => {
    const resp = {
      results: {
        bb84: {
          ...base,
          method: "bb84",
          status: "protected",
          bundle: { ciphertext_b64: "Y3Q=", channel: { alice_bases: "ZX", sample_positions: [1], final_key: "SECRET" } },
        },
      },
    } as unknown as ProtectResponse;
    const { request } = buildReattackRequest(resp, { bb84_attack: { eve_intercept_fraction: 1, channel_noise: 0, seed: 7 } });
    expect(JSON.stringify(request)).not.toContain("SECRET");
    expect(request.bundles.bb84).toEqual({ ciphertext_b64: "Y3Q=", channel: { alice_bases: "ZX", sample_positions: [1] } });
    expect(request.original_attack).toBeUndefined();
  });

  it("deep assertion catches a smuggled secret", () => {
    expect(() => assertNoSecretsDeep({ bundles: { aes256: { nested: { shared_secret: "x" } } } })).toThrow(SecretLeakError);
    expect(() => assertNoSecretsDeep({ bundles: { aes256: { ciphertext_b64: "x" } } })).not.toThrow();
  });
});
