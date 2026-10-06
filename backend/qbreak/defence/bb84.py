"""Defence 3: BB84 quantum key distribution, simulated in Qiskit, driving AES-256-GCM.

Protocol (Bennett & Brassard 1984), one qubit per photon:

1. Alice picks a random bit and a random basis (Z or X) per photon and prepares it:
   Z: |0>/|1>; X: |+>/|-> (an H after the optional X).
2. The photon crosses the channel: an identity gate carrying the channel noise model, and,
   optionally, Eve's intercept-resend attack.
3. Bob measures each photon in a random basis.
4. Sifting: Alice and Bob announce their bases publicly and keep matching positions.
5. They disclose a random sample of the sifted bits to estimate the QBER, then discard it.
6. QBER above the threshold (default 11%, Shor & Preskill 2000) → abort, discard the key.
7. Otherwise: simplified information reconciliation (block parity + binary search, a few
   shuffled passes, no Cascade back-tracking) and privacy amplification (SHA-256 → 256 bits).
8. The 256-bit key drives AES-256-GCM.

Eve (intercept-resend) is modelled faithfully in two stages: Alice→Eve circuits in which
Eve measures each intercepted photon in a random basis, then Eve→Bob circuits prepared
from what she saw. Theory: QBER ≈ fraction / 4.

Channel noise ``p`` is the per-photon probability that the channel flips the bit Bob reads,
whichever basis he uses: a depolarising channel of strength 2p on the identity gate
(Qiskit's depolarizing_error(λ) flips any fixed basis with probability λ/2).

Every circuit is Clifford (X, H, measure), so it runs on Aer's stabilizer method in narrow
batches (``BB84_BATCH_QUBITS`` photons each) through the shared simulator helper.
"""

from __future__ import annotations

import hashlib
import math
import random
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from qiskit import QuantumCircuit, qasm3
from qiskit_aer.noise import NoiseModel, depolarizing_error

from qbreak.common.simulator import run_circuit
from qbreak.config import (
    BB84_BATCH_QUBITS,
    BB84_DEFAULT_RAW_QUBITS,
    BB84_MAX_CHANNEL_NOISE,
    BB84_MAX_RAW_QUBITS,
    BB84_MIN_RAW_QUBITS,
    BB84_PREVIEW_PHOTONS,
    BB84_QBER_THRESHOLD,
    BB84_SAMPLE_FRACTION,
)
from qbreak.defence.types import (
    BB84_HONESTY_NOTE,
    GCM_TAG_BYTES,
    NONCE_BYTES,
    ProtectResult,
    Stopwatch,
    b64,
    gcm_open,
    gcm_seal,
    public_metrics,
)

FINAL_KEY_BITS = 256
SIMULATOR_METHOD = "stabilizer"
RECONCILIATION_PASSES = 4
CONFIRMATION_TAG_BITS = 64
"""Alice and Bob compare a 64-bit hash of the reconciled key; it counts as disclosed."""
BASIS = ("Z", "X")


@lru_cache(maxsize=32)
def channel_noise_model(p: float) -> NoiseModel:
    """Flip probability p on the channel (identity) gate, in either basis."""
    if not 0 <= p <= 0.5:
        raise ValueError("channel noise must be between 0 and 0.5")
    model = NoiseModel()
    if p > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(2 * p, 1), ["id"])
    return model


def _prepare(qc: QuantumCircuit, q: int, bit: int, basis: int) -> None:
    if bit:
        qc.x(q)
    if basis:
        qc.h(q)


def _measure_in(qc: QuantumCircuit, q: int, basis: int) -> None:
    if basis:
        qc.h(q)
    qc.measure(q, q)


def build_channel_circuit(bits: list[int], prep_bases: list[int], meas_bases: list[int], channel: bool = True) -> QuantumCircuit:
    """One batch: prepare each photon, pass it through the channel, measure it."""
    n = len(bits)
    qc = QuantumCircuit(n, n, name="bb84_batch")
    for q in range(n):
        _prepare(qc, q, bits[q], prep_bases[q])
    qc.barrier()
    if channel:
        for q in range(n):
            qc.id(q)
        qc.barrier()
    for q in range(n):
        _measure_in(qc, q, meas_bases[q])
    return qc


def _read(counts: dict[str, int], n: int) -> list[int]:
    (bitstring,) = counts  # one shot
    return [int(bitstring[-1 - q]) for q in range(n)]


