"""Experiments runner for the symmetric breach test (Grover on MiniAES).

One function per experiment family. Each run appends records in the shared schema
(`qbreak.experiments.schema`) under results/<experiment>/. Backend B appends its Shor
records through the same schema module; it does not edit this file.

Unlike the attack, an EXPERIMENT knows the true key: it is the evaluation harness that
measures whether the blind attack succeeded. The key is only used to generate the
ciphertext and to score the result, never passed to the attack.

Usage (from backend/):
    python -m qbreak.experiments.runner --quick          # a few minutes
    python -m qbreak.experiments.runner                  # the full benchmark suite
    python -m qbreak.experiments.runner --only grover_noise_sweep
Then: python -m qbreak.experiments.aggregate

The defence experiments (bb84_qber_vs_eve, bb84_qber_vs_noise, bb84_key_rate,
defence_overhead) live in `qbreak.defence.experiments` and are registered below, so
`--only bb84_qber_vs_eve` works the same way.

Benchmark instances are self-generated (see README "Dataset"): every key of each size
(or a seeded sample for 10/12-bit), the fixed MESSAGES below, and fixed seeds.
"""

from __future__ import annotations

import argparse
import random
import time
import warnings

from qbreak.aes.cipher import encrypt_nibbles
from qbreak.aes.classical import classical_key_search
from qbreak.aes.conditions import circuit_spec
from qbreak.aes.counting import run_quantum_counting
from qbreak.aes.grover import (
    build_grover_circuit,
    optimal_iterations,
    run_grover_attack,
    theoretical_success,
)
from qbreak.common.encoding import text_to_nibbles
from qbreak.common.simulator import run_circuit
from qbreak.defence.experiments import EXPERIMENTS as DEFENCE_EXPERIMENTS
from qbreak.defence.experiments import QUICK_ARGS as DEFENCE_QUICK_ARGS
from qbreak.experiments.schema import append_record, make_record

MESSAGES: tuple[str, ...] = ("Hi judges!", "Top secret plan", "Quantum 2026", "Hello, world", "meet me at noon")
"""The fixed message set of the benchmark suite."""

SUBSTRINGS: dict[str, str] = {"Hi judges!": "judges", "Top secret plan": "secret", "Quantum 2026": "2026", "Hello, world": "world", "meet me at noon": "noon"}

BASE_SEED = 1234
NOISE_LEVELS: tuple[float, ...] = (0.0, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 1e-2)
"""The 4-bit circuit has ~20k CX gates after decomposition, so success is already gone near 1e-3."""


def _key_str(key: int, bits: int) -> str:
    return format(key, f"0{bits}b")


def _instance(key_bits: int, key: int, msg: str, condition: str) -> tuple[list[int] | None, list[int]]:
    ct = encrypt_nibbles(text_to_nibbles(msg), key, key_bits)
    if condition == "known_beginning":
        return text_to_nibbles(msg[:3]), ct
    if condition == "known_substring":
        return text_to_nibbles(SUBSTRINGS[msg]), ct
    return None, ct


def _circuit_metrics(qc, tqc, iterations: int) -> dict:
    return {
        "oracle_calls": iterations,
        "iterations": iterations,
        "qubits": qc.num_qubits,
        "depth": qc.depth() or 0,
        "transpiled_depth": tqc.depth() or 0,
        "gate_counts": {str(k): int(v) for k, v in tqc.count_ops().items()},
    }


def grover_iteration_curve(key_bits: int = 4, max_iterations: int = 8, shots: int = 1024, seed: int = BASE_SEED) -> list[dict]:
    """Measured success probability vs Grover iterations, next to the sin^2 envelope."""
    key = random.Random(seed).randrange(1 << key_bits)
    known, ct = _instance(key_bits, key, MESSAGES[0], "known_beginning")
    spec = circuit_spec("known_beginning", known, ct, key_bits)
    m = sum(spec.fits(k) for k in range(1 << key_bits))  # ground truth, for the theory curve only
    records = []
    for r in range(max_iterations + 1):
        qc = build_grover_circuit(spec, key_bits, r)
        sim = run_circuit(qc, shots=shots, seed=seed + r)
        p = sim.counts.get(_key_str(key, key_bits), 0) / shots
        records.append(make_record(
            "grover_iteration_curve", "miniaes", {"key_bits": key_bits}, condition="known_beginning", seed=seed + r,
            success=p > 1 / (1 << key_bits) * 4, p_success=p, quantum=_circuit_metrics(qc, sim.transpiled, r),
            extra={"iterations": r, "theory_p_success": theoretical_success(key_bits, m, r) / max(1, m), "num_solutions": m,
                   "optimal_iterations": optimal_iterations(key_bits, m)},
        ))
    return records


