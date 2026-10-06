"""Re-attack: the same quantum adversary against each protected bundle — blind.

This module receives ONLY what an eavesdropper sees: ciphertexts, nonces, the ML-KEM
encapsulation key and KEM ciphertext, and the public BB84 channel record. It never imports
the protect functions, key generation, or AES-GCM decryption, and no function here takes a
key, shared secret or plaintext (tests enforce both).

Honesty about what runs:
- AES-256 vs Grover: a feasibility check from the cited estimator; no circuit is executed.
- ML-KEM vs Shor: the Shor pipeline's input stage finds nothing to attack; no circuit runs.
- BB84 vs intercept-resend: a fresh BB84 exchange with Eve is actually simulated in Qiskit.
"""

from __future__ import annotations

import math
from typing import Any

from qbreak.aes.grover import optimal_iterations
from qbreak.aes.resources import aes_resource_estimate
from qbreak.config import (
    BB84_DEFAULT_RAW_QUBITS,
    BB84_QBER_THRESHOLD,
    SIMULATED_KEY_BITS,
    SYMMETRIC_MAX_KEY_BITS,
)
from qbreak.defence.bb84 import eavesdrop_exchange
from qbreak.defence.types import BB84_HONESTY_NOTE, CITATIONS, MLKEM_HONESTY_NOTE, unb64
from qbreak.experiments.aggregate import build_series
from qbreak.rsa.shor import shor_input_stage

STATEVECTOR_BYTES_PER_AMPLITUDE = 16
"""complex128 amplitudes, as Aer's statevector method stores them."""


def _cite(*keys: str) -> dict[str, str]:
    return {key: CITATIONS[key] for key in keys}


def _toy_grover_curve() -> list[dict[str, Any]]:
    """Measured MiniAES Grover scaling from round 2 (qubits / iterations vs key bits)."""
    try:
        rows = build_series("scaling")["rows"]
    except Exception:
        rows = []
    return [
        {"key_bits": r["size"], "qubits": r["qubits"], "iterations": r["iterations"], "transpiled_depth": r["transpiled_depth"]}
        for r in rows
        if r.get("cipher") == "miniaes" and r.get("size_kind") == "key_bits"
    ]


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    if len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return slope, my - slope * mx


