// Synthetic stand-in for the defence engine (/api/defence/*), used by mock mode and by
// scripts/gen-defence-mocks.ts to write the defence fixtures.
//
// Unlike the attack fixtures, these were NOT recorded from the live engine: the defence
// backend had not merged when the defence UI was built. So this file computes believable
// responses that follow the §7 contract exactly:
//   - AES-256-GCM is real (WebCrypto), with seeded key and nonce bytes;
//   - the ML-KEM-768 encapsulation key and KEM ciphertext are seeded RANDOM BYTES of the
//     standard sizes (1184 / 1088 B), not a real KEM;
//   - BB84 is a seeded classical Monte Carlo of the protocol's statistics, not Qiskit.
// Every response says so in its steps or evidence. Re-record from the live engine once it merges.

import type {
  Bb84Options,
  ComparisonRow,
  DefenceBundle,
  DefenceInfo,
  DefenceMethod,
  DefenceVerdict,
  EvaluationSeries,
  PhotonRow,
  ProtectRequest,
  ProtectResponse,
  ProtectResult,
  QkdSummary,
  ReattackRequest,
  ReattackResponse,
} from "../types";

export const MOCK_NOTE = "MOCK DATA: synthetic stand-in for the defence engine, not a recording of it.";

export const BB84_DEFAULTS: Bb84Options = {
  eve: false,
  eve_intercept_fraction: 1,
  channel_noise: 0,
  raw_qubits: 1024,
  qber_threshold: 0.11,
  seed: null,
};

const FINAL_KEY_BITS = 256;
const SAMPLE_FRACTION = 0.25;
const MLKEM_EK_BYTES = 1184;
const MLKEM_CT_BYTES = 1088;
const GCM_TAG_BYTES = 16;

// ---------- Seeded randomness ----------

/** mulberry32: small, fast, deterministic. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

function bytes(rand: () => number, n: number): Uint8Array {
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) out[i] = Math.floor(rand() * 256);
  return out;
}

function b64(u: Uint8Array): string {
  let s = "";
  for (const b of u) s += String.fromCharCode(b);
  return btoa(s);
}

async function aesGcm(key: Uint8Array, nonce: Uint8Array, plaintext: string): Promise<{ ct: Uint8Array; ok: boolean; ms: number }> {
  const t0 = performance.now();
  const k = await crypto.subtle.importKey("raw", key, "AES-GCM", false, ["encrypt", "decrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, k, new TextEncoder().encode(plaintext)));
  const ms = performance.now() - t0;
  const back = new TextDecoder().decode(await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, k, ct));
  return { ct, ok: back === plaintext, ms };
}

const round = (x: number, d = 3) => Number(x.toFixed(d));

// ---------- BB84 statistics ----------

export interface Bb84Run {
  qkd: QkdSummary;
  /** Public channel record: what Alice and Bob announce. */
  channel: { bob_bases: string; sample_positions: number[]; sample_values: number[] };
  key: Uint8Array | null;
  eveCount: number;
}

