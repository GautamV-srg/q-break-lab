"""MiniRSA: genuine RSA arithmetic with numbers far too small to be secure.

This is the *victim* side ("Your organization"). It knows the prime factors
p and q of the public modulus N, and from them builds the key pair:

- phi = (p - 1)(q - 1)
- e   = the smallest odd e >= 3 with gcd(e, phi) = 1   (public exponent)
- d   = e^-1 mod phi                                   (private exponent)

A message chunk m (0 <= m < N) encrypts to c = m^e mod N and decrypts with
m = c^d mod N. This is textbook RSA with no padding, so equal chunks encrypt
to equal ciphertexts. At N = 15, 21 and 35 the exponents are even equal
(e = d); ``e_equals_d`` flags this for every modulus, so it is reported
wherever it occurs (it does not at N = 33, 55 or 77). These keys demonstrate Shor's factor-recovery workflow; they are
not secure RSA examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd

# The victim's private knowledge: modulus -> its prime factors.
# The attacker module (shor.py) must never import this table.
SUPPORTED_MODULI: dict[int, tuple[int, int]] = {
    15: (3, 5),
    21: (3, 7),
    33: (3, 11),
    35: (5, 7),
    55: (5, 11),
    77: (7, 11),
}


@dataclass
class RSAKeyPair:
    """A MiniRSA key pair. (n, e) is public; p, q, phi and d are private."""

    n: int
    e: int
    d: int
    p: int
    q: int
    phi: int
    e_equals_d: bool


def _smallest_public_exponent(phi: int) -> int:
    """Smallest odd e >= 3 that is coprime to phi."""
    e = 3
    while gcd(e, phi) != 1:
        e += 2
    return e


def private_exponent(p: int, q: int, e: int) -> tuple[int, int]:
    """Return (d, phi) for the modulus p*q and public exponent e.

    The quantum adversary calls this *after* Shor has recovered p and q.
    Computing d from the factors is ordinary public mathematics, so it is
    not a leak: the factors are the whole secret.

    Raises ValueError if e is not invertible modulo phi.
    """
    phi = (p - 1) * (q - 1)
    if gcd(e, phi) != 1:
        raise ValueError(f"e = {e} is not coprime to phi = {phi}; no private exponent exists")
    return pow(e, -1, phi), phi


def generate_keypair(n: int) -> RSAKeyPair:
    """Generate the organization's key pair for a supported tiny modulus n.

    Raises ValueError if n is not in SUPPORTED_MODULI.
    """
    if n not in SUPPORTED_MODULI:
        supported = ", ".join(str(k) for k in sorted(SUPPORTED_MODULI))
        raise ValueError(f"Unsupported modulus N = {n}; supported: {supported}")
    p, q = SUPPORTED_MODULI[n]
    phi = (p - 1) * (q - 1)
    e = _smallest_public_exponent(phi)
    d, _ = private_exponent(p, q, e)
    return RSAKeyPair(n=n, e=e, d=d, p=p, q=q, phi=phi, e_equals_d=(e == d))


def encrypt_chunks(chunks: list[int], n: int, e: int) -> list[int]:
    """Encrypt each chunk m with the public key: c = m^e mod n.

    Raises ValueError if any chunk is outside 0 <= m < n.
    """
    for i, m in enumerate(chunks):
        if not 0 <= m < n:
            raise ValueError(f"Chunk {i} = {m} is out of range; need 0 <= m < {n}")
    return [pow(m, e, n) for m in chunks]


def decrypt_chunks(cipher: list[int], n: int, d: int) -> list[int]:
    """Decrypt each ciphertext value c with the private exponent: m = c^d mod n."""
    for i, c in enumerate(cipher):
        if not 0 <= c < n:
            raise ValueError(f"Ciphertext value {i} = {c} is out of range; need 0 <= c < {n}")
    return [pow(c, d, n) for c in cipher]
