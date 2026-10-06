"""Orchestrate miniature RSA and Shor attack workflows."""

from math import ceil, log2

from qbreak.api.schemas import RSAAttackRequest, RSAEncryptRequest, RSAKeygenRequest
from qbreak.common.encoding import chunks_to_text, text_to_chunks
from qbreak.config import (
    ENABLED_MODULI,
    RSA_DISABLED_MODULI,
    RSA_MAX_NOISE_P,
    RSA_MODULI_CATALOGUE,
    RSA_NOISE_MODULI,
)
from qbreak.services.aes_service import _empty_circuit

PRECOMPUTATION_NOTE = (
    "Disclosed classical pre-computation: each controlled multiply-by-b block embeds the "
    "permutation x → b·x mod N with b = a^(2^k) mod N, computed classically when the circuit is "
    "built (standard for small demonstrations; a full-scale Shor would need reversible "
    "modular-arithmetic circuits). The period itself is read from the quantum measurement."
)

CONSTRUCTIONS = [
    {
        "key": "swap",
        "name": "textbook-swaps",
        "label": "Textbook swap circuit (2n counting qubits)",
        "counting_qubits": "2n",
        "description": "Hand-built Qiskit-textbook circuit: multiplication by a mod 15 as swaps and NOTs, then an inverse QFT.",
        "headline": False,
    },
    {
        "key": "permutation",
        "name": "permutation-unitary",
        "label": "Permutation blocks (2n counting qubits)",
        "counting_qubits": "2n",
        "description": "Counting register of 2n qubits and an inverse QFT; each controlled multiplication is a classically computed, disclosed permutation block.",
        "headline": False,
    },
    {
        "key": "iterative",
        "name": "iterative-phase-estimation",
        "label": "Iterative Shor (1 counting qubit)",
        "counting_qubits": "1",
        "description": "One counting qubit reset and reused for 2n rounds, with measurement-conditioned phase corrections replacing the inverse QFT: same factors, far fewer qubits.",
        "headline": True,
    },
]


def _qubits(n: int) -> tuple[int, int]:
    n_work = ceil(log2(n))
    return 3 * n_work, 1 + n_work


def config_fields() -> dict:
    """Public-key section of /api/config: moduli (enabled and disabled, with reasons) and constructions."""
    options = []
    for n in RSA_MODULI_CATALOGUE:
        enabled = n in ENABLED_MODULI
        register_2n, iterative = _qubits(n)
        options.append({
            "n": n, "label": f"N = {n}", "enabled": enabled, "kind": "supported",
            "reason": None if enabled else "Not enabled on this instance (QBREAK_MODULI).",
            "qubits_register_2n": register_2n, "qubits_iterative": iterative,
        })
    options.extend(
        {**option, "enabled": False, "qubits_register_2n": None, "qubits_iterative": None}
        for option in RSA_DISABLED_MODULI
    )
    constructions = [
        {**c, "moduli": [n for n in ENABLED_MODULI if c["key"] != "swap" or n == 15]} for c in CONSTRUCTIONS
    ]
    return {
        "rsa_moduli_options": options,
        "rsa_constructions": constructions,
        "rsa_noise_moduli": [n for n in RSA_NOISE_MODULI if n in ENABLED_MODULI],
        "rsa_max_noise_p": RSA_MAX_NOISE_P,
    }


def keygen(req: RSAKeygenRequest) -> dict:
    """Generate the organization's miniature RSA key pair."""
    try:
        from qbreak.rsa.minirsa import generate_keypair
    except ImportError:
        p, q, e = 3, 5, 3
        phi, d = 8, 3
        e_equals_d = True
    else:
        pair = generate_keypair(req.n)
        p, q, e, phi, d, e_equals_d = pair.p, pair.q, pair.e, pair.phi, pair.d, pair.e_equals_d
    warnings = []
    if e_equals_d:
        warnings.append(f"At N={req.n} the public and private exponents are equal (e = d = {e}). This is a demonstration of Shor's factor-recovery workflow, not a secure RSA example.")
    return {"n": req.n, "e": e, "victim_secret": {"p": p, "q": q, "phi": phi, "d": d}, "e_equals_d": e_equals_d, "warnings": warnings}


def encrypt(req: RSAEncryptRequest) -> dict:
    """Encode and encrypt the organization's plaintext in three-bit chunks."""
    chunks, bit_length = text_to_chunks(req.plaintext)
    try:
        from qbreak.rsa.minirsa import encrypt_chunks
    except ImportError:
        ciphertext = [pow(chunk, req.e, req.n) for chunk in chunks]
    else:
        ciphertext = encrypt_chunks(chunks, req.n, req.e)
    return {"plaintext_chunks": chunks, "bit_length": bit_length, "chunk_bits": 3, "ciphertext": ciphertext}


