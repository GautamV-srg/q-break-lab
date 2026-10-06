"""Classical baseline for the symmetric breach test: brute-force key search.

It solves exactly the same problem as the Grover attack, under the same attack condition
and from the same intercepted data (ciphertext, plus known plaintext where the condition
has some). It never receives the key. It walks the keyspace in order, testing every key
against the condition's full constraint, and counts how many keys it had to try.

The fair comparison with Grover is the number of queries: one classical "try" evaluates
the cipher under one candidate key, one Grover oracle call evaluates it under all keys in
superposition. Classically a single matching key takes (N + 1) / 2 tries on average
(N = 2^k); Grover needs about pi/4 * sqrt(N) oracle calls. Wall-clock time is NOT a fair
comparison here: simulating the quantum circuit on a classical computer is far slower
than the brute force it is compared with.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from qbreak.aes.conditions import AttackSpec, full_spec

WALLCLOCK_NOTE = (
    "Wall-clock time is not the fair comparison: at these toy sizes the classical brute "
    "force finishes in milliseconds, while simulating the quantum circuit on a classical "
    "computer takes far longer. The meaningful metric is the number of queries — Grover "
    "oracle calls versus classical cipher evaluations — where Grover needs about √N "
    "against about N/2. No quantum speed advantage is claimed for these miniature sizes."
)


@dataclass
class ClassicalResult:
    """What the classical brute force found and how much work it took."""

    key_bits: int
    condition: str
    candidates: list[int]
    cipher_evaluations: int
    """Keys tried (in order 0, 1, 2, ...) until the first one satisfying the condition."""
    exhaustive_evaluations: int
    """Keys tried to list every candidate: the whole keyspace, 2^k."""
    block_evaluations: int
    """Single-block cipher evaluations performed during the full sweep (early exit per key)."""
    expected_tries: float
    """Average tries to the first candidate for a random key: (N + 1) / (M + 1)."""
    wall_ms: float


def classical_key_search(
    known_plain: list[int] | None,
    cipher: list[int],
    key_bits: int,
    condition: str = "known_beginning",
) -> ClassicalResult:
    """Brute-force every key against the condition's full constraint (blind: no key input)."""
    spec = full_spec(condition, known_plain, cipher, key_bits)
    return search_spec(spec)


def search_spec(spec: AttackSpec) -> ClassicalResult:
    """Brute-force every key against an AttackSpec, counting the work done."""
    t0 = time.perf_counter()
    n_keys = 1 << spec.key_bits
    candidates: list[int] = []
    first_hit: int | None = None
    blocks = 0
    for key in range(n_keys):
        ok = False
        for group in spec.groups:
            group_ok = True
            for check in group:
                blocks += 1
                if not check.holds(key, spec.key_bits):
                    group_ok = False
                    break
            if group_ok:
                ok = True
                break
        if ok:
            candidates.append(key)
            if first_hit is None:
                first_hit = key + 1
    m = len(candidates)
    return ClassicalResult(
        key_bits=spec.key_bits,
        condition=spec.condition,
        candidates=candidates,
        cipher_evaluations=first_hit if first_hit is not None else n_keys,
        exhaustive_evaluations=n_keys,
        block_evaluations=blocks,
        expected_tries=(n_keys + 1) / (m + 1),
        wall_ms=(time.perf_counter() - t0) * 1000,
    )


def comparison_record(grover_result, classical: ClassicalResult) -> dict:
    """The per-run 'Quantum vs classical' record for the Breach Report and charts.

    `grover_result` is a `qbreak.aes.grover.GroverResult` from the same intercepted data.
    """
    counting = grover_result.counting
    grover_calls = sum(a.iterations for a in grover_result.attempts)
    counting_calls = counting.controlled_grover_calls if counting is not None else 0
    n_keys = 1 << classical.key_bits
    m = max(1, len(classical.candidates))
    return {
        "quantum": {
            "oracle_calls": grover_calls + counting_calls,
            "grover_iterations": grover_result.iterations,
            "grover_oracle_calls": grover_calls,
            "counting_oracle_calls": counting_calls,
            "circuit_runs": len(grover_result.attempts) + (1 if counting is not None else 0),
            "qubits": grover_result.circuit.num_qubits,
            "depth": grover_result.circuit.depth() or 0,
            "transpiled_depth": grover_result.transpiled.depth() or 0,
        },
        "classical": {
            "cipher_evaluations": classical.cipher_evaluations,
            "expected_tries": classical.expected_tries,
            "exhaustive_evaluations": classical.exhaustive_evaluations,
            "block_evaluations": classical.block_evaluations,
            "candidates": len(classical.candidates),
        },
        "theory": {
            "search_space": n_keys,
            "classical_average_tries": (n_keys + 1) / (m + 1),
            "grover_optimal_iterations": math.pi / 4 * math.sqrt(n_keys / m),
        },
        "quantum_wallclock_ms": grover_result.sim_time_ms,
        "classical_wallclock_ms": classical.wall_ms,
        "wallclock_note": WALLCLOCK_NOTE,
        "oracle_calls_note": "Oracle calls are counted per circuit execution (one shot); "
        "shots repeat the circuit only to draw the histogram.",
    }
