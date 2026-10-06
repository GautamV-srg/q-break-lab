"""Pydantic models for the stable Q-Break HTTP contract."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qbreak.common.encoding import text_to_nibbles
from qbreak.config import (
    AES_NOISE_MAX_KEY_BITS,
    ENABLED_KEY_BITS,
    ENABLED_MODULI,
    MAX_AES_TEXT_CHARS,
    MAX_NOISE_P,
    MAX_NOISY_SHOTS,
    MAX_RSA_TEXT_CHARS,
    MAX_SHOTS,
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


class ConfigResponse(StrictModel):
    model_config = ConfigDict(extra="allow")  # Backend B adds RSA fields here

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

    @model_validator(mode="after")
    def validate_attack(self) -> Self:
        if self.n not in ENABLED_MODULI:
            raise ValueError(f"n must be one of {ENABLED_MODULI}")
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