def grover_noise_sweep(key_bits: int = 4, levels: tuple[float, ...] = NOISE_LEVELS, shots: int = 256, seed: int = BASE_SEED) -> list[dict]:
    """Attack success probability vs depolarising noise (u + cx basis, p on cx, p/10 on u)."""
    key = random.Random(seed).randrange(1 << key_bits)
    known, ct = _instance(key_bits, key, MESSAGES[0], "known_beginning")
    spec = circuit_spec("known_beginning", known, ct, key_bits)
    iterations = optimal_iterations(key_bits, 1)
    qc = build_grover_circuit(spec, key_bits, iterations)
    records = []
    for i, p_noise in enumerate(levels):
        sim = run_circuit(qc, shots=shots, seed=seed + i, noise_p=p_noise)
        ranked = sorted(sim.counts.items(), key=lambda kv: -kv[1])
        p = sim.counts.get(_key_str(key, key_bits), 0) / shots
        records.append(make_record(
            "grover_noise_sweep", "miniaes", {"key_bits": key_bits}, condition="known_beginning", seed=seed + i,
            success=ranked[0][0] == _key_str(key, key_bits), p_success=p, quantum=_circuit_metrics(qc, sim.transpiled, iterations),
            noise={"model": "depolarizing", "p": p_noise, "backend": None},
            extra={"uniform_baseline": 1 / (1 << key_bits), "shots": shots},
        ))
    return records


def grover_fake_backend(key_bits: int = 4, backend_name: str = "FakeGuadalupeV2", shots: int = 256, seed: int = BASE_SEED) -> list[dict]:
    """The 4-bit attack transpiled to a real IBM chip layout and run with its calibrated noise."""
    warnings.filterwarnings("ignore", category=UserWarning)
    from qiskit_ibm_runtime import fake_provider

    backend = getattr(fake_provider, backend_name)()
    key = random.Random(seed).randrange(1 << key_bits)
    known, ct = _instance(key_bits, key, MESSAGES[0], "known_beginning")
    spec = circuit_spec("known_beginning", known, ct, key_bits)
    records = []
    for iterations in (0, 1, optimal_iterations(key_bits, 1)):
        qc = build_grover_circuit(spec, key_bits, iterations)
        sim = run_circuit(qc, shots=shots, seed=seed, backend=backend)
        ranked = sorted(sim.counts.items(), key=lambda kv: -kv[1])
        p = sim.counts.get(_key_str(key, key_bits), 0) / shots
        records.append(make_record(
            "grover_fake_backend", "miniaes", {"key_bits": key_bits}, condition="known_beginning", seed=seed,
            success=ranked[0][0] == _key_str(key, key_bits), p_success=p, quantum=_circuit_metrics(qc, sim.transpiled, iterations),
            noise={"model": "fake_backend", "p": None, "backend": backend_name},
            extra={"iterations": iterations, "uniform_baseline": 1 / (1 << key_bits), "backend_qubits": backend.num_qubits,
                   "ideal_p_success": theoretical_success(key_bits, 1, iterations)},
        ))
    return records


def grover_scaling(key_sizes: tuple[int, ...] = (4, 6, 8, 10, 12), seed: int = BASE_SEED) -> list[dict]:
    """Qubits and depth (logical and Aer-transpiled) vs key size, at the M = 1 iteration count.

    Circuits are built and transpiled but not simulated, so 12-bit is cheap here.
    """
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    records = []
    for bits in key_sizes:
        key = random.Random(seed + bits).randrange(1 << bits)
        known, ct = _instance(bits, key, MESSAGES[0], "known_beginning")
        spec = circuit_spec("known_beginning", known, ct, bits)
        iterations = optimal_iterations(bits, 1)
        qc = build_grover_circuit(spec, bits, iterations)
        t0 = time.perf_counter()
        tqc = transpile(qc, AerSimulator(), optimization_level=0)
        records.append(make_record(
            "grover_scaling", "miniaes", {"key_bits": bits}, condition="known_beginning", seed=seed + bits,
            quantum=_circuit_metrics(qc, tqc, iterations),
            classical={"evaluations": (2**bits + 1) / 2},
            extra={"statevector_mb": 16 * 2**qc.num_qubits / 2**20, "transpile_ms": (time.perf_counter() - t0) * 1000},
        ))
    return records