def attack_aes256(bundle: dict[str, Any]) -> dict[str, Any]:
    """Grover vs AES-256: compute what the attack would need; do not run it."""
    ciphertext_bytes = len(unb64(bundle["ciphertext_b64"]))
    estimate = aes_resource_estimate(256)
    curve = _toy_grover_curve()
    fit = _linear_fit([r["key_bits"] for r in curve], [r["qubits"] for r in curve])
    largest = max([b for b in SIMULATED_KEY_BITS if b <= SYMMETRIC_MAX_KEY_BITS], default=SIMULATED_KEY_BITS[0])
    largest_qubits = next((round(r["qubits"]) for r in curve if r["key_bits"] == largest), None)
    qubits = estimate["logical_qubits"]["value"]
    iterations_log2 = estimate["grover_iterations"]["log2"]
    evidence = {
        # Headline numbers (flat, for the UI's key-number grid); details follow.
        "key_bits": 256,
        "effective_quantum_security_bits": 128,
        "logical_qubits": qubits,
        "grover_iterations": estimate["grover_iterations"]["text"],
        "grover_formula": estimate["grover_iterations"]["formula"],
        "t_depth": estimate["t_depth"]["text"],
        "simulator_ceiling_qubits": largest_qubits,
        "ciphertext_bytes": ciphertext_bytes,
        "note": "Not executed: a feasibility check from the cited resource estimate, not a Grover run.",
        "observed": {"ciphertext_bytes": ciphertext_bytes, "nonce_bytes": len(unb64(bundle["nonce_b64"])), "known_plaintext_pairs": 0},
        "required": {
            "logical_qubits": qubits,
            "grover_iterations": estimate["grover_iterations"]["text"],
            "grover_iterations_log2": round(iterations_log2, 2),
            "grover_iterations_formula": estimate["grover_iterations"]["formula"],
            "t_gates": estimate["t_gates"]["text"],
            "t_depth": estimate["t_depth"]["text"],
            "known_pairs_needed": estimate["known_pairs_needed"]["value"],
            "statevector_bytes_log2": qubits + int(math.log2(STATEVECTOR_BYTES_PER_AMPLITUDE)),
        },
        "simulator_ceiling": {
            "largest_simulated_key_bits": largest,
            "largest_simulated_qubits": largest_qubits,
            "largest_simulated_iterations": optimal_iterations(largest),
            "note": "Every extra qubit doubles a state vector's memory; about 30 qubits already needs "
            "16 GB. No simulator, and no existing quantum machine, comes within thousands of "
            "error-corrected logical qubits of this attack.",
        },
        "toy_curve": curve,
        "toy_extrapolation": None if fit is None else {
            "qubits_per_key_bit": round(fit[0], 3),
            "qubits_at_256_bits": round(fit[0] * 256 + fit[1]),
            "note": "A naive straight-line extrapolation of our MiniAES circuits (not real AES); "
            "the cited estimate for real AES-256 is the number that counts.",
        },
        "nist": estimate["nist"],
        "parallelism_caveat": estimate["parallelism_caveat"],
    }
    return {
        "method": "aes256",
        "attack": "Grover key search",
        "executed": False,
        "verdict": "infeasible",
        "explanation": (
            f"Grover would need about {qubits:,} error-corrected logical qubits and {estimate['grover_iterations']['text']} "
            "sequential iterations to search a 256-bit key (Grassl et al. 2016); our simulator tops out at "
            f"{largest_qubits or 'about 24'} qubits for a {largest}-bit toy key. No circuit was run: Grover only halves "
            "AES-256's strength, leaving about 128 bits."
        ),
        "evidence": evidence,
        "citations": _cite("GLRS16", "NIST16", "FIPS197"),
    }


def attack_mlkem(bundle: dict[str, Any]) -> dict[str, Any]:
    """Shor vs ML-KEM: hand the public bundle to the Shor pipeline's input stage."""
    public = {k: v for k, v in bundle.items() if k != "public_metrics"}
    stage = shor_input_stage(public)
    evidence = {
        "parameter_set": bundle.get("parameter_set", "ML-KEM-768"),
        "encapsulation_key_bytes": len(unb64(bundle["encapsulation_key_b64"])),
        "kem_ciphertext_bytes": len(unb64(bundle["kem_ciphertext_b64"])),
        "shor_applicable": stage["applicable"],
        "note": "Not executed: the Shor pipeline's input stage found nothing to factor. " + MLKEM_HONESTY_NOTE,
        "shor_input_stage": stage,
        "observed": {
            "parameter_set": bundle.get("parameter_set", "ML-KEM-768"),
            "encapsulation_key_bytes": len(unb64(bundle["encapsulation_key_b64"])),
            "kem_ciphertext_bytes": len(unb64(bundle["kem_ciphertext_b64"])),
            "ciphertext_bytes": len(unb64(bundle["ciphertext_b64"])),
        },
        "hard_problem": "Module Learning With Errors (Module-LWE), ML-KEM-768: module rank k = 3, n = 256, q = 3329.",
        "best_known_quantum_attacks": "Lattice reduction and sieving; known quantum speed-ups for these are "
        "at most polynomial, not exponential. No efficient quantum algorithm for Module-LWE is known.",
        "implementation_note": MLKEM_HONESTY_NOTE,
    }
    if stage["applicable"]:  # the request schema forbids extra fields, so this cannot happen
        raise ValueError("ML-KEM bundle unexpectedly carries an RSA modulus or discrete-log group")
    return {
        "method": "mlkem",
        "attack": "Shor's algorithm",
        "executed": False,
        "verdict": "not_applicable",
        "explanation": (
            "The Shor pipeline's input stage found no RSA modulus and no discrete-log group in the ML-KEM "
            "bundle, so there is nothing to factor. ML-KEM rests on the Module-LWE lattice problem, for "
            "which there is no known efficient quantum attack (FIPS 203)."
        ),
        "evidence": evidence,
        "citations": _cite("FIPS203", "SHOR97", "KYBERPY"),
    }


