"""Classical baselines for the public-key breach test (the non-quantum adversary).

Like the quantum adversary in ``shor``, these baselines are **blind**: they see
only the public modulus N (the public exponent and ciphertext are not needed to
factor N), never p, q, phi or d, and this module never imports the victim-side
``minirsa`` module.

1. **Trial division** factors N directly and counts the divisions it performs.
2. **Classical order finding** solves the *same* sub-problem as Shor's circuit:
   it computes a, a^2, a^3, ... mod N until the value returns to 1, which gives
   the period r, then applies the identical gcd post-processing. It counts the
   modular multiplications. It tries bases in the same order as the quantum
   attack (``shor.choose_bases`` with the same seed), so the two are compared
   on the same bases.

``comparison_record`` sets one Shor run beside both baselines. The fair metric
is resource count (circuit runs and qubits versus divisions and
multiplications), not wall-clock time: at these toy sizes the classical code
finishes in microseconds while the classical *simulation* of the quantum
circuit takes milliseconds to seconds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from math import gcd, isqrt

from qbreak.rsa.shor import (
    CONSTRUCTION_KEYS,
    ShorResult,
    choose_bases,
    factors_from_period,
    qubit_counts,
)

WALLCLOCK_NOTE = (
    "At these toy moduli the classical baselines finish in microseconds, while simulating the "
    "quantum circuit on a classical computer takes milliseconds to seconds, so the simulator is "
    "slower in wall-clock time. The fair comparison is resource count: Shor circuit runs and "
    "qubits versus classical trial divisions and modular multiplications. No quantum speed "
    "advantage is claimed (the track does not require one)."
)


@dataclass
class TrialDivisionResult:
    """Outcome of factoring N by trial division."""

    n: int
    factors: tuple[int, int] | None
    divisions: int
    wallclock_ms: float


@dataclass
class OrderFindingAttempt:
    """One base examined by classical order finding."""

    a: int
    period: int
    multiplications: int
    ok: bool
    reason: str


@dataclass
class OrderFindingResult:
    """Outcome of factoring N by classical order finding."""

    n: int
    factors: tuple[int, int] | None
    a: int | None
    period: int | None
    multiplications: int  # total over every base tried
    bases_tried: int
    attempts: list[OrderFindingAttempt] = field(default_factory=list)
    wallclock_ms: float = 0.0


def trial_division(n: int) -> TrialDivisionResult:
    """Factor n by dividing by 2, then 3, 5, 7, ... up to sqrt(n); count divisions."""
    if n < 4:
        raise ValueError("n must be a composite integer >= 4")
    t0 = time.perf_counter()
    divisions = 0
    factors = None
    for divisor in [2, *range(3, isqrt(n) + 1, 2)]:
        divisions += 1
        if n % divisor == 0:
            factors = (divisor, n // divisor)
            break
    return TrialDivisionResult(n, factors, divisions, (time.perf_counter() - t0) * 1000)


def find_order(a: int, n: int) -> tuple[int, int]:
    """Smallest r >= 1 with a^r ≡ 1 (mod n), by repeated multiplication.

    Returns (r, multiplications); reaching a^r takes r − 1 multiplications by a.
    """
    if gcd(a, n) != 1:
        raise ValueError(f"a = {a} must be coprime to n = {n}")
    value, r = a % n, 1
    while value != 1:
        value = (value * a) % n
        r += 1
    return r, r - 1


def classical_order_finding(
    n: int, a: int | None = None, seed: int | None = None, max_bases: int | None = None
) -> OrderFindingResult:
    """Factor n by finding the order of a classically, base by base.

    Bases come from ``shor.choose_bases(n, seed)`` (``a`` first when given), so
    with the same seed this tries the same bases as the quantum attack. For
    each base: find r, then accept only if r is even and a^(r/2) ≢ −1 (mod n),
    and the gcds split n, exactly as in Shor's post-processing.
    """
    t0 = time.perf_counter()
    bases = choose_bases(n, seed)
    if a is not None and a in bases:
        bases = [a] + [b for b in bases if b != a]
    if max_bases is not None:
        bases = bases[:max_bases]
    attempts: list[OrderFindingAttempt] = []
    total = 0
    for base in bases:
        r, mults = find_order(base, n)
        total += mults
        factors = factors_from_period(base, r, n)
        if factors is not None:
            reason = f"{base}^{r} mod {n} = 1; r even; {base}^{r // 2} mod {n} = {pow(base, r // 2, n)} ≠ {n - 1}"
        elif r % 2:
            reason = f"{base}^{r} mod {n} = 1; r is odd"
        else:
            reason = f"{base}^{r} mod {n} = 1; r even; a^(r/2) ≡ −1 mod N"
        attempts.append(OrderFindingAttempt(base, r, mults, factors is not None, reason))
        if factors is not None:
            return OrderFindingResult(
                n, factors, base, r, total, len(attempts), attempts, (time.perf_counter() - t0) * 1000
            )
    return OrderFindingResult(
        n, None, None, None, total, len(attempts), attempts, (time.perf_counter() - t0) * 1000
    )


def construction_key(construction: str) -> str:
    """API key (swap / permutation / iterative) for a full construction name."""
    return next((key for key, name in CONSTRUCTION_KEYS.items() if name == construction), construction)


def comparison_record(result: ShorResult, shots: int, seed: int | None = None) -> dict:
    """Quantum-vs-classical record for one Shor run, from public data only.

    Shape: ``{quantum: {construction, circuit_runs, qubits, depth, ...},
    classical: {trial_divisions, order_finding_mults, ...}, wallclock_note}``.
    The classical order finding uses the same seed and starting base as the
    Shor run.
    """
    first_base = next((att.a for att in result.attempts if att.measured), result.a)
    trial = trial_division(result.n)
    order = classical_order_finding(result.n, a=first_base, seed=seed)
    return {
        "quantum": {
            "construction": construction_key(result.construction),
            "construction_name": result.construction,
            "circuit_runs": result.circuit_runs,
            "shots_per_run": shots,
            "qubits": result.circuit.num_qubits,
            "depth": result.transpiled.depth() or 0,
            "qubits_by_construction": qubit_counts(result.n),
            "factors_found": result.factors is not None,
        },
        "classical": {
            "trial_divisions": trial.divisions,
            "order_finding_mults": order.multiplications,
            "order_finding_bases_tried": order.bases_tried,
            "factors_found": trial.factors is not None and order.factors is not None,
        },
        "wallclock_ms": {
            "quantum_simulation": round(result.sim_time_ms, 3),
            "trial_division": round(trial.wallclock_ms, 4),
            "order_finding": round(order.wallclock_ms, 4),
        },
        "wallclock_note": WALLCLOCK_NOTE,
    }
