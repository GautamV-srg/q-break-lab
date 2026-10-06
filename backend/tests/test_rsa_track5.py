"""Track 5 public-key additions: N = 55/77, iterative Shor, classical baselines,
Shor experiments, resource estimate, Mosca, and the RSA API surface."""

from __future__ import annotations

import inspect
import re
from math import gcd
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qiskit.quantum_info import Statevector

from qbreak.api.main import app
from qbreak.common.simulator import run_circuit
from qbreak.risk.mosca import mosca_risk
from qbreak.rsa import classical, experiments, resource_estimate, shor
from qbreak.rsa.shor import (
    SHOR_SUPPORTED_N,
    build_period_finding_circuit,
    run_shor_attack,
)

SEED = 1234
EXPECTED_FACTORS = {15: (3, 5), 21: (3, 7), 33: (3, 11), 35: (5, 7), 55: (5, 11), 77: (7, 11)}
client = TestClient(app)


def _order(a: int, n: int) -> int:
    return classical.find_order(a, n)[0]


def _tvd(exact: dict[str, float], counts: dict[str, int]) -> float:
    shots = sum(counts.values())
    return 0.5 * sum(abs(exact.get(k, 0.0) - counts.get(k, 0) / shots) for k in set(exact) | set(counts))


def _exact_register_distribution(a: int, n: int) -> dict[str, float]:
    qc = build_period_finding_circuit(a, n, construction="permutation")
    t = qc.num_clbits
    qc.remove_final_measurements()
    probs = Statevector(qc).probabilities_dict(qargs=list(range(t)))
    return {format(int(k, 2), f"0{t}b"): v for k, v in probs.items()}


# --- moduli 55 and 77 ------------------------------------------------------


@pytest.mark.parametrize("n", [55, 77])
def test_new_moduli_factor_and_recover_p_q(n: int) -> None:
    from qbreak.rsa.minirsa import (
        decrypt_chunks,
        encrypt_chunks,
        generate_keypair,
        private_exponent,
    )

    kp = generate_keypair(n)
    res = run_shor_attack(n, seed=SEED, max_bases=6)
    assert res.factors == EXPECTED_FACTORS[n] == (kp.p, kp.q)
    assert res.period == _order(res.a, n)
    d, phi = private_exponent(*res.factors, kp.e)
    assert (d, phi) == (kp.d, kp.phi)
    plain = list(range(8))
    assert decrypt_chunks(encrypt_chunks(plain, n, kp.e), n, d) == plain


@pytest.mark.parametrize("n,a,r", [(55, 2, 20), (77, 2, 30)])
def test_known_periods_new_moduli(n: int, a: int, r: int) -> None:
    assert _order(a, n) == r
    res = run_shor_attack(n, a=a, seed=SEED, max_bases=1)
    assert (res.period, res.factors) == (r, EXPECTED_FACTORS[n])


# --- iterative (single counting qubit) Shor --------------------------------


@pytest.mark.parametrize("n", SHOR_SUPPORTED_N)
def test_iterative_uses_one_counting_qubit(n: int) -> None:
    qc = build_period_finding_circuit(2, n, construction="iterative")
    n_work = shor.work_qubits(n)
    assert [r.name for r in qc.qregs] == ["count", "work"]
    assert qc.qregs[0].size == 1 and qc.num_qubits == n_work + 1
    assert qc.num_clbits == 2 * n_work and len(qc.cregs) == 1
    assert shor.qubit_counts(n) == {"register_2n": 3 * n_work, "iterative": n_work + 1}
    assert "IQFT" not in {inst.operation.label for inst in qc.data}


def test_iterative_matches_exact_register_distribution_n21() -> None:
    """Third cross-check branch: the iterative circuit samples the same y
    distribution as the 2n-register permutation circuit (exact statevector)."""
    exact = _exact_register_distribution(2, 21)
    it = run_circuit(build_period_finding_circuit(2, 21, construction="iterative"), shots=8192, seed=SEED)
    pu = run_circuit(build_period_finding_circuit(2, 21, construction="permutation"), shots=8192, seed=SEED)
    assert _tvd(exact, it.counts) < 0.06
    assert _tvd(exact, it.counts) < _tvd(exact, pu.counts) + 0.03