def attack_bb84(
    bundle: dict[str, Any] | None,
    *,
    eve_intercept_fraction: float = 1.0,
    channel_noise: float = 0.0,
    raw_qubits: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Intercept-resend vs BB84: actually run a fresh exchange with Eve in Qiskit."""
    channel = (bundle or {}).get("channel") or {}
    raw = raw_qubits or channel.get("raw_qubits") or BB84_DEFAULT_RAW_QUBITS
    threshold = channel.get("qber_threshold", BB84_QBER_THRESHOLD)
    view = eavesdrop_exchange(raw, eve_intercept_fraction=eve_intercept_fraction, channel_noise=channel_noise, qber_threshold=threshold, seed=seed)
    sifted = view["sifted_bits"]
    if view["detected"]:
        verdict = "detected"
        explanation = (
            f"Eve intercepted {view['intercepted_photons']} of {view['raw_qubits']} photons. Measuring them disturbed the "
            f"states: the QBER rose to {view['qber']:.1%}, above the {threshold:.0%} threshold, so Alice and Bob aborted "
            "and discarded the key. The attacker gains nothing usable."
        )
    else:
        leak = round(eve_intercept_fraction / 2 * sifted)
        verdict = "undetected_low_intercept"
        explanation = (
            f"Eve intercepted only {eve_intercept_fraction:.0%} of photons, so the QBER ({view['qber']:.1%}) stayed under the "
            f"{threshold:.0%} threshold. She saw about {leak} of {sifted} sifted bits in the matching basis "
            f"(≈ fraction/2); privacy amplification hashes the key down so that this partial knowledge is removed."
        )
    evidence = {k: v for k, v in view.items() if k != "evidence"}
    evidence["expected_eve_info_bits"] = round(eve_intercept_fraction / 2 * sifted)
    evidence["expected_leak_bits"] = evidence["expected_eve_info_bits"]
    evidence["key_discarded"] = view["detected"] or not view["accepted"]
    evidence["note"] = "Executed: a fresh BB84 exchange with Eve was simulated in Qiskit Aer. " + BB84_HONESTY_NOTE
    evidence["circuits"] = view["evidence"]
    evidence["honesty_note"] = BB84_HONESTY_NOTE
    evidence["original_exchange"] = {
        "accepted": channel.get("accepted"),
        "qber": channel.get("qber"),
        "note": "The re-attack runs a fresh exchange; the original key was never sent to the attacker.",
    }
    return {
        "method": "bb84",
        "attack": "Intercept-resend eavesdropping",
        "executed": True,
        "verdict": verdict,
        "explanation": explanation,
        "evidence": evidence,
        "citations": _cite("BB84", "SP2000"),
    }


ORIGINAL_ATTACK_TEXT = {
    "miniaes": "Stage 1: Grover's search recovered the MiniAES key and read the message.",
    "minirsa": "Stage 1: Shor's algorithm factored the MiniRSA modulus, rebuilt the private key and read the message.",
}


def original_context(original: dict[str, Any] | None) -> dict[str, Any] | None:
    """The 'before' half of before → after."""
    if not original:
        return None
    cipher = original["cipher"]
    breached = original.get("verdict", "breached") == "breached"
    return {
        "cipher": cipher,
        "verdict": original.get("verdict", "breached"),
        "text": ORIGINAL_ATTACK_TEXT[cipher] if breached else f"Stage 1: the {cipher} attack did not breach the message.",
    }
