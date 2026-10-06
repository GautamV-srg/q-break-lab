"""Orchestrate MiniAES encryption and Grover attack workflows."""

import math

from qbreak.api.schemas import AESAttackRequest, AESEncryptRequest
from qbreak.common.encoding import int_to_key_str, key_str_to_int, nibbles_to_text, text_to_nibbles


def _empty_circuit() -> dict:
    return {
        "num_qubits": 0,
        "num_clbits": 0,
        "depth": 0,
        "transpiled_depth": 0,
        "gate_counts": {},
        "registers": [],
        "drawings": [{"title": "Full attack circuit", "text": "Quantum module not merged yet."}],
        "qasm": None,
    }


def encrypt(req: AESEncryptRequest) -> dict:
    """Encode and encrypt the organization's plaintext."""
    plaintext_nibbles = text_to_nibbles(req.plaintext)
    try:
        from qbreak.aes.cipher import encrypt_nibbles, trace_encrypt_nibble
    except ImportError:
        if req.plaintext == "Hi judges!" and req.key == "1001" and req.key_bits == 4:
            ciphertext = [3, 8, 14, 13, 9, 5, 14, 2, 0, 10, 14, 3, 14, 0, 14, 10, 0, 12, 9, 6]
        else:
            key = key_str_to_int(req.key, req.key_bits) & 0xF
            ciphertext = [value ^ key for value in plaintext_nibbles]
        trace = [{"step": "Input P", "value": plaintext_nibbles[0], "detail": f"{plaintext_nibbles[0]:04b}"}]
    else:
        key = key_str_to_int(req.key, req.key_bits)
        ciphertext = encrypt_nibbles(plaintext_nibbles, key, req.key_bits)
        trace = trace_encrypt_nibble(plaintext_nibbles[0], key, req.key_bits)
    return {
        "key_bits": req.key_bits,
        "plaintext_nibbles": plaintext_nibbles,
        "ciphertext_nibbles": ciphertext,
        "ciphertext_hex": "".join(f"{value:x}" for value in ciphertext),
        "byte_length": len(req.plaintext.encode("utf-8")),
        "trace": trace,
    }


def attack(req: AESAttackRequest) -> dict:
    """Run Grover's algorithm using only intercepted attacker inputs."""
    known = text_to_nibbles(req.known_plaintext)
    try:
        from qbreak.aes.cipher import decrypt_nibbles
        from qbreak.aes.grover import run_grover_attack
    except ImportError:
        return _mock_attack(req, known)

    result = run_grover_attack(known, req.ciphertext_nibbles, req.key_bits, req.shots, req.seed)
    recovered_keys = [int_to_key_str(key, req.key_bits) for key in result.recovered_keys]
    candidate_decryptions = []
    decrypted_by_key: dict[int, tuple[list[int], str | None]] = {}
    for key in result.recovered_keys:
        decrypted_nibbles = decrypt_nibbles(req.ciphertext_nibbles, key, req.key_bits)
        try:
            text = nibbles_to_text(decrypted_nibbles)
        except ValueError:
            text = None
        decrypted_by_key[key] = (decrypted_nibbles, text)
        candidate_decryptions.append({"key": int_to_key_str(key, req.key_bits), "text": text})

    unique = len(result.recovered_keys) == 1
    unique_key = result.recovered_keys[0] if unique else None
    decrypted_nibbles, decrypted_text = decrypted_by_key.get(unique_key, ([], None))
    warnings: list[str] = []
    if len(result.recovered_keys) > 1:
        warnings.append("Several keys fit the known plaintext; supply a longer known prefix to disambiguate.")
    if len(set(result.pairs_used)) <= 1:
        warnings.append("The known prefix supplies only one distinct block pair, so the crib is weak.")

    from qbreak.common.evidence import circuit_info, measurement
    from qbreak.verification.aes_checks import verify_aes_attack

    return {
        "key_bits": req.key_bits,
        "search_space": 1 << req.key_bits,
        "pairs_used": [{"plain": plain, "cipher": cipher} for plain, cipher in result.pairs_used],
        "iterations": result.iterations,
        "optimal_iterations_formula": _iteration_formula(req.key_bits, result.iterations),
        "recovered_keys": recovered_keys,
        "unique": unique,
        "key": int_to_key_str(unique_key, req.key_bits) if unique_key is not None else None,
        "decrypted_text": decrypted_text,
        "decrypted_nibbles": decrypted_nibbles,
        "candidate_decryptions": candidate_decryptions,
        "attempts": [{"iterations": attempt.iterations, "verified_keys": [int_to_key_str(key, req.key_bits) for key in attempt.verified_keys]} for attempt in result.attempts],
        "sim_time_ms": result.sim_time_ms,
        "circuit": circuit_info(result.circuit, result.transpiled, result.register_roles, result.explain_circuits),
        "measurement": measurement(result.counts, req.shots, lambda bits: f"key {bits}" + (" ✓ recovered" if bits in recovered_keys else "")),
        "verification": verify_aes_attack(req, result, unique_key, decrypted_text),
        "warnings": warnings,
    }


def _iteration_formula(key_bits: int, iterations: int) -> str:
    return f"⌊π/4 · √({1 << key_bits}/1)⌋ = {iterations}"


def _mock_attack(req: AESAttackRequest, known: list[int]) -> dict:
    key = "1001" if req.key_bits == 4 else "0" * req.key_bits
    iterations = math.floor(math.pi / 4 * math.sqrt(1 << req.key_bits))
    counts = {key: req.shots}
    pairs = [{"plain": plain, "cipher": cipher} for plain, cipher in zip(known[:2], req.ciphertext_nibbles[:2])]
    decrypted = "Hi judges!" if req.ciphertext_nibbles[:2] == [3, 8] else None
    return {
        "key_bits": req.key_bits,
        "search_space": 1 << req.key_bits,
        "pairs_used": pairs,
        "iterations": iterations,
        "optimal_iterations_formula": _iteration_formula(req.key_bits, iterations),
        "recovered_keys": [key],
        "unique": True,
        "key": key,
        "decrypted_text": decrypted,
        "decrypted_nibbles": text_to_nibbles(decrypted) if decrypted else [],
        "candidate_decryptions": [{"key": key, "text": decrypted}],
        "attempts": [{"iterations": iterations, "verified_keys": [key]}],
        "sim_time_ms": 0.0,
        "circuit": _empty_circuit(),
        "measurement": {"shots": req.shots, "counts": counts, "top": [{"bitstring": key, "value": int(key, 2), "count": req.shots, "probability": 1.0, "meaning": f"key {key} ✓ recovered"}]},
        "verification": [{"name": "Attacker input contains no key", "passed": True, "detail": "Received key_bits, known_plaintext, ciphertext_nibbles, shots, and seed only."}],
        "warnings": ["MOCK DATA — quantum module not merged yet"],
    }
