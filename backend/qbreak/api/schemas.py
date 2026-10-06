"""Pydantic models for the stable Q-Break HTTP contract."""

import base64
import binascii
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qbreak.common.encoding import text_to_nibbles
from qbreak.config import (
    AES_NOISE_MAX_KEY_BITS,
    BB84_DEFAULT_RAW_QUBITS,
    BB84_MAX_CHANNEL_NOISE,
    BB84_MAX_QBER_THRESHOLD,
    BB84_MAX_RAW_QUBITS,
    BB84_MIN_QBER_THRESHOLD,
    BB84_MIN_RAW_QUBITS,
    BB84_QBER_THRESHOLD,
    ENABLED_KEY_BITS,
    ENABLED_MODULI,
    MAX_AES_TEXT_CHARS,
    MAX_DEFENCE_TEXT_CHARS,
    MAX_NOISE_P,
    MAX_NOISY_SHOTS,
    MAX_RSA_TEXT_CHARS,
    MAX_SHOTS,
    RSA_MAX_NOISE_P,
    RSA_NOISE_MODULI,
    key_bits_rejection,
)

AttackCondition = Literal["known_beginning", "known_substring", "ciphertext_only"]


class StrictModel(BaseModel):
    """Base model that rejects undocumented API fields."""

    model_config = ConfigDict(extra="forbid")


class RegisterInfo(StrictModel):
    name: str
    size: int
    role: str


class CircuitDrawing(StrictModel):
    title: str
    text: str


class CircuitInfo(StrictModel):
    num_qubits: int
    num_clbits: int
    depth: int
    transpiled_depth: int
    gate_counts: dict[str, int]
    registers: list[RegisterInfo]
    drawings: list[CircuitDrawing]
    qasm: str | None


class MeasurementEntry(StrictModel):
    bitstring: str
    value: int
    count: int
    probability: float
    meaning: str


class Measurement(StrictModel):
    shots: int
    counts: dict[str, int]
    top: list[MeasurementEntry]


class VerificationStep(StrictModel):
    name: str
    passed: bool
    detail: str


class KeySizeOption(StrictModel):
    bits: int
    enabled: bool
    simulated: bool
    reason: str | None


class AttackConditionInfo(StrictModel):
    id: str
    label: str
    needs_known_text: bool
    description: str


class RSAModulusOption(StrictModel):
    n: int
    label: str
    enabled: bool
    kind: str  # "supported" | "factor_of_2" | "p_equals_q"
    reason: str | None
    qubits_register_2n: int | None
    qubits_iterative: int | None


class RSAConstructionOption(StrictModel):
    key: str  # value for RSAAttackRequest.construction
    name: str  # full name recorded in the evidence object
    label: str
    moduli: list[int]
    counting_qubits: str
    description: str
    headline: bool


class BB84Defaults(StrictModel):
    eve: bool
    eve_intercept_fraction: float
    channel_noise: float
    raw_qubits: int
    qber_threshold: float
    seed: int | None


class BB84Limits(StrictModel):
    defaults: BB84Defaults
    min_raw_qubits: int
    max_raw_qubits: int
    batch_qubits: int
    qber_threshold: float
    min_qber_threshold: float
    max_qber_threshold: float
    max_channel_noise: float
    sample_fraction: float
    final_key_bits: int


class ConfigResponse(StrictModel):
    aes_key_bits: list[int]
    rsa_moduli: list[int]
    max_shots: int
    max_aes_text_chars: int
    max_rsa_text_chars: int
    default_known_prefix_chars: int
    aes_key_options: list[KeySizeOption] = []
    aes_max_key_bits: int = 12
    aes_key_bits_16_note: str = ""
    aes_conditions: list[AttackConditionInfo] = []
    aes_counting_max_key_bits: int = 4
    aes_noise_max_key_bits: int = 4
    aes_max_noise_p: float = 0.05
    aes_max_noisy_shots: int = 64
    # --- public-key (RSA) section ---
    rsa_moduli_options: list[RSAModulusOption]
    rsa_constructions: list[RSAConstructionOption]
    rsa_noise_moduli: list[int]
    rsa_max_noise_p: float
    # --- defence section ---
    defence_methods: list[str] = []
    defence_max_text_chars: int = 1000
    defence_bb84: BB84Limits | None = None


class AESEncryptRequest(StrictModel):
    plaintext: str = Field(min_length=1, max_length=MAX_AES_TEXT_CHARS)
    key: str
    key_bits: int

    @model_validator(mode="after")
    def validate_key(self) -> Self:
        if self.key_bits not in ENABLED_KEY_BITS:
            raise ValueError(key_bits_rejection(self.key_bits))
        if len(self.key) != self.key_bits or any(bit not in "01" for bit in self.key):
            raise ValueError(f"key must contain exactly {self.key_bits} binary digits")
        return self


