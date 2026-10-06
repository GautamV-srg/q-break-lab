"""Tests for the classical MiniAES cipher."""

from __future__ import annotations

import pytest

from qbreak.aes.cipher import (
    INV_SBOX,
    SBOX,
    decrypt_nibble,
    decrypt_nibbles,
    encrypt_nibble,
    encrypt_nibbles,
    matching_keys,
    round_keys,
    trace_encrypt_nibble,
)

KEY_BITS = (4, 6, 8)


def test_sbox_is_a_permutation() -> None:
    assert sorted(SBOX) == list(range(16))
    assert all(INV_SBOX[SBOX[v]] == v for v in range(16))


@pytest.mark.parametrize("key_bits", KEY_BITS)
def test_decrypt_inverts_encrypt(key_bits: int) -> None:
    for key in range(1 << key_bits):
        for p in range(16):
            assert decrypt_nibble(encrypt_nibble(p, key, key_bits), key, key_bits) == p


@pytest.mark.parametrize("key_bits", KEY_BITS)
def test_encrypt_is_bijection_and_keys_distinct(key_bits: int) -> None:
    perms = set()
    for key in range(1 << key_bits):
        perm = tuple(encrypt_nibble(p, key, key_bits) for p in range(16))
        assert sorted(perm) == list(range(16))
        perms.add(perm)
    assert len(perms) == 1 << key_bits


def test_hand_computed_vector() -> None:
    # x = 0100 ^ 1001 = 1101 -> S = 1001 -> rotl = 0011; K1 = rotl(1001) ^ 0011 = 0000
    assert round_keys(0b1001, 4) == (0b1001, 0b0000)
    assert encrypt_nibble(0x4, 0b1001, 4) == 0x3


def test_api_contract_vector() -> None:
    # "Hi judges!" with key 1001 (A6 example)
    plain = [4, 8, 6, 9, 2, 0, 6, 10, 7, 5, 6, 4, 6, 7, 6, 5, 7, 3, 2, 1]
    cipher = [3, 8, 14, 13, 9, 5, 14, 2, 0, 10, 14, 3, 14, 0, 14, 10, 0, 12, 9, 6]
    assert encrypt_nibbles(plain, 0b1001, 4) == cipher
    assert decrypt_nibbles(cipher, 0b1001, 4) == plain


def test_round_keys_use_high_and_low_bits() -> None:
    # 8-bit: K0 = low nibble, H = high nibble
    assert round_keys(0xA5, 8) == (0x5, ((0xA << 1 | 0xA >> 3) & 0xF) ^ 0x3)
    # 6-bit: K0 = bits 0-3, H = bits 2-5
    k = 0b110110
    assert round_keys(k, 6) == (0b0110, ((0b1101 << 1 | 0b1101 >> 3) & 0xF) ^ 0x3)


@pytest.mark.parametrize("key_bits", KEY_BITS)
def test_trace_matches_encrypt(key_bits: int) -> None:
    for key in range(0, 1 << key_bits, 3):
        for p in range(16):
            trace = trace_encrypt_nibble(p, key, key_bits)
            assert [t["step"] for t in trace] == [
                "Input P",
                "AddRoundKey K0",
                "SubNibble",
                "RotateBits",
                "AddRoundKey K1",
            ]
            assert trace[-1]["value"] == encrypt_nibble(p, key, key_bits)


def test_trace_details() -> None:
    trace = trace_encrypt_nibble(0x4, 0b1001, 4)
    assert trace[0]["detail"] == "0100"
    assert trace[1]["detail"] == "0100 ⊕ 1001 = 1101"
    assert trace[2]["detail"] == "S[1101] = 1001"
    assert trace[3]["detail"] == "rotl(1001) = 0011"


@pytest.mark.parametrize(
    ("key", "key_bits"),
    [(16, 4), (-1, 4), (64, 6), (256, 8), (0, 5), (0, 3), (0, 16), ("1001", 4)],
)
def test_invalid_key_raises(key: object, key_bits: int) -> None:
    with pytest.raises(ValueError):
        encrypt_nibble(0, key, key_bits)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        decrypt_nibble(0, key, key_bits)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [-1, 16, 99])
def test_invalid_nibble_raises(bad: int) -> None:
    with pytest.raises(ValueError):
        encrypt_nibble(bad, 0, 4)
    with pytest.raises(ValueError):
        decrypt_nibble(bad, 0, 4)


def test_matching_keys_ground_truth() -> None:
    key = 0b1001
    pairs = [(p, encrypt_nibble(p, key, 4)) for p in (0x4, 0x8, 0x6)]
    assert matching_keys(pairs, 4) == [key]
    # A single pair matches at most 2 keys at 4 bits.
    for p in range(16):
        for c in range(16):
            assert len(matching_keys([(p, c)], 4)) <= 2
    with pytest.raises(ValueError):
        matching_keys([(0, 0)], 5)
