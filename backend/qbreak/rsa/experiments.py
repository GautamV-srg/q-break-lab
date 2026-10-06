"""Shor experiments: noise, fake backends, per-base success, runs to factor, scaling.

Every run becomes one record in the **shared experiments-results schema owned
by the symmetric backend** (``qbreak.experiments.schema``). When that module
is installed its ``make_record`` / ``validate_record`` are used directly;
until it is merged, ``_mirror_make_record`` builds the identical shape:

    {schema_version, experiment, cipher, size, condition, seed, success,
     p_success, quantum, classical, noise, extra, timestamp}

Records are written to ``<results_dir>/<experiment>/<name>.json``. Shor
experiment names and the ``extra`` keys the shared aggregator reads:

- ``shor_noise_sweep``  depolarising sweep        extra: a, construction, uniform_baseline
- ``shor_fake_backend`` fake IBM devices          extra: a, construction, fits_device
- ``shor_base_success`` every base a, every N     extra: a, construction, true_order, usable
- ``shor_success_rate`` single-shot runs to factor extra: runs_to_success, construction
                        (quantum.oracle_calls = circuit runs, for the comparison chart)
- ``shor_scaling``      qubits / depth vs N       extra: construction, cx_count, ...

``shor_series`` also builds per-construction series (2n register vs
iterative side by side), which the shared aggregator does not separate.

All attacks here are the blind ones from ``shor`` and ``classical``; the true
order of a base is computed only to *label* chart points (public maths).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from math import gcd
from pathlib import Path
from statistics import mean

from qiskit import transpile

from qbreak.rsa import shor
from qbreak.rsa.classical import (
    classical_order_finding,
    construction_key,
    find_order,
    trial_division,
)

SCHEMA_VERSION = 1
RESULTS_SCHEMA_KEYS: tuple[str, ...] = (
    "schema_version",
    "experiment",
    "cipher",
    "size",
    "condition",
    "seed",
    "success",
    "p_success",
    "quantum",
    "classical",
    "noise",
    "extra",
    "timestamp",
)

NOISE_SWEEP_P: tuple[float, ...] = (0.0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1)
GATE_BASIS: tuple[str, ...] = ("rz", "sx", "x", "cx")

ITERATIVE_N15_CAVEAT = (
    "At N = 15 every base has order dividing 4, so U^(2^k) is the identity for k >= 2: the "
    "iterative circuit's first t-2 rounds contain no two-qubit gates and stay almost noise-free, "
    "pinning y's low bits to 0. Even uniformly random values of the two noisy high bits then "
    "factor N 3 times in 4, so this curve's floor is 0.75, not the uniform 0.25. Its flatness "
    "reflects the N = 15 shortcut, not genuine noise immunity."
)


def _caveat(n: int, construction: str) -> dict:
    return {"caveat": ITERATIVE_N15_CAVEAT} if n == 15 and construction == "iterative" else {}


def _mirror_make_record(experiment: str, cipher: str, size: dict, **fields) -> dict:
    """Same shape as ``qbreak.experiments.schema.make_record`` (used until it is merged)."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "experiment": experiment,
        "cipher": cipher,
        "size": dict(size),
        "condition": fields.get("condition"),
        "seed": fields.get("seed"),
        "success": fields.get("success"),
        "p_success": None if fields.get("p_success") is None else float(fields["p_success"]),
        "quantum": dict(fields.get("quantum") or {}),
        "classical": dict(fields.get("classical") or {}),
        "noise": {"model": "ideal", "p": None, "backend": None, **(fields.get("noise") or {})},
        "extra": dict(fields.get("extra") or {}),
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if tuple(record) != RESULTS_SCHEMA_KEYS:
        raise ValueError("record does not follow the shared schema")
    return record


try:  # the shared schema, once the symmetric backend's runner is merged
    from qbreak.experiments.schema import make_record as _shared_make_record
except ImportError:  # pragma: no cover - depends on merge order
    _shared_make_record = _mirror_make_record


