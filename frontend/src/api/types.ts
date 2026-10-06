// Exact TypeScript mirror of the HTTP contract (A6). Field names must not drift.
//
// Track 5 fields are optional wherever one backend branch can be deployed without the
// other (symmetric and public-key work merge separately), so the UI reads what the
// engine actually exposes and degrades gracefully when a field is absent.

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

// ---------- /api/config ----------

export type AttackCondition = "known_beginning" | "known_substring" | "ciphertext_only";

/** One symmetric key size the UI may show; `reason` says why a size is not enabled. */
export interface AesKeyOption {
  bits: number;
  enabled: boolean;
  simulated: boolean;
  reason: string | null;
}

export interface AesConditionInfo {
  id: AttackCondition;
  label: string;
  needs_known_text: boolean;
  description: string;
}

/** One RSA modulus the UI may show; disabled kinds carry a one-line `reason`. */
export interface RsaModulusOption {
  n: number;
  label: string;
  enabled: boolean;
  /** "supported" | "factor_of_2" | "p_equals_q" */
  kind: string;
  reason: string | null;
  qubits_register_2n: number | null;
  qubits_iterative: number | null;
}

export interface RsaConstructionOption {
  /** Value for RsaAttackRequest.construction. */
  key: string;
  /** Full name recorded in the evidence object (RsaAttackResponse.construction). */
  name: string;
  label: string;
  moduli: number[];
  counting_qubits: string;
  description: string;
  headline: boolean;
}