/** One intercept-resend BB84 exchange, as a classical Monte Carlo of the protocol. */
export function simulateBb84(o: Bb84Options, seed: number): Bb84Run {
  const rand = rng(seed);
  const basis = () => (rand() < 0.5 ? "Z" : "X");
  const rows: PhotonRow[] = [];
  let eveCount = 0;
  for (let i = 0; i < o.raw_qubits; i++) {
    const alice_bit = rand() < 0.5 ? 1 : 0;
    const alice_basis = basis();
    let bit = alice_bit;
    let prepBasis = alice_basis;
    let eve_basis: string | null = null;
    if (o.eve && rand() < o.eve_intercept_fraction) {
      eveCount++;
      eve_basis = basis();
      // Measuring in the wrong basis gives a random result; Eve re-sends what she saw.
      bit = eve_basis === prepBasis ? bit : rand() < 0.5 ? 1 : 0;
      prepBasis = eve_basis;
    }
    if (o.channel_noise > 0 && rand() < o.channel_noise) bit ^= 1;
    const bob_basis = basis();
    const bob_bit = bob_basis === prepBasis ? bit : rand() < 0.5 ? 1 : 0;
    const kept = bob_basis === alice_basis;
    rows.push({ alice_bit, alice_basis, eve_basis, bob_basis, bob_bit, kept, error: kept && bob_bit !== alice_bit });
  }
  const siftedIdx = rows.map((r, i) => (r.kept ? i : -1)).filter((i) => i >= 0);
  const sampleSize = Math.max(1, Math.round(siftedIdx.length * SAMPLE_FRACTION));
  // Sample positions: a seeded shuffle of the sifted positions.
  const shuffled = [...siftedIdx];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  const sample = shuffled.slice(0, sampleSize).sort((a, b) => a - b);
  const errors = sample.filter((i) => rows[i].error).length;
  const qber = sample.length ? errors / sample.length : 0;
  const remaining = siftedIdx.length - sample.length;
  let accepted = qber <= o.qber_threshold && remaining >= FINAL_KEY_BITS;
  let reason: string;
  if (qber > o.qber_threshold) {
    accepted = false;
    reason = `QBER ${(qber * 100).toFixed(1)}% is above the ${(o.qber_threshold * 100).toFixed(0)}% threshold: an eavesdropper (or a very noisy channel) disturbed the photons. The key is discarded.`;
  } else if (remaining < FINAL_KEY_BITS) {
    reason = `Only ${remaining} sifted bits remain after sampling, fewer than the ${FINAL_KEY_BITS} needed. Send more raw qubits.`;
  } else {
    reason = `QBER ${(qber * 100).toFixed(1)}% is within the ${(o.qber_threshold * 100).toFixed(0)}% threshold. After reconciliation and privacy amplification, a ${FINAL_KEY_BITS}-bit key is shared.`;
  }
  return {
    qkd: {
      raw_bits: o.raw_qubits,
      sifted_bits: siftedIdx.length,
      sample_bits: sample.length,
      final_key_bits: accepted ? FINAL_KEY_BITS : 0,
      qber: round(qber, 4),
      qber_threshold: o.qber_threshold,
      accepted,
      reason,
      photon_preview: rows.slice(0, 16),
    },
    channel: {
      bob_bases: rows.map((r) => r.bob_basis).join(""),
      sample_positions: sample,
      sample_values: sample.map((i) => rows[i].alice_bit),
    },
    key: accepted ? bytes(rand, 32) : null,
    eveCount,
  };
}

// ---------- Info ----------

export function info(maxTextChars: number): DefenceInfo {
  return {
    methods: [
      {
        id: "aes256",
        name: "AES-256",
        description: "Symmetric encryption with a key big enough that Grover's quadratic speed-up still leaves 128-bit security.",
        kind: "Real AES-256-GCM encryption",
      },
      {
        id: "mlkem",
        name: "ML-KEM-768",
        description: "NIST's post-quantum key-encapsulation standard (FIPS 203): a lattice-based key exchange, then AES-256-GCM.",
        kind: "Real KEM + AES-256-GCM (educational implementation)",
      },
      {
        id: "bb84",
        name: "BB84 QKD",
        description: "Quantum key distribution: photons in random bases, so an eavesdropper leaves detectable errors.",
        kind: "Simulated in Qiskit; its 256-bit key drives AES-256-GCM",
      },
    ],
    comparison_rows: STATIC_ROWS,
    citations: CITATIONS,
    bb84: {
      defaults: BB84_DEFAULTS,
      limits: {
        raw_qubits_min: 256,
        raw_qubits_max: 4096,
        eve_intercept_fraction_min: 0,
        eve_intercept_fraction_max: 1,
        channel_noise_min: 0,
        channel_noise_max: 0.25,
        qber_threshold_min: 0.01,
        qber_threshold_max: 0.25,
      },
    },
    honesty_notes: [
      "AES-256 and ML-KEM really encrypt your message; the round trip is checked on the server.",
      "BB84 is a faithful simulation in Qiskit. Real QKD needs a photon source and a quantum channel.",
      "The ML-KEM implementation is an educational implementation of FIPS 203, not a vetted constant-time production library.",
      "ML-KEM has no known efficient quantum attack. That is not the same as proven unbreakable.",
    ],
    max_text_chars: maxTextChars,
  };
}

