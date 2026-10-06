"""Independent verification for public-key breach-test results."""

from qbreak.api.schemas import RSAAttackRequest, VerificationStep
from qbreak.common.encoding import text_to_chunks


def verify_rsa_attack(req: RSAAttackRequest, result, d: int | None, phi: int | None, decrypted_text: str | None) -> list[VerificationStep]:
    """Return evidence-backed checks for a Shor factor-recovery result."""
    accepted = next((attempt for attempt in result.attempts if attempt.ok), None)
    if accepted is None or result.period is None or result.factors is None:
        return [VerificationStep(name="Measured phase produced a usable period", passed=False, detail="No accepted period and nontrivial factors were found in this run.")]
    p, q = result.factors
    r = result.period
    phase_ok = accepted.fraction.endswith(f"/{r}") or accepted.r_candidate == r
    steps = [VerificationStep(name="Measured phase y/2^t → fraction s/r", passed=phase_ok, detail=f"y={accepted.y}, phase={accepted.phase:.6f} → {accepted.fraction}, candidate r={accepted.r_candidate}.")]
    period_ok = pow(result.a, r, req.n) == 1
    steps.append(VerificationStep(name="a^r ≡ 1 (mod N)", passed=period_ok, detail=f"{result.a}^{r} mod {req.n} = {pow(result.a, r, req.n)}."))
    half = pow(result.a, r // 2, req.n) if r % 2 == 0 else None
    useful = r % 2 == 0 and half != req.n - 1
    steps.append(VerificationStep(name="r is even and a^(r/2) ≠ −1 (mod N)", passed=useful, detail=f"r={r}; {result.a}^({r}//2) mod {req.n} = {half}."))
    factors_ok = p * q == req.n and 1 < p < req.n and 1 < q < req.n
    steps.append(VerificationStep(name="p · q = N, both nontrivial", passed=factors_ok, detail=f"{p} × {q} = {p * q}; N={req.n}."))
    exponent_ok = d is not None and phi is not None and req.e * d % phi == 1
    steps.append(VerificationStep(name="e · d ≡ 1 (mod φ)", passed=exponent_ok, detail=f"{req.e} × {d} mod {phi} = {(req.e * d % phi) if d is not None and phi else 'unavailable'}."))
    if decrypted_text is None:
        chunks_match = False
    else:
        chunks, _ = text_to_chunks(decrypted_text)
        chunks_match = [pow(chunk, req.e, req.n) for chunk in chunks] == req.ciphertext
    steps.append(VerificationStep(name="Re-encrypting the decrypted chunks reproduces the ciphertext", passed=chunks_match, detail=f"Re-encryption {'matched' if chunks_match else 'did not match'} all {len(req.ciphertext)} ciphertext chunks."))
    steps.append(VerificationStep(name="Decrypted text is valid UTF-8", passed=decrypted_text is not None, detail=f"Decoded text: {decrypted_text!r}."))
    return steps