class TraceStep(StrictModel):
    step: str
    value: int
    detail: str


class AESEncryptResponse(StrictModel):
    key_bits: int
    plaintext_nibbles: list[int]
    ciphertext_nibbles: list[int]
    ciphertext_hex: str
    byte_length: int
    trace: list[TraceStep]


class AESAttackRequest(StrictModel):
    key_bits: int
    condition: AttackCondition = "known_beginning"
    known_plaintext: str | None = Field(default=None, max_length=MAX_AES_TEXT_CHARS)
    ciphertext_nibbles: list[int] = Field(min_length=1, max_length=8 * MAX_AES_TEXT_CHARS)
    shots: int = Field(default=1024, ge=1, le=MAX_SHOTS)
    seed: int | None = None
    noise_p: float | None = Field(default=None, ge=0, le=MAX_NOISE_P)

    @model_validator(mode="after")
    def validate_attack(self) -> Self:
        if self.key_bits not in ENABLED_KEY_BITS:
            raise ValueError(key_bits_rejection(self.key_bits))
        if any(isinstance(value, bool) or not 0 <= value <= 15 for value in self.ciphertext_nibbles):
            raise ValueError("ciphertext_nibbles values must be integers from 0 to 15")
        if self.condition == "ciphertext_only":
            if self.known_plaintext:
                raise ValueError("the ciphertext_only condition takes no known_plaintext")
        elif not self.known_plaintext:
            raise ValueError(f"the {self.condition} condition needs known_plaintext")
        elif len(text_to_nibbles(self.known_plaintext)) > len(self.ciphertext_nibbles):
            raise ValueError("known_plaintext is longer than the ciphertext")
        if self.noise_p is not None:
            if self.key_bits > AES_NOISE_MAX_KEY_BITS:
                raise ValueError(f"noisy runs are enabled for keys up to {AES_NOISE_MAX_KEY_BITS} bits on this instance")
            if self.shots > MAX_NOISY_SHOTS:
                raise ValueError(f"noisy runs simulate every shot separately; use at most {MAX_NOISY_SHOTS} shots")
        return self


class KnownPair(StrictModel):
    plain: int
    cipher: int


class CandidateDecryption(StrictModel):
    key: str
    text: str | None


class GroverAttemptResponse(StrictModel):
    iterations: int
    verified_keys: list[str]


class CountingOutcomeResponse(StrictModel):
    y: int
    count: int
    phase: float
    m_estimate: float


class CountingResponse(StrictModel):
    """Quantum counting: the estimated number of matching keys, and how it was derived."""

    ran: bool
    skipped_reason: str | None = None
    estimated_matching_keys: int | None = None
    peak_m_estimate: float | None = None
    counting_qubits: int | None = None
    controlled_grover_calls: int | None = None
    phase: float | None = None
    y: int | None = None
    num_qubits: int | None = None
    transpiled_depth: int | None = None
    sim_time_ms: float | None = None
    outcomes: list[CountingOutcomeResponse] = []
    derivation: list[str] = []
    true_matching_keys_note: str | None = None


class QuantumCost(StrictModel):
    oracle_calls: int
    grover_iterations: int
    grover_oracle_calls: int
    counting_oracle_calls: int
    circuit_runs: int
    qubits: int
    depth: int
    transpiled_depth: int


class ClassicalCost(StrictModel):
    cipher_evaluations: int
    expected_tries: float
    exhaustive_evaluations: int
    block_evaluations: int
    candidates: int


class ComparisonTheory(StrictModel):
    search_space: int
    classical_average_tries: float
    grover_optimal_iterations: float


class ComparisonRecord(StrictModel):
    """The 'Quantum vs classical' box: query counts, with an honest wall-clock note."""

    quantum: QuantumCost
    classical: ClassicalCost
    theory: ComparisonTheory
    quantum_wallclock_ms: float
    classical_wallclock_ms: float
    wallclock_note: str
    oracle_calls_note: str