const CITATIONS: Record<string, string> = {
  FIPS203: "NIST, \"Module-Lattice-Based Key-Encapsulation Mechanism Standard\", FIPS 203, August 2024.",
  BB84: "C. H. Bennett, G. Brassard, \"Quantum cryptography: Public key distribution and coin tossing\", Proc. IEEE ICCSSP, 1984.",
  GLRS16: "M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, \"Applying Grover's algorithm to AES: quantum resource estimates\", PQCrypto 2016, arXiv:1512.04965.",
  NIST16: "NIST, \"Submission Requirements and Evaluation Criteria for the Post-Quantum Cryptography Standardization Process\", 2016, Section 4.A.5.",
};

const STATIC_ROWS: ComparisonRow[] = [
  {
    label: "Quantum-safe, and why",
    aes256: "Yes: Grover only halves effective strength, to about 128-bit",
    mlkem: "Yes: lattice problem (Module-LWE), no known quantum attack",
    bb84: "Yes: physics, measuring a photon disturbs it",
  },
  { label: "Detects eavesdroppers", aes256: "No", mlkem: "No", bb84: "Yes (QBER)" },
  { label: "Key-exchange problem solved", aes256: "No: needs a way to share the key", mlkem: "Yes", bb84: "Yes" },
  { label: "Special hardware", aes256: "None", mlkem: "None", bb84: "Photon source + quantum channel" },
  { label: "Distance", aes256: "Unlimited", mlkem: "Unlimited", bb84: "~100 km fibre without trusted relays" },
  { label: "Maturity", aes256: "Standard for decades", mlkem: "NIST FIPS 203 (2024)", bb84: "Niche deployments" },
];

// ---------- Protect ----------