@pytest.mark.parametrize("n", [15, 21, 55])
def test_three_constructions_give_same_factors(n: int) -> None:
    constructions = (["swap"] if n == 15 else []) + ["permutation", "iterative"]
    results = [run_shor_attack(n, a=2, seed=SEED, max_bases=1, construction=c) for c in constructions]
    assert {r.factors for r in results} == {EXPECTED_FACTORS[n]}
    assert {r.period for r in results} == {_order(2, n)}
    names = {r.construction for r in results}
    assert "iterative-phase-estimation" in names


def test_iterative_result_metadata_and_reasons() -> None:
    res = run_shor_attack(77, a=2, seed=SEED, max_bases=1, construction="iterative")
    assert res.construction == shor.ITERATIVE
    assert res.counting_qubits == 1 and res.n_count == 14 and res.circuit.num_qubits == 8
    assert res.multiplier_blocks == "permutation-unitary"  # disclosed classical pre-computation
    assert res.circuit_runs == 1
    assert all(att.reason for att in res.attempts)
    assert set(res.register_roles) == {"count", "work"} and "reused" in res.register_roles["count"]
    titles = [title for title, _ in res.explain_circuits]
    assert titles == ["Controlled U^(2^0)", "One iterative round (measures y bit 2)"]
    assert run_shor_attack(15, seed=SEED, construction="iterative").multiplier_blocks == "textbook-swaps"


def test_construction_selector_validation() -> None:
    assert shor.resolve_construction(15, "auto") == shor.TEXTBOOK
    assert shor.resolve_construction(21, "auto") == shor.PERMUTATION
    assert shor.resolve_construction(21, "iterative") == shor.ITERATIVE
    with pytest.raises(ValueError):
        shor.resolve_construction(21, "swap")
    with pytest.raises(ValueError):
        shor.resolve_construction(15, "nonsense")


def test_shot_success_probability() -> None:
    # ideal N = 15, a = 7: y in {64, 128, 192} factor, y = 0 does not
    counts = {format(y, "08b"): 1 for y in (0, 64, 128, 192)}
    assert shor.shot_success_probability(counts, 8, 15, 7) == 0.75
    assert shor.shot_success_probability({}, 8, 15, 7) == 0.0


def test_noisy_attack_runs_and_degrades() -> None:
    clean = run_shor_attack(15, a=7, seed=SEED, max_bases=1, construction="swap", noise_p=0.0)
    noisy = run_shor_attack(15, a=7, seed=SEED, max_bases=1, construction="swap", noise_p=0.1)
    p_clean = shor.shot_success_probability(clean.counts, 8, 15, 7)
    p_noisy = shor.shot_success_probability(noisy.counts, 8, 15, 7)
    assert p_clean > 0.7 and p_noisy < p_clean


@pytest.mark.slow
@pytest.mark.parametrize("n", SHOR_SUPPORTED_N)
@pytest.mark.parametrize("seed", range(5))
def test_iterative_every_modulus_many_seeds(n: int, seed: int) -> None:
    res = run_shor_attack(n, seed=seed, max_bases=6, construction="iterative")
    assert res.factors == EXPECTED_FACTORS[n]
    assert res.period == _order(res.a, n)


@pytest.mark.slow
@pytest.mark.parametrize("n", [n for n in SHOR_SUPPORTED_N if n != 21])
def test_iterative_matches_exact_distribution_all_n(n: int) -> None:
    exact = _exact_register_distribution(2, n)
    it = run_circuit(build_period_finding_circuit(2, n, construction="iterative"), shots=8192, seed=SEED)
    pu = run_circuit(build_period_finding_circuit(2, n, construction="permutation"), shots=8192, seed=SEED)
    assert _tvd(exact, it.counts) < _tvd(exact, pu.counts) + 0.03


# --- classical baselines ---------------------------------------------------


@pytest.mark.parametrize("n", SHOR_SUPPORTED_N)
def test_trial_division(n: int) -> None:
    res = classical.trial_division(n)
    assert res.factors == EXPECTED_FACTORS[n]
    p = EXPECTED_FACTORS[n][0]
    assert res.divisions == 1 + (p - 1) // 2  # 2, then odd divisors 3..p


@pytest.mark.parametrize("n", SHOR_SUPPORTED_N)
def test_classical_order_finding(n: int) -> None:
    res = classical.classical_order_finding(n, seed=SEED)
    assert res.factors == EXPECTED_FACTORS[n]
    assert res.period == _order(res.a, n)
    assert res.multiplications == sum(att.multiplications for att in res.attempts)
    assert all(att.multiplications == att.period - 1 for att in res.attempts)
    assert res.attempts[-1].ok and not any(att.ok for att in res.attempts[:-1])
    # same base order as the quantum attack
    assert [att.a for att in res.attempts] == shor.choose_bases(n, SEED)[: res.bases_tried]


