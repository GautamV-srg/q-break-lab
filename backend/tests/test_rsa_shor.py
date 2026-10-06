"""Tests for the Shor period-finding attack (attacker side)."""

from __future__ import annotations

import inspect
import re
from math import gcd
from pathlib import Path

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector

from qbreak.common.simulator import run_circuit
from qbreak.rsa import shor
from qbreak.rsa.shor import (
    SHOR_SUPPORTED_N,
    amod15,
    build_period_finding_circuit,
    candidate_periods,
    choose_bases,
    factors_from_period,
    inverse_qft,
    permutation_matrix,
    run_shor_attack,
)

SEED = 1234
EXPECTED_FACTORS = {15: (3, 5), 21: (3, 7), 33: (3, 11), 35: (5, 7), 55: (5, 11), 77: (7, 11)}


def _order(a: int, n: int) -> int:
    r, x = 1, a % n
    while x != 1:
        x = (x * a) % n
        r += 1
    return r


# --- circuit building blocks ------------------------------------------------


def _qft(t: int) -> QuantumCircuit:
    """Hand-built QFT (the textbook one), independent of inverse_qft's code."""
    qc = QuantumCircuit(t)
    for j in reversed(range(t)):
        qc.h(j)
        for m in reversed(range(j)):
            qc.cp(np.pi / float(2 ** (j - m)), m, j)
    for q in range(t // 2):
        qc.swap(q, t - q - 1)
    return qc


@pytest.mark.parametrize("t", [3, 4])
def test_inverse_qft_is_inverse_of_qft(t: int) -> None:
    assert Operator(inverse_qft(t)).equiv(Operator(_qft(t)).adjoint())


def test_inverse_qft_maps_fourier_state_to_integer() -> None:
    # The state sum_x e^{2πi·x·y/8}|x⟩ must come out as |y⟩ (qubit 0 = LSB).
    t, y = 3, 5
    amps = np.exp(2j * np.pi * np.arange(2**t) * y / 2**t) / np.sqrt(2**t)
    out = Statevector(amps).evolve(inverse_qft(t))
    assert np.isclose(abs(out.data[y]), 1.0)


@pytest.mark.parametrize("a", [2, 4, 7, 8, 11, 13])
def test_amod15_maps_one_to_a(a: int) -> None:
    qc = QuantumCircuit(5)  # qubit 0 = control, qubits 1..4 = work
    qc.x(0)
    qc.x(1)  # work = |0001⟩
    qc.append(amod15(a, 1), [0, 1, 2, 3, 4])
    probs = Statevector(qc).probabilities_dict()
    work_value = int(max(probs, key=probs.get), 2) >> 1
    assert work_value == a


@pytest.mark.parametrize("a", [2, 4, 7, 8, 11, 13])
@pytest.mark.parametrize("power", [1, 2, 4, 8])
def test_amod15_powers_multiply_correctly(a: int, power: int) -> None:
    for x in range(1, 15):
        qc = QuantumCircuit(5)
        qc.x(0)
        for i in range(4):
            if (x >> i) & 1:
                qc.x(1 + i)
        qc.append(amod15(a, power), range(5))
        probs = Statevector(qc).probabilities_dict()
        assert int(max(probs, key=probs.get), 2) >> 1 == (pow(a, power, 15) * x) % 15


def test_amod15_control_off_is_identity() -> None:
    qc = QuantumCircuit(5)
    qc.x(1)
    qc.append(amod15(7, 1), range(5))
    assert Statevector(qc).probabilities_dict() == pytest.approx({"00010": 1.0})


def test_amod15_rejects_bad_base() -> None:
    with pytest.raises(ValueError):
        amod15(5, 1)


@pytest.mark.parametrize("n", [15, 21, 33, 35, 55, 77])
def test_permutation_matrix_is_controlled_multiplication(n: int) -> None:
    n_work = shor.work_qubits(n)
    for b in (b for b in range(2, n) if gcd(b, n) == 1):
        M = permutation_matrix(b, n, n_work)
        dim = 2 ** (n_work + 1)
        assert np.allclose(M @ M.T, np.eye(dim))  # unitary (real permutation)
        for x in range(2**n_work):
            col_off = M[:, x]  # ctrl = 0
            assert col_off[x] == 1
            col_on = M[:, (1 << n_work) | x]  # ctrl = 1
            expected = (1 << n_work) | ((b * x) % n if x < n else x)
            assert col_on[expected] == 1


def test_permutation_matrix_rejects_non_coprime() -> None:
    with pytest.raises(ValueError):
        permutation_matrix(3, 15, 4)


@pytest.mark.parametrize(
    "n,n_work,n_count,total",
    [(15, 4, 8, 12), (21, 5, 10, 15), (33, 6, 12, 18), (35, 6, 12, 18), (55, 6, 12, 18), (77, 7, 14, 21)],
)
def test_register_sizes(n: int, n_work: int, n_count: int, total: int) -> None:
    a = 2
    construction = "permutation-unitary"
    qc = build_period_finding_circuit(a, n, construction=construction)
    assert qc.num_qubits == total
    assert qc.num_clbits == n_count
    assert [r.name for r in qc.qregs] == ["count", "work"]
    assert len(qc.cregs) == 1


def test_auto_construction_choice() -> None:
    qc15 = build_period_finding_circuit(7, 15)
    labels = {inst.operation.label for inst in qc15.data if inst.operation.label}
    assert "IQFT" in labels and "U^(2^0)" in labels
    assert any(
        inst.operation.name != "unitary" and inst.operation.label == "U^(2^0)" for inst in qc15.data
    )
    qc21 = build_period_finding_circuit(2, 21)
    assert any(inst.operation.name == "unitary" for inst in qc21.data)


def test_textbook_only_for_15() -> None:
    with pytest.raises(ValueError):
        build_period_finding_circuit(2, 21, construction="textbook-swaps")


def test_build_rejects_non_coprime_base() -> None:
    with pytest.raises(ValueError):
        build_period_finding_circuit(5, 15)


def _top_peaks(counts: dict[str, int], k: int = 4) -> set[str]:
    return {b for b, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:k]}