export async function protect(req: ProtectRequest): Promise<ProtectResponse> {
  const o: Bb84Options = { ...BB84_DEFAULTS, ...req.bb84 };
  const seed = o.seed ?? hashSeed(JSON.stringify([req.plaintext, o]));
  const rand = rng(seed ^ 0x5eed);
  const ptBytes = new TextEncoder().encode(req.plaintext).length;
  const results: ProtectResponse["results"] = {};

  if (req.methods.includes("aes256")) {
    const key = bytes(rand, 32);
    const nonce = bytes(rand, 12);
    const { ct, ok, ms } = await aesGcm(key, nonce, req.plaintext);
    results.aes256 = {
      method: "aes256",
      status: "protected",
      bundle: { ciphertext_b64: b64(ct), nonce_b64: b64(nonce) },
      sizes: { plaintext_bytes: ptBytes, key_bytes: 32, nonce_bytes: 12, ciphertext_bytes: ct.length },
      timings_ms: { keygen: 0.02, encrypt: round(ms), decrypt: round(ms * 0.8) },
      roundtrip_ok: ok,
      steps: [
        "Generated a fresh random 256-bit key and 96-bit nonce (kept on the organization's side).",
        `Encrypted ${ptBytes} bytes with AES-256-GCM: ${ct.length} bytes of ciphertext including the ${GCM_TAG_BYTES}-byte tag.`,
        `Decrypted on the organization's side: round trip ${ok ? "matches" : "FAILED"}.`,
        MOCK_NOTE,
      ],
    };
  }

  if (req.methods.includes("mlkem")) {
    const ek = bytes(rand, MLKEM_EK_BYTES);
    const kct = bytes(rand, MLKEM_CT_BYTES);
    const key = bytes(rand, 32);
    const nonce = bytes(rand, 12);
    const { ct, ok, ms } = await aesGcm(key, nonce, req.plaintext);
    results.mlkem = {
      method: "mlkem",
      status: "protected",
      parameter_set: "ML-KEM-768",
      bundle: { ciphertext_b64: b64(ct), nonce_b64: b64(nonce), encapsulation_key_b64: b64(ek), kem_ciphertext_b64: b64(kct) },
      sizes: {
        plaintext_bytes: ptBytes,
        encapsulation_key_bytes: ek.length,
        kem_ciphertext_bytes: kct.length,
        shared_secret_bytes: 32,
        ciphertext_bytes: ct.length,
      },
      timings_ms: { keygen: 41.2, encaps: 48.7, encrypt: round(ms), decaps: 55.3 },
      roundtrip_ok: ok,
      steps: [
        "Receiver generated an ML-KEM-768 key pair: the encapsulation key is public, the decapsulation key stays private.",
        "Sender encapsulated against the public key: a 32-byte shared secret and a KEM ciphertext.",
        "Derived an AES-256-GCM key from the shared secret with HKDF-SHA256 and encrypted the message.",
        `Receiver decapsulated, re-derived the key and decrypted: round trip ${ok ? "matches" : "FAILED"}.`,
        "Educational implementation of FIPS 203, not a vetted constant-time production library.",
        `${MOCK_NOTE} The encapsulation key and KEM ciphertext here are random bytes of the standard sizes.`,
      ],
    };
  }

  if (req.methods.includes("bb84")) {
    const run = simulateBb84(o, seed);
    let bundle: DefenceBundle | null = null;
    let sizes: ProtectResult["sizes"] = { plaintext_bytes: ptBytes, raw_qubits: o.raw_qubits, sifted_bits: run.qkd.sifted_bits };
    let ok = false;
    let encMs = 0;
    if (run.key) {
      const nonce = bytes(rand, 12);
      const enc = await aesGcm(run.key, nonce, req.plaintext);
      ok = enc.ok;
      encMs = enc.ms;
      bundle = { ciphertext_b64: b64(enc.ct), nonce_b64: b64(nonce), channel: run.channel };
      sizes = { ...sizes, key_bytes: 32, ciphertext_bytes: enc.ct.length };
    }
    results.bb84 = {
      method: "bb84",
      status: run.qkd.accepted ? "protected" : "aborted",
      bundle,
      qkd: run.qkd,
      evidence: bb84Evidence(o, run),
      sizes,
      timings_ms: { qkd_simulation: round(o.raw_qubits * 0.21, 1), sifting: 0.4, encrypt: round(encMs) },
      roundtrip_ok: ok,
      steps: [
        `Alice prepared ${o.raw_qubits} qubits, each a random bit in a random basis (Z or X).`,
        o.eve
          ? `Eve intercepted ${run.eveCount} photons (${Math.round(o.eve_intercept_fraction * 100)}%), measured each in a random basis and re-sent what she saw.`
          : "No eavesdropper on the channel.",
        `Bob measured in random bases. Sifting kept ${run.qkd.sifted_bits} positions where the bases matched.`,
        `They compared a public sample of ${run.qkd.sample_bits} bits: QBER ${(run.qkd.qber * 100).toFixed(1)}%.`,
        run.qkd.accepted
          ? `Reconciliation and privacy amplification (SHA-256) gave a ${FINAL_KEY_BITS}-bit key, which encrypted the message with AES-256-GCM: round trip ${ok ? "matches" : "FAILED"}.`
          : "Key discarded: no ciphertext was produced.",
        `${MOCK_NOTE} The photon statistics come from a classical Monte Carlo, not a Qiskit run.`,
      ],
    };
  }
  return { results };
}