export interface ConfigResponse {
  aes_key_bits: number[];
  rsa_moduli: number[];
  max_shots: number;
  max_aes_text_chars: number;
  max_rsa_text_chars: number;
  default_known_prefix_chars: number;
  // --- symmetric (Track 5) ---
  aes_key_options?: AesKeyOption[];
  aes_max_key_bits?: number;
  aes_key_bits_16_note?: string;
  aes_conditions?: AesConditionInfo[];
  aes_counting_max_key_bits?: number;
  aes_noise_max_key_bits?: number;
  aes_max_noise_p?: number;
  aes_max_noisy_shots?: number;
  // --- public-key (Track 5) ---
  rsa_moduli_options?: RsaModulusOption[];
  rsa_constructions?: RsaConstructionOption[];
  rsa_noise_moduli?: number[];
  rsa_max_noise_p?: number;
  // --- defence (round 3) ---
  defence?: DefenceConfig;
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
  /** Omitted for engines that predate the attack-mode selector (they assume known_beginning). */
  condition?: AttackCondition;
  /** null for ciphertext_only. */
  known_plaintext: string | null;
  ciphertext_nibbles: number[];
  shots: number;
  seed: number | null;
  /** Depolarising noise rate; omitted for an ideal run. */
  noise_p?: number;
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

export interface CountingOutcome {
  y: number;
  count: number;
  phase: number;
  m_estimate: number;
}

/** Quantum counting: the estimated number of matching keys, and how it was derived. */
export interface CountingEvidence {
  ran: boolean;
  skipped_reason?: string | null;
  estimated_matching_keys?: number | null;
  peak_m_estimate?: number | null;
  counting_qubits?: number | null;
  controlled_grover_calls?: number | null;
  phase?: number | null;
  y?: number | null;
  num_qubits?: number | null;
  transpiled_depth?: number | null;
  sim_time_ms?: number | null;
  outcomes?: CountingOutcome[];
  derivation?: string[];
  true_matching_keys_note?: string | null;
}

export interface AesComparison {
  quantum: {
    oracle_calls: number;
    grover_iterations: number;
    grover_oracle_calls: number;
    counting_oracle_calls: number;
    circuit_runs: number;
    qubits: number;
    depth: number;
    transpiled_depth: number;
  };
  classical: {
    cipher_evaluations: number;
    expected_tries: number;
    exhaustive_evaluations: number;
    block_evaluations: number;
    candidates: number;
  };
  theory: {
    search_space: number;
    classical_average_tries: number;
    grover_optimal_iterations: number;
  };
  quantum_wallclock_ms: number;
  classical_wallclock_ms: number;
  wallclock_note: string;
  oracle_calls_note: string;
}

export type AesVerdict = "breached" | "ambiguous" | "not_breached";

export interface AesAttackResponse {
  key_bits: number;
  condition?: AttackCondition;
  verdict?: AesVerdict;
  verdict_text?: string;
  estimated_matching_keys?: number | null;
  counting?: CountingEvidence | null;
  comparison?: AesComparison | null;
  /** known_substring only: character offsets where the known text can sit. */
  known_text_offsets?: number[];
  plausibility_alphabet?: string | null;
  noise_p?: number | null;
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
  /** "auto" | "swap" | "permutation" | "iterative"; omitted lets the engine choose. */
  construction?: string;
  /** Depolarising noise rate; omitted for an ideal run. */
  noise_p?: number;
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

export interface RsaComparison {
  quantum: {
    construction: string;
    construction_name: string;
    circuit_runs: number;
    shots_per_run: number;
    qubits: number;
    depth: number;
    qubits_by_construction: { register_2n: number; iterative: number };
    factors_found: boolean;
  };
  classical: {
    trial_divisions: number;
    order_finding_mults: number;
    order_finding_bases_tried: number;
    factors_found: boolean;
  };
  wallclock_ms: { quantum_simulation: number; trial_division: number; order_finding: number };
  wallclock_note: string;
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
  // --- Track 5 ---
  construction_key?: string;
  counting_qubits?: number;
  multiplier_blocks?: string;
  circuit_runs?: number;
  noise_p?: number | null;
  classical_precomputation_note?: string | null;
  comparison?: RsaComparison | null;
}

// ---------- Evaluation (read-only aggregated experiment series) ----------

export type SeriesRow = Record<string, string | number | boolean | null>;

export interface EvaluationSeries {
  series: string;
  empty: boolean;
  rows: SeriesRow[];
  description: string;
}

export interface EvaluationResponse {
  series: string[];
  data: Record<string, EvaluationSeries>;
}

// ---------- Mosca risk model ----------

export interface MoscaRequest {
  x: number;
  y: number;
  z: number;
}

export interface MoscaResult {
  at_risk: boolean;
  /** Z − (X + Y); negative when at risk. */
  margin: number;
  verdict_text: string;
  inequality: string;
  x: number;
  y: number;
  z: number;
  exposure: number;
}

export interface MoscaInfo {
  inequality: string;
  defaults: { x: number; y: number; z: number };
  max_years: number;
  explanation: string;
  citation: Record<string, string | number>;
  default_result: MoscaResult;
}

// ---------- Published real-scale resource estimates (cited by the engine) ----------

export interface CitedValue {
  value?: number | null;
  text?: string;
  source?: string;
  note?: string;
}

export interface AesResourceEstimate {
  cipher: string;
  key_bits: number;
  grover_iterations: CitedValue;
  classical_tries: CitedValue;
  logical_qubits: CitedValue;
  t_gates: CitedValue;
  t_depth: CitedValue;
  [extra: string]: unknown;
}

export interface AesResources {
  estimates: AesResourceEstimate[];
  takeaway: string;
  citations: Record<string, string>;
}

export interface RsaResourceFigure {
  name: string;
  value: number;
  unit: string;
  /** "published" (quoted from the paper) | "formula" (the paper's formula at this size). */
  kind: string;
  citation: string;
  quote?: string;
  formula?: string;
}

export interface RsaCitation {
  authors: string;
  title: string;
  venue: string;
  year: number;
  url: string;
}

export interface RsaResourceEstimate {
  modulus_bits: number;
  figures: RsaResourceFigure[];
  physical_estimate_note?: string;
  citations: Record<string, RsaCitation>;
  honesty_note: string;
  [extra: string]: unknown;
}

// ---------- Defence (round 3): protect, re-attack, compare ----------
//
// Mirrors AGENT_DEFENCE_A_BACKEND.md §7. The live OpenAPI schema wins: fields the brief
// leaves open (sizes, timings, evidence, bundle contents) are typed loosely and read by key.

export type DefenceMethod = "aes256" | "mlkem" | "bb84";

export interface Bb84Options {
  eve: boolean;
  eve_intercept_fraction: number;
  channel_noise: number;
  raw_qubits: number;
  qber_threshold: number;
  seed: number | null;
}

export interface ProtectRequest {
  plaintext: string;
  methods: DefenceMethod[];
  bb84: Bb84Options;
}

/** Public material only: what an eavesdropper on the channel would capture. */
export interface DefenceBundle {
  ciphertext_b64?: string;
  nonce_b64?: string;
  /** ML-KEM only. */
  encapsulation_key_b64?: string;
  kem_ciphertext_b64?: string;
  /** BB84 only: the public channel record (announced bases, sample positions and values). */
  [field: string]: unknown;
}

export interface PhotonRow {
  alice_bit: number;
  alice_basis: string;
  eve_basis: string | null;
  bob_basis: string;
  bob_bit: number;
  kept: boolean;
  error: boolean;
}

export interface QkdSummary {
  raw_bits: number;
  sifted_bits: number;
  sample_bits: number;
  final_key_bits: number;
  qber: number;
  qber_threshold: number;
  accepted: boolean;
  reason: string;
  photon_preview: PhotonRow[];
}

export interface ProtectResult {
  method: DefenceMethod;
  /** "protected" | "aborted" */
  status: string;
  bundle: DefenceBundle | null;
  sizes: Record<string, number | string | null>;
  timings_ms: Record<string, number | null>;
  roundtrip_ok: boolean;
  steps: string[];
  /** ML-KEM only, e.g. "ML-KEM-768". */
  parameter_set?: string;
  /** BB84 only. */
  qkd?: QkdSummary;
  /** BB84 only: circuits, simulator method, an example circuit drawing and OpenQASM. */
  evidence?: Record<string, unknown>;
}

export interface ProtectResponse {
  results: Partial<Record<DefenceMethod, ProtectResult>>;
}

export interface ReattackRequest {
  bundles: Partial<Record<DefenceMethod, DefenceBundle | null>>;
  bb84_attack: { eve_intercept_fraction: number; channel_noise: number; seed: number | null };
  original_attack?: { cipher: "miniaes" | "minirsa"; verdict: string };
}

/** "infeasible" | "not_applicable" | "detected" | "undetected_low_intercept" */
export type DefenceVerdictKind = string;

export type Citation = string | { authors?: string; title?: string; venue?: string; year?: number | string; url?: string; [k: string]: unknown };

export interface DefenceVerdict {
  method: DefenceMethod;
  attack: string;
  executed: boolean;
  verdict: DefenceVerdictKind;
  explanation: string;
  evidence: Record<string, unknown>;
  citations: Citation[] | Record<string, Citation>;
}

export interface ComparisonRow {
  label: string;
  aes256: string;
  mlkem: string;
  bb84: string;
}

export interface ReattackResponse {
  verdicts: Partial<Record<DefenceMethod, DefenceVerdict>>;
  comparison: { rows: ComparisonRow[] };
  recommendation: { text: string; rule: string };
}

export interface DefenceMethodInfo {
  id: DefenceMethod;
  name: string;
  description: string;
  /** e.g. "Real AES-256-GCM encryption" or "Simulated in Qiskit". */
  kind?: string;
}

export interface Bb84Limits {
  raw_qubits_min?: number;
  raw_qubits_max?: number;
  eve_intercept_fraction_min?: number;
  eve_intercept_fraction_max?: number;
  channel_noise_min?: number;
  channel_noise_max?: number;
  qber_threshold_min?: number;
  qber_threshold_max?: number;
}

export interface DefenceInfo {
  methods: DefenceMethodInfo[];
  comparison_rows: ComparisonRow[];
  citations: Record<string, Citation> | Citation[];
  bb84: { defaults: Bb84Options; limits: Bb84Limits };
  honesty_notes: string[];
  max_text_chars?: number;
}

/** Defence fields added to /api/config. */
export interface DefenceConfig {
  methods?: DefenceMethod[];
  max_text_chars?: number;
  bb84_defaults?: Partial<Bb84Options>;
  bb84_limits?: Bb84Limits;
}
