// Mock engine: answers API calls from responses RECORDED from the real Q-Break engine
// (see README.md in this folder), so the UI can be demoed with no backend.
//
// For the recorded message and keys every answer is a verbatim engine response. For other
// inputs the nearest recording is relabelled (the organization's key and message are
// remembered from the mock "encrypt" call, standing in for the real engine's ability to
// recover them), and the response carries a warning saying so.

import type {
  AesAttackRequest,
  AesAttackResponse,
  AesEncryptRequest,
  AesEncryptResponse,
  AesResources,
  AttackCondition,
  ConfigResponse,
  EvaluationResponse,
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
} from "../types";
import { MOCK_KEYS, MOCK_MESSAGE } from "./demo";

import configFixture from "./config.json";
import aesEncryptFixture from "./aes_encrypt.json";
import aesAttackFixture from "./aes_attack.json";
import aesNoiseFixture from "./aes_noise.json";
import rsaKeygenFixture from "./rsa_keygen.json";
import rsaEncryptFixture from "./rsa_encrypt.json";
import rsaAttackFixture from "./rsa_attack.json";
import rsaNoiseFixture from "./rsa_noise.json";
import evaluationFixture from "./evaluation.json";
import moscaInfoFixture from "./mosca_info.json";
import aesResourcesFixture from "./aes_resources.json";
import rsaResourceFixture from "./rsa_resource_estimate.json";

const CONFIG = configFixture as unknown as ConfigResponse;
const AES_ENCRYPT = aesEncryptFixture as unknown as { byBits: Record<string, AesEncryptResponse>; short: AesEncryptResponse };
const AES_ATTACK = aesAttackFixture as unknown as {
  byBits: Record<string, Record<AttackCondition, AesAttackResponse>>;
  short: AesAttackResponse;
};
const AES_NOISE = aesNoiseFixture as unknown as Partial<AesAttackResponse>[];
const RSA_KEYGEN = rsaKeygenFixture as unknown as Record<string, RsaKeygenResponse>;
const RSA_ENCRYPT = rsaEncryptFixture as unknown as Record<string, RsaEncryptResponse>;
const RSA_ATTACK = rsaAttackFixture as unknown as Record<string, Record<string, RsaAttackResponse>>;
const RSA_NOISE = rsaNoiseFixture as unknown as Record<string, Record<string, Partial<RsaAttackResponse>[]>>;

const SYNTH_NOTE =
  "MOCK DATA: this input was not recorded from the engine, so the nearest recorded run was relabelled for it. Figures are illustrative.";
/** Ciphertext-only on a message this short is ambiguous on the real engine, too. */
const SHORT_MESSAGE_BYTES = 3;

const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const hex = (nibbles: number[]) => nibbles.map((n) => n.toString(16)).join("");
const utf8 = (s: string) => Array.from(new TextEncoder().encode(s));

/** The recorded level closest to `p` on a log scale (0 matches the ideal recording). */
function nearestNoise<T extends { noise_p?: number | null }>(runs: T[], p: number): T {
  const pos = (x: number) => (x > 0 ? Math.log10(x) : -12);
  return runs.reduce((best, r) => (Math.abs(pos(r.noise_p ?? 0) - pos(p)) < Math.abs(pos(best.noise_p ?? 0) - pos(p)) ? r : best));
}

export function config(): ConfigResponse {
  return CONFIG;
}

// ---------- Symmetric ----------

interface AesSession {
  key: string;
  plaintext: string;
  recorded: boolean;
}
/** What the mock "organization" encrypted, by ciphertext. Stands in for the real cipher. */
const aesSessions = new Map<string, AesSession>();
for (const [bits, enc] of Object.entries(AES_ENCRYPT.byBits)) {
  aesSessions.set(`${bits}|${enc.ciphertext_hex}`, { key: MOCK_KEYS[Number(bits)], plaintext: MOCK_MESSAGE, recorded: true });
}
aesSessions.set(`4|${AES_ENCRYPT.short.ciphertext_hex}`, { key: MOCK_KEYS[4], plaintext: "Hi", recorded: true });

// A fixed 4-bit permutation: gives stand-in ciphertexts the look of a block cipher. Not MiniAES.
const MOCK_PERMUTATION = [9, 4, 10, 11, 13, 1, 8, 5, 6, 2, 0, 3, 12, 14, 15, 7];

