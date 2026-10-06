"""Benchmark the Shor attack for each modulus.

Usage (from backend/):
    python scripts/benchmark_shor.py --n 15 21 33 35 55 77 --trials 5

For each N prints qubits, logical depth, transpiled depth, transpiled gate
counts, mean / max simulation time, success rate and peak RSS. Moduli not yet
in SHOR_SUPPORTED_N are benchmarked anyway (that is how they earn a place).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qbreak.rsa import shor  # noqa: E402


def _peak_rss_mb() -> float | None:
    """Peak resident memory of this process in MB (None if unavailable)."""
    try:
        import resource  # POSIX

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / 1024 / (1024 if sys.platform == "darwin" else 1)
    except ImportError:
        pass
    try:
        import psutil

        info = psutil.Process(os.getpid()).memory_info()
        return getattr(info, "peak_wset", info.rss) / 2**20
    except ImportError:
        return None


def benchmark(n: int, trials: int, shots: int) -> dict:
    """Run the attack ``trials`` times with seeds 0..trials-1 and summarise."""
    original = shor.SHOR_SUPPORTED_N
    shor.SHOR_SUPPORTED_N = tuple(sorted(set(original) | {n}))
    try:
        times, wall, successes, res = [], [], 0, None
        for seed in range(trials):
            t0 = time.perf_counter()
            res = shor.run_shor_attack(n, shots=shots, seed=seed)
            wall.append((time.perf_counter() - t0) * 1000)
            times.append(res.sim_time_ms)
            successes += res.factors is not None
    finally:
        shor.SHOR_SUPPORTED_N = original
    ops = dict(sorted(res.transpiled.count_ops().items(), key=lambda kv: -kv[1]))
    return {
        "n": n,
        "qubits": res.circuit.num_qubits,
        "depth": res.circuit.depth(),
        "t_depth": res.transpiled.depth(),
        "gates": ", ".join(f"{k}:{v}" for k, v in ops.items() if k not in ("measure", "barrier")),
        "mean_ms": sum(times) / len(times),
        "max_ms": max(times),
        "max_wall_ms": max(wall),
        "success": f"{successes}/{trials}",
        "construction": res.construction,
        "rss_mb": _peak_rss_mb(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, nargs="+", default=[15, 21, 33, 35, 55, 77])
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--shots", type=int, default=1024)
    args = parser.parse_args()

    rows = [benchmark(n, args.trials, args.shots) for n in args.n]
    print(
        "| N | construction | qubits | depth | transpiled depth | sim mean ms | sim max ms "
        "| wall max ms | success | peak RSS MB | transpiled gates |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        rss = f"{r['rss_mb']:.0f}" if r["rss_mb"] is not None else "n/a"
        print(
            f"| {r['n']} | {r['construction']} | {r['qubits']} | {r['depth']} | {r['t_depth']} "
            f"| {r['mean_ms']:.0f} | {r['max_ms']:.0f} | {r['max_wall_ms']:.0f} | {r['success']} "
            f"| {rss} | {r['gates']} |"
        )
    print("\nPeak RSS is cumulative for the process (rows run in order).")


if __name__ == "__main__":
    main()