def make_record(
    experiment: str,
    n: int,
    seed: int | None,
    success: bool | None,
    p_success: float | None,
    quantum: dict,
    classical: dict,
    noise: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """One MiniRSA record in the shared schema (size {"modulus": n}, condition null)."""
    return _shared_make_record(
        experiment, "minirsa", {"modulus": n}, condition=None, seed=seed,
        success=None if success is None else bool(success),
        p_success=None if p_success is None else round(float(p_success), 6),
        quantum=quantum, classical=classical, noise=noise, extra=extra,
    )


def write_record(record: dict, results_dir: Path, name: str) -> Path:
    """Write ``record`` to ``results_dir/<experiment>/<name>.json`` (a rerun overwrites it)."""
    path = Path(results_dir) / record["experiment"] / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _classical(n: int, a: int | None = None, seed: int | None = None) -> dict:
    trial = trial_division(n)
    order = classical_order_finding(n, a=a, seed=seed)
    return {
        "evaluations": trial.divisions,
        "trial_divisions": trial.divisions,
        "order_finding_mults": order.multiplications,
        "order_finding_bases_tried": order.bases_tried,
    }


def _quantum(result: shor.ShorResult, shots: int) -> dict:
    return {
        "circuit_runs": result.circuit_runs,
        "shots_per_run": shots,
        "qubits": result.circuit.num_qubits,
        "depth": result.circuit.depth() or 0,
        "transpiled_depth": result.transpiled.depth() or 0,
        "gate_counts": {str(k): int(v) for k, v in result.transpiled.count_ops().items()},
    }


def _shot_success(result: shor.ShorResult) -> float:
    return shor.shot_success_probability(result.counts, result.n_count, result.n, result.a)


def random_guess_floor(n: int, a: int) -> float:
    """p_success if every counting-register outcome were equally likely (total noise)."""
    t = shor.default_count_qubits(n)
    return shor.shot_success_probability({format(y, f"0{t}b"): 1 for y in range(2**t)}, t, n, a)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


def noise_sweep(
    n: int = 15,
    a: int = 7,
    constructions: tuple[str, ...] = ("swap", "iterative"),
    ps: tuple[float, ...] = NOISE_SWEEP_P,
    seeds: tuple[int, ...] = (0, 1, 2),
    shots: int = 1024,
) -> list[tuple[str, dict]]:
    """Depolarising sweep: per-shot success of base a at each noise level."""
    floor = random_guess_floor(n, a)
    out = []
    for construction in constructions:
        for p in ps:
            for seed in seeds:
                res = shor.run_shor_attack(
                    n, a=a, shots=shots, seed=seed, max_bases=1, construction=construction, noise_p=p
                )
                record = make_record(
                    "shor_noise_sweep", n, seed, res.factors is not None, _shot_success(res),
                    _quantum(res, shots), _classical(n, a, seed),
                    {"model": "depolarizing", "p": p, "backend": None},
                    {"a": a, "construction": construction, "uniform_baseline": round(floor, 6),
                     **_caveat(n, construction)},
                )
                out.append((f"N{n}-{construction}-a{a}-p{p:g}-seed{seed}", record))
    return out


def fake_backend_runs(
    n: int = 15, a: int = 7, seeds: tuple[int, ...] = (0, 1, 2), shots: int = 1024
) -> list[tuple[str, dict]]:
    """Run on fake IBM devices (real coupling map, basis and calibrated noise).

    FakeManilaV2 has 5 qubits: only the iterative circuit (1 + 4 qubits) fits;
    the 12-qubit register circuit is recorded as not fitting rather than run.
    """
    from qiskit_ibm_runtime.fake_provider import FakeBrisbane, FakeManilaV2

    floor = random_guess_floor(n, a)
    out = []
    for backend in (FakeManilaV2(), FakeBrisbane()):
        for construction in ("swap", "iterative"):
            needed = shor.qubit_counts(n)["iterative" if construction == "iterative" else "register_2n"]
            noise = {"model": "fake_backend", "p": None, "backend": backend.name}
            extra = {"a": a, "construction": construction, "uniform_baseline": round(floor, 6),
                     "device_qubits": backend.num_qubits, **_caveat(n, construction)}
            if needed > backend.num_qubits:
                record = make_record(
                    "shor_fake_backend", n, None, None, None, {"qubits": needed}, _classical(n, a),
                    noise, {**extra, "fits_device": False},
                )
                out.append((f"N{n}-{construction}-{backend.name}-does-not-fit", record))
                continue
            for seed in seeds:
                res = shor.run_shor_attack(
                    n, a=a, shots=shots, seed=seed, max_bases=1, construction=construction, backend=backend
                )
                record = make_record(
                    "shor_fake_backend", n, seed, res.factors is not None, _shot_success(res),
                    _quantum(res, shots), _classical(n, a, seed), noise, {**extra, "fits_device": True},
                )
                out.append((f"N{n}-{construction}-{backend.name}-seed{seed}", record))
    return out


def base_success(
    moduli: tuple[int, ...] = shor.SHOR_SUPPORTED_N,
    seeds: tuple[int, ...] = (0, 1, 2),
    shots: int = 1024,
    construction: str = "auto",
) -> list[tuple[str, dict]]:
    """Per-base success: for every coprime base a, single-base attacks and per-shot success."""
    out = []
    for n in moduli:
        key = construction_key(shor.resolve_construction(n, construction))
        for a in (a for a in range(2, n - 1) if gcd(a, n) == 1):
            r, _ = find_order(a, n)
            usable = r % 2 == 0 and pow(a, r // 2, n) != n - 1
            for seed in seeds:
                res = shor.run_shor_attack(n, a=a, shots=shots, seed=seed, max_bases=1, construction=construction)
                record = make_record(
                    "shor_base_success", n, seed, res.factors is not None, _shot_success(res),
                    _quantum(res, shots), _classical(n, a, seed), None,
                    {"a": a, "construction": key, "true_order": r, "usable": usable},
                )
                out.append((f"N{n}-{key}-a{a}-seed{seed}", record))
    return out


def runs_to_factor(
    moduli: tuple[int, ...] = shor.SHOR_SUPPORTED_N,
    trials: int = 20,
    constructions: tuple[str, ...] = ("auto", "iterative"),
) -> list[tuple[str, dict]]:
    """Single-shot circuit runs until the factors appear, over random bases.

    Each run is one shot of one circuit on a fresh base (``shots=1``), so the
    run count is the number of quantum executions the attack needed. It is
    stored as ``quantum.oracle_calls`` for the shared quantum-vs-classical chart.
    """
    out = []
    for n in moduli:
        n_bases = len([a for a in range(2, n - 1) if gcd(a, n) == 1])
        for construction in constructions:
            key = construction_key(shor.resolve_construction(n, construction))
            for seed in range(trials):
                res = shor.run_shor_attack(n, shots=1, seed=seed, max_bases=n_bases, construction=construction)
                ok = res.factors is not None
                record = make_record(
                    "shor_success_rate", n, seed, ok, None,
                    {**_quantum(res, 1), "oracle_calls": res.circuit_runs}, _classical(n, seed=seed), None,
                    {"construction": key, "runs_to_success": res.circuit_runs if ok else None},
                )
                out.append((f"N{n}-{key}-runs-seed{seed}", record))
    return out


def scaling(moduli: tuple[int, ...] = shor.SHOR_SUPPORTED_N, a: int = 2) -> list[tuple[str, dict]]:
    """Qubits and depth vs modulus for each construction (no simulation).

    ``transpiled_depth`` / ``cx_count`` come from transpiling to a generic
    rz, sx, x, cx basis (optimization level 1), which synthesises every
    permutation block into elementary gates; ``depth`` counts each block as one
    layer.
    """
    out = []
    for n in moduli:
        for construction in (["swap"] if n == 15 else []) + ["permutation", "iterative"]:
            qc = shor.build_period_finding_circuit(a, n, construction=construction)
            gate_level = transpile(
                qc, basis_gates=[*GATE_BASIS, "reset", "measure", "if_else"], optimization_level=1, seed_transpiler=0
            )
            quantum = {
                "qubits": qc.num_qubits,
                "depth": qc.depth() or 0,
                "transpiled_depth": gate_level.depth() or 0,
                "gate_counts": {str(k): int(v) for k, v in gate_level.count_ops().items()},
            }
            extra = {
                "construction": construction,
                "a": a,
                "counting_qubits": 1 if construction == "iterative" else shor.default_count_qubits(n),
                "work_qubits": shor.work_qubits(n),
                "cx_count": int(gate_level.count_ops().get("cx", 0)),
                "mid_circuit_measurements": qc.num_clbits if construction == "iterative" else 0,
            }
            record = make_record("shor_scaling", n, None, None, None, quantum, _classical(n, a), None, extra)
            out.append((f"N{n}-{construction}", record))
    return out


# ---------------------------------------------------------------------------
# Per-construction chart series
# ---------------------------------------------------------------------------


def load_records(results_dir: Path) -> list[dict]:
    """Every MiniRSA record under ``results_dir/shor_*``."""
    records = []
    for path in sorted(Path(results_dir).glob("shor_*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("cipher") == "minirsa":
            records.append(record)
    return records


def _stats(rs: list[dict]) -> dict:
    ps = [r["p_success"] for r in rs if r["p_success"] is not None]
    oks = [r["success"] for r in rs if r["success"] is not None]
    return {"p_success_mean": round(mean(ps), 4) if ps else None,
            "success_rate": round(mean(oks), 4) if oks else None, "samples": len(rs)}


def shor_series(records: list[dict]) -> dict:
    """Shor series split by construction (2n register vs iterative)."""
    def group(experiment: str, key) -> list[tuple[tuple, list[dict]]]:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for record in records:
            if record["experiment"] == experiment:
                groups[key(record)].append(record)
        return sorted(groups.items(), key=lambda kv: tuple(
            (0, v) if isinstance(v, int | float) else (1, str(v)) for v in kv[0]))

    n_of = lambda r: r["size"]["modulus"]  # noqa: E731
    series: dict[str, list] = {}
    series["noise"] = [
        {"n": n, "construction": c, "a": a, "p": p, "uniform_baseline": rs[0]["extra"].get("uniform_baseline"),
         "caveat": rs[0]["extra"].get("caveat"), **_stats(rs)}
        for (n, c, a, p), rs in group("shor_noise_sweep", lambda r: (n_of(r), r["extra"]["construction"], r["extra"]["a"], r["noise"]["p"]))
    ]
    series["fake_backend"] = [
        {"n": n, "construction": c, "backend": b, "fits_device": rs[0]["extra"]["fits_device"],
         "device_qubits": rs[0]["extra"]["device_qubits"], "qubits": rs[0]["quantum"]["qubits"],
         "transpiled_depth": rs[0]["quantum"].get("transpiled_depth"), "caveat": rs[0]["extra"].get("caveat"),
         **_stats(rs)}
        for (n, c, b), rs in group("shor_fake_backend", lambda r: (n_of(r), r["extra"]["construction"], r["noise"]["backend"]))
    ]
    series["base_success"] = [
        {"n": n, "construction": c, "a": a, "true_order": rs[0]["extra"]["true_order"],
         "usable": rs[0]["extra"]["usable"], **_stats(rs)}
        for (n, c, a), rs in group("shor_base_success", lambda r: (n_of(r), r["extra"]["construction"], r["extra"]["a"]))
    ]
    series["runs_to_factor"] = []
    for (n, c), rs in group("shor_success_rate", lambda r: (n_of(r), r["extra"]["construction"])):
        runs = [r["extra"]["runs_to_success"] for r in rs if r["extra"]["runs_to_success"] is not None]
        series["runs_to_factor"].append({
            "n": n, "construction": c, "trials": len(rs), "success_rate": round(len(runs) / len(rs), 4),
            "mean_circuit_runs": round(mean(runs), 3) if runs else None,
            "mean_order_finding_mults": round(mean(r["classical"]["order_finding_mults"] for r in rs), 3),
            "trial_divisions": rs[0]["classical"]["trial_divisions"], "qubits": rs[0]["quantum"]["qubits"],
        })
    series["scaling"] = [
        {"n": n, "construction": c, "qubits": rs[0]["quantum"]["qubits"], "depth": rs[0]["quantum"]["depth"],
         "transpiled_depth": rs[0]["quantum"]["transpiled_depth"],
         **{k: rs[0]["extra"][k] for k in ("counting_qubits", "work_qubits", "cx_count", "mid_circuit_measurements")}}
        for (n, c), rs in group("shor_scaling", lambda r: (n_of(r), r["extra"]["construction"]))
    ]
    runs = {(row["n"], row["construction"]): row for row in series["runs_to_factor"]}
    series["quantum_vs_classical"] = []
    for n in sorted({row["n"] for row in series["scaling"]}):
        qubits = {row["construction"]: row["qubits"] for row in series["scaling"] if row["n"] == n}
        register = runs.get((n, "swap" if n == 15 else "permutation"), {})
        iterative = runs.get((n, "iterative"), {})
        series["quantum_vs_classical"].append({
            "n": n,
            "qubits_register_2n": qubits.get("permutation"),
            "qubits_iterative": qubits.get("iterative"),
            "shor_mean_circuit_runs": register.get("mean_circuit_runs"),
            "shor_iterative_mean_circuit_runs": iterative.get("mean_circuit_runs"),
            "trial_divisions": trial_division(n).divisions,
            "order_finding_mults_mean": register.get("mean_order_finding_mults"),
        })
    return series