@dataclass
class _Batches:
    circuits: int = 0
    sim_time_ms: float = 0.0
    max_width: int = 0


def _run_photons(
    bits: list[int],
    prep: list[int],
    meas: list[int],
    noise: NoiseModel | None,
    channel: bool,
    seed: int | None,
    stats: _Batches,
) -> list[int]:
    out: list[int] = []
    for start in range(0, len(bits), BB84_BATCH_QUBITS):
        sl = slice(start, start + BB84_BATCH_QUBITS)
        qc = build_channel_circuit(bits[sl], prep[sl], meas[sl], channel=channel)
        run = run_circuit(
            qc,
            shots=1,
            seed=None if seed is None else seed + stats.circuits,
            method=SIMULATOR_METHOD,
            noise_model=noise,
        )
        stats.circuits += 1
        stats.sim_time_ms += run.sim_time_ms
        stats.max_width = max(stats.max_width, qc.num_qubits)
        out.extend(_read(run.counts, qc.num_qubits))
    return out


def _parity(bits: list[int], idx: list[int]) -> int:
    return sum(bits[i] for i in idx) & 1


def reconcile(alice: list[int], bob: list[int], qber_estimate: float, rng: random.Random) -> tuple[list[int], int, int]:
    """Simplified reconciliation: Bob corrects his key towards Alice's.

    Each pass splits the (shuffled) key into blocks, compares block parities over the public
    channel and, where they differ, binary-searches the block (one parity per halving) to
    find and flip one error. Block size starts near 0.73/QBER and doubles each pass.
    Returns (bob_corrected, disclosed_parity_bits, corrections).
    """
    bob = list(bob)
    n = len(alice)
    if n == 0:
        return bob, 0, 0
    k = max(4, min(64, int(0.73 / max(qber_estimate, 0.01))))
    disclosed = corrected = 0
    for p in range(RECONCILIATION_PASSES):
        order = list(range(n)) if p == 0 else rng.sample(range(n), n)
        for start in range(0, n, k):
            block = order[start : start + k]
            disclosed += 1
            if _parity(alice, block) == _parity(bob, block):
                continue
            while len(block) > 1:
                half = block[: len(block) // 2]
                disclosed += 1
                block = half if _parity(alice, half) != _parity(bob, half) else block[len(block) // 2 :]
            bob[block[0]] ^= 1
            corrected += 1
        k = min(2 * k, n)
    return bob, disclosed, corrected


def privacy_amplify(bits: list[int]) -> bytes:
    """Hash the reconciled bits to a 256-bit key (SHA-256)."""
    packed = int("".join(map(str, bits)) or "0", 2).to_bytes(max(1, math.ceil(len(bits) / 8)), "big")
    return hashlib.sha256(len(bits).to_bytes(4, "big") + packed).digest()


def _tag(bits: list[int]) -> bytes:
    return hashlib.sha256(b"confirm" + bytes(bits)).digest()[: CONFIRMATION_TAG_BITS // 8]


@dataclass
class Exchange:
    """Everything one simulated BB84 run produced. Keys stay server-side."""

    raw_bits: int
    eve: bool
    eve_intercept_fraction: float
    channel_noise: float
    qber_threshold: float
    alice_bits: list[int]
    alice_bases: list[int]
    bob_bases: list[int]
    bob_bits: list[int]
    eve_bases: list[int | None]
    sifted_positions: list[int]
    sample_positions: list[int]
    sample_alice_bits: list[int]
    sample_bob_bits: list[int]
    qber: float
    qber_all_sifted: float
    accepted: bool
    reason: str
    intercepted: int
    disclosed_parity_bits: int = 0
    corrections: int = 0
    reconciled_bits: int = 0
    secure_bits_estimate: int = 0
    final_key_bits: int = 0
    alice_key: bytes | None = None
    bob_key: bytes | None = None
    stage_circuits: dict[str, int] = field(default_factory=dict)
    sim_time_ms: float = 0.0
    max_width: int = 0
    example: QuantumCircuit | None = None

    @property
    def sifted_bits(self) -> int:
        return len(self.sifted_positions)

    @property
    def sample_bits(self) -> int:
        return len(self.sample_positions)

    def photon_preview(self, n: int = BB84_PREVIEW_PHOTONS) -> list[dict[str, Any]]:
        rows = []
        for i in range(min(n, self.raw_bits)):
            kept = self.alice_bases[i] == self.bob_bases[i]
            eve_basis = self.eve_bases[i]
            rows.append({
                "alice_bit": self.alice_bits[i],
                "alice_basis": BASIS[self.alice_bases[i]],
                "eve_basis": None if eve_basis is None else BASIS[eve_basis],
                "bob_basis": BASIS[self.bob_bases[i]],
                "bob_bit": self.bob_bits[i],
                "kept": kept,
                "error": kept and self.alice_bits[i] != self.bob_bits[i],
            })
        return rows

    def public_channel_record(self) -> dict[str, Any]:
        """What Alice and Bob said on the public channel — all an eavesdropper can read."""
        return {
            "raw_qubits": self.raw_bits,
            "alice_bases": "".join(BASIS[b] for b in self.alice_bases),
            "bob_bases": "".join(BASIS[b] for b in self.bob_bases),
            "sample_positions": list(self.sample_positions),
            "sample_alice_bits": list(self.sample_alice_bits),
            "sample_bob_bits": list(self.sample_bob_bits),
            "qber": round(self.qber, 6),
            "qber_threshold": self.qber_threshold,
            "disclosed_parity_bits": self.disclosed_parity_bits,
            "confirmation_tag_bits": CONFIRMATION_TAG_BITS if self.reconciled_bits else 0,
            "accepted": self.accepted,
        }

    def qkd_summary(self) -> dict[str, Any]:
        return {
            "raw_bits": self.raw_bits,
            "sifted_bits": self.sifted_bits,
            "sample_bits": self.sample_bits,
            "final_key_bits": self.final_key_bits,
            "qber": round(self.qber, 6),
            "qber_threshold": self.qber_threshold,
            "accepted": self.accepted,
            "reason": self.reason,
            "photon_preview": self.photon_preview(),
            "reconciliation": {
                "scheme": f"block parity + binary search, {RECONCILIATION_PASSES} shuffled passes (simplified, no back-tracking)",
                "reconciled_bits": self.reconciled_bits,
                "disclosed_parity_bits": self.disclosed_parity_bits,
                "corrections": self.corrections,
                "confirmation_tag_bits": CONFIRMATION_TAG_BITS if self.reconciled_bits else 0,
            },
            "privacy_amplification": {
                "method": "SHA-256 of the reconciled bits → 256-bit key",
                "secure_bits_estimate": self.secure_bits_estimate,
                "required_bits": FINAL_KEY_BITS,
            },
        }

    def evidence(self) -> dict[str, Any]:
        example = self.example
        drawing = str(example.draw(output="text", fold=-1)) if example is not None else None
        try:
            qasm = qasm3.dumps(example) if example is not None else None
        except Exception:
            qasm = None
        return {
            "eve_intercepted": self.intercepted,
            "theory_qber": round(theory_qber(self.eve_intercept_fraction if self.eve else 0.0, self.channel_noise), 6),
            "num_circuits": sum(self.stage_circuits.values()),
            "note": BB84_HONESTY_NOTE,
            "simulator_method": SIMULATOR_METHOD,
            "qubits_per_circuit": self.max_width,
            "batch_qubits": BB84_BATCH_QUBITS,
            "circuits": sum(self.stage_circuits.values()),
            "stage_circuits": dict(self.stage_circuits),
            "shots_per_circuit": 1,
            "sim_time_ms": round(self.sim_time_ms, 3),
            "eve": {
                "enabled": self.eve,
                "model": "intercept-resend (two stages: Alice→Eve measured, Eve→Bob re-prepared)",
                "intercept_fraction": self.eve_intercept_fraction if self.eve else 0.0,
                "intercepted_photons": self.intercepted,
                "theory_qber": round(self.eve_intercept_fraction / 4, 6) if self.eve else 0.0,
            },
            "channel": {
                "noise": self.channel_noise,
                "model": "depolarising channel of strength 2p on the channel gate (bit flip p in either basis)",
                "theory_qber_from_noise": self.channel_noise,
            },
            "example_circuit": {
                "title": f"Alice → Bob, first {example.num_qubits if example is not None else 0} photons (prepare · channel · measure)",
                "drawing": drawing,
                "qasm": qasm,
            },
            "honesty_note": BB84_HONESTY_NOTE,
        }


def run_exchange(
    raw_qubits: int = BB84_DEFAULT_RAW_QUBITS,
    *,
    eve: bool = False,
    eve_intercept_fraction: float = 1.0,
    channel_noise: float = 0.0,
    qber_threshold: float = BB84_QBER_THRESHOLD,
    seed: int | None = None,
) -> Exchange:
    """Simulate one BB84 key exchange end to end (Alice, the channel, optional Eve, Bob)."""
    if not BB84_MIN_RAW_QUBITS <= raw_qubits <= BB84_MAX_RAW_QUBITS:
        raise ValueError(f"raw_qubits must be between {BB84_MIN_RAW_QUBITS} and {BB84_MAX_RAW_QUBITS}")
    if not 0 <= eve_intercept_fraction <= 1:
        raise ValueError("eve_intercept_fraction must be between 0 and 1")
    if not 0 <= channel_noise <= BB84_MAX_CHANNEL_NOISE:
        raise ValueError(f"channel_noise must be between 0 and {BB84_MAX_CHANNEL_NOISE}")
    rng: random.Random = random.Random(seed) if seed is not None else secrets.SystemRandom()
    n = raw_qubits
    alice_bits = [rng.getrandbits(1) for _ in range(n)]
    alice_bases = [rng.getrandbits(1) for _ in range(n)]
    bob_bases = [rng.getrandbits(1) for _ in range(n)]
    intercepted = [eve and rng.random() < eve_intercept_fraction for _ in range(n)]
    eve_bases: list[int | None] = [rng.getrandbits(1) if hit else None for hit in intercepted]
    noise = channel_noise_model(float(channel_noise)) if channel_noise > 0 else None

    stats = _Batches()
    stage: dict[str, int] = {}
    # Stage 1 (Alice -> Eve): Eve measures every intercepted photon in her random basis.
    hits = [i for i in range(n) if intercepted[i]]
    send_bits, send_bases = list(alice_bits), list(alice_bases)
    if hits:
        before = stats.circuits
        eve_bits = _run_photons(
            [alice_bits[i] for i in hits], [alice_bases[i] for i in hits], [eve_bases[i] for i in hits],
            None, False, None if seed is None else seed * 7919 + 1, stats,
        )
        stage["alice_to_eve"] = stats.circuits - before
        for i, bit in zip(hits, eve_bits, strict=True):
            send_bits[i], send_bases[i] = bit, eve_bases[i]  # Eve re-prepares what she saw
    # Stage 2 (sender -> Bob): Alice's photon, or Eve's replacement, through the noisy channel.
    before = stats.circuits
    bob_bits = _run_photons(send_bits, send_bases, bob_bases, noise, True, None if seed is None else seed * 7919 + 2, stats)
    stage["to_bob"] = stats.circuits - before
    preview_width = min(8, n)
    example = build_channel_circuit(send_bits[:preview_width], send_bases[:preview_width], bob_bases[:preview_width])

    sifted = [i for i in range(n) if alice_bases[i] == bob_bases[i]]
    sample_size = max(1, round(len(sifted) * BB84_SAMPLE_FRACTION)) if sifted else 0
    sample_idx = sorted(rng.sample(range(len(sifted)), sample_size)) if sample_size else []
    sample_positions = [sifted[j] for j in sample_idx]
    sample_alice = [alice_bits[i] for i in sample_positions]
    sample_bob = [bob_bits[i] for i in sample_positions]
    errors = sum(a != b for a, b in zip(sample_alice, sample_bob, strict=True))
    qber = errors / sample_size if sample_size else 1.0
    all_errors = sum(alice_bits[i] != bob_bits[i] for i in sifted)
    qber_all = all_errors / len(sifted) if sifted else 1.0

    ex = Exchange(
        raw_bits=n, eve=eve, eve_intercept_fraction=float(eve_intercept_fraction), channel_noise=float(channel_noise),
        qber_threshold=float(qber_threshold), alice_bits=alice_bits, alice_bases=alice_bases, bob_bases=bob_bases,
        bob_bits=bob_bits, eve_bases=eve_bases, sifted_positions=sifted, sample_positions=sample_positions,
        sample_alice_bits=sample_alice, sample_bob_bits=sample_bob, qber=qber, qber_all_sifted=qber_all,
        accepted=False, reason="", intercepted=len(hits), stage_circuits=stage, sim_time_ms=stats.sim_time_ms,
        max_width=stats.max_width, example=example,
    )
    if qber > qber_threshold:
        ex.reason = (
            f"Aborted: estimated QBER {qber:.1%} on {sample_size} sampled bits exceeds the "
            f"{qber_threshold:.0%} threshold. Someone (or something) disturbed the photons; the key is discarded."
        )
        return ex

    sampled = set(sample_positions)
    keep = [i for i in sifted if i not in sampled]
    alice_key_bits = [alice_bits[i] for i in keep]
    bob_raw = [bob_bits[i] for i in keep]
    bob_key_bits, disclosed, corrected = reconcile(alice_key_bits, bob_raw, qber, rng)
    ex.disclosed_parity_bits, ex.corrections, ex.reconciled_bits = disclosed, corrected, len(keep)
    # Conservative leak budget: parities + confirmation tag + Eve's intercept-resend knowledge
    # (QBER q implies an intercept fraction 4q, of which Eve knows about half: 2q of the bits)
    # + the kept, unsampled bits shown in the photon preview.
    preview_exposed = sum(1 for i in keep if i < BB84_PREVIEW_PHOTONS)
    eve_leak = math.ceil(2 * qber * len(keep))
    ex.secure_bits_estimate = len(keep) - disclosed - CONFIRMATION_TAG_BITS - eve_leak - preview_exposed
    if _tag(alice_key_bits) != _tag(bob_key_bits):
        ex.reason = "Aborted: reconciliation left residual errors (confirmation hashes differ); the key is discarded."
        return ex
    if ex.secure_bits_estimate < FINAL_KEY_BITS:
        ex.reason = (
            f"Aborted: only about {max(ex.secure_bits_estimate, 0)} secure bits remain after sifting, sampling, "
            f"reconciliation and the leak budget; {FINAL_KEY_BITS} are needed. Send more raw qubits."
        )
        return ex
    ex.alice_key, ex.bob_key = privacy_amplify(alice_key_bits), privacy_amplify(bob_key_bits)
    ex.final_key_bits = FINAL_KEY_BITS
    ex.accepted = ex.alice_key == ex.bob_key
    ex.reason = (
        f"Accepted: QBER {qber:.1%} is within the {qber_threshold:.0%} threshold; "
        f"{len(keep)} bits reconciled and hashed to a {FINAL_KEY_BITS}-bit key."
        if ex.accepted else "Aborted: Alice's and Bob's final keys differ."
    )
    return ex


def protect_bb84(
    plaintext: str,
    *,
    eve: bool = False,
    eve_intercept_fraction: float = 1.0,
    channel_noise: float = 0.0,
    raw_qubits: int = BB84_DEFAULT_RAW_QUBITS,
    qber_threshold: float = BB84_QBER_THRESHOLD,
    seed: int | None = None,
) -> ProtectResult:
    """Run BB84; if the key is accepted, Alice encrypts with it and Bob decrypts with his."""
    data = plaintext.encode("utf-8")
    watch = Stopwatch()
    with watch.time("key_exchange"):
        ex = run_exchange(
            raw_qubits, eve=eve, eve_intercept_fraction=eve_intercept_fraction,
            channel_noise=channel_noise, qber_threshold=qber_threshold, seed=seed,
        )
    watch.timings_ms["simulation"] = round(ex.sim_time_ms, 3)
    steps = [
        f"Alice prepared {ex.raw_bits} photons with random bits in random bases (Z or X).",
        "The photons crossed the channel"
        + (f" with {ex.channel_noise:.1%} bit-flip noise" if ex.channel_noise else " (noiseless)")
        + (f"; Eve intercepted {ex.intercepted} of them, measured in a random basis and re-sent what she saw." if ex.eve else "; no eavesdropper."),
        "Bob measured each photon in a random basis.",
        f"Sifting: bases compared publicly; {ex.sifted_bits} matching positions kept.",
        f"QBER estimate: {ex.sample_bits} sifted bits disclosed and compared → {ex.qber:.1%} "
        f"(threshold {ex.qber_threshold:.0%}).",
    ]
    sizes = {
        "plaintext_bytes": len(data),
        "raw_qubits": ex.raw_bits,
        "sifted_bits": ex.sifted_bits,
        "sample_bits": ex.sample_bits,
        "final_key_bits": ex.final_key_bits,
        "nonce_bytes": NONCE_BYTES,
    }
    extra = {"qkd": ex.qkd_summary(), "evidence": ex.evidence()}
    if not ex.accepted:
        steps.append(ex.reason)
        steps.append("No ciphertext was produced: the message is not sent under a key that may be compromised.")
        steps.append("Simulation: " + BB84_HONESTY_NOTE)
        return ProtectResult("bb84", "aborted", None, sizes, watch.timings_ms, False, steps, extra=extra)

    with watch.time("encrypt"):
        nonce, ciphertext = gcm_seal(ex.alice_key, data)
    with watch.time("decrypt"):
        roundtrip_ok = gcm_open(ex.bob_key, nonce, ciphertext) == data
    sizes.update({"ciphertext_bytes": len(ciphertext), "tag_bytes": GCM_TAG_BYTES, "key_bytes": FINAL_KEY_BITS // 8})
    steps += [
        f"Reconciliation: {ex.disclosed_parity_bits} parity bits disclosed, {ex.corrections} errors corrected "
        "(simplified block-parity / binary search).",
        f"Privacy amplification: {ex.reconciled_bits} reconciled bits hashed with SHA-256 to a "
        f"{FINAL_KEY_BITS}-bit key (about {ex.secure_bits_estimate} bits estimated secret after the leak budget).",
        f"Alice encrypted the message with AES-256-GCM under the QKD key → {len(ciphertext)} bytes; "
        "Bob decrypted with his copy: " + ("the message matches." if roundtrip_ok else "MISMATCH."),
        "Public bundle: ciphertext, nonce and the public channel record (bases, sample, disclosed parities).",
        "Simulation: " + BB84_HONESTY_NOTE,
    ]
    bundle = {
        "ciphertext_b64": b64(ciphertext),
        "nonce_b64": b64(nonce),
        "channel": ex.public_channel_record(),
        "public_metrics": public_metrics(sizes, watch.timings_ms),
    }
    return ProtectResult("bb84", "protected", bundle, sizes, watch.timings_ms, roundtrip_ok, steps, extra=extra)


def eavesdrop_exchange(
    raw_qubits: int = BB84_DEFAULT_RAW_QUBITS,
    *,
    eve_intercept_fraction: float = 1.0,
    channel_noise: float = 0.0,
    qber_threshold: float = BB84_QBER_THRESHOLD,
    seed: int | None = None,
) -> dict[str, Any]:
    """The attacker's view of a fresh BB84 run with Eve on: public outcome only, no keys."""
    ex = run_exchange(
        raw_qubits, eve=True, eve_intercept_fraction=eve_intercept_fraction,
        channel_noise=channel_noise, qber_threshold=qber_threshold, seed=seed,
    )
    detected = ex.qber > ex.qber_threshold
    # Of the sifted bits, Eve guessed the basis right on about half of those she intercepted.
    eve_known = sum(
        1 for i in ex.sifted_positions if ex.eve_bases[i] is not None and ex.eve_bases[i] == ex.alice_bases[i]
    )
    return {
        "raw_qubits": ex.raw_bits,
        "sifted_bits": ex.sifted_bits,
        "sample_bits": ex.sample_bits,
        "qber": round(ex.qber, 6),
        "qber_threshold": ex.qber_threshold,
        "theory_qber": round(theory_qber(eve_intercept_fraction, channel_noise), 6),
        "detected": detected,
        "accepted": ex.accepted,
        "reason": ex.reason,
        "intercepted_photons": ex.intercepted,
        "eve_intercept_fraction": eve_intercept_fraction,
        "channel_noise": channel_noise,
        "eve_matching_basis_sifted_bits": eve_known,
        "expected_eve_info_fraction": round(eve_intercept_fraction / 2, 6),
        "secure_bits_estimate": ex.secure_bits_estimate if not detected else 0,
        # Bases and error flags only: no bit values, even from this throw-away exchange.
        "photon_preview": [
            {k: row[k] for k in ("alice_basis", "eve_basis", "bob_basis", "kept", "error")} for row in ex.photon_preview()
        ],
        "evidence": ex.evidence(),
    }


def theory_qber(eve_intercept_fraction: float, channel_noise: float) -> float:
    """Expected QBER: Eve's f/4 and the channel's p combine as two independent bit flips."""
    e = eve_intercept_fraction / 4
    return e + channel_noise - 2 * e * channel_noise