function bb84Evidence(o: Bb84Options, run: Bb84Run): Record<string, unknown> {
  const p = run.qkd.photon_preview[0];
  const prep = [p.alice_bit ? "x q[0];" : null, p.alice_basis === "X" ? "h q[0];" : null].filter(Boolean);
  const meas = [p.bob_basis === "X" ? "h q[0];" : null, "measure q[0] -> c[0];"].filter(Boolean);
  const box = (g: string | null) => (g ? `┤ ${g} ├` : "─────");
  const drawing = [
    `photon 0: Alice bit ${p.alice_bit} in basis ${p.alice_basis}, Bob measures in basis ${p.bob_basis}`,
    "     ┌───┐┌───┐   ┌───┐┌─┐",
    `q: ─${box(p.alice_bit ? "X" : null)}${box(p.alice_basis === "X" ? "H" : null)}─░─${box(p.bob_basis === "X" ? "H" : null)}┤M├`,
    "     └───┘└───┘ ░ └───┘└╥┘",
    "c: 1/════════════════════╩═",
    "      Alice prepares  │ channel │  Bob measures",
  ].join("\n");
  return {
    simulator_method: "stabilizer",
    qubits_per_circuit: 1,
    num_circuits: o.raw_qubits * (o.eve ? 2 : 1),
    eve_intercepted: run.eveCount,
    theory_qber: round((o.eve ? o.eve_intercept_fraction : 0) / 4 + o.channel_noise / 2, 4),
    example_circuit: {
      title: "Photon 0: prepare, send, measure",
      drawing,
      qasm: ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[1];", "creg c[1];", ...prep, "barrier q[0];", ...meas].join("\n"),
    },
    note: `${MOCK_NOTE} The circuit is the one the live engine runs for photon 0; the statistics are classical.`,
  };
}

// ---------- Re-attack ----------

interface AesRealScale {
  grover_iterations?: { text?: string; formula?: string; log2?: number; source?: string };
  logical_qubits?: { value?: number | null; source?: string };
  t_depth?: { text?: string; source?: string };
}

const bundleBytes = (b: DefenceBundle | null | undefined, field: string): number | null => {
  const v = b?.[field];
  return typeof v === "string" ? atob(v).length : null;
};

