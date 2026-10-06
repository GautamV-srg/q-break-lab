"""Pydantic models for the stable Q-Break HTTP contract."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qbreak.common.encoding import text_to_nibbles
from qbreak.config import (
    ENABLED_KEY_BITS,
    ENABLED_MODULI,
    MAX_AES_TEXT_CHARS,
    MAX_RSA_TEXT_CHARS,
    MAX_SHOTS,
)


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


class ConfigResponse(StrictModel):
    aes_key_bits: list[int]
    rsa_moduli: list[int]
    max_shots: int
    max_aes_text_chars: int
    max_rsa_text_chars: int
    default_known_prefix_chars: int


class AESEncryptRequest(StrictModel):
    plaintext: str = Field(min_length=1, max_length=MAX_AES_TEXT_CHARS)
    key: str
    key_bits: int

    @model_validator(mode="after")
    def validate_key(self) -> Self:
        if self.key_bits not in ENABLED_KEY_BITS:
            raise ValueError(f"key_bits must be one of {ENABLED_KEY_BITS}")
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
    known_plaintext: str = Field(min_length=1, max_length=MAX_AES_TEXT_CHARS)
    ciphertext_nibbles: list[int] = Field(min_length=1)
    shots: int = Field(default=1024, ge=1, le=MAX_SHOTS)
    seed: int | None = None

    @model_validator(mode="after")
    def validate_attack(self) -> Self:
        if self.key_bits not in ENABLED_KEY_BITS:
            raise ValueError(f"key_bits must be one of {ENABLED_KEY_BITS}")
        if any(isinstance(value, bool) or not 0 <= value <= 15 for value in self.ciphertext_nibbles):
            raise ValueError("ciphertext_nibbles values must be integers from 0 to 15")
        if len(text_to_nibbles(self.known_plaintext)) > len(self.ciphertext_nibbles):
            raise ValueError("known_plaintext is longer than the ciphertext")
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


class AESAttackResponse(StrictModel):
    key_bits: int
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