export function aesEncrypt(req: AesEncryptRequest): AesEncryptResponse {
  const recorded = AES_ENCRYPT.byBits[String(req.key_bits)];
  if (recorded && req.plaintext === MOCK_MESSAGE && req.key === MOCK_KEYS[req.key_bits]) return recorded;
  if (req.key_bits === 4 && req.plaintext === "Hi" && req.key === MOCK_KEYS[4]) return AES_ENCRYPT.short;

  const plain = utf8(req.plaintext).flatMap((b) => [b >> 4, b & 15]);
  const k = parseInt(req.key, 2);
  const cipher = plain.map((n) => MOCK_PERMUTATION[n ^ (k & 15)] ^ ((k >> 4) & 15));
  aesSessions.set(`${req.key_bits}|${hex(cipher)}`, { key: req.key, plaintext: req.plaintext, recorded: false });
  return {
    key_bits: req.key_bits,
    plaintext_nibbles: plain,
    ciphertext_nibbles: cipher,
    ciphertext_hex: hex(cipher),
    byte_length: plain.length / 2,
    trace: [
      { step: "Input P", value: plain[0] ?? 0, detail: (plain[0] ?? 0).toString(2).padStart(4, "0") },
      { step: "Mock stand-in cipher", value: cipher[0] ?? 0, detail: "the round-by-round trace needs the live engine" },
    ],
  };
}

/** Text of the same length that reads as wrong-key gibberish. */
function scramble(text: string, salt: number): string {
  return Array.from(text, (ch, i) => String.fromCharCode(0x20 + ((ch.charCodeAt(0) + 7 * (i + 1) + 13 * salt) % 95))).join("");
}

function notBreached(r: AesAttackResponse): AesAttackResponse {
  return {
    ...r,
    verdict: "not_breached",
    verdict_text: "Not breached: no measured key survived classical verification.",
    recovered_keys: [],
    unique: false,
    key: null,
    decrypted_text: null,
    decrypted_nibbles: [],
    candidate_decryptions: [],
    attempts: r.attempts.map((a) => ({ ...a, verified_keys: [] })),
    verification: r.verification.filter((v) => v.name.startsWith("Attacker input")),
    measurement: { ...r.measurement, top: r.measurement.top.map((t) => ({ ...t, meaning: t.meaning.replace(" ✓ recovered", "") })) },
  };
}

/** Relabel a recorded run for a different organization key and message. */
function relabel(r: AesAttackResponse, recordedKey: string, session: AesSession): AesAttackResponse {
  const bits = r.key_bits;
  const shift = parseInt(recordedKey, 2) ^ parseInt(session.key, 2);
  const map = (k: string) => (parseInt(k, 2) ^ shift).toString(2).padStart(bits, "0");
  const swapText = (s: string) => s.split(recordedKey).join(session.key).split(MOCK_MESSAGE).join(session.plaintext);
  const counts: Record<string, number> = {};
  for (const [k, v] of Object.entries(r.measurement.counts)) counts[map(k)] = v;
  const keys = r.recovered_keys.map(map);
  return {
    ...r,
    recovered_keys: keys,
    key: r.key === null ? null : map(r.key),
    decrypted_text: r.decrypted_text === null ? null : session.plaintext,
    decrypted_nibbles: r.decrypted_text === null ? [] : utf8(session.plaintext).flatMap((b) => [b >> 4, b & 15]),
    candidate_decryptions: r.candidate_decryptions.map((c, i) => {
      const key = map(c.key);
      return { key, text: key === session.key ? session.plaintext : scramble(session.plaintext, i) };
    }),
    attempts: r.attempts.map((a) => ({ ...a, verified_keys: a.verified_keys.map(map) })),
    measurement: {
      ...r.measurement,
      counts,
      top: r.measurement.top.map((t) => {
        const b = map(t.bitstring);
        return { ...t, bitstring: b, value: parseInt(b, 2), meaning: `key ${b}${keys.includes(b) ? " ✓ recovered" : ""}` };
      }),
    },
    verification: r.verification.map((v) => ({ ...v, detail: swapText(v.detail) })),
    warnings: [...r.warnings, SYNTH_NOTE],
  };
}

export function aesAttack(req: AesAttackRequest): AesAttackResponse {
  const condition = req.condition ?? "known_beginning";
  const session = aesSessions.get(`${req.key_bits}|${hex(req.ciphertext_nibbles)}`) ?? {
    key: MOCK_KEYS[req.key_bits] ?? "0".repeat(req.key_bits),
    plaintext: MOCK_MESSAGE,
    recorded: false,
  };
  const byCondition = AES_ATTACK.byBits[String(req.key_bits)] ?? AES_ATTACK.byBits["4"];
  const short = condition === "ciphertext_only" && req.key_bits === 4 && utf8(session.plaintext).length <= SHORT_MESSAGE_BYTES;
  let r = clone(short ? AES_ATTACK.short : byCondition[condition]);

  if (req.noise_p != null && !short) {
    // Noise runs were recorded for the 4-bit known-beginning attack; reuse its measurements.
    const patch = clone(nearestNoise(AES_NOISE, req.noise_p));
    r = { ...r, ...patch, circuit: r.circuit, condition, noise_p: req.noise_p };
  }

  const recordedKey = MOCK_KEYS[r.key_bits] ?? MOCK_KEYS[4];
  const recordedKnown = condition === "known_beginning" ? "Hi " : condition === "known_substring" ? "judges" : null;
  const verbatim = session.recorded && session.key === recordedKey && (req.known_plaintext ?? null) === recordedKnown;
  if (!verbatim) r = relabel(r, recordedKey, session);

  // The adversary's guess has to be true of the message, or nothing verifies.
  const known = req.known_plaintext ?? "";
  const consistent =
    condition === "ciphertext_only" ||
    (condition === "known_beginning" ? session.plaintext.startsWith(known) : session.plaintext.includes(known));
  return consistent ? r : notBreached(r);
}