export function reattack(req: ReattackRequest, aes256: AesRealScale | undefined): ReattackResponse {
  const verdicts: ReattackResponse["verdicts"] = {};
  if ("aes256" in req.bundles) {
    verdicts.aes256 = {
      method: "aes256",
      attack: "Grover key search",
      executed: false,
      verdict: "infeasible",
      explanation:
        "A Grover search over 2^256 keys needs about π/4 · 2^128 sequential iterations on thousands of error-corrected logical qubits. No simulator or existing machine comes close, so no circuit was run; the numbers below are the cited estimate.",
      evidence: {
        key_bits: 256,
        grover_iterations: aes256?.grover_iterations?.text ?? "≈ 2^127.7",
        grover_formula: aes256?.grover_iterations?.formula ?? "⌊π/4 · 2^128⌋",
        logical_qubits: aes256?.logical_qubits?.value ?? null,
        t_depth: aes256?.t_depth?.text ?? null,
        simulator_ceiling_qubits: 32,
        effective_quantum_security_bits: 128,
        ciphertext_bytes: bundleBytes(req.bundles.aes256, "ciphertext_b64"),
      },
      citations: [CITATIONS.GLRS16, CITATIONS.NIST16],
    };
  }
  if ("mlkem" in req.bundles) {
    verdicts.mlkem = {
      method: "mlkem",
      attack: "Shor's algorithm (applicability check)",
      executed: false,
      verdict: "not_applicable",
      explanation:
        "The Shor pipeline's input stage found no RSA modulus and no factoring or period structure in the bundle, so there is nothing for Shor to attack. ML-KEM rests on the Module-LWE lattice problem, for which no efficient quantum algorithm is known.",
      evidence: {
        shor_input_stage: "no RSA modulus or group-order structure in the public bundle",
        hard_problem: "Module-LWE (lattice)",
        parameter_set: "ML-KEM-768",
        encapsulation_key_bytes: bundleBytes(req.bundles.mlkem, "encapsulation_key_b64"),
        kem_ciphertext_bytes: bundleBytes(req.bundles.mlkem, "kem_ciphertext_b64"),
      },
      citations: [CITATIONS.FIPS203],
    };
  }
  if ("bb84" in req.bundles) {
    const a = req.bb84_attack;
    const o: Bb84Options = { ...BB84_DEFAULTS, eve: true, eve_intercept_fraction: a.eve_intercept_fraction, channel_noise: a.channel_noise, seed: a.seed };
    const run = simulateBb84(o, a.seed ?? hashSeed(JSON.stringify(a)) ^ 0xbb84);
    const detected = run.qkd.qber > o.qber_threshold;
    const leak = Math.round((a.eve_intercept_fraction / 2) * run.qkd.sifted_bits);
    verdicts.bb84 = {
      method: "bb84",
      attack: "Intercept-resend eavesdropping on the key exchange",
      executed: true,
      verdict: detected ? "detected" : "undetected_low_intercept",
      explanation: detected
        ? `Eve intercepted ${Math.round(a.eve_intercept_fraction * 100)}% of the photons. Her wrong-basis measurements pushed the QBER to ${(run.qkd.qber * 100).toFixed(1)}%, above the ${(o.qber_threshold * 100).toFixed(0)}% threshold, so Alice and Bob discarded the key: she gains nothing usable.`
        : `At a ${Math.round(a.eve_intercept_fraction * 100)}% intercept the QBER stayed at ${(run.qkd.qber * 100).toFixed(1)}%, under the threshold, so the exchange went ahead. Eve saw about ${leak} sifted bits in the matching basis; privacy amplification hashes the key so that partial knowledge is removed.`,
      evidence: {
        eve_intercept_fraction: a.eve_intercept_fraction,
        channel_noise: a.channel_noise,
        raw_bits: run.qkd.raw_bits,
        sifted_bits: run.qkd.sifted_bits,
        qber: run.qkd.qber,
        qber_threshold: o.qber_threshold,
        theory_qber: round(a.eve_intercept_fraction / 4 + a.channel_noise / 2, 4),
        key_discarded: detected,
        expected_leak_bits: detected ? 0 : leak,
        note: `${MOCK_NOTE} Classical Monte Carlo of the exchange, not a Qiskit run.`,
      },
      citations: [CITATIONS.BB84],
    };
  }

  const label = (v: DefenceVerdict | undefined) =>
    !v ? "Not run" : ({ infeasible: "Infeasible", not_applicable: "Not applicable", detected: "Detected", undetected_low_intercept: "Undetected (low intercept)" } as Record<string, string>)[v.verdict] ?? v.verdict;
  const kb = (n: number | null) => (n == null ? "—" : `${n.toLocaleString()} B`);
  const rows: ComparisonRow[] = [
    STATIC_ROWS[0],
    { label: "Re-attack verdict", aes256: label(verdicts.aes256), mlkem: label(verdicts.mlkem), bb84: label(verdicts.bb84) },
    ...STATIC_ROWS.slice(1, 5),
    {
      label: "Overhead (measured)",
      aes256: `key 32 B, ciphertext ${kb(bundleBytes(req.bundles.aes256, "ciphertext_b64"))}`,
      mlkem: `public key ${kb(bundleBytes(req.bundles.mlkem, "encapsulation_key_b64"))}, KEM ct ${kb(bundleBytes(req.bundles.mlkem, "kem_ciphertext_b64"))}, ciphertext ${kb(bundleBytes(req.bundles.mlkem, "ciphertext_b64"))}`,
      bb84: req.bundles.bb84
        ? `ciphertext ${kb(bundleBytes(req.bundles.bb84, "ciphertext_b64"))}, ~4 raw qubits per key bit`
        : "no ciphertext: key discarded",
    },
    STATIC_ROWS[5],
  ];

  return {
    verdicts,
    comparison: { rows },
    recommendation: {
      text:
        "Use ML-KEM for key exchange over ordinary networks and AES-256 for the data itself: together they are what ML-KEM + AES-256-GCM already does here. Add BB84 only on high-security fixed links where photon hardware exists and detecting an eavesdropper matters.",
      rule: "default: mlkem_key_exchange + aes256_data; bb84 if fixed_link and photon_hardware",
    },
  };
}

