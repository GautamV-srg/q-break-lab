"""Tests for the MiniRSA victim side."""

from __future__ import annotations

import pytest

from qbreak.rsa.minirsa import (
    SUPPORTED_MODULI,
    decrypt_chunks,
    encrypt_chunks,
    generate_keypair,
    private_exponent,
)

EXPECTED = {
    # n: (p, q, phi, e, d, e_equals_d)
    15: (3, 5, 8, 3, 3, True),
    21: (3, 7, 12, 5, 5, True),
    33: (3, 11, 20, 3, 7, False),
    35: (5, 7, 24, 5, 5, True),
}


@pytest.mark.parametrize("n", sorted(EXPECTED))
def test_keypair_matches_table(n: int) -> None:
    p, q, phi, e, d, eq = EXPECTED[n]
    kp = generate_keypair(n)
    assert (kp.n, kp.p, kp.q, kp.phi, kp.e, kp.d, kp.e_equals_d) == (n, p, q, phi, e, d, eq)


@pytest.mark.parametrize("n", sorted(SUPPORTED_MODULI))
def test_ed_inverse_mod_phi(n: int) -> None:
    kp = generate_keypair(n)
    assert (kp.e * kp.d) % kp.phi == 1
    assert kp.p * kp.q == n


@pytest.mark.parametrize("n", sorted(SUPPORTED_MODULI))
def test_round_trip_every_3bit_chunk(n: int) -> None:
    kp = generate_keypair(n)
    chunks = list(range(8))
    cipher = encrypt_chunks(chunks, kp.n, kp.e)
    assert all(0 <= c < n for c in cipher)
    assert decrypt_chunks(cipher, kp.n, kp.d) == chunks


def test_hi_vector_n15() -> None:
    chunks = [2, 2, 0, 6, 4, 4]  # "Hi", bit_length 16
    cipher = encrypt_chunks(chunks, 15, 3)
    assert cipher == [8, 8, 0, 6, 4, 4]
    assert decrypt_chunks(cipher, 15, 3) == chunks


@pytest.mark.parametrize("n", [1, 14, 16, 22, 39, 77])
def test_unsupported_modulus_raises(n: int) -> None:
    with pytest.raises(ValueError):
        generate_keypair(n)


def test_encrypt_rejects_out_of_range_chunk() -> None:
    with pytest.raises(ValueError):
        encrypt_chunks([15], 15, 3)
    with pytest.raises(ValueError):
        encrypt_chunks([-1], 15, 3)


def test_private_exponent_from_factors() -> None:
    assert private_exponent(3, 11, 3) == (7, 20)
    assert private_exponent(3, 5, 3) == (3, 8)


def test_private_exponent_rejects_non_coprime_e() -> None:
    with pytest.raises(ValueError):
        private_exponent(3, 5, 2)