class AESAttackResponse(StrictModel):
    key_bits: int
    condition: AttackCondition = "known_beginning"
    verdict: Literal["breached", "ambiguous", "not_breached"] = "breached"
    verdict_text: str = ""
    estimated_matching_keys: int | None = None
    counting: CountingResponse | None = None
    comparison: ComparisonRecord | None = None
    known_text_offsets: list[int] = []
    plausibility_alphabet: str | None = None
    noise_p: float | None = None
    search_space: int
    pairs_used: list[KnownPair]
    iterations: int
    optimal_iterations_formula: str
    recovered_keys: list[str]
    unique: bool
    key: str | None
    decrypted_text: str | None
    decrypted_nibbles: list[int]
    candidate_decryptions: list[CandidateDecryption]
    attempts: list[GroverAttemptResponse]
    sim_time_ms: float
    circuit: CircuitInfo
    measurement: Measurement
    verification: list[VerificationStep]
    warnings: list[str]


class EvaluationSeries(StrictModel):
    """Chart-ready experiment series, read from the experiments runner output."""

    model_config = ConfigDict(extra="allow")

    series: str
    empty: bool
    rows: list[dict[str, Any]]
    description: str


class RSAKeygenRequest(StrictModel):
    n: int

    @model_validator(mode="after")
    def validate_modulus(self) -> Self:
        if self.n not in ENABLED_MODULI:
            raise ValueError(f"n must be one of {ENABLED_MODULI}")
        return self


class VictimSecret(StrictModel):
    p: int
    q: int
    phi: int
    d: int


class RSAKeygenResponse(StrictModel):
    n: int
    e: int
    victim_secret: VictimSecret
    e_equals_d: bool
    warnings: list[str]


class RSAEncryptRequest(StrictModel):
    plaintext: str = Field(min_length=1, max_length=MAX_RSA_TEXT_CHARS)
    n: int
    e: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_modulus(self) -> Self:
        if self.n not in ENABLED_MODULI:
            raise ValueError(f"n must be one of {ENABLED_MODULI}")
        return self


class RSAEncryptResponse(StrictModel):
    plaintext_chunks: list[int]
    bit_length: int
    chunk_bits: int
    ciphertext: list[int]


class RSAAttackRequest(StrictModel):
    n: int
    e: int = Field(gt=0)
    ciphertext: list[int] = Field(min_length=1)
    bit_length: int = Field(gt=0)
    a: int | None = None
    shots: int = Field(default=1024, ge=1, le=MAX_SHOTS)
    seed: int | None = None
    construction: Literal["auto", "swap", "permutation", "iterative"] = "auto"
    noise_p: float | None = Field(default=None, ge=0, le=RSA_MAX_NOISE_P)

    @model_validator(mode="after")
    def validate_attack(self) -> Self:
        if self.n not in ENABLED_MODULI:
            raise ValueError(f"n must be one of {ENABLED_MODULI}")
        if self.construction == "swap" and self.n != 15:
            raise ValueError("construction 'swap' (textbook swaps) exists only for n = 15")
        if self.noise_p is not None and self.n not in RSA_NOISE_MODULI:
            raise ValueError(f"noise_p is supported only for n in {list(RSA_NOISE_MODULI)}")
        if any(isinstance(value, bool) or not 0 <= value < self.n for value in self.ciphertext):
            raise ValueError("every ciphertext value must be a non-negative integer less than n")
        if self.bit_length > len(self.ciphertext) * 3:
            raise ValueError("bit_length exceeds the supplied ciphertext data")
        return self


class ShorAttemptResponse(StrictModel):
    a: int
    measured: str
    y: int
    phase: float
    fraction: str
    r_candidate: int | None
    ok: bool
    reason: str


class RSAQubitsByConstruction(StrictModel):
    register_2n: int
    iterative: int


class RSAComparisonQuantum(StrictModel):
    construction: str
    construction_name: str
    circuit_runs: int
    shots_per_run: int
    qubits: int
    depth: int
    qubits_by_construction: RSAQubitsByConstruction
    factors_found: bool


class RSAComparisonClassical(StrictModel):
    trial_divisions: int
    order_finding_mults: int
    order_finding_bases_tried: int
    factors_found: bool


class RSAComparisonWallclock(StrictModel):
    quantum_simulation: float
    trial_division: float
    order_finding: float


class RSAComparison(StrictModel):
    quantum: RSAComparisonQuantum
    classical: RSAComparisonClassical
    wallclock_ms: RSAComparisonWallclock
    wallclock_note: str


class RSAAttackResponse(StrictModel):
    n: int
    a: int
    period: int | None
    factors: tuple[int, int] | None
    phi: int | None
    d: int | None
    decrypted_text: str | None
    n_count: int
    n_work: int
    construction: str
    attempts: list[ShorAttemptResponse]
    sim_time_ms: float
    circuit: CircuitInfo
    measurement: Measurement
    verification: list[VerificationStep]
    warnings: list[str]
    construction_key: str
    counting_qubits: int
    multiplier_blocks: str
    circuit_runs: int
    noise_p: float | None
    classical_precomputation_note: str | None
    comparison: RSAComparison


