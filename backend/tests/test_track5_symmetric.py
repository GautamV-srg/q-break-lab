"""Track 5 symmetric tests: attack conditions, 10/12-bit keys, quantum counting,
classical baseline, config gating, experiments schema and resource estimates."""

from __future__ import annotations

import inspect
import json
import os
import random
import subprocess
import sys

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

import qbreak.aes.cipher as cipher_mod
from qbreak.aes.cipher import (
    decrypt_nibble,
    decrypt_nibbles,
    encrypt_nibble,
    encrypt_nibbles,
)
from qbreak.aes.classical import WALLCLOCK_NOTE, classical_key_search, comparison_record
from qbreak.aes.conditions import (
    PLAUSIBLE_HIGH_NIBBLES,
    circuit_spec,
    full_spec,
    substring_offsets,
)
from qbreak.aes.counting import (
    maximum_likelihood_m,
    outcome_distribution,
    run_quantum_counting,
)
from qbreak.aes.grover import build_grover_circuit, build_oracle, run_grover_attack
from qbreak.common.encoding import text_to_nibbles

ALL_BITS = (4, 6, 8, 10, 12)


# ------------------------------------------------------------------ helpers


def classical_oracle_flags(spec, key_bits: int, keys) -> dict[int, bool]:
    """Run the oracle as a reversible classical circuit on basis states.

    The oracle uses only X / CX / MCX / CSWAP, so on a basis state it is a permutation:
    with the flag in |0> (instead of |->) it ends as 1 exactly for marked keys. Also
    asserts that the key is unchanged and every scratch qubit returns to 0.
    """
    qc = build_oracle(spec, key_bits)
    index = {q: i for i, q in enumerate(qc.qubits)}
    ops = []
    for inst in qc.data:
        name = inst.operation.name
        qs = [index[q] for q in inst.qubits]
        if name == "x":
            ops.append(("x", qs))
        elif name in ("cx", "ccx", "mcx") or name.startswith("mcx"):
            ops.append(("mcx", qs))
        elif name == "cswap":
            ops.append(("cswap", qs))
        else:
            raise AssertionError(f"unexpected gate {name}")
    flags = {}
    for key in keys:
        state = [0] * qc.num_qubits
        for i in range(key_bits):
            state[i] = (key >> i) & 1
        for kind, qs in ops:
            if kind == "x":
                for q in qs:
                    state[q] ^= 1
            elif kind == "mcx":
                if all(state[q] for q in qs[:-1]):
                    state[qs[-1]] ^= 1
            elif state[qs[0]]:
                state[qs[1]], state[qs[2]] = state[qs[2]], state[qs[1]]
        assert sum(state[i] << i for i in range(key_bits)) == key
        assert not any(state[key_bits:-1]), "scratch qubits must be uncomputed"
        flags[key] = bool(state[-1])
    return flags


def _keys(bits: int, n: int = 160) -> list[int]:
    return list(range(1 << bits)) if bits <= 8 else random.Random(bits).sample(range(1 << bits), n)


# ------------------------------------------------------------------ cipher 10/12-bit


@pytest.mark.parametrize("key_bits", (10, 12))
def test_large_keys_decrypt_and_are_distinct(key_bits: int) -> None:
    perms = set()
    for key in range(1 << key_bits):
        perm = tuple(encrypt_nibble(p, key, key_bits) for p in range(16))
        assert all(decrypt_nibble(perm[p], key, key_bits) == p for p in range(16))
        perms.add(perm)
    assert len(perms) == 1 << key_bits, "every key must give a different permutation"


def test_large_key_low_byte_is_the_8bit_cipher() -> None:
    for key in range(256):
        for p in range(16):
            assert encrypt_nibble(p, key, 10) == encrypt_nibble(p, key, 12) == encrypt_nibble(p, key, 8)


# ------------------------------------------------------------------ oracle correctness, every size


@pytest.mark.parametrize("key_bits", ALL_BITS)
@pytest.mark.parametrize("condition", ("known_beginning", "known_substring", "ciphertext_only"))
def test_oracle_marks_exactly_the_condition(key_bits: int, condition: str) -> None:
    msg, sub = "meet me at noon", "noon"
    key = random.Random(key_bits).randrange(1 << key_bits)
    ct = encrypt_nibbles(text_to_nibbles(msg), key, key_bits)
    known = {"known_beginning": text_to_nibbles(msg[:3]), "known_substring": text_to_nibbles(sub), "ciphertext_only": None}[condition]
    spec = circuit_spec(condition, known, ct, key_bits)
    keys = _keys(key_bits) + [key]
    flags = classical_oracle_flags(spec, key_bits, keys)
    assert flags[key], "the real key must always be marked"
    for k in keys:
        assert flags[k] == spec.fits(k)


