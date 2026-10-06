"""Orchestrate miniature RSA and Shor attack workflows."""

from qbreak.api.schemas import RSAAttackRequest, RSAEncryptRequest, RSAKeygenRequest
from qbreak.common.encoding import chunks_to_text, text_to_chunks
from qbreak.services.aes_service import _empty_circuit


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
    from qbreak.rsa.minirsa import decrypt_chunks, private_exponent
    from qbreak.verification.rsa_checks import verify_rsa_attack

    result = run_shor_attack(req.n, req.a, req.shots, req.seed)
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
    if result.construction == "permutation-unitary":
        warnings.append("Modular multiplication blocks are built from a classically computed permutation (standard for small demos).")
    return {
        "n": req.n, "a": result.a, "period": result.period, "factors": result.factors,
        "phi": phi, "d": d, "decrypted_text": decrypted_text, "n_count": result.n_count,
        "n_work": result.n_work, "construction": result.construction,
        "attempts": [vars(attempt) for attempt in result.attempts], "sim_time_ms": result.sim_time_ms,
        "circuit": circuit_info(result.circuit, result.transpiled, result.register_roles, result.explain_circuits),
        "measurement": measurement(result.counts, req.shots, lambda bits: f"y={int(bits, 2)}"),
        "verification": verify_rsa_attack(req, result, d, phi, decrypted_text), "warnings": warnings,
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
    }
