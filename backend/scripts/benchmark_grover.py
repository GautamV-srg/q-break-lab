"""Benchmark the Grover attack on MiniAES for several key sizes.

Usage (from backend/):
    python scripts/benchmark_grover.py --bits 4 6 8 --trials 5
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time

from qbreak.aes.cipher import encrypt_nibbles
from qbreak.aes.grover import GroverResult, optimal_iterations, run_grover_attack

MESSAGES = ("Hi judges!", "Top secret plan", "Quantum 2026", "Hello, world")


def _nibbles(text: str) -> list[int]:
    out: list[int] = []
    for b in text.encode("utf-8"):
        out += [b >> 4, b & 0xF]
    return out


def peak_rss_mb() -> float:
    """Peak resident memory of this process in MB (Linux/macOS via resource, Windows via psapi)."""
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
    except ImportError:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = kernel32.K32GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        get_info(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / (1024 * 1024)


def bench(key_bits: int, trials: int, shots: int) -> dict[str, object]:
    rng = random.Random(1234 + key_bits)
    times: list[float] = []
    wall: list[float] = []
    successes = 0
    attempts_used: list[int] = []
    sized: GroverResult | None = None
    for t in range(trials):
        key = rng.randrange(1 << key_bits)
        msg = MESSAGES[t % len(MESSAGES)]
        ct = encrypt_nibbles(_nibbles(msg), key, key_bits)
        t0 = time.perf_counter()
        res = run_grover_attack(_nibbles(msg[:3]), ct, key_bits, shots=shots, seed=t)
        wall.append((time.perf_counter() - t0) * 1000)
        times.append(res.sim_time_ms)
        attempts_used.append(len(res.attempts))
        successes += key in res.recovered_keys

        if res.iterations == optimal_iterations(key_bits):
            sized = res  # an M = 1 run: report its circuit size

    if sized is None:
        sized = res
    ops = sized.transpiled.count_ops()
    return {
        "bits": key_bits,
        "qubits": sized.circuit.num_qubits,
        "iters": sized.iterations,
        "depth": sized.circuit.depth(),
        "t_depth": sized.transpiled.depth(),
        "mcx": ops.get("mcx", 0),
        "sim_mean": statistics.mean(times),
        "sim_max": max(times),
        "wall_max": max(wall),
        "attempts": statistics.mean(attempts_used),
        "success": f"{successes}/{trials}",
        "rss": peak_rss_mb(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bits", type=int, nargs="+", default=[4], choices=[4, 6, 8])
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--shots", type=int, default=1024)
    args = parser.parse_args()

    header = (
        "| bits | qubits | iters | logical depth | transpiled depth | mcx | "
        "sim mean ms | sim max ms | wall max ms | runs/attack | success | peak RSS MB |"
    )
    print(header)
    print("|" + "---|" * (header.count("|") - 1))
    for bits in args.bits:
        r = bench(bits, args.trials, args.shots)
        print(
            f"| {r['bits']} | {r['qubits']} | {r['iters']} | {r['depth']} | {r['t_depth']} | "
            f"{r['mcx']} | {r['sim_mean']:.0f} | {r['sim_max']:.0f} | {r['wall_max']:.0f} | "
            f"{r['attempts']:.1f} | {r['success']} | {r['rss']:.0f} |",
            flush=True,
        )


if __name__ == "__main__":
    main()