def test_substring_with_several_positions_uses_or_of_hits() -> None:
    # "aXa" style ciphertext: the known text "a" can sit at several positions.
    msg = "abcab"
    key = 0b1011
    ct = encrypt_nibbles(text_to_nibbles(msg), key, 4)
    spec = circuit_spec("known_substring", text_to_nibbles("ab"), ct, 4)
    assert len(spec.groups) > 1
    oracle = build_oracle(spec, 4)
    assert "hit" in {r.name for r in oracle.qregs}
    flags = classical_oracle_flags(spec, 4, range(16))
    assert flags == {k: spec.fits(k) for k in range(16)}
    assert flags[key]


def test_phase_oracle_signs_ciphertext_only_statevector() -> None:
    ct = encrypt_nibbles(text_to_nibbles("ok go"), 0b0110, 4)
    spec = circuit_spec("ciphertext_only", None, ct, 4)
    oracle = build_oracle(spec, 4)
    prep = QuantumCircuit(oracle.num_qubits)
    prep.h(range(4))
    prep.x(oracle.num_qubits - 1)
    prep.h(oracle.num_qubits - 1)
    before = Statevector(prep).data
    after = Statevector(prep).evolve(oracle).data
    expected = before.copy()
    for idx in np.flatnonzero(np.abs(before) > 1e-12):
        if spec.fits(int(idx) & 0xF):
            expected[idx] = -before[idx]
    assert np.allclose(after, expected, atol=1e-9)


# ------------------------------------------------------------------ conditions


def test_mode_selector_routes_to_the_condition() -> None:
    ct = encrypt_nibbles(text_to_nibbles("Hi judges!"), 0b1001, 4)
    for condition, known in (("known_beginning", "Hi "), ("known_substring", "judges"), ("ciphertext_only", None)):
        res = run_grover_attack(text_to_nibbles(known) if known else None, ct, 4, seed=5, condition=condition, counting=False)
        assert res.condition == condition and res.spec.condition == condition
        assert 0b1001 in res.recovered_keys
    with pytest.raises(ValueError, match="condition"):
        run_grover_attack(text_to_nibbles("Hi "), ct, 4, condition="guess")


def test_known_substring_block_aligned_offsets() -> None:
    msg = "xx secret yy"
    ct = encrypt_nibbles(text_to_nibbles(msg), 0b0101, 4)
    found = substring_offsets(text_to_nibbles("secret"), ct)
    assert all(offset % 2 == 0 for offset, _ in found), "only byte (2-block) aligned offsets"
    assert 6 in [offset for offset, _ in found]  # "secret" starts at character 3
    spec = full_spec("known_substring", text_to_nibbles("secret"), ct, 4)
    assert 3 in spec.offsets
    for k in range(16):
        expected = any(all(encrypt_nibble(p, k, 4) == c for p, c in pairs) for _, pairs in found)
        assert spec.fits(k) == expected


def test_known_substring_absent_is_rejected() -> None:
    ct = encrypt_nibbles(text_to_nibbles("aaaa"), 3, 4)
    with pytest.raises(ValueError, match="cannot appear"):
        full_spec("known_substring", text_to_nibbles("ab"), ct, 4)


@pytest.mark.parametrize("key_bits", (4, 6, 8))
def test_ciphertext_only_marks_exactly_the_plausibility_set(key_bits: int) -> None:
    msg = "attack at dawn"
    ct = encrypt_nibbles(text_to_nibbles(msg), 5, key_bits)
    spec = full_spec("ciphertext_only", None, ct, key_bits)
    for k in range(1 << key_bits):
        plain = decrypt_nibbles(ct, k, key_bits)
        assert spec.fits(k) == all(n in PLAUSIBLE_HIGH_NIBBLES for n in plain[0::2])
    # the in-circuit set is a superset of the full set (post-filtering only shrinks it)
    cspec = circuit_spec("ciphertext_only", None, ct, key_bits)
    assert {k for k in range(1 << key_bits) if spec.fits(k)} <= {k for k in range(1 << key_bits) if cspec.fits(k)}


