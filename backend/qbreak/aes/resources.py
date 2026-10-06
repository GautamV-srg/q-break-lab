"""What a Grover key search would cost against REAL AES, from published estimates.

Nothing here is computed from our miniature circuits or invented: every hardware figure
is quoted from the cited source, so the frontend and notebook can show "what this means
at real scale" with references. Figures are stored as mantissa x 2^exponent exactly as
the sources state them.

Sources
    [GLRS16] M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt. "Applying Grover's
             algorithm to AES: quantum resource estimates." PQCrypto 2016, LNCS 9606,
             pp. 29-43. arXiv:1512.04965. Logical-qubit, T-gate, Clifford-gate and T-depth
             counts for a full Grover key search on AES-128/192/256 (r = 3/4/5 known
             plaintext-ciphertext pairs to make the key unique).
    [NIST16] NIST, "Submission Requirements and Evaluation Criteria for the Post-Quantum
             Cryptography Standardization Process" (Call for Proposals, 2016), Sec. 4.A.5:
             security categories 1/3/5 are defined by AES-128/192/256 key search, with
             quantum gate cost 2^170 / 2^233 / 2^298 divided by MAXDEPTH, and MAXDEPTH
             between 2^40 and 2^96.
    [JNRV20] S. Jaques, M. Naehrig, M. Roetteler, F. Virdia. "Implementing Grover oracles
             for quantum key search on AES and LowMC." EUROCRYPT 2020. Later, cheaper
             circuits; listed as further reading (no figures quoted here).
"""

from __future__ import annotations

import math

CITATIONS: dict[str, str] = {
    "GLRS16": "M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, \"Applying Grover's "
    "algorithm to AES: quantum resource estimates\", PQCrypto 2016, LNCS 9606, pp. 29-43, "
    "arXiv:1512.04965.",
    "NIST16": "NIST, \"Submission Requirements and Evaluation Criteria for the Post-Quantum "
    "Cryptography Standardization Process\", Call for Proposals, 2016, Section 4.A.5.",
    "JNRV20": "S. Jaques, M. Naehrig, M. Roetteler, F. Virdia, \"Implementing Grover oracles "
    "for quantum key search on AES and LowMC\", EUROCRYPT 2020, arXiv:1910.01700.",
}

_GLRS16: dict[int, dict] = {
    128: {"pairs": 3, "logical_qubits": 2953, "t_gates": (1.19, 86), "clifford_gates": (1.55, 86), "t_depth": (1.06, 80)},
    192: {"pairs": 4, "logical_qubits": 4449, "t_gates": (1.81, 118), "clifford_gates": (1.17, 119), "t_depth": (1.21, 112)},
    256: {"pairs": 5, "logical_qubits": 6681, "t_gates": (1.41, 151), "clifford_gates": (1.83, 151), "t_depth": (1.44, 144)},
}

_NIST_GATE_COST_EXP: dict[int, int] = {128: 170, 192: 233, 256: 298}
_NIST_CATEGORY: dict[int, int] = {128: 1, 192: 3, 256: 5}


def _power(mantissa: float, exponent: int) -> dict:
    return {"mantissa": mantissa, "exponent": exponent, "log2": exponent + math.log2(mantissa), "text": f"{mantissa}·2^{exponent}"}


def aes_resource_estimate(key_bits: int) -> dict:
    """Published resource estimate for a Grover key search on AES-`key_bits` (128/192/256)."""
    if key_bits not in _GLRS16:
        raise ValueError("Real-scale estimates exist for AES-128, AES-192 and AES-256 only")
    g = _GLRS16[key_bits]
    iterations_log2 = math.log2(math.pi / 4) + key_bits / 2
    return {
        "cipher": f"AES-{key_bits}",
        "key_bits": key_bits,
        "grover_iterations": {
            "formula": f"⌊π/4 · 2^{key_bits // 2}⌋",
            "log2": iterations_log2,
            "text": f"≈ 2^{iterations_log2:.1f}",
            "source": "NIST16",
        },
        "classical_tries": {"text": f"≈ 2^{key_bits - 1} on average", "log2": key_bits - 1},
        "known_pairs_needed": {"value": g["pairs"], "source": "GLRS16"},
        "logical_qubits": {"value": g["logical_qubits"], "source": "GLRS16"},
        "physical_qubits": {
            "value": None,
            "note": "Not estimated: GLRS16 reports logical qubits only. Physical counts depend "
            "on the error-correcting code and hardware error rates; error correction typically "
            "multiplies the logical count by a large factor.",
        },
        "t_gates": {**_power(*g["t_gates"]), "source": "GLRS16"},
        "clifford_gates": {**_power(*g["clifford_gates"]), "source": "GLRS16"},
        "t_depth": {**_power(*g["t_depth"]), "source": "GLRS16"},
        "nist": {
            "security_category": _NIST_CATEGORY[key_bits],
            "quantum_gate_cost": f"2^{_NIST_GATE_COST_EXP[key_bits]} / MAXDEPTH",
            "maxdepth_range": "2^40 to 2^96 logical gates in series",
            "source": "NIST16",
        },
        "parallelism_caveat": "Grover parallelises badly: splitting the search over P machines "
        "only cuts each machine's iterations by √P, so a depth limit (MAXDEPTH) makes the total "
        "cost grow. This is why NIST states the cost as gates divided by MAXDEPTH.",
        "verify_note": "Figures are quoted from the cited papers; check them against the source "
        "before re-publishing.",
        "citations": {key: CITATIONS[key] for key in ("GLRS16", "NIST16", "JNRV20")},
    }


def all_aes_estimates() -> dict:
    """Estimates for AES-128/192/256, plus the honest framing for the UI and notebook."""
    return {
        "estimates": [aes_resource_estimate(bits) for bits in (128, 192, 256)],
        "takeaway": "Even the smallest real AES key search needs thousands of error-corrected "
        "logical qubits, about 2^86 T gates and a T-depth near 2^80 — far beyond any "
        "existing machine. Our miniature MiniAES runs show the attack's workflow, not a threat "
        "to deployed AES.",
        "citations": CITATIONS,
    }