def test_classical_order_finding_reasons() -> None:
    res = classical.classical_order_finding(21, a=4, seed=SEED)  # order 3: odd
    assert res.attempts[0].a == 4 and "odd" in res.attempts[0].reason
    res = classical.classical_order_finding(21, a=5, seed=SEED)  # 5^3 ≡ −1
    assert "−1" in res.attempts[0].reason


def test_comparison_record_shape() -> None:
    res = run_shor_attack(35, seed=SEED, construction="iterative")
    record = classical.comparison_record(res, shots=1024, seed=SEED)
    assert set(record) == {"quantum", "classical", "wallclock_ms", "wallclock_note"}
    q, c = record["quantum"], record["classical"]
    assert {"construction", "circuit_runs", "qubits", "depth"} <= set(q)
    assert {"trial_divisions", "order_finding_mults"} <= set(c)
    assert q["construction"] == "iterative" and q["qubits"] == 7 and q["circuit_runs"] == res.circuit_runs
    assert q["qubits_by_construction"] == {"register_2n": 18, "iterative": 7}
    assert c["trial_divisions"] == 3 and c["factors_found"]
    assert "slower in wall-clock" in record["wallclock_note"]
    assert "advantage" in record["wallclock_note"]


# --- blindness -------------------------------------------------------------

_ATTACKER_MODULES = (shor, classical, experiments, resource_estimate)
_FORBIDDEN_PARAMS = {"p", "q", "d", "phi", "factors", "private", "secret", "keypair"}


