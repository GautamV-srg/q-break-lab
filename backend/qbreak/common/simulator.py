"""The single door to Qiskit Aer, with a process-wide concurrency limit.

Every simulation in Q-Break (attacks, quantum counting, noise experiments) goes through
`run_circuit`, so the `QBREAK_MAX_CONCURRENT_SIMS` semaphore bounds memory use.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

_SIM = AerSimulator()
_GATE = threading.Semaphore(int(os.getenv("QBREAK_MAX_CONCURRENT_SIMS", "1")))

NOISE_BASIS: tuple[str, ...] = ("u", "cx")
"""Noisy runs are transpiled to this basis so every gate picks up its error."""


class SimulatorBusyError(RuntimeError):
    """Raised when all simulator slots remain occupied for thirty seconds."""


@dataclass
class SimRun:
    """The measurements and execution metadata from one Aer simulation."""

    counts: dict[str, int]
    transpiled: QuantumCircuit
    sim_time_ms: float
    shots: int


@lru_cache(maxsize=32)
def depolarizing_noise_model(p: float) -> NoiseModel:
    """Depolarising noise: error p on every two-qubit gate (cx), p/10 on one-qubit gates (u).

    The 10:1 ratio mirrors today's hardware, where two-qubit gates dominate the error.
    """
    if not 0 <= p <= 1:
        raise ValueError("noise probability must be between 0 and 1")
    model = NoiseModel(basis_gates=list(NOISE_BASIS))
    if p > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p / 10, 1), ["u"])
        model.add_all_qubit_quantum_error(depolarizing_error(p, 2), ["cx"])
    return model


def run_circuit(
    qc: QuantumCircuit,
    shots: int = 1024,
    seed: int | None = None,
    noise_p: float | None = None,
    backend: object | None = None,
) -> SimRun:
    """Transpile for Aer and run. qc must have exactly one classical register.

    noise_p: run under `depolarizing_noise_model(noise_p)`, transpiled to u + cx.
    backend: a fake IBM backend (qiskit_ibm_runtime.fake_provider); the circuit is
        transpiled to its coupling map and basis and run with its calibrated noise.
    Without either the run is ideal, as before.
    """
    if len(qc.cregs) != 1:
        raise ValueError("run_circuit expects exactly one classical register")
    if not _GATE.acquire(timeout=30):
        raise SimulatorBusyError("Simulator busy, try again")
    try:
        t0 = time.perf_counter()
        if backend is not None:
            sim = AerSimulator.from_backend(backend)
            tqc = transpile(qc, backend, optimization_level=1, seed_transpiler=seed)
        elif noise_p is not None:
            model = depolarizing_noise_model(float(noise_p))
            sim = AerSimulator(noise_model=model)
            tqc = transpile(qc, basis_gates=list(NOISE_BASIS), optimization_level=1, seed_transpiler=seed)
        else:
            sim = _SIM
            tqc = transpile(qc, _SIM, optimization_level=0)
        result = sim.run(tqc, shots=shots, seed_simulator=seed).result()
        elapsed = (time.perf_counter() - t0) * 1000
    finally:
        _GATE.release()
    return SimRun(
        counts=dict(result.get_counts()),
        transpiled=tqc,
        sim_time_ms=elapsed,
        shots=shots,
    )
