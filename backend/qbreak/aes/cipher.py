"""MiniAES: an AES-inspired toy cipher (the "test subject" of the symmetric breach test).

This is NOT a reduced version of the real AES standard. It is a deliberately tiny,
deliberately insecure cipher that borrows AES vocabulary so the steps are familiar:

    block  = 4 bits (one nibble), one round, every nibble encrypted independently (ECB)
    key    = 4, 6 or 8 bits

    x = p XOR K0          AddRoundKey  (mix in the first round key)
    s = SBOX[x]           SubNibble    (non-linear substitution, the Mini-AES S-box)
    y = rotl4(s, 1)       RotateBits   (a stand-in for AES's ShiftRows / MixColumns)
    c = y XOR K1          AddRoundKey  (mix in the second round key)

Round keys:
    K0 = the low 4 bits of the key
    H  = the high 4 bits of the key,  K1 = rotl4(H, 1) XOR RCON

Every key bit affects the result, and every key gives a different permutation of the
16 nibbles, so a long enough known plaintext always pins down a unique key.
"""

from __future__ import annotations

SBOX: tuple[int, ...] = (
    0xE, 0x4, 0xD, 0x1, 0x2, 0xF, 0xB, 0x8,
    0x3, 0xA, 0x6, 0xC, 0x5, 0x9, 0x0, 0x7,
)  # fmt: skip
"""The S-box from the educational Mini-AES (R. Phan, 2002)."""

INV_SBOX: tuple[int, ...] = tuple(SBOX.index(i) for i in range(16))
RCON: int = 0x3

SUPPORTED_KEY_BITS: tuple[int, ...] = (4, 6, 8)


def _rotl4(v: int) -> int:
    """Rotate a nibble left by one bit."""
    return ((v << 1) | (v >> 3)) & 0xF


def _rotr4(v: int) -> int:
    """Rotate a nibble right by one bit."""
    return ((v >> 1) | (v << 3)) & 0xF


def _bin4(v: int) -> str:
    """Nibble as a 4-character MSB-first binary string."""
    return format(v, "04b")


def _check_nibble(v: int, name: str) -> None:
    if not isinstance(v, int) or not 0 <= v <= 0xF:
        raise ValueError(f"{name} must be a nibble (0..15), got {v!r}")


def round_keys(key: int, key_bits: int) -> tuple[int, int]:
    """Derive the two round keys (K0, K1) from a key.

    K0 is the low nibble of the key. K1 is built from the high nibble H of the key:
    K1 = rotl4(H, 1) XOR RCON. For 4-bit keys H and K0 are the same nibble; for
    6-bit keys they overlap in two bits; for 8-bit keys they are disjoint.

    Raises ValueError for an unsupported key size or an out-of-range key.
    """
    if key_bits not in SUPPORTED_KEY_BITS:
        raise ValueError(f"key_bits must be one of {SUPPORTED_KEY_BITS}, got {key_bits!r}")
    if not isinstance(key, int) or not 0 <= key < (1 << key_bits):
        raise ValueError(f"key must be an integer in 0..{(1 << key_bits) - 1}, got {key!r}")
    k0 = key & 0xF
    h = (key >> (key_bits - 4)) & 0xF
    k1 = _rotl4(h) ^ RCON
    return k0, k1


def encrypt_nibble(p: int, key: int, key_bits: int) -> int:
    """Encrypt one 4-bit plaintext nibble with MiniAES."""
    _check_nibble(p, "plaintext nibble")
    k0, k1 = round_keys(key, key_bits)
    return _rotl4(SBOX[p ^ k0]) ^ k1


def decrypt_nibble(c: int, key: int, key_bits: int) -> int:
    """Decrypt one 4-bit ciphertext nibble with MiniAES (the steps in reverse)."""
    _check_nibble(c, "ciphertext nibble")
    k0, k1 = round_keys(key, key_bits)
    return INV_SBOX[_rotr4(c ^ k1)] ^ k0


def encrypt_nibbles(ps: list[int], key: int, key_bits: int) -> list[int]:
    """Encrypt a list of nibbles independently (ECB mode: equal inputs give equal outputs)."""
    round_keys(key, key_bits)  # validate even when the list is empty
    return [encrypt_nibble(p, key, key_bits) for p in ps]


def decrypt_nibbles(cs: list[int], key: int, key_bits: int) -> list[int]:
    """Decrypt a list of nibbles independently (ECB mode)."""
    round_keys(key, key_bits)
    return [decrypt_nibble(c, key, key_bits) for c in cs]


def trace_encrypt_nibble(p: int, key: int, key_bits: int) -> list[dict]:
    """Encrypt one nibble and record every intermediate value, for the UI explainer.

    Returns five steps, each {"step": str, "value": int, "detail": str}, with
    MSB-first binary in the details. The last step's value equals encrypt_nibble(p, ...).
    """
    _check_nibble(p, "plaintext nibble")
    k0, k1 = round_keys(key, key_bits)
    x = p ^ k0
    s = SBOX[x]
    y = _rotl4(s)
    c = y ^ k1
    return [
        {"step": "Input P", "value": p, "detail": _bin4(p)},
        {"step": "AddRoundKey K0", "value": x, "detail": f"{_bin4(p)} ⊕ {_bin4(k0)} = {_bin4(x)}"},
        {"step": "SubNibble", "value": s, "detail": f"S[{_bin4(x)}] = {_bin4(s)}"},
        {"step": "RotateBits", "value": y, "detail": f"rotl({_bin4(s)}) = {_bin4(y)}"},
        {
            "step": "AddRoundKey K1",
            "value": c,
            "detail": f"{_bin4(y)} ⊕ K1 {_bin4(k1)} = {_bin4(c)}",
        },
    ]


def matching_keys(pairs: list[tuple[int, int]], key_bits: int) -> list[int]:
    """CLASSICAL brute force: every key that maps each plain nibble to its cipher nibble.

    Exists ONLY for tests and verification displays (ground truth). The quantum attack
    in grover.py never calls this.
    """
    if key_bits not in SUPPORTED_KEY_BITS:
        raise ValueError(f"key_bits must be one of {SUPPORTED_KEY_BITS}, got {key_bits!r}")
    return [
        k
        for k in range(1 << key_bits)
        if all(encrypt_nibble(p, k, key_bits) == c for p, c in pairs)
    ]