def test_constructions_agree_at_n15() -> None:
    tb = run_circuit(build_period_finding_circuit(7, 15, construction="textbook-swaps"), seed=SEED)
    pu = run_circuit(
        build_period_finding_circuit(7, 15, construction="permutation-unitary"), seed=SEED
    )
    ideal = {format(y, "08b") for y in (0, 64, 128, 192)}
    it = run_circuit(build_period_finding_circuit(7, 15, construction="iterative"), seed=SEED)
    assert _top_peaks(tb.counts) == ideal
    assert _top_peaks(pu.counts) == ideal
    assert _top_peaks(it.counts) == ideal  # third branch: single counting qubit
    assert set(tb.counts) == ideal  # exact peaks: nothing else is ever measured
    assert set(it.counts) == ideal


@pytest.mark.parametrize("a", [2, 4, 7, 8, 11, 13])
def test_constructions_have_identical_operators_n15(a: int) -> None:
    tb = build_period_finding_circuit(a, 15, n_count=3, construction="textbook-swaps")
    pu = build_period_finding_circuit(a, 15, n_count=3, construction="permutation-unitary")
    tb.remove_final_measurements()
    pu.remove_final_measurements()
    # Compare on the physically reachable subspace: work starts at |1⟩.
    assert Statevector(tb).equiv(Statevector(pu))


# --- classical post-processing ---------------------------------------------


def test_choose_bases() -> None:
    bases = choose_bases(15)
    assert bases[0] == 7
    assert sorted(bases) == [2, 4, 7, 8, 11, 13]
    assert choose_bases(21, seed=3) == choose_bases(21, seed=3)
    assert all(gcd(a, 35) == 1 and 2 <= a <= 33 for a in choose_bases(35, seed=1))


def test_candidate_periods_ideal_n15() -> None:
    atts = candidate_periods({"01000000": 10, "00000000": 9, "10000000": 3}, 8, 15, 7)
    assert [a.y for a in atts] == [64, 0, 128]
    first = atts[0]
    assert first.ok and first.r_candidate == 4 and first.fraction == "1/4"
    assert first.phase == 0.25
    assert first.reason == "7^4 mod 15 = 1; r even; 7^2 mod 15 = 4 ≠ 14"
    assert not atts[1].ok and atts[1].reason == "phase 0 carries no period information"
    assert atts[2].ok and atts[2].r_candidate == 4  # 1/2 -> multiple 2r = 4


