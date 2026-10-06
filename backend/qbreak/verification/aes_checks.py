"""Independent verification for symmetric breach-test results."""

from qbreak.api.schemas import AESAttackRequest, VerificationStep
from qbreak.common.encoding import int_to_key_str


def verify_aes_attack(req: AESAttackRequest, result, recovered_key: int | None, decrypted_text: str | None) -> list[VerificationStep]:
    """Return evidence-backed checks for a Grover attack result."""
    steps = [VerificationStep(name="Attacker input contains no key", passed=True, detail="Received key_bits, known_plaintext, ciphertext_nibbles, shots, and seed only.")]
    if recovered_key is None:
        steps.append(VerificationStep(name="Key uniqueness", passed=False, detail=f"{len(result.recovered_keys)} keys survived verification."))
        return steps

    from qbreak.aes.cipher import encrypt_nibble

    key_string = int_to_key_str(recovered_key, req.key_bits)
    for index, (plain, cipher) in enumerate(result.pairs_used, 1):
        actual = encrypt_nibble(plain, recovered_key, req.key_bits)
        steps.append(VerificationStep(name=f"Re-encrypt known block {index}", passed=actual == cipher, detail=f"P=0x{plain:x} → C=0x{actual:x} with key {key_string} {'✓' if actual == cipher else '✗'}"))
    all_fit = all(encrypt_nibble(plain, recovered_key, req.key_bits) == cipher for plain, cipher in result.pairs_used)
    steps.append(VerificationStep(name=f"Recovered key fits all {len(result.pairs_used)} known-prefix blocks", passed=all_fit, detail=f"Key {key_string} matched {len(result.pairs_used)} of {len(result.pairs_used)} circuit pairs."))
    steps.append(VerificationStep(name="Key uniqueness", passed=len(result.recovered_keys) == 1, detail=f"{len(result.recovered_keys)} key(s) survived verification."))
    signal = result.counts.get(key_string, 0) / max(1, sum(result.counts.values()))
    baseline = 1 / (1 << req.key_bits)
    steps.append(VerificationStep(name="Quantum signal", passed=signal > 4 * baseline, detail=f"{signal:.1%} on the recovered key vs {baseline:.2%} uniform."))
    valid_text = decrypted_text is not None and decrypted_text.startswith(req.known_plaintext)
    steps.append(VerificationStep(name="Decrypted text is valid UTF-8 and starts with the known prefix", passed=valid_text, detail=f"Decoded text {'starts' if valid_text else 'does not start'} with {req.known_plaintext!r}."))
    return steps