class MoscaRequest(StrictModel):
    x: float = Field(ge=0, le=200)
    y: float = Field(ge=0, le=200)
    z: float = Field(ge=0, le=200)


class MoscaResponse(StrictModel):
    at_risk: bool
    margin: float
    verdict_text: str
    inequality: str
    x: float
    y: float
    z: float
    exposure: float


class MoscaInfoResponse(StrictModel):
    inequality: str
    defaults: dict[str, float]
    max_years: float
    explanation: str
    citation: dict[str, str | int]
    default_result: MoscaResponse


# --------------------------------------------------------------------------------------
# Defence (protect -> re-attack -> compare). Bundles are strict: any key, secret or
# plaintext field is an undocumented field and is rejected with 422 (extra="forbid").
# --------------------------------------------------------------------------------------

DefenceMethod = Literal["aes256", "mlkem", "bb84"]


def _check_b64(value: str, name: str) -> str:
    try:
        base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError(f"{name} must be base64") from exc
    return value


class BB84Options(StrictModel):
    eve: bool = False
    eve_intercept_fraction: float = Field(default=1.0, ge=0, le=1)
    channel_noise: float = Field(default=0.0, ge=0, le=BB84_MAX_CHANNEL_NOISE)
    raw_qubits: int = Field(default=BB84_DEFAULT_RAW_QUBITS, ge=BB84_MIN_RAW_QUBITS, le=BB84_MAX_RAW_QUBITS)
    qber_threshold: float = Field(default=BB84_QBER_THRESHOLD, ge=BB84_MIN_QBER_THRESHOLD, le=BB84_MAX_QBER_THRESHOLD)
    seed: int | None = None


class ProtectRequest(StrictModel):
    plaintext: str = Field(min_length=1, max_length=MAX_DEFENCE_TEXT_CHARS)
    methods: list[DefenceMethod] = Field(default_factory=lambda: ["aes256", "mlkem", "bb84"], min_length=1, max_length=3)
    bb84: BB84Options = Field(default_factory=BB84Options)

    @model_validator(mode="after")
    def unique_methods(self) -> Self:
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("methods must not repeat")
        return self


class PublicMetrics(StrictModel):
    """Non-secret sizes and timings, carried in the bundle so the comparison can cite them."""

    sizes: dict[str, int]
    timings_ms: dict[str, float]


class AES256Bundle(StrictModel):
    ciphertext_b64: str = Field(min_length=1, max_length=8 * MAX_DEFENCE_TEXT_CHARS)
    nonce_b64: str = Field(min_length=1, max_length=64)
    public_metrics: PublicMetrics | None = None

    @model_validator(mode="after")
    def base64_fields(self) -> Self:
        _check_b64(self.ciphertext_b64, "ciphertext_b64")
        _check_b64(self.nonce_b64, "nonce_b64")
        return self


class MLKEMBundle(AES256Bundle):
    parameter_set: Literal["ML-KEM-768"] = "ML-KEM-768"
    encapsulation_key_b64: str = Field(min_length=1, max_length=4096)
    kem_ciphertext_b64: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def kem_base64_fields(self) -> Self:
        _check_b64(self.encapsulation_key_b64, "encapsulation_key_b64")
        _check_b64(self.kem_ciphertext_b64, "kem_ciphertext_b64")
        return self


class BB84ChannelRecord(StrictModel):
    """The public classical channel: what Alice and Bob announced. No bit of the final key."""

    raw_qubits: int = Field(ge=BB84_MIN_RAW_QUBITS, le=BB84_MAX_RAW_QUBITS)
    alice_bases: str = Field(pattern=r"^[ZX]*$", max_length=BB84_MAX_RAW_QUBITS)
    bob_bases: str = Field(pattern=r"^[ZX]*$", max_length=BB84_MAX_RAW_QUBITS)
    sample_positions: list[int] = Field(max_length=BB84_MAX_RAW_QUBITS)
    sample_alice_bits: list[int] = Field(max_length=BB84_MAX_RAW_QUBITS)
    sample_bob_bits: list[int] = Field(max_length=BB84_MAX_RAW_QUBITS)
    qber: float = Field(ge=0, le=1)
    qber_threshold: float = Field(ge=BB84_MIN_QBER_THRESHOLD, le=BB84_MAX_QBER_THRESHOLD)
    disclosed_parity_bits: int = Field(ge=0)
    confirmation_tag_bits: int = Field(ge=0)
    accepted: bool


class BB84Bundle(AES256Bundle):
    channel: BB84ChannelRecord