def grover_success_rate(
    key_sizes: tuple[int, ...] = (4,),
    conditions: tuple[str, ...] = ("known_beginning", "known_substring", "ciphertext_only"),
    keys_per_size: int | None = None,
    shots: int = 1024,
    seed: int = BASE_SEED,
) -> list[dict]:
    """Full blind attacks across keys and messages: success rate plus quantum vs classical queries.

    Each record carries the comparison record (oracle calls vs classical cipher evaluations).
    `keys_per_size=None` uses every key for sizes up to 6 bits and 8 seeded keys above.
    """
    records = []
    for bits in key_sizes:
        rng = random.Random(seed + bits)
        if keys_per_size is None:
            keys = list(range(1 << bits)) if bits <= 6 else [rng.randrange(1 << bits) for _ in range(8)]
        else:
            keys = [rng.randrange(1 << bits) for _ in range(keys_per_size)]
        for condition in conditions:
            for i, key in enumerate(keys):
                msg = MESSAGES[i % len(MESSAGES)]
                known, ct = _instance(bits, key, msg, condition)
                run_seed = seed + 1000 * bits + i
                try:
                    res = run_grover_attack(known, ct, bits, shots=shots, seed=run_seed, condition=condition)
                except ValueError as exc:  # e.g. a substring that fits too many positions
                    records.append(make_record("grover_success_rate", "miniaes", {"key_bits": bits}, condition=condition,
                                               seed=run_seed, success=False, extra={"error": str(exc), "message": msg}))
                    continue
                classical = classical_key_search(known, ct, bits, condition)
                p = res.counts.get(_key_str(key, bits), 0) / shots
                oracle_calls = sum(a.iterations for a in res.attempts) + (res.counting.controlled_grover_calls if res.counting else 0)
                records.append(make_record(
                    "grover_success_rate", "miniaes", {"key_bits": bits}, condition=condition, seed=run_seed,
                    success=key in res.recovered_keys, p_success=p,
                    quantum={**_circuit_metrics(res.circuit, res.transpiled, res.iterations), "oracle_calls": oracle_calls},
                    classical={"evaluations": classical.cipher_evaluations, "expected_tries": classical.expected_tries,
                               "candidates": len(classical.candidates)},
                    extra={"message": msg, "unique": len(res.recovered_keys) == 1, "recovered": len(res.recovered_keys),
                           "estimated_m": res.counting.estimated_m_rounded if res.counting else None,
                           "sim_time_ms": res.sim_time_ms, "classical_ms": classical.wall_ms},
                ))
    return records


def grover_counting_accuracy(key_bits: int = 4, shots: int = 1024, seed: int = BASE_SEED) -> list[dict]:
    """Quantum-counting estimate of M vs the true count (computed classically for scoring)."""
    records = []
    rng = random.Random(seed)
    cases = [("known_beginning", "Hi "), ("known_beginning", "H"), ("known_substring", None), ("ciphertext_only", None)]
    for i, msg in enumerate(MESSAGES):
        for condition, crib in cases:
            key = rng.randrange(1 << key_bits)
            known, ct = _instance(key_bits, key, msg, condition)
            if crib and condition == "known_beginning":
                known = text_to_nibbles(msg[: len(crib)])
            try:
                spec = circuit_spec(condition, known, ct, key_bits)
            except ValueError:
                continue
            true_m = sum(spec.fits(k) for k in range(1 << key_bits))
            c = run_quantum_counting(spec, key_bits, shots=shots, seed=seed + i)
            records.append(make_record(
                "grover_counting_accuracy", "miniaes", {"key_bits": key_bits}, condition=condition, seed=seed + i,
                success=c.estimated_m_rounded == true_m,
                quantum={"oracle_calls": c.controlled_grover_calls, "qubits": c.num_qubits, "transpiled_depth": c.transpiled_depth},
                extra={"true_m": true_m, "estimated_m": c.estimated_m_rounded, "peak_m_estimate": c.estimated_m,
                       "counting_qubits": c.counting_qubits, "message": msg},
            ))
    return records


EXPERIMENTS = {
    "grover_iteration_curve": grover_iteration_curve,
    "grover_noise_sweep": grover_noise_sweep,
    "grover_fake_backend": grover_fake_backend,
    "grover_scaling": grover_scaling,
    "grover_success_rate": grover_success_rate,
    "grover_counting_accuracy": grover_counting_accuracy,
    **DEFENCE_EXPERIMENTS,
}

QUICK_ARGS: dict[str, dict] = {
    "grover_iteration_curve": {"max_iterations": 6},
    "grover_noise_sweep": {"levels": (0.0, 3e-5, 1e-4, 1e-3), "shots": 128},
    "grover_fake_backend": {"shots": 128},
    "grover_scaling": {},
    "grover_success_rate": {"key_sizes": (4,), "keys_per_size": 4},
    "grover_counting_accuracy": {},
    **DEFENCE_QUICK_ARGS,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Grover and defence experiments into results/.")
    parser.add_argument("--only", nargs="+", choices=sorted(EXPERIMENTS))
    parser.add_argument("--quick", action="store_true", help="small settings for a fast smoke run")
    args = parser.parse_args()
    for name in args.only or list(EXPERIMENTS):
        t0 = time.perf_counter()
        records = EXPERIMENTS[name](**(QUICK_ARGS[name] if args.quick else {}))
        for record in records:
            append_record(record)
        print(f"{name}: {len(records)} records in {time.perf_counter() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
