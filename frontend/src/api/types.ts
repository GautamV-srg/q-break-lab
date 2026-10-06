// Exact TypeScript mirror of the HTTP contract (A6). Field names must not drift.

export interface RegisterInfo {
  name: string;
  size: number;
  role: string;
}

export interface CircuitDrawing {
  title: string;
  text: string;
}

export interface CircuitInfo {
  num_qubits: number;
  num_clbits: number;
  depth: number;
  transpiled_depth: number;
  gate_counts: Record<string, number>;
  registers: RegisterInfo[];
  drawings: CircuitDrawing[];
  qasm: string | null;
}

export interface MeasurementTop {
  bitstring: string;
  value: number;
  count: number;
  probability: number;
  meaning: string;
}

export interface Measurement {
  shots: number;
  counts: Record<string, number>;
  top: MeasurementTop[];
}

export interface VerificationStep {
  name: string;
  passed: boolean;
  detail: string;
}

export interface HealthResponse {
  status: string;
}

export interface ConfigResponse {
  aes_key_bits: number[];
  rsa_moduli: number[];
  max_shots: number;
  max_aes_text_chars: number;
  max_rsa_text_chars: number;
  default_known_prefix_chars: number;
}

// ---------- AES (symmetric) ----------

export interface AesEncryptRequest {
  plaintext: string;
  key: string;
  key_bits: number;
}

export interface TraceStep {
  step: string;
  value: number;
  detail: string;
}

export interface AesEncryptResponse {
  key_bits: number;
  plaintext_nibbles: number[];
  ciphertext_nibbles: number[];
  ciphertext_hex: string;
  byte_length: number;
  trace: TraceStep[];
}

/** Attacker request. There is deliberately NO key field. */
export interface AesAttackRequest {
  key_bits: number;
  known_plaintext: string;
  ciphertext_nibbles: number[];
  shots: number;
  seed: number | null;
}

export interface KnownPair {
  plain: number;
  cipher: number;
}

export interface CandidateDecryption {
  key: string;
  text: string | null;
}

export interface AesAttempt {
  iterations: number;
  verified_keys: string[];
}

export interface AesAttackResponse {
  key_bits: number;
  search_space: number;
  pairs_used: KnownPair[];
  iterations: number;
  optimal_iterations_formula: string;
  recovered_keys: string[];
  unique: boolean;
  key: string | null;
  decrypted_text: string | null;
  decrypted_nibbles: number[] | null;
  candidate_decryptions: CandidateDecryption[];
  attempts: AesAttempt[];
  sim_time_ms: number;
  circuit: CircuitInfo;
  measurement: Measurement;
  verification: VerificationStep[];
  warnings: string[];
}

// ---------- RSA (public-key) ----------

export interface RsaKeygenRequest {
  n: number;
}

export interface RsaVictimSecret {
  p: number;
  q: number;
  phi: number;
  d: number;
}

export interface RsaKeygenResponse {
  n: number;
  e: number;
  victim_secret: RsaVictimSecret;
  e_equals_d: boolean;
  warnings: string[];
}

export interface RsaEncryptRequest {
  plaintext: string;
  n: number;
  e: number;
}

export interface RsaEncryptResponse {
  plaintext_chunks: number[];
  bit_length: number;
  chunk_bits: number;
  ciphertext: number[];
}

/** Attacker request. There are deliberately NO p, q, d or phi fields. */
export interface RsaAttackRequest {
  n: number;
  e: number;
  ciphertext: number[];
  bit_length: number;
  a: number | null;
  shots: number;
  seed: number | null;
}

export interface ShorAttempt {
  a: number;
  measured: string;
  y: number;
  phase: number;
  fraction: string;
  r_candidate: number | null;
  ok: boolean;
  reason: string;
}

export interface RsaAttackResponse {
  n: number;
  a: number;
  period: number | null;
  factors: [number, number] | null;
  phi: number | null;
  d: number | null;
  decrypted_text: string | null;
  n_count: number;
  n_work: number;
  construction: string;
  attempts: ShorAttempt[];
  sim_time_ms: number;
  circuit: CircuitInfo;
  measurement: Measurement;
  verification: VerificationStep[];
  warnings: string[];
}