def test_ciphertext_only_attack_reports_ambiguous_or_breached() -> None:
    ct = encrypt_nibbles(text_to_nibbles("aaaa"), 0b1100, 4)  # few distinct blocks: weak constraint
    res = run_grover_attack(None, ct, 4, seed=2, condition="ciphertext_only")
    truth = classical_key_search(None, ct, 4, "ciphertext_only").candidates
    assert 0b1100 in truth
    assert set(res.recovered_keys) <= set(truth)
    assert 0b1100 in res.recovered_keys or len(truth) > 4


# ------------------------------------------------------------------ quantum counting


def test_counting_distribution_is_normalised() -> None:
    for m in (0, 1, 3, 16):
        assert outcome_distribution(m, 4, 4).sum() == pytest.approx(1.0)


def test_counting_mle_recovers_m_from_ideal_histogram() -> None:
    for m in (0, 1, 2, 5):
        probs = outcome_distribution(m, 4, 5)
        counts = {format(y, "05b"): int(round(4096 * p)) for y, p in enumerate(probs) if round(4096 * p)}
        assert maximum_likelihood_m(counts, 4, 5)[0] == m


@pytest.mark.parametrize(("condition", "msg", "known"), [("known_beginning", "Hi judges!", "Hi "), ("ciphertext_only", "attack at dawn", None)])
def test_quantum_counting_matches_true_m(condition: str, msg: str, known: str | None) -> None:
    ct = encrypt_nibbles(text_to_nibbles(msg), 5, 4)
    spec = circuit_spec(condition, text_to_nibbles(known) if known else None, ct, 4)
    true_m = sum(spec.fits(k) for k in range(16))
    res = run_quantum_counting(spec, 4, shots=1024, seed=1)
    assert res.estimated_m_rounded == true_m
    assert abs(res.estimated_m - true_m) <= 2.5  # the single-peak reading, at 1/16 resolution
    assert res.controlled_grover_calls == 2**res.counting_qubits - 1
    assert any("accept M" in line for line in res.derivation)


def test_counting_drives_iteration_choice() -> None:
    ct = encrypt_nibbles(text_to_nibbles("Hi judges!"), 0b1001, 4)
    res = run_grover_attack(text_to_nibbles("H"), ct, 4, seed=4, counting=True)
    assert res.counting is not None
    m = res.counting.estimated_m_rounded
    from qbreak.aes.grover import optimal_iterations

    assert res.attempts[0].iterations == optimal_iterations(4, max(1, m))


# ------------------------------------------------------------------ blindness


@pytest.mark.parametrize("fn", [run_grover_attack, classical_key_search, run_quantum_counting])
def test_no_key_parameter(fn) -> None:
    params = inspect.signature(fn).parameters
    assert [p for p in params if "key" in p and p != "key_bits"] == []


