from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

_SIM = AerSimulator()
_GATE = threading.Semaphore(int(os.getenv("QBREAK_MAX_CONCURRENT_SIMS", "1")))


class SimulatorBusyError(RuntimeError):
    """Raised when all simulator slots remain occupied for thirty seconds."""


@dataclass
class SimRun:
    """The measurements and execution metadata from one Aer simulation."""

    counts: dict[str, int]
    transpiled: QuantumCircuit
    sim_time_ms: float
    shots: int


def run_circuit(
    qc: QuantumCircuit, shots: int = 1024, seed: int | None = None
) -> SimRun:
    """Transpile for Aer and run. qc must have exactly one classical register."""
    if len(qc.cregs) != 1:
        raise ValueError("run_circuit expects exactly one classical register")
    if not _GATE.acquire(timeout=30):
        raise SimulatorBusyError("Simulator busy, try again")
    try:
        t0 = time.perf_counter()
        tqc = transpile(qc, _SIM, optimization_level=0)
        result = _SIM.run(tqc, shots=shots, seed_simulator=seed).result()
        elapsed = (time.perf_counter() - t0) * 1000
    finally:
        _GATE.release()
    return SimRun(
        counts=dict(result.get_counts()),
        transpiled=tqc,
        sim_time_ms=elapsed,
        shots=shots,
    )