def attack(req: RSAAttackRequest) -> dict:
    """Run Shor's workflow using only the public key and intercepted ciphertext."""
    try:
        from qbreak.rsa.shor import run_shor_attack
    except ImportError:
        return _mock_attack(req)

    from qbreak.common.evidence import circuit_info, measurement
    from qbreak.rsa.classical import comparison_record, construction_key
    from qbreak.rsa.minirsa import decrypt_chunks, private_exponent
    from qbreak.verification.rsa_checks import verify_rsa_attack

    result = run_shor_attack(req.n, req.a, req.shots, req.seed, construction=req.construction, noise_p=req.noise_p)
    phi = d = None
    decrypted_text = None
    if result.factors:
        d, phi = private_exponent(*result.factors, req.e)
        decrypted_chunks = decrypt_chunks(req.ciphertext, req.n, d)
        try:
            decrypted_text = chunks_to_text(decrypted_chunks, req.bit_length)
        except ValueError:
            decrypted_text = None
    warnings = []
    note = PRECOMPUTATION_NOTE if result.multiplier_blocks == "permutation-unitary" else None
    if note:
        warnings.append("Modular multiplication blocks are built from a classically computed permutation (standard for small demos).")
    if req.noise_p is not None:
        warnings.append(f"Run under depolarising noise p = {req.noise_p:g} (two-qubit gates; p/10 on one-qubit gates), transpiled to u + cx.")
    return {
        "n": req.n, "a": result.a, "period": result.period, "factors": result.factors,
        "phi": phi, "d": d, "decrypted_text": decrypted_text, "n_count": result.n_count,
        "n_work": result.n_work, "construction": result.construction,
        "attempts": [vars(attempt) for attempt in result.attempts], "sim_time_ms": result.sim_time_ms,
        "circuit": circuit_info(result.circuit, result.transpiled, result.register_roles, result.explain_circuits),
        "measurement": measurement(result.counts, req.shots, lambda bits: f"y={int(bits, 2)}"),
        "verification": verify_rsa_attack(req, result, d, phi, decrypted_text), "warnings": warnings,
        "construction_key": construction_key(result.construction), "counting_qubits": result.counting_qubits,
        "multiplier_blocks": result.multiplier_blocks, "circuit_runs": result.circuit_runs,
        "noise_p": req.noise_p, "classical_precomputation_note": note,
        "comparison": comparison_record(result, req.shots, req.seed),
    }


def _mock_attack(req: RSAAttackRequest) -> dict:
    decrypted_chunks = [pow(value, 3, req.n) for value in req.ciphertext]
    try:
        text = chunks_to_text(decrypted_chunks, req.bit_length)
    except ValueError:
        text = None
    measured = "01000000"
    return {
        "n": req.n, "a": 7, "period": 4, "factors": (3, 5), "phi": 8, "d": 3,
        "decrypted_text": text, "n_count": 8, "n_work": 4, "construction": "textbook-swaps",
        "attempts": [{"a": 7, "measured": measured, "y": 64, "phase": 0.25, "fraction": "1/4", "r_candidate": 4, "ok": True, "reason": "7^4 mod 15 = 1; r even; 7^2 mod 15 = 4 ≠ 14"}],
        "sim_time_ms": 0.0, "circuit": _empty_circuit(),
        "measurement": {"shots": req.shots, "counts": {measured: req.shots}, "top": [{"bitstring": measured, "value": 64, "count": req.shots, "probability": 1.0, "meaning": "y=64 → phase 0.25 → 1/4"}]},
        "verification": [{"name": "Attacker input contains no factors", "passed": True, "detail": "Received n, e, ciphertext, bit_length, a, shots, and seed only."}],
        "warnings": ["MOCK DATA — quantum module not merged yet"],
        "construction_key": "swap", "counting_qubits": 8, "multiplier_blocks": "textbook-swaps", "circuit_runs": 1,
        "noise_p": req.noise_p, "classical_precomputation_note": None,
        "comparison": {
            "quantum": {"construction": "swap", "construction_name": "textbook-swaps", "circuit_runs": 1, "shots_per_run": req.shots, "qubits": 12, "depth": 0, "qubits_by_construction": {"register_2n": 12, "iterative": 5}, "factors_found": True},
            "classical": {"trial_divisions": 2, "order_finding_mults": 3, "order_finding_bases_tried": 1, "factors_found": True},
            "wallclock_ms": {"quantum_simulation": 0.0, "trial_division": 0.0, "order_finding": 0.0},
            "wallclock_note": "MOCK DATA",
        },
    }