@pytest.mark.parametrize("condition", ("known_beginning", "known_substring", "ciphertext_only"))
def test_attack_paths_never_use_ground_truth(condition: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("attack path accessed matching_keys")

    monkeypatch.setattr(cipher_mod, "matching_keys", forbidden)
    msg = "meet me at noon"
    ct = encrypt_nibbles(text_to_nibbles(msg), 0b0111, 4)
    known = {"known_beginning": text_to_nibbles("mee"), "known_substring": text_to_nibbles("noon"), "ciphertext_only": None}[condition]
    res = run_grover_attack(known, ct, 4, seed=1, condition=condition)
    classical = classical_key_search(known, ct, 4, condition)
    assert 0b0111 in classical.candidates
    assert set(res.recovered_keys) <= set(classical.candidates)


def test_attack_modules_do_not_import_key_material() -> None:
    import qbreak.aes.classical
    import qbreak.aes.conditions
    import qbreak.aes.counting

    for module in (qbreak.aes.classical, qbreak.aes.conditions, qbreak.aes.counting):
        source = inspect.getsource(module)
        assert "matching_keys(" not in source
        assert "AESEncryptRequest" not in source


# ------------------------------------------------------------------ classical baseline


def test_classical_baseline_and_comparison_record() -> None:
    key = 0b1001
    ct = encrypt_nibbles(text_to_nibbles("Hi judges!"), key, 4)
    classical = classical_key_search(text_to_nibbles("Hi "), ct, 4)
    assert classical.candidates == [key]
    assert classical.cipher_evaluations == key + 1  # tries keys 0, 1, ..., key
    assert classical.exhaustive_evaluations == 16
    assert classical.expected_tries == pytest.approx(17 / 2)
    res = run_grover_attack(text_to_nibbles("Hi "), ct, 4, seed=1)
    record = comparison_record(res, classical)
    assert set(record) >= {"quantum", "classical", "wallclock_note"}
    assert set(record["quantum"]) >= {"oracle_calls", "grover_iterations", "qubits", "depth"}
    assert record["classical"]["cipher_evaluations"] == key + 1
    assert record["quantum"]["oracle_calls"] >= record["quantum"]["grover_iterations"]
    assert record["wallclock_note"] == WALLCLOCK_NOTE
    assert "far longer" in WALLCLOCK_NOTE and "No quantum speed advantage" in WALLCLOCK_NOTE


# ------------------------------------------------------------------ API + config


def _client():
    from fastapi.testclient import TestClient

    from qbreak.api.main import app

    return TestClient(app)


def test_api_conditions_and_comparison() -> None:
    client = _client()
    ct = client.post("/api/aes/encrypt", json={"plaintext": "meet me at noon", "key": "0110", "key_bits": 4}).json()["ciphertext_nibbles"]
    sub = client.post("/api/aes/attack", json={"key_bits": 4, "condition": "known_substring", "known_plaintext": "noon", "ciphertext_nibbles": ct, "seed": 1}).json()
    assert sub["condition"] == "known_substring" and "0110" in sub["recovered_keys"]
    assert 11 in sub["known_text_offsets"]
    assert sub["comparison"]["classical"]["cipher_evaluations"] >= 1
    assert "ran" in sub["counting"]
    only = client.post("/api/aes/attack", json={"key_bits": 4, "condition": "ciphertext_only", "ciphertext_nibbles": ct, "seed": 1}).json()
    assert only["verdict"] in ("breached", "ambiguous") and only["plausibility_alphabet"]


def test_api_condition_validation() -> None:
    client = _client()
    base = {"key_bits": 4, "ciphertext_nibbles": [3, 8, 1, 2]}
    assert client.post("/api/aes/attack", json={**base, "condition": "ciphertext_only", "known_plaintext": "H"}).status_code == 422
    assert client.post("/api/aes/attack", json={**base, "condition": "known_substring"}).status_code == 422
    assert client.post("/api/aes/attack", json={**base, "condition": "nope", "known_plaintext": "H"}).status_code == 422
    assert client.post("/api/aes/attack", json={**base, "known_plaintext": "H", "noise_p": 0.5}).status_code == 422


def test_text_limit_is_1000() -> None:
    client = _client()
    config = client.get("/api/config").json()
    assert config["max_aes_text_chars"] == 1000
    ok = client.post("/api/aes/encrypt", json={"plaintext": "a" * 1000, "key": "1001", "key_bits": 4})
    assert ok.status_code == 200
    assert client.post("/api/aes/encrypt", json={"plaintext": "a" * 1001, "key": "1001", "key_bits": 4}).status_code == 422


def test_config_exposes_16bit_note_and_options() -> None:
    config = _client().get("/api/config").json()
    options = {o["bits"]: o for o in config["aes_key_options"]}
    assert set(options) == {4, 6, 8, 10, 12, 16}
    assert not options[16]["enabled"] and not options[16]["simulated"]
    note = config["aes_key_bits_16_note"]
    assert "16 GB" in note and "200" in note and options[16]["reason"] == note
    assert [c["id"] for c in config["aes_conditions"]] == ["known_beginning", "known_substring", "ciphertext_only"]


def test_config_gating_excludes_12bit_under_cap() -> None:
    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from qbreak.api.main import app\n"
        "c = TestClient(app)\n"
        "cfg = c.get('/api/config').json()\n"
        "r = c.post('/api/aes/encrypt', json={'plaintext': 'Hi', 'key': '0'*12, 'key_bits': 12})\n"
        "print(json.dumps({'bits': cfg['aes_key_bits'], 'cap': cfg['aes_max_key_bits'], "
        "'opt': [o for o in cfg['aes_key_options'] if o['bits'] == 12][0], 'status': r.status_code, 'detail': r.json()['detail']}))\n"
    )
    env = {**os.environ, "QBREAK_KEY_BITS": "4,8,12", "SYMMETRIC_MAX_KEY_BITS": "8"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, check=True)
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["bits"] == [4, 8] and data["cap"] == 8
    assert data["opt"]["enabled"] is False and "not enabled on this instance" in data["opt"]["reason"].lower()
    assert data["status"] == 422 and "not enabled on this instance" in data["detail"].lower()