// ---------- Public-key ----------

const rsaSessions = new Map<string, string>();

function modpow(base: number, exp: number, mod: number): number {
  let result = 1;
  let b = base % mod;
  for (let e = exp; e > 0; e = Math.floor(e / 2)) {
    if (e % 2 === 1) result = (result * b) % mod;
    b = (b * b) % mod;
  }
  return result;
}

export function rsaKeygen(req: RsaKeygenRequest): RsaKeygenResponse {
  return RSA_KEYGEN[String(req.n)] ?? RSA_KEYGEN["15"];
}

export function rsaEncrypt(req: RsaEncryptRequest): RsaEncryptResponse {
  const recorded = RSA_ENCRYPT[String(req.n)];
  if (recorded && req.plaintext === MOCK_MESSAGE) return recorded;
  // Textbook RSA on 3-bit chunks, as the engine does; plain modular arithmetic on public values.
  const bits = utf8(req.plaintext).map((b) => b.toString(2).padStart(8, "0")).join("");
  const chunks: number[] = [];
  for (let i = 0; i < bits.length; i += 3) chunks.push(parseInt(bits.slice(i, i + 3).padEnd(3, "0"), 2));
  const ciphertext = chunks.map((m) => modpow(m, req.e, req.n));
  rsaSessions.set(`${req.n}|${ciphertext.join(",")}`, req.plaintext);
  return { plaintext_chunks: chunks, bit_length: bits.length, chunk_bits: 3, ciphertext };
}

export function rsaAttack(req: RsaAttackRequest): RsaAttackResponse {
  const byConstruction = RSA_ATTACK[String(req.n)] ?? RSA_ATTACK["15"];
  const wanted = req.construction && req.construction !== "auto" ? req.construction : req.n === 15 ? "swap" : "permutation";
  const key = byConstruction[wanted] ? wanted : Object.keys(byConstruction)[0];
  let r = clone(byConstruction[key]);

  if (req.noise_p != null) {
    const runs = RSA_NOISE[String(req.n)]?.[key];
    if (runs?.length) r = { ...r, ...clone(nearestNoise(runs, req.noise_p)), circuit: r.circuit, noise_p: req.noise_p };
  }

  const recorded = RSA_ENCRYPT[String(req.n)];
  const sameCiphertext = recorded && recorded.ciphertext.join(",") === req.ciphertext.join(",");
  const notes: string[] = [];
  if (!sameCiphertext) {
    if (r.decrypted_text !== null) r.decrypted_text = rsaSessions.get(`${req.n}|${req.ciphertext.join(",")}`) ?? null;
    notes.push(SYNTH_NOTE);
  }
  if (req.a !== null && req.a !== r.a) notes.push(`MOCK DATA: the recorded run used base a = ${r.a}, not the requested a = ${req.a}.`);
  return { ...r, warnings: [...r.warnings, ...notes] };
}

// ---------- Evaluation, risk, published estimates ----------

export function evaluation(): EvaluationResponse {
  return evaluationFixture as unknown as EvaluationResponse;
}

export function moscaInfo(): MoscaInfo {
  return moscaInfoFixture as unknown as MoscaInfo;
}

/** Mirrors the engine's Mosca endpoint (X + Y > Z), including its wording. */
export function mosca({ x, y, z }: MoscaRequest): MoscaResult {
  const fmt = (n: number) => `${Number(n.toPrecision(6))} year${n === 1 ? "" : "s"}`;
  const total = x + y;
  const margin = z - total;
  const at_risk = total > z;
  const verdict_text = at_risk
    ? `At risk: X + Y = ${fmt(total)} > Z = ${fmt(z)}. Data encrypted today must stay secret for ${fmt(x)} and migration takes ${fmt(y)}, so traffic harvested now could be decrypted up to ${fmt(-margin)} before it stops being sensitive. Start migrating to post-quantum cryptography now.`
    : margin === 0
      ? `On the boundary: X + Y = Z = ${fmt(z)}, so there is no margin. Any delay in migration or an earlier quantum computer puts this data at risk.`
      : `Not at risk under these assumptions: X + Y = ${fmt(total)} ≤ Z = ${fmt(z)}, a margin of ${fmt(margin)}. The margin shrinks if migration overruns or Z arrives sooner.`;
  return { at_risk, margin, verdict_text, inequality: (moscaInfoFixture as unknown as MoscaInfo).inequality, x, y, z, exposure: Math.max(0, -margin) };
}

export function aesResources(): AesResources {
  return aesResourcesFixture as unknown as AesResources;
}

export function rsaResourceEstimate(): RsaResourceEstimate {
  return rsaResourceFixture as unknown as RsaResourceEstimate;
}