// ---------- Evaluation series ----------

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length);
}

export function evaluationSeries(): Record<string, EvaluationSeries> {
  const seeds = [11, 22, 33, 44, 55];
  const run = (o: Partial<Bb84Options>, s: number) => simulateBb84({ ...BB84_DEFAULTS, ...o }, s);

  const vsEve = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].map((f) => ({
    eve_intercept_fraction: f,
    qber: round(mean(seeds.map((s) => run({ eve: f > 0, eve_intercept_fraction: f }, s).qkd.qber)), 4),
    theory: round(f / 4, 4),
    qber_threshold: BB84_DEFAULTS.qber_threshold,
    runs: seeds.length,
  }));
  const vsNoise = [0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.12, 0.15, 0.2].map((p) => ({
    channel_noise: p,
    qber: round(mean(seeds.map((s) => run({ channel_noise: p }, s).qkd.qber)), 4),
    qber_threshold: BB84_DEFAULTS.qber_threshold,
    runs: seeds.length,
  }));
  const keyRate = [256, 512, 1024, 2048, 4096].map((n) => {
    const rs = seeds.map((s) => run({ raw_qubits: n }, s).qkd);
    const finalBits = mean(rs.map((q) => q.final_key_bits));
    return {
      raw_qubits: n,
      sifted_bits: round(mean(rs.map((q) => q.sifted_bits)), 1),
      final_key_bits: round(finalBits, 1),
      key_rate: round(finalBits / n, 4),
      accepted_rate: round(mean(rs.map((q) => (q.accepted ? 1 : 0))), 2),
      runs: seeds.length,
    };
  });
  const overhead: Record<string, number | string>[] = [
    { method: "aes256", public_bytes: 0, ciphertext_bytes: 26, key_bytes: 32, total_ms: 0.21, runs: 5 },
    { method: "mlkem", public_bytes: MLKEM_EK_BYTES + MLKEM_CT_BYTES, ciphertext_bytes: 26, key_bytes: 32, total_ms: 145.3, runs: 5 },
    { method: "bb84", public_bytes: 0, ciphertext_bytes: 26, key_bytes: 32, raw_qubits: 1024, total_ms: 215.9, runs: 5 },
  ];
  const desc = (d: string) => `${d} ${MOCK_NOTE}`;
  return {
    bb84_qber_vs_eve: { series: "bb84_qber_vs_eve", empty: false, rows: vsEve, description: desc("QBER as the eavesdropper intercepts a growing fraction of photons, against the fraction/4 theory.") },
    bb84_qber_vs_noise: { series: "bb84_qber_vs_noise", empty: false, rows: vsNoise, description: desc("QBER as channel bit-flip noise rises, with no eavesdropper, against the 11% abort threshold.") },
    bb84_key_rate: { series: "bb84_key_rate", empty: false, rows: keyRate, description: desc("Final key bits per raw qubit, no eavesdropper and no noise.") },
    defence_overhead: { series: "defence_overhead", empty: false, rows: overhead, description: desc("Bytes on the wire and time per method for a 10-character message.") },
  };
}

export type { DefenceMethod };