def test_candidate_periods_rejection_reasons() -> None:
    # a^(r/2) ≡ -1: N = 21, a = 5 has order 6? 5^3 mod 21 = 20 = -1.
    assert _order(5, 21) == 6 and pow(5, 3, 21) == 20
    y = round(1024 / 6)  # phase ≈ 1/6
    att = candidate_periods({format(y, "010b"): 1}, 10, 21, 5)[0]
    assert not att.ok and "≡ −1 mod N" in att.reason
    # odd period: N = 21, a = 4 has order 3
    assert _order(4, 21) == 3
    att = candidate_periods({format(round(1024 / 3), "010b"): 1}, 10, 21, 4)[0]
    assert not att.ok and "odd" in att.reason
    # garbage phase that matches no period
    att = candidate_periods({format(1, "08b"): 1}, 8, 15, 7)[0]
    assert not att.ok and att.reason.startswith("a^r mod N ≠ 1")


def test_candidate_periods_cap() -> None:
    counts = {format(y, "08b"): 1 for y in range(40)}
    assert len(candidate_periods(counts, 8, 15, 7)) == 16


@pytest.mark.parametrize("n", [15, 21, 33, 35, 55, 77])
def test_factors_from_period_true_orders(n: int) -> None:
    for a in (a for a in range(2, n - 1) if gcd(a, n) == 1):
        r = _order(a, n)
        f = factors_from_period(a, r, n)
        if r % 2 == 0 and pow(a, r // 2, n) != n - 1:
            assert f == EXPECTED_FACTORS[n]
        else:
            assert f is None


# --- end-to-end attack (N = 15) --------------------------------------------


def test_run_shor_attack_n15_default() -> None:
    res = run_shor_attack(15, seed=SEED)
    assert res.factors == (3, 5)
    assert res.n_count == 8 and res.n_work == 4
    assert res.construction == "textbook-swaps"
    assert res.circuit.num_qubits == 12
    assert res.sim_time_ms > 0
    assert set(res.register_roles) == {"count", "work"}
    assert [title for title, _ in res.explain_circuits] == ["Controlled U^(2^0)", "Inverse QFT"]
    assert all(isinstance(a.reason, str) and a.reason for a in res.attempts)


def test_run_shor_attack_n15_a7() -> None:
    res = run_shor_attack(15, a=7, seed=SEED)
    assert (res.a, res.period, res.factors) == (7, 4, (3, 5))


@pytest.mark.parametrize("a", [2, 7, 8, 13])
def test_run_shor_attack_n15_order4_bases(a: int) -> None:
    res = run_shor_attack(15, a=a, seed=SEED, max_bases=1)
    assert (res.a, res.period, res.factors) == (a, 4, (3, 5))


@pytest.mark.parametrize("a", [4, 11])
def test_run_shor_attack_n15_order2_bases(a: int) -> None:
    res = run_shor_attack(15, a=a, seed=SEED, max_bases=1)
    if res.factors is not None:
        assert (res.period, res.factors) == (2, (3, 5))
    else:
        assert all(not att.ok and att.reason for att in res.attempts)


def test_run_shor_attack_deterministic() -> None:
    r1 = run_shor_attack(15, seed=SEED)
    r2 = run_shor_attack(15, seed=SEED)
    assert r1.counts == r2.counts and r1.a == r2.a and r1.factors == r2.factors


def test_run_shor_attack_non_coprime_base_is_skipped() -> None:
    res = run_shor_attack(15, a=5, seed=SEED)
    assert res.attempts[0].a == 5 and not res.attempts[0].ok
    assert res.attempts[0].reason.startswith("skipped: gcd(a, N) > 1")
    assert res.factors == (3, 5) and res.a != 5


@pytest.mark.parametrize("n", [22, 39, 49])
def test_run_shor_attack_unsupported_n(n: int) -> None:
    with pytest.raises(ValueError):
        run_shor_attack(n)


def test_run_shor_attack_failure_returns_result() -> None:
    # 1 shot at a = 7: if it lands on phase 0, the attack must report failure, not raise.
    for s in range(20):
        res = run_shor_attack(15, a=7, shots=1, seed=s, max_bases=1)
        if res.factors is None:
            assert res.period is None and res.attempts
            assert res.attempts[-1].reason == "phase 0 carries no period information"
            return
    pytest.skip("no 1-shot run landed on phase 0 within 20 seeds")


# --- blindness (integrity rule 1) ------------------------------------------


def test_shor_does_not_import_minirsa() -> None:
    src = Path(shor.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+[\w.]*minirsa", src, re.MULTILINE)
    assert "minirsa" not in {
        line.split()[1] for line in src.splitlines() if line.startswith(("import ", "from "))
    }


def test_attack_signature_has_no_secrets() -> None:
    forbidden = {"p", "q", "d", "phi", "factors", "private", "secret"}
    for fn in (
        run_shor_attack,
        build_period_finding_circuit,
        shor.build_iterative_circuit,
        shor.shot_success_probability,
        candidate_periods,
        choose_bases,
    ):
        assert forbidden.isdisjoint(inspect.signature(fn).parameters)


# --- larger moduli (slow) --------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("n", [n for n in (21, 33, 35, 55, 77) if n in SHOR_SUPPORTED_N])
def test_run_shor_attack_larger_n(n: int) -> None:
    res = run_shor_attack(n, seed=SEED)
    assert res.factors == EXPECTED_FACTORS[n]
    assert res.construction == "permutation-unitary"
    assert pow(res.a, res.period, n) == 1


@pytest.mark.slow
@pytest.mark.parametrize("n,a,r", [(21, 2, 6), (33, 5, 10), (35, 2, 12)])
def test_known_periods_larger_n(n: int, a: int, r: int) -> None:
    assert _order(a, n) == r
    qc = build_period_finding_circuit(a, n, construction="permutation-unitary")
    run = run_circuit(qc, shots=1024, seed=SEED)
    accepted = [att for att in candidate_periods(run.counts, qc.num_clbits, n, a) if att.ok]
    assert accepted and all(att.r_candidate == r for att in accepted)
    assert factors_from_period(a, r, n) == EXPECTED_FACTORS[n]


# --- every base, every modulus, many seeds ---------------------------------


def _all_bases(n: int) -> list[int]:
    return [a for a in range(2, n - 1) if gcd(a, n) == 1]


def _usable(a: int, n: int) -> bool:
    r = _order(a, n)
    return r % 2 == 0 and pow(a, r // 2, n) != n - 1


_BASE_CASES = [(n, a) for n in SHOR_SUPPORTED_N for a in _all_bases(n)]


@pytest.mark.slow
@pytest.mark.parametrize("n,a", _BASE_CASES, ids=[f"N{n}-a{a}" for n, a in _BASE_CASES])
def test_every_base_single_run(n: int, a: int) -> None:
    """One base, no fallback: usable bases must factor with the TRUE period;
    unusable ones (odd order, or a^(r/2) ≡ −1) must fail with a clear reason."""
    res = run_shor_attack(n, a=a, seed=SEED, max_bases=1)
    assert res.a == a
    assert all(att.a == a and att.reason for att in res.attempts)
    if _usable(a, n):
        assert res.factors == EXPECTED_FACTORS[n]
        assert res.period == _order(a, n)
    else:
        assert res.factors is None and res.period is None
        assert not any(att.ok for att in res.attempts)
        r = _order(a, n)
        expected = "odd" if r % 2 else "≡ −1 mod N"
        assert any(expected in att.reason for att in res.attempts if att.r_candidate)


@pytest.mark.parametrize("a", _all_bases(15))
@pytest.mark.parametrize("seed", range(5))
def test_every_base_n15_many_seeds(a: int, seed: int) -> None:
    res = run_shor_attack(15, a=a, seed=seed, max_bases=1)
    assert (res.period, res.factors) == (_order(a, 15), (3, 5))


@pytest.mark.slow
@pytest.mark.parametrize("n", SHOR_SUPPORTED_N)
@pytest.mark.parametrize("seed", range(20))
def test_default_attack_many_seeds(n: int, seed: int) -> None:
    res = run_shor_attack(n, seed=seed, max_bases=6)
    assert res.factors == EXPECTED_FACTORS[n]
    assert pow(res.a, res.period, n) == 1 and res.period == _order(res.a, n)


@pytest.mark.parametrize(
    "n", [15] + [pytest.param(n, marks=pytest.mark.slow) for n in (21, 33, 35, 55, 77)]
)
def test_breach_round_trip_every_chunk(n: int) -> None:
    """Victim encrypts every 3-bit chunk; the adversary, knowing only (n, e) and
    the ciphertext, factors n, rebuilds d and recovers every chunk."""
    from qbreak.rsa.minirsa import (
        decrypt_chunks,
        encrypt_chunks,
        generate_keypair,
        private_exponent,
    )

    kp = generate_keypair(n)
    plain = list(range(8)) * 2
    cipher = encrypt_chunks(plain, kp.n, kp.e)
    res = run_shor_attack(kp.n, seed=SEED, max_bases=6)
    assert res.factors is not None
    d, phi = private_exponent(*res.factors, kp.e)
    assert (d, phi) == (kp.d, kp.phi)
    assert decrypt_chunks(cipher, kp.n, d) == plain
