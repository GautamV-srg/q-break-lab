"""Tests for the Grover attack on MiniAES."""

from __future__ import annotations

import inspect
import itertools
import random

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

import qbreak.aes.cipher as cipher_mod
from qbreak.aes.cipher import (
    RCON,
    decrypt_nibbles,
    encrypt_nibble,
    encrypt_nibbles,
    matching_keys,
)
from qbreak.aes.grover import (
    build_diffuser,
    build_grover_circuit,
    build_oracle,
    optimal_iterations,
    run_grover_attack,
    select_known_pairs,
)

MESSAGES = ("Hi judges!", "Top secret plan", "Quantum 2026")


def _nibbles(text: str) -> list[int]:
    out: list[int] = []
    for b in text.encode("utf-8"):
        out += [b >> 4, b & 0xF]
    return out


def _bit(v: int, i: int) -> int:
    return (v >> i) & 1


# --------------------------------------------------------------- comparison algebra


@pytest.mark.parametrize("key_bits", (4, 6, 8))
def test_match_formula_equals_cipher(key_bits: int) -> None:
    """The in-circuit comparison s_j ^ H_j == RCON_(j+1) ^ C_(j+1) is exactly 'E_k(P) == C'."""
    from qbreak.aes.cipher import SBOX

    for k in range(1 << key_bits):
        k0 = k & 0xF
        h = (k >> (key_bits - 4)) & 0xF
        for p in range(16):
            s = SBOX[p ^ k0]
            for c in range(16):
                formula = all(
                    _bit(s, j) ^ _bit(h, j) == _bit(RCON, (j + 1) % 4) ^ _bit(c, (j + 1) % 4)
                    for j in range(4)
                )
                assert formula == (encrypt_nibble(p, k, key_bits) == c)


# --------------------------------------------------------------- oracle correctness


def _check_phase_oracle(pairs: list[tuple[int, int]]) -> None:
    """Apply the oracle to (all keys) x |0 ancillas> x |->, in one statevector pass.

    Expected: every key keeps its amplitude, except keys in matching_keys(pairs), whose
    amplitude flips sign; and the work/sbox/match ancillas end exactly back in |0>.
    """
    oracle = build_oracle(pairs, 4)
    prep = QuantumCircuit(oracle.num_qubits)
    prep.h(range(4))  # key = qubits 0..3 (LSB first)
    prep.x(oracle.num_qubits - 1)  # flag = last qubit, in |->
    prep.h(oracle.num_qubits - 1)
    before = Statevector(prep).data
    after = Statevector(prep).evolve(oracle).data
    marked = set(matching_keys(pairs, 4))
    expected = before.copy()
    for idx in np.flatnonzero(np.abs(before) > 1e-12):
        if idx & 0xF in marked:
            expected[idx] = -before[idx]
    assert np.allclose(after, expected, atol=1e-9)


@pytest.mark.parametrize("seed", range(4))
def test_oracle_is_clean_phase_oracle_4bit(seed: int) -> None:
    rng = random.Random(seed)
    true_key = rng.randrange(16)
    plains = rng.sample(range(16), rng.choice([1, 2]))
    _check_phase_oracle([(p, encrypt_nibble(p, true_key, 4)) for p in plains])


def test_oracle_marks_nothing_for_impossible_pairs() -> None:
    # A permutation cannot send two inputs to the same output, so no key matches.
    _check_phase_oracle([(0, 0), (1, 0)])


def test_diffuser_is_inversion_about_mean() -> None:
    d = build_diffuser(4)
    n = 16
    psi = np.zeros(n, dtype=complex)
    psi[5] = 1.0
    out = Statevector(psi).evolve(d).data
    # 2|s><s| - I applied to |5>, up to a global phase of -1.
    target = np.full(n, 2 / n, dtype=complex)
    target[5] -= 1
    phase = out[0] / target[0]
    assert np.allclose(out, phase * target)
    assert abs(phase) == pytest.approx(1.0)


# --------------------------------------------------------------- pair selection


def test_select_known_pairs_dedupes_and_caps() -> None:
    plain = [4, 8, 4, 8, 6, 9]
    ciph = encrypt_nibbles(plain + [1, 2], 0b1001, 4)
    pairs = select_known_pairs(plain, ciph, 4)
    assert pairs == [(4, ciph[0]), (8, ciph[1])]
    assert len(select_known_pairs(plain, ciph, 4, max_pairs=10)) == 4


def test_select_known_pairs_errors() -> None:
    with pytest.raises(ValueError):
        select_known_pairs([], [1, 2], 4)
    with pytest.raises(ValueError, match="inconsistent"):
        select_known_pairs([4, 4], [3, 5], 4)
    with pytest.raises(ValueError):
        select_known_pairs([1, 2, 3], [1, 2], 4)
    with pytest.raises(ValueError):
        select_known_pairs([1], [1], 5)


# --------------------------------------------------------------- sizes


@pytest.mark.parametrize(("key_bits", "iters"), [(4, 3), (6, 6), (8, 12)])
def test_optimal_iterations(key_bits: int, iters: int) -> None:
    assert optimal_iterations(key_bits) == iters
    assert optimal_iterations(4, 16) == 1


@pytest.mark.parametrize(("key_bits", "pairs", "qubits"), [(4, 2, 15), (6, 3, 18), (8, 3, 20)])
def test_qubit_counts(key_bits: int, pairs: int, qubits: int) -> None:
    pair_list = [(p, p) for p in range(pairs)]
    qc = build_grover_circuit(pair_list, key_bits, 1)
    assert qc.num_qubits == qubits
    assert qc.num_clbits == key_bits
    assert len(qc.cregs) == 1