# ------------------------------------------------------------------ experiments schema + evaluation


def test_results_schema_roundtrip_and_aggregate(tmp_path) -> None:
    from qbreak.experiments.aggregate import build_all, write_aggregates
    from qbreak.experiments.schema import (
        append_record,
        load_records,
        make_record,
        validate_record,
    )

    rec = make_record("grover_noise_sweep", "miniaes", {"key_bits": 4}, condition="known_beginning", seed=1, success=True,
                      p_success=0.8, quantum={"oracle_calls": 3, "qubits": 15}, noise={"model": "depolarizing", "p": 0.01})
    shor = make_record("shor_noise_sweep", "minirsa", {"modulus": 15}, seed=2, success=False, p_success=0.2,
                       noise={"model": "depolarizing", "p": 0.01})
    append_record(rec, tmp_path)
    append_record(shor, tmp_path)
    assert len(load_records(tmp_path)) == 2
    with pytest.raises(ValueError):
        validate_record({**rec, "surprise": 1})
    with pytest.raises(ValueError):
        make_record("x", "des", {"key_bits": 4})
    series = build_all(load_records(tmp_path))
    assert {r["cipher"] for r in series["noise"]["rows"]} == {"miniaes", "minirsa"}
    assert series["scaling"]["empty"]
    out = write_aggregates(tmp_path)
    assert (out / "noise.csv").read_text().startswith("cipher")


def test_evaluation_endpoints_read_only(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QBREAK_RESULTS_DIR", str(tmp_path))
    client = _client()
    for name in ("scaling", "noise", "iteration-curve", "success_rate", "comparison", "counting"):
        body = client.get(f"/api/evaluation/{name}").json()
        assert body["empty"] is True and body["rows"] == []
    assert client.get("/api/evaluation/unknown").status_code == 404
    assert "fields" in client.get("/api/evaluation/schema").json()


def test_scaling_experiment_records_real_counts(tmp_path) -> None:
    from qbreak.experiments.runner import grover_scaling

    records = grover_scaling((4, 6))
    assert [r["quantum"]["qubits"] for r in records] == [15, 18]


# ------------------------------------------------------------------ resource estimator


def test_aes_resource_estimates_are_cited() -> None:
    from qbreak.aes.resources import aes_resource_estimate, all_aes_estimates

    est = aes_resource_estimate(128)
    assert est["logical_qubits"] == {"value": 2953, "source": "GLRS16"}
    assert est["t_gates"]["text"] == "1.19·2^86"
    assert "Grassl" in est["citations"]["GLRS16"] and "NIST" in est["citations"]["NIST16"]
    assert est["physical_qubits"]["value"] is None
    assert [e["key_bits"] for e in all_aes_estimates()["estimates"]] == [128, 192, 256]
    with pytest.raises(ValueError):
        aes_resource_estimate(64)
    assert _client().get("/api/aes/resources").status_code == 200


# ------------------------------------------------------------------ slow


@pytest.mark.slow
@pytest.mark.parametrize("key_bits", (10, 12))
def test_large_key_recovery(key_bits: int) -> None:
    for trial, key in enumerate(random.Random(key_bits).sample(range(1 << key_bits), 2)):
        ct = encrypt_nibbles(text_to_nibbles("Hi judges!"), key, key_bits)
        res = run_grover_attack(text_to_nibbles("Hi "), ct, key_bits, seed=trial)
        assert key in res.recovered_keys


@pytest.mark.slow
def test_noise_sweep_degrades_success() -> None:
    from qbreak.experiments.runner import grover_noise_sweep

    records = grover_noise_sweep(levels=(0.0, 0.02), shots=128)
    assert records[0]["p_success"] > records[1]["p_success"]


@pytest.mark.slow
def test_full_scaling_benchmark() -> None:
    from qbreak.experiments.runner import grover_scaling

    records = grover_scaling()
    qubits = [r["quantum"]["qubits"] for r in records]
    assert qubits == sorted(qubits) and records[-1]["size"] == {"key_bits": 12}


def test_grover_circuit_qubits_large_keys() -> None:
    for bits, expected in ((10, 22), (12, 24)):
        qc = build_grover_circuit([(1, 2), (3, 4), (5, 6)], bits, 1)
        assert qc.num_qubits == expected