class QKDPhoton(StrictModel):
    alice_bit: int
    alice_basis: Literal["Z", "X"]
    eve_basis: Literal["Z", "X"] | None
    bob_basis: Literal["Z", "X"]
    bob_bit: int
    kept: bool
    error: bool


class QKDSummary(StrictModel):
    raw_bits: int
    sifted_bits: int
    sample_bits: int
    final_key_bits: int
    qber: float
    qber_threshold: float
    accepted: bool
    reason: str
    photon_preview: list[QKDPhoton]
    reconciliation: dict[str, Any]
    privacy_amplification: dict[str, Any]


class AES256ProtectResult(StrictModel):
    method: Literal["aes256"]
    status: Literal["protected"]
    bundle: AES256Bundle
    sizes: dict[str, int]
    timings_ms: dict[str, float]
    roundtrip_ok: bool
    steps: list[str]


class MLKEMProtectResult(StrictModel):
    method: Literal["mlkem"]
    status: Literal["protected"]
    parameter_set: Literal["ML-KEM-768"]
    honesty_note: str
    bundle: MLKEMBundle
    sizes: dict[str, int]
    timings_ms: dict[str, float]
    roundtrip_ok: bool
    steps: list[str]


class BB84ProtectResult(StrictModel):
    method: Literal["bb84"]
    status: Literal["protected", "aborted"]
    bundle: BB84Bundle | None
    qkd: QKDSummary
    evidence: dict[str, Any]
    sizes: dict[str, int]
    timings_ms: dict[str, float]
    roundtrip_ok: bool
    steps: list[str]


class ProtectResults(StrictModel):
    aes256: AES256ProtectResult | None = None
    mlkem: MLKEMProtectResult | None = None
    bb84: BB84ProtectResult | None = None


class ProtectResponse(StrictModel):
    results: ProtectResults


class ReattackBundles(StrictModel):
    """Public bundles only. bb84 may be null (an aborted exchange): BB84 is still re-attacked."""

    aes256: AES256Bundle | None = None
    mlkem: MLKEMBundle | None = None
    bb84: BB84Bundle | None = None


class BB84AttackOptions(StrictModel):
    eve_intercept_fraction: float = Field(default=1.0, ge=0, le=1)
    channel_noise: float = Field(default=0.0, ge=0, le=BB84_MAX_CHANNEL_NOISE)
    raw_qubits: int | None = Field(default=None, ge=BB84_MIN_RAW_QUBITS, le=BB84_MAX_RAW_QUBITS)
    seed: int | None = None


class OriginalAttack(StrictModel):
    cipher: Literal["miniaes", "minirsa"]
    verdict: Literal["breached", "ambiguous", "not_breached"] = "breached"


class ReattackRequest(StrictModel):
    bundles: ReattackBundles
    bb84_attack: BB84AttackOptions = Field(default_factory=BB84AttackOptions)
    original_attack: OriginalAttack | None = None

    @model_validator(mode="after")
    def something_to_attack(self) -> Self:
        if not self.bundles.model_fields_set:
            raise ValueError("bundles must include at least one of aes256, mlkem, bb84")
        return self


class Citation(StrictModel):
    id: str
    text: str


class ReattackVerdict(StrictModel):
    method: DefenceMethod
    attack: str
    executed: bool
    verdict: Literal["infeasible", "not_applicable", "detected", "undetected_low_intercept"]
    explanation: str
    evidence: dict[str, Any]
    citations: list[Citation]


class ReattackVerdicts(StrictModel):
    aes256: ReattackVerdict | None = None
    mlkem: ReattackVerdict | None = None
    bb84: ReattackVerdict | None = None


class ComparisonRow(StrictModel):
    label: str
    aes256: str
    mlkem: str
    bb84: str


class DefenceComparison(StrictModel):
    rows: list[ComparisonRow]


class Recommendation(StrictModel):
    text: str
    rule: str


class OriginalAttackContext(StrictModel):
    cipher: Literal["miniaes", "minirsa"]
    verdict: str
    text: str


class ReattackResponse(StrictModel):
    verdicts: ReattackVerdicts
    comparison: DefenceComparison
    recommendation: Recommendation
    before: OriginalAttackContext | None = None


class DefenceMethodInfo(StrictModel):
    id: DefenceMethod
    label: str


class DefenceInfoResponse(StrictModel):
    methods: list[DefenceMethodInfo]
    comparison: DefenceComparison
    citations: list[Citation]
    bb84: BB84Limits
    max_text_chars: int
    honesty_notes: list[str]
    rules: dict[str, str]