# --------------------------------------------------------------- the attack


def test_attack_has_no_key_parameter() -> None:
    params = inspect.signature(run_grover_attack).parameters
    assert [p for p in params if "key" in p] == ["key_bits"]


def test_single_solution_probability_4bit() -> None:
    """M = 1 with 3 iterations should put about sin^2(7 theta) = 96% on the key."""
    key = 0b0001
    plain = _nibbles("Hi ")
    res = run_grover_attack(plain, encrypt_nibbles(plain, key, 4), 4, shots=2048, seed=7)
    assert res.iterations == 3
    assert res.recovered_keys == [key]
    assert res.counts["0001"] / 2048 > 0.9


@pytest.mark.parametrize("key", range(16))
def test_every_4bit_key_recovered(key: int, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> list[int]:
        raise AssertionError("the attack must not call matching_keys")

    monkeypatch.setattr(cipher_mod, "matching_keys", forbidden)
    for i, msg in enumerate(MESSAGES):
        plain = _nibbles(msg)
        crib = _nibbles(msg[:3])
        ct = encrypt_nibbles(plain, key, 4)
        res = run_grover_attack(crib, ct, 4, seed=100 + 16 * i + key)
        assert key in res.recovered_keys, (msg, key, res.attempts)
        crib_pairs = list(zip(crib, ct))
        for k in res.recovered_keys:
            assert all(encrypt_nibble(p, k, 4) == c for p, c in crib_pairs)


def test_result_fields_4bit() -> None:
    key = 0b1001
    msg = "Hi judges!"
    ct = encrypt_nibbles(_nibbles(msg), key, 4)
    res = run_grover_attack(_nibbles("Hi "), ct, 4, seed=1)
    assert res.key_bits == 4
    assert res.pairs_used == [(4, 3), (8, 8)]
    assert res.recovered_keys == [key]
    assert res.candidate_keys[0] == key
    assert res.attempts and res.attempts[-1].iterations == res.iterations
    assert len(res.circuit.cregs) == 1
    assert res.circuit.num_qubits == 15
    names = {inst.operation.name for inst in res.circuit.data}
    assert {"Oracle", "Diffuser"} <= names
    assert [t for t, _ in res.explain_circuits] == [
        "One Grover iteration",
        "Oracle (decomposed)",
        "Diffuser",
    ]
    assert set(res.register_roles) == {"key", "work", "sbox", "match", "flag"}
    assert res.sim_time_ms > 0
    assert res.transpiled.num_qubits >= 15


def test_multiple_solutions_handled() -> None:
    """A one-nibble crib can match two 4-bit keys; both must come back verified."""
    for key in range(16):
        for p in range(16):
            pair = [(p, encrypt_nibble(p, key, 4))]
            if len(matching_keys(pair, 4)) == 2:
                res = run_grover_attack([p], [pair[0][1]], 4, seed=3)
                assert sorted(res.recovered_keys) == matching_keys(pair, 4)
                return
    pytest.fail("expected some single pair with two matching keys")


def test_api_example_end_to_end() -> None:
    """The A6 example: crib "Hi " recovers key 1001 and decrypts the full message."""
    msg = "Hi judges!"
    ct = encrypt_nibbles(_nibbles(msg), 0b1001, 4)
    res = run_grover_attack(_nibbles("Hi "), ct, 4, seed=42)
    assert res.recovered_keys == [0b1001]
    plain = decrypt_nibbles(ct, res.recovered_keys[0], 4)
    assert bytes((plain[i] << 4) | plain[i + 1] for i in range(0, len(plain), 2)).decode() == msg


def test_extra_crib_pairs_filter_out_false_keys() -> None:
    """In-circuit pairs fit two keys; the crib's third block (not in the circuit) removes one."""
    for key in range(16):
        for p1, p2, p3 in itertools.permutations(range(16), 3):
            crib = [p1, p2, p3]
            pairs = [(p, encrypt_nibble(p, key, 4)) for p in crib]
            if len(matching_keys(pairs[:2], 4)) == 2 and matching_keys(pairs, 4) == [key]:
                ct = encrypt_nibbles(crib + [0, 5, 10], key, 4)
                res = run_grover_attack(crib, ct, 4, seed=11)
                assert res.pairs_used == pairs[:2]
                chosen = next(a for a in res.attempts if a.iterations == res.iterations)
                assert sorted(chosen.verified_keys) == matching_keys(pairs[:2], 4)
                assert res.recovered_keys == [key]
                return
    pytest.fail("expected a crib whose first two blocks fit two keys")


@pytest.mark.slow
@pytest.mark.parametrize("key_bits", (6, 8))
def test_random_keys_recovered_large(key_bits: int) -> None:
    rng = random.Random(key_bits)
    keys = [rng.randrange(1 << key_bits) for _ in range(8)]
    keys += [0, (1 << key_bits) - 1]  # edge cases: all-zeros and all-ones keys
    for trial, key in enumerate(keys):
        msg = MESSAGES[trial % len(MESSAGES)]
        ct = encrypt_nibbles(_nibbles(msg), key, key_bits)
        res = run_grover_attack(_nibbles(msg[:3]), ct, key_bits, seed=trial)
        assert key in res.recovered_keys, (key_bits, key, res.attempts)