@pytest.mark.parametrize("module", _ATTACKER_MODULES, ids=lambda m: m.__name__)
def test_attacker_modules_never_import_minirsa(module) -> None:
    src = Path(module.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+[\w.]*minirsa", src, re.MULTILINE)
    assert "minirsa import" not in src


def test_baselines_signatures_have_no_secrets() -> None:
    for fn in (
        classical.trial_division,
        classical.find_order,
        classical.classical_order_finding,
        classical.comparison_record,
        shor.build_iterative_circuit,
    ):
        assert _FORBIDDEN_PARAMS.isdisjoint(inspect.signature(fn).parameters), fn.__name__


def test_baselines_do_not_touch_victim_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from qbreak.rsa import minirsa

    monkeypatch.setattr(minirsa, "SUPPORTED_MODULI", {})
    monkeypatch.setattr(minirsa, "generate_keypair", lambda *a, **k: pytest.fail("victim keygen used"))
    assert classical.trial_division(77).factors == (7, 11)
    assert classical.classical_order_finding(77, seed=SEED).factors == (7, 11)
    assert run_shor_attack(55, seed=SEED, construction="iterative").factors == (5, 11)


# --- experiments (shared results schema) -----------------------------------


def test_experiment_records_follow_shared_schema(tmp_path: Path) -> None:
    rows = experiments.noise_sweep(constructions=("iterative",), ps=(0.0, 0.05), seeds=(0,), shots=128)
    rows += experiments.scaling(moduli=(15,))
    rows += experiments.runs_to_factor(moduli=(15,), trials=2, constructions=("iterative",))
    for name, record in rows:
        assert tuple(record) == experiments.RESULTS_SCHEMA_KEYS
        assert record["schema_version"] == 1 and isinstance(record["extra"], dict)
        assert record["cipher"] == "minirsa" and record["size"] == {"modulus": 15}
        assert record["condition"] is None
        experiments.write_record(record, tmp_path, name)
    assert {p.name for p in tmp_path.iterdir()} == {"shor_noise_sweep", "shor_scaling", "shor_success_rate"}
    series = experiments.shor_series(experiments.load_records(tmp_path))
    assert [row["p"] for row in series["noise"]] == [0.0, 0.05]
    assert 0 < series["noise"][0]["uniform_baseline"] < 1
    assert "noise immunity" in series["noise"][0]["caveat"]  # N = 15 iterative shortcut is disclosed
    scaling = {row["construction"]: row for row in series["scaling"]}
    assert scaling["iterative"]["qubits"] == 5 and scaling["swap"]["qubits"] == 12
    runs = series["runs_to_factor"][0]
    assert runs["construction"] == "iterative" and runs["success_rate"] == 1.0


def test_records_pass_shared_validator_when_present(tmp_path: Path) -> None:
    schema = pytest.importorskip("qbreak.experiments.schema")
    for _, record in experiments.scaling(moduli=(15,)):
        schema.validate_record(record)


def test_aggregate_scaling_keeps_constructions_apart() -> None:
    aggregate = pytest.importorskip("qbreak.experiments.aggregate")
    records = [record for _, record in experiments.scaling(moduli=(15,))]
    rows = aggregate.build_series("scaling", records)["rows"]
    by_construction = {row["construction"]: row for row in rows}
    assert set(by_construction) == {"swap", "permutation", "iterative"}
    assert all(row["runs"] == 1 for row in rows)  # one circuit per row, never a mean over circuits
    assert by_construction["iterative"]["qubits"] < by_construction["swap"]["qubits"]


@pytest.mark.slow
def test_fake_backend_runs() -> None:
    pytest.importorskip("qiskit_ibm_runtime")
    rows = dict(experiments.fake_backend_runs(seeds=(0,), shots=256))
    assert rows["N15-swap-fake_manila-does-not-fit"]["extra"]["fits_device"] is False
    assert rows["N15-iterative-fake_manila-seed0"]["p_success"] is not None


@pytest.mark.slow
def test_base_success_and_runs_benchmarks() -> None:
    rows = experiments.base_success(moduli=(15, 21), seeds=(0,), shots=512)
    for _, record in rows:
        assert record["success"] == record["extra"]["usable"]  # usable bases factor, others fail
    runs = experiments.runs_to_factor(moduli=(15, 21, 77), trials=10)
    assert all(record["success"] for _, record in runs)


# --- resource estimate -----------------------------------------------------


def test_resource_estimate_2048_is_cited() -> None:
    est = resource_estimate.estimate_rsa_resources(2048)
    by_name = {fig["name"]: fig for fig in est["figures"]}
    assert by_name["Physical qubits (RSA-2048)"]["value"] == 20_000_000
    assert by_name["Runtime (RSA-2048)"]["value"] == 8
    assert by_name["Logical qubits"]["value"] == round(3 * 2048 + 0.002 * 2048 * 11)
    for fig in est["figures"]:
        assert fig["citation"] in est["citations"] and fig["quote"]
        assert fig["kind"] in {"published", "formula"}
    assert est["citations"]["gidney_ekera_2021"]["year"] == 2021
    assert [t["n"] for t in est["toy_instances"]] == list(SHOR_SUPPORTED_N)


def test_resource_estimate_other_sizes_do_not_extrapolate_physical() -> None:
    est = resource_estimate.estimate_rsa_resources(4096)
    assert not est["published_physical_estimates_available"]
    assert all(fig["kind"] == "formula" for fig in est["figures"])
    with pytest.raises(ValueError):
        resource_estimate.estimate_rsa_resources(4)


# --- Mosca -----------------------------------------------------------------


@pytest.mark.parametrize(
    "x,y,z,at_risk",
    [(10, 6, 15, True), (5, 5, 15, False), (10, 5, 15, False), (0, 0, 0, False), (0, 0.5, 0, True), (30, 10, 20, True)],
)
def test_mosca_matches_inequality(x: float, y: float, z: float, at_risk: bool) -> None:
    res = mosca_risk(x, y, z)
    assert res["at_risk"] is at_risk is (x + y > z)
    assert res["margin"] == z - (x + y)
    assert res["inequality"] == "X + Y > Z"
    assert res["verdict_text"].startswith("At risk" if at_risk else ("On the boundary" if x + y == z else "Not at risk"))


@pytest.mark.parametrize("bad", [-1, 201, float("nan"), float("inf"), True])
def test_mosca_rejects_bad_years(bad) -> None:
    with pytest.raises(ValueError):
        mosca_risk(bad, 1, 1)


def test_mosca_endpoints() -> None:
    info = client.get("/api/risk/mosca").json()
    assert info["inequality"] == "X + Y > Z" and info["explanation"]
    assert set(info["defaults"]) == {"x", "y", "z"}
    res = client.post("/api/risk/mosca", json={"x": 10, "y": 6, "z": 15}).json()
    assert res["at_risk"] is True and res["margin"] == -1
    assert client.post("/api/risk/mosca", json={"x": -1, "y": 6, "z": 15}).status_code == 422


# --- API -------------------------------------------------------------------


def test_config_rsa_section() -> None:
    cfg = client.get("/api/config").json()
    assert cfg["max_rsa_text_chars"] == 300
    options = {opt["n"]: opt for opt in cfg["rsa_moduli_options"]}
    assert [n for n, opt in options.items() if opt["enabled"]] == [15, 21, 33, 35, 55, 77]
    disabled = {opt["kind"]: opt for opt in cfg["rsa_moduli_options"] if not opt["enabled"]}
    assert set(disabled) == {"factor_of_2", "p_equals_q"}
    assert disabled["factor_of_2"]["n"] % 2 == 0 and disabled["factor_of_2"]["reason"]
    assert disabled["p_equals_q"]["n"] == 49 and "distinct" in disabled["p_equals_q"]["reason"]
    assert options[77]["qubits_iterative"] == 8 and options[77]["qubits_register_2n"] == 21
    keys = {c["key"]: c for c in cfg["rsa_constructions"]}
    assert set(keys) == {"swap", "permutation", "iterative"}
    assert keys["swap"]["moduli"] == [15] and keys["iterative"]["headline"]
    assert cfg["rsa_noise_moduli"] == [15]


def test_disabled_moduli_rejected() -> None:
    for n in (22, 49):
        assert client.post("/api/rsa/keygen", json={"n": n}).status_code == 422


def test_rsa_text_limit_300() -> None:
    assert client.post("/api/rsa/encrypt", json={"plaintext": "x" * 300, "n": 15, "e": 3}).status_code == 200
    assert client.post("/api/rsa/encrypt", json={"plaintext": "x" * 301, "n": 15, "e": 3}).status_code == 422


@pytest.mark.parametrize("construction", ["swap", "permutation", "iterative"])
def test_attack_construction_selector(construction: str) -> None:
    enc = client.post("/api/rsa/encrypt", json={"plaintext": "Hi", "n": 15, "e": 3}).json()
    body = {"n": 15, "e": 3, "ciphertext": enc["ciphertext"], "bit_length": 16, "seed": 42, "construction": construction}
    res = client.post("/api/rsa/attack", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["decrypted_text"] == "Hi" and data["construction_key"] == construction
    assert data["comparison"]["quantum"]["construction"] == construction
    assert data["counting_qubits"] == (1 if construction == "iterative" else 8)
    if construction == "permutation":
        assert data["classical_precomputation_note"].startswith("Disclosed classical pre-computation")
    else:
        assert data["classical_precomputation_note"] is None


def test_attack_iterative_n55_end_to_end() -> None:
    kp = client.post("/api/rsa/keygen", json={"n": 55}).json()
    enc = client.post("/api/rsa/encrypt", json={"plaintext": "Hi judges!", "n": 55, "e": kp["e"]}).json()
    body = {"n": 55, "e": kp["e"], "ciphertext": enc["ciphertext"], "bit_length": enc["bit_length"],
            "seed": 42, "construction": "iterative"}
    data = client.post("/api/rsa/attack", json=body).json()
    assert data["decrypted_text"] == "Hi judges!" and data["circuit"]["num_qubits"] == 7
    assert data["classical_precomputation_note"]  # permutation blocks are disclosed
    assert all(step["passed"] for step in data["verification"])


def test_attack_validation() -> None:
    base = {"n": 21, "e": 5, "ciphertext": [1], "bit_length": 3}
    assert client.post("/api/rsa/attack", json={**base, "construction": "swap"}).status_code == 422
    assert client.post("/api/rsa/attack", json={**base, "construction": "magic"}).status_code == 422
    assert client.post("/api/rsa/attack", json={**base, "noise_p": 0.01}).status_code == 422
    assert client.post("/api/rsa/attack", json={**base, "n": 15, "e": 3, "noise_p": 0.5}).status_code == 422
    assert client.post("/api/rsa/attack", json={**base, "phi": 12}).status_code == 422


def test_attack_with_noise() -> None:
    body = {"n": 15, "e": 3, "ciphertext": [8, 8, 0, 6, 4, 4], "bit_length": 16, "seed": 4, "shots": 256,
            "construction": "iterative", "noise_p": 0.01}
    data = client.post("/api/rsa/attack", json=body).json()
    assert data["noise_p"] == 0.01 and any("depolarising" in w for w in data["warnings"])


def test_resource_estimate_endpoint() -> None:
    data = client.get("/api/rsa/resource-estimate").json()
    assert data["modulus_bits"] == 2048 and data["citations"]
    assert client.get("/api/rsa/resource-estimate", params={"modulus_bits": 3}).status_code == 422


def test_all_bases_coprime_helper() -> None:
    # sanity for the parametrisations above
    assert all(gcd(2, n) == 1 for n in SHOR_SUPPORTED_N)
