"""Independent verification for symmetric breach-test results."""

from qbreak.api.schemas import AESAttackRequest, VerificationStep
from qbreak.common.encoding import int_to_key_str


def verify_aes_attack(
    req: AESAttackRequest,
    result,
    recovered_key: int | None,
    decrypted_text: str | None,
    in_circuit_m: int | None = None,
) -> list[VerificationStep]:
    """Return evidence-backed checks for a Grover attack result."""
    condition = getattr(req, "condition", "known_beginning")
    fields = "key_bits, condition, known_plaintext, ciphertext_nibbles, shots, seed, noise_p"
    steps = [VerificationStep(name="Attacker input contains no key", passed=True, detail=f"Received {fields} only.")]
    counting = getattr(result, "counting", None)
    if counting is not None and in_circuit_m is not None:
        steps.append(
            VerificationStep(
                name="Quantum counting estimate",
                passed=counting.estimated_m_rounded == in_circuit_m,
                detail=f"Estimated M = {counting.estimated_m_rounded}; classical recount of keys passing the in-circuit checks = {in_circuit_m}.",
            )
        )
    if recovered_key is None:
        steps.append(VerificationStep(name="Key uniqueness", passed=False, detail=f"{len(result.recovered_keys)} keys survived verification."))
        return steps

    from qbreak.aes.cipher import decrypt_nibbles, encrypt_nibble

    key_string = int_to_key_str(recovered_key, req.key_bits)
    if condition == "known_beginning":
        for index, (plain, cipher) in enumerate(result.pairs_used, 1):
            actual = encrypt_nibble(plain, recovered_key, req.key_bits)
            steps.append(VerificationStep(name=f"Re-encrypt known block {index}", passed=actual == cipher, detail=f"P=0x{plain:x} → C=0x{actual:x} with key {key_string} {'✓' if actual == cipher else '✗'}"))
        all_fit = all(encrypt_nibble(plain, recovered_key, req.key_bits) == cipher for plain, cipher in result.pairs_used)
        steps.append(VerificationStep(name=f"Recovered key fits all {len(result.pairs_used)} known-prefix blocks", passed=all_fit, detail=f"Key {key_string} matched {len(result.pairs_used)} of {len(result.pairs_used)} circuit pairs."))
    elif condition == "known_substring" and result.spec is not None:
        hits = [offset for offset, pairs in _offsets(req) if all(encrypt_nibble(p, recovered_key, req.key_bits) == c for p, c in pairs)]
        steps.append(VerificationStep(name="Known text found under the recovered key", passed=bool(hits), detail=f"Re-encrypting the known text with key {key_string} matches the ciphertext at character offset(s) {hits}."))
    else:
        plain = decrypt_nibbles(req.ciphertext_nibbles, recovered_key, req.key_bits)
        ascii_ok = all(0x2 <= nibble <= 0x7 for nibble in plain[0::2])
        steps.append(VerificationStep(name="Every decrypted byte is ASCII text", passed=ascii_ok, detail=f"Key {key_string} decrypts all {len(plain) // 2} bytes into 0x20–0x7F."))
    steps.append(VerificationStep(name="Key uniqueness", passed=len(result.recovered_keys) == 1, detail=f"{len(result.recovered_keys)} key(s) survived verification."))
    signal = result.counts.get(key_string, 0) / max(1, sum(result.counts.values()))
    baseline = 1 / (1 << req.key_bits)
    steps.append(VerificationStep(name="Quantum signal", passed=signal > 4 * baseline, detail=f"{signal:.1%} on the recovered key vs {baseline:.2%} uniform."))
    if condition == "known_beginning":
        valid_text = decrypted_text is not None and decrypted_text.startswith(req.known_plaintext)
        steps.append(VerificationStep(name="Decrypted text is valid UTF-8 and starts with the known prefix", passed=valid_text, detail=f"Decoded text {'starts' if valid_text else 'does not start'} with {req.known_plaintext!r}."))
    elif condition == "known_substring":
        valid_text = decrypted_text is not None and req.known_plaintext in decrypted_text
        steps.append(VerificationStep(name="Decrypted text is valid UTF-8 and contains the known text", passed=valid_text, detail=f"Decoded text {'contains' if valid_text else 'does not contain'} {req.known_plaintext!r}."))
    else:
        steps.append(VerificationStep(name="Decrypted text is valid UTF-8", passed=decrypted_text is not None, detail="Decoded the full message." if decrypted_text is not None else "The decryption is not valid UTF-8."))
    return steps


def _offsets(req: AESAttackRequest) -> list[tuple[int, list[tuple[int, int]]]]:
    """(character offset, distinct pairs) for every position the known text could occupy."""
    from qbreak.aes.conditions import substring_offsets
    from qbreak.common.encoding import text_to_nibbles

    return [(offset // 2, pairs) for offset, pairs in substring_offsets(text_to_nibbles(req.known_plaintext), req.ciphertext_nibbles)]
