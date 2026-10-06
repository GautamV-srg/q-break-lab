"""Shor's period-finding attack on MiniRSA: the quantum adversary.

The adversary knows only the public modulus N (plus e and the ciphertext,
which it does not need for factoring). It never sees p, q, phi or d, and this
module never imports the victim-side ``minirsa`` module.

How the attack works, in plain English
--------------------------------------
1. Pick a base a with gcd(a, N) = 1. The function x -> a^x mod N repeats with
   some period r (the "order" of a): a^r mod N = 1.
2. The circuit has two registers:
   - the **counting register** (t qubits) holds every exponent x = 0 .. 2^t - 1
     at once, thanks to a Hadamard on each qubit;
   - the **work register** starts at |1> and, controlled by the counting
     register, gets multiplied by a^x mod N. Counting qubit j controls
     "multiply by a^(2^j) mod N", so together they compute a^x mod N.
3. Because a^x mod N repeats every r steps, the counting register now carries
   a hidden frequency of 1/r. The **inverse quantum Fourier transform** turns
   that frequency into a measurable number: the result y is (close to)
   s * 2^t / r for a random s, so the **phase** y / 2^t is close to s / r.
4. Classical post-processing: continued fractions turn the phase into the
   fraction s / r, whose denominator is a candidate period r. We check it
   (a^r mod N must be 1), need r even and a^(r/2) not equal to -1 mod N, then
   gcd(a^(r/2) - 1, N) and gcd(a^(r/2) + 1, N) are the prime factors.
5. With the factors, the private key is rebuilt with ordinary public maths.

Honesty note on the circuit construction
----------------------------------------
- ``"textbook-swaps"`` (N = 15 only): the hand-built Qiskit-textbook circuit
  in which multiplication by a mod 15 is a rotation of the 4 work bits, plus a
  NOT on every bit for some bases.
- ``"permutation-unitary"`` (any supported N): each controlled block embeds
  the permutation x -> b*x mod N with b = a^(2^j) mod N. That permutation is
  computed classically when the circuit is built. This is the standard
  approach in small textbook demonstrations; a full-scale Shor would instead
  need reversible modular-arithmetic circuits built from elementary gates.
- ``"iterative-phase-estimation"`` (any supported N): the semiclassical
  (Griffiths-Niu) version of phase estimation. A **single** counting qubit is
  reset and reused for t rounds; each round applies one controlled U^(2^k),
  then phase corrections conditioned on the bits already measured, then a
  Hadamard and a mid-circuit measurement. It replaces the t-qubit counting
  register and the inverse QFT, and yields the same output distribution.
  Its multiplication blocks are the textbook swaps at N = 15 and the
  classically computed (disclosed) permutation blocks for every other N.
In every case the period itself is *not* computed classically: it is read
out of the quantum measurement.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, gcd, log2

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import Gate
from qiskit.circuit.library import UnitaryGate

from qbreak.common.simulator import run_circuit

# Moduli whose circuits are implemented, tested and benchmarked.
SHOR_SUPPORTED_N: tuple[int, ...] = (15, 21, 33, 35, 55, 77)

TEXTBOOK = "textbook-swaps"
PERMUTATION = "permutation-unitary"
ITERATIVE = "iterative-phase-estimation"
_CONSTRUCTIONS = (TEXTBOOK, PERMUTATION, ITERATIVE)

# Short API names for each construction ("auto" = textbook at N = 15, else permutation).
CONSTRUCTION_KEYS: dict[str, str] = {
    "swap": TEXTBOOK,
    "permutation": PERMUTATION,
    "iterative": ITERATIVE,
}

_MAX_ATTEMPTS_PER_BASE = 16

REGISTER_ROLES: dict[str, str] = {
    "count": (
        "Exponent register: superposition of x = 0..2^t−1; after IQFT its measurement encodes s/r"
    ),
    "work": "Holds a^x mod N, starts at |1⟩",
}

ITERATIVE_REGISTER_ROLES: dict[str, str] = {
    "count": (
        "Single counting qubit, reset and reused for each of the t rounds; each round measures one "
        "bit of y, with phase corrections conditioned on the bits already measured (no IQFT)"
    ),
    "work": "Holds a^x mod N, starts at |1⟩",
}


@dataclass
class ShorAttempt:
    """One measured outcome examined by the classical post-processing."""

    a: int
    measured: str  # bitstring of counting register
    y: int
    phase: float  # y / 2^t
    fraction: str  # e.g. "1/4"
    r_candidate: int | None
    ok: bool
    reason: str  # human-readable: why accepted / rejected


@dataclass
class ShorResult:
    """Everything the breach report needs about one Shor attack run."""

    n: int
    a: int  # base that succeeded (or last tried)
    period: int | None
    factors: tuple[int, int] | None
    counts: dict[str, int]  # counts for the circuit of the successful/last base
    n_count: int  # bits of phase precision t (= counting qubits for the register constructions)
    n_work: int  # work qubits
    attempts: list[ShorAttempt]
    circuit: QuantumCircuit
    transpiled: QuantumCircuit
    sim_time_ms: float  # total simulation time over every base tried
    construction: str  # "textbook-swaps", "permutation-unitary" or "iterative-phase-estimation"
    explain_circuits: list[tuple[str, QuantumCircuit]]
    register_roles: dict[str, str]
    counting_qubits: int = 0  # physical counting qubits: t, or 1 for the iterative construction
    multiplier_blocks: str = ""  # how controlled U^(2^k) is built: textbook-swaps / permutation-unitary
    circuit_runs: int = 0  # circuits simulated (one per base tried)


# ---------------------------------------------------------------------------
# Register sizes
# ---------------------------------------------------------------------------


def work_qubits(n: int) -> int:
    """Number of work qubits: enough to hold any value 0..N-1."""
    return ceil(log2(n))


def default_count_qubits(n: int) -> int:
    """Default counting-register size t = 2 * n_work (enough precision for s/r)."""
    return 2 * work_qubits(n)


def qubit_counts(n: int) -> dict[str, int]:
    """Total qubits for each construction family at modulus n (t = 2 * n_work).

    The 2n-register circuit needs t counting + n_work work qubits; the
    iterative circuit needs 1 counting + n_work work qubits.
    """
    n_work = work_qubits(n)
    return {"register_2n": 3 * n_work, "iterative": 1 + n_work}


# ---------------------------------------------------------------------------
# Circuit building blocks
# ---------------------------------------------------------------------------


def inverse_qft(t: int) -> QuantumCircuit:
    """Inverse quantum Fourier transform on t qubits, written by hand.

    It matches the convention "counting qubit j controls U^(2^j)", so after
    it the counting register reads y ≈ s · 2^t / r (qubit 0 = least significant).
    """
    qc = QuantumCircuit(t, name="IQFT")
    for q in range(t // 2):
        qc.swap(q, t - q - 1)
    for j in range(t):
        for m in range(j):
            qc.cp(-np.pi / float(2 ** (j - m)), m, j)
        qc.h(j)
    return qc


def amod15(a: int, power: int) -> Gate:
    """Controlled 'multiply by a^power mod 15' (Qiskit textbook construction).

    Multiplication by 2 mod 15 is a 1-bit left rotation of the 4 work bits,
    by 4 a 2-bit rotation, by 8 a right rotation; 7, 11 and 13 are those
    rotations followed by a NOT on every bit (since 15 - x = NOT x on 4 bits).
    Every allowed a satisfies a^4 ≡ 1 mod 15, so only power % 4 matters.

    Returns a 5-qubit controlled gate: append with ``[count[j]] + list(work)``.
    """
    if a not in (2, 4, 7, 8, 11, 13):
        raise ValueError("a must be 2,4,7,8,11,13")
    U = QuantumCircuit(4)
    for _ in range(power % 4):  # every valid a has order dividing 4 mod 15
        if a in (2, 13):
            U.swap(2, 3)
            U.swap(1, 2)
            U.swap(0, 1)
        if a in (7, 8):
            U.swap(0, 1)
            U.swap(1, 2)
            U.swap(2, 3)
        if a in (4, 11):
            U.swap(1, 3)
            U.swap(0, 2)
        if a in (7, 11, 13):
            for q in range(4):
                U.x(q)
    gate = U.to_gate(label=f"{a}^{power} mod 15")
    return gate.control(1)  # append with [count[j]] + list(work)


def permutation_matrix(b: int, n: int, n_work: int) -> np.ndarray:
    """Matrix of 'if control then x -> b·x mod n' on n_work + 1 qubits.

    The control is the highest qubit. Values x >= n (which never occur when
    the work register starts at |1⟩) and the control-off half are left
    unchanged, so the matrix is a permutation and therefore unitary.
    """
    if gcd(b, n) != 1:
        raise ValueError(f"b = {b} must be coprime to n = {n}")
    dim = 2 ** (n_work + 1)
    M = np.zeros((dim, dim))
    for idx in range(dim):
        ctrl, x = idx >> n_work, idx & ((1 << n_work) - 1)
        out = (ctrl << n_work) | ((b * x) % n) if (ctrl and x < n) else idx
        M[out, idx] = 1
    return M


def controlled_mult_gate(b: int, n: int, n_work: int, label: str) -> UnitaryGate:
    """Controlled multiplication by b mod n as a permutation UnitaryGate.

    Honesty note: this block embeds the multiplication-by-b permutation,
    computed classically when the circuit is built (b = a^(2^j) mod n by
    repeated squaring). That is standard for small demonstrations; a
    full-scale Shor would need reversible modular-arithmetic circuits.

    Append with ``list(work) + [count[j]]`` (control last = highest index).
    """
    return UnitaryGate(permutation_matrix(b, n, n_work), label=label)


def resolve_construction(n: int, construction: str) -> str:
    """Map "auto", an API key (swap / permutation / iterative) or a full name to a full name."""
    construction = CONSTRUCTION_KEYS.get(construction, construction)
    if construction == "auto":
        return TEXTBOOK if n == 15 else PERMUTATION
    if construction not in _CONSTRUCTIONS:
        raise ValueError(f"Unknown construction {construction!r}")
    if construction == TEXTBOOK and n != 15:
        raise ValueError("The textbook-swaps construction exists only for N = 15")
    return construction


_resolve_construction = resolve_construction


def multiplier_blocks(n: int, construction: str) -> str:
    """How the controlled U^(2^k) blocks are built for a resolved construction.

    The iterative construction reuses the hand-built swaps at N = 15 and the
    disclosed, classically computed permutation blocks everywhere else.
    """
    if construction == ITERATIVE:
        return TEXTBOOK if n == 15 else PERMUTATION
    return construction


def _controlled_power_gate(a: int, n: int, n_work: int, j: int, construction: str) -> Gate:
    """Controlled U^(2^j) for the chosen construction, labelled for drawings."""
    label = f"U^(2^{j})"
    if construction == TEXTBOOK:
        gate = amod15(a, 2**j)
        gate.label = label
        return gate
    return controlled_mult_gate(pow(a, 2**j, n), n, n_work, label)


def _append_controlled_power(
    qc: QuantumCircuit, gate: Gate, control, work, construction: str
) -> None:
    if construction == TEXTBOOK:
        qc.append(gate, [control] + list(work))
    else:
        qc.append(gate, list(work) + [control])


def build_period_finding_circuit(
    a: int, n: int, n_count: int | None = None, construction: str = "auto"
) -> QuantumCircuit:
    """Build the full period-finding circuit for base a modulo n.

    Layout: counting register ``count`` (t qubits, Hadamards), work register
    ``work`` (initialised to |1⟩), one controlled U^(2^j) per counting qubit j,
    then the inverse QFT on ``count`` and measurement count[i] -> c[i].

    ``construction`` is "textbook-swaps" (N = 15 only), "permutation-unitary",
    or "auto" (textbook for N = 15, permutation otherwise).
    """
    if not 2 <= a <= n - 2:
        raise ValueError(f"a = {a} must satisfy 2 <= a <= N - 2")
    if gcd(a, n) != 1:
        raise ValueError(f"gcd({a}, {n}) > 1: that would factor N classically")
    construction = _resolve_construction(n, construction)
    if construction == ITERATIVE:
        return build_iterative_circuit(a, n, n_count)
    n_work = work_qubits(n)
    t = n_count if n_count is not None else 2 * n_work

    count = QuantumRegister(t, "count")
    work = QuantumRegister(n_work, "work")
    c = ClassicalRegister(t, "c")
    qc = QuantumCircuit(count, work, c, name=f"Shor period finding a={a} N={n}")

    qc.h(count)
    qc.x(work[0])  # work register starts at |1⟩ (qubit 0 is the LSB)
    for j in range(t):
        gate = _controlled_power_gate(a, n, n_work, j, construction)
        _append_controlled_power(qc, gate, count[j], work, construction)
    qc.append(inverse_qft(t).to_gate(label="IQFT"), count)
    qc.measure(count, c)
    return qc


def build_iterative_circuit(a: int, n: int, n_count: int | None = None) -> QuantumCircuit:
    """Iterative (semiclassical) period finding with a single counting qubit.

    Registers: ``count`` (1 qubit, reused), ``work`` (n_work qubits, starts at
    |1⟩) and the classical register ``c`` (t bits). Round k = t−1 … 0 measures
    bit y_b with b = t−1−k (least significant bit first):

    1. reset the counting qubit (after the first round) and apply H;
    2. apply controlled U^(2^k); the eigenphase kicked back is 2π·y/2^(b+1);
    3. for every bit y_i (i < b) already measured, apply P(−π/2^(b−i)) if
       y_i = 1, cancelling the lower bits' contribution to that phase;
    4. apply H and measure into c[b].

    This is the inverse QFT done one qubit at a time with classical
    feed-forward (Griffiths & Niu, 1996), so c reads the same y ≈ s·2^t/r as
    the 2n-register circuit, with the same distribution, on 1 + n_work qubits.
    """
    if not 2 <= a <= n - 2:
        raise ValueError(f"a = {a} must satisfy 2 <= a <= N - 2")
    if gcd(a, n) != 1:
        raise ValueError(f"gcd({a}, {n}) > 1: that would factor N classically")
    blocks = multiplier_blocks(n, ITERATIVE)
    n_work = work_qubits(n)
    t = n_count if n_count is not None else 2 * n_work

    count = QuantumRegister(1, "count")
    work = QuantumRegister(n_work, "work")
    c = ClassicalRegister(t, "c")
    qc = QuantumCircuit(count, work, c, name=f"Iterative Shor period finding a={a} N={n}")

    qc.x(work[0])  # work register starts at |1⟩ (qubit 0 is the LSB)
    for k in reversed(range(t)):
        _append_iterative_round(qc, a, n, n_work, t, k, blocks)
    return qc


def _append_iterative_round(
    qc: QuantumCircuit, a: int, n: int, n_work: int, t: int, k: int, blocks: str
) -> None:
    """One round of iterative phase estimation: controlled U^(2^k), measure y bit t−1−k."""
    count, work, c = qc.qregs[0][0], qc.qregs[1], qc.cregs[0]
    bit = t - 1 - k
    if bit:
        qc.reset(count)
    qc.h(count)
    gate = _controlled_power_gate(a, n, n_work, k, blocks)
    _append_controlled_power(qc, gate, count, work, blocks)
    for i in range(bit):
        with qc.if_test((c[i], 1)):
            qc.p(-np.pi / float(2 ** (bit - i)), count)
    qc.h(count)
    qc.measure(count, c[bit])


def _shield_unitaries(qc: QuantumCircuit) -> QuantumCircuit:
    """Wrap each permutation UnitaryGate one level deep.

    The evidence builder draws explainer circuits after one ``decompose()``;
    without the wrapper that would synthesise a 2^(n_work+1)-dimensional
    permutation into thousands of gates (about a minute at N = 77). Wrapped,
    it is drawn as the single labelled, disclosed block it is.
    """
    out = qc.copy_empty_like()
    for inst in qc.data:
        op = inst.operation
        if op.name == "unitary":
            inner = QuantumCircuit(op.num_qubits, name=op.label)
            inner.append(op, range(op.num_qubits))
            op = inner.to_gate(label=op.label)
        out.append(op, inst.qubits, inst.clbits)
    return out


def _explain_circuits(
    a: int, n: int, t: int, construction: str
) -> list[tuple[str, QuantumCircuit]]:
    """Small circuits for the "Pop the Hood" explainer."""
    blocks = multiplier_blocks(n, construction)
    n_work = work_qubits(n)
    ctrl = QuantumRegister(1, "count0")
    work = QuantumRegister(n_work, "work")
    block = QuantumCircuit(ctrl, work, name="Controlled U^(2^0)")
    gate = _controlled_power_gate(a, n, n_work, 0, blocks)
    _append_controlled_power(block, gate, ctrl[0], work, blocks)
    if blocks == TEXTBOOK:
        block = block.decompose()  # show the controlled swaps / NOTs
    else:
        block = _shield_unitaries(block)
    if construction != ITERATIVE:
        return [("Controlled U^(2^0)", block), ("Inverse QFT", inverse_qft(t))]
    # The third round (y bit 2) shows both conditioned phase corrections.
    demo = QuantumCircuit(
        QuantumRegister(1, "count"), QuantumRegister(n_work, "work"), ClassicalRegister(3, "c")
    )
    _append_iterative_round(demo, a, n, n_work, 3, 0, blocks)
    return [
        ("Controlled U^(2^0)", block),
        ("One iterative round (measures y bit 2)", _shield_unitaries(demo)),
    ]


# ---------------------------------------------------------------------------
# Classical pre- and post-processing
# ---------------------------------------------------------------------------


def choose_bases(n: int, seed: int | None = None) -> list[int]:
    """All bases 2 <= a <= n - 2 coprime to n, shuffled with random.Random(seed).

    Bases sharing a factor with n are excluded: they would factor n by
    luck, classically, which is not a quantum result. For N = 15 with no
    seed, the classic example a = 7 (order 4) comes first.
    """
    bases = [a for a in range(2, n - 1) if gcd(a, n) == 1]
    random.Random(seed).shuffle(bases)
    if n == 15 and seed is None:
        bases.remove(7)
        bases.insert(0, 7)
    return bases


def candidate_periods(counts: dict[str, int], n_count: int, n: int, a: int) -> list[ShorAttempt]:
    """Turn measured counting-register bitstrings into checked period candidates.

    For each bitstring (most frequent first, at most 16): y -> phase y/2^t ->
    closest fraction s/r with r <= N (continued fractions) -> test r, 2r, 3r
    until a^r mod N = 1 -> accept only if r is even and a^(r/2) is not ±1
    mod N. Every attempt carries a plain-English reason.
    """
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    attempts: list[ShorAttempt] = []
    for bitstring, _ in ordered[:_MAX_ATTEMPTS_PER_BASE]:
        y = int(bitstring, 2)
        phase = y / 2**n_count
        if y == 0:
            attempts.append(
                ShorAttempt(
                    a,
                    bitstring,
                    y,
                    phase,
                    "0/1",
                    None,
                    False,
                    "phase 0 carries no period information",
                )
            )
            continue
        frac = Fraction(y, 2**n_count).limit_denominator(n)
        fraction = f"{frac.numerator}/{frac.denominator}"
        r0 = frac.denominator
        r = next((k * r0 for k in (1, 2, 3) if pow(a, k * r0, n) == 1), None)
        if r is None:
            reason = (
                f"a^r mod N ≠ 1: {a}^{r0} mod {n} = {pow(a, r0, n)} "
                f"(also tried 2r = {2 * r0}, 3r = {3 * r0})"
            )
            attempts.append(ShorAttempt(a, bitstring, y, phase, fraction, None, False, reason))
            continue
        how = (
            f"{a}^{r} mod {n} = 1"
            if r == r0
            else (f"denominator {r0} fails, multiple {r} works: {a}^{r} mod {n} = 1")
        )
        if r % 2 == 1:
            attempts.append(
                ShorAttempt(a, bitstring, y, phase, fraction, r, False, f"{how}; r is odd")
            )
            continue
        half = pow(a, r // 2, n)
        if half == n - 1:
            reason = f"{how}; r even; a^(r/2) ≡ −1 mod N ({a}^{r // 2} mod {n} = {half})"
            attempts.append(ShorAttempt(a, bitstring, y, phase, fraction, r, False, reason))
            continue
        if half == 1:
            reason = (
                f"{how}; r even; but {a}^{r // 2} mod {n} = 1, "
                "so r is a multiple of the true period"
            )
            attempts.append(ShorAttempt(a, bitstring, y, phase, fraction, r, False, reason))
            continue
        reason = f"{how}; r even; {a}^{r // 2} mod {n} = {half} ≠ {n - 1}"
        attempts.append(ShorAttempt(a, bitstring, y, phase, fraction, r, True, reason))
    return attempts


def shot_success_probability(counts: dict[str, int], n_count: int, n: int, a: int) -> float:
    """Fraction of shots whose outcome *on its own* yields the factors of n.

    Every distinct outcome is post-processed exactly as in the attack
    (continued fractions → period checks → gcd); no secret is consulted.
    """
    shots = sum(counts.values())
    if not shots:
        return 0.0
    good = 0
    for bitstring, count in counts.items():
        att = candidate_periods({bitstring: count}, n_count, n, a)[0]
        if att.ok and att.r_candidate and factors_from_period(a, att.r_candidate, n):
            good += count
    return good / shots


def factors_from_period(a: int, r: int, n: int) -> tuple[int, int] | None:
    """Factors of n from an even period r of a: gcd(a^(r/2) ∓ 1, n).

    Returns the sorted pair (p, q) with 1 < p <= q < n and p·q = n, or None.
    """
    if r <= 0 or r % 2:
        return None
    half = pow(a, r // 2, n)
    for g in (gcd(half - 1, n), gcd(half + 1, n)):
        if 1 < g < n and n % g == 0:
            p, q = sorted((g, n // g))
            return (p, q)
    return None


def run_shor_attack(
    n: int,
    a: int | None = None,
    shots: int = 1024,
    seed: int | None = None,
    max_bases: int = 4,
    construction: str = "auto",
    noise_p: float | None = None,
    backend: object | None = None,
) -> ShorResult:
    """Factor n with Shor's period finding, simulated on Aer.

    Tries up to ``max_bases`` bases (the given ``a`` first, otherwise
    ``choose_bases``). For each: build the circuit, simulate it, post-process
    the measurements, and stop at the first accepted period that yields
    factors. If every base fails, returns period=None, factors=None with all
    attempts listed (it does not raise).

    If the caller passes an ``a`` with gcd(a, n) > 1, it is recorded as a
    skipped attempt (that would be a classical lucky factor, not a quantum
    result) and the attack continues with other bases.

    ``construction`` is "auto", "swap" / "textbook-swaps" (N = 15 only),
    "permutation" / "permutation-unitary" or "iterative" /
    "iterative-phase-estimation". ``noise_p`` (depolarising rate) or ``backend``
    (a fake IBM device) runs the circuits under noise through the shared
    simulator helper; both default to an ideal run.
    """
    if n not in SHOR_SUPPORTED_N:
        supported = ", ".join(str(k) for k in SHOR_SUPPORTED_N)
        raise ValueError(f"N = {n} is not supported by the Shor attack; supported: {supported}")
    if max_bases < 1:
        raise ValueError("max_bases must be >= 1")

    attempts: list[ShorAttempt] = []
    bases = choose_bases(n, seed)
    if a is not None:
        if not 2 <= a <= n - 2:
            raise ValueError(f"a = {a} must satisfy 2 <= a <= N - 2")
        if gcd(a, n) > 1:
            attempts.append(
                ShorAttempt(
                    a,
                    "",
                    0,
                    0.0,
                    "",
                    None,
                    False,
                    "skipped: gcd(a, N) > 1 would factor classically (not a quantum result)",
                )
            )
        else:
            bases = [a] + [b for b in bases if b != a]

    construction = _resolve_construction(n, construction)
    n_work = work_qubits(n)
    t = 2 * n_work
    total_ms = 0.0
    result: ShorResult | None = None
    roles = ITERATIVE_REGISTER_ROLES if construction == ITERATIVE else REGISTER_ROLES

    for i, base in enumerate(bases[:max_bases]):
        qc = build_period_finding_circuit(base, n, t, construction)
        run = run_circuit(
            qc, shots=shots, seed=None if seed is None else seed + i, noise_p=noise_p, backend=backend
        )
        total_ms += run.sim_time_ms
        base_attempts = candidate_periods(run.counts, t, n, base)
        attempts.extend(base_attempts)

        period, factors = None, None
        for att in base_attempts:
            if att.ok and att.r_candidate is not None:
                f = factors_from_period(base, att.r_candidate, n)
                if f is not None:
                    period, factors = att.r_candidate, f
                    break

        result = ShorResult(
            n=n,
            a=base,
            period=period,
            factors=factors,
            counts=run.counts,
            n_count=t,
            n_work=n_work,
            attempts=attempts,
            circuit=qc,
            transpiled=run.transpiled,
            sim_time_ms=total_ms,
            construction=construction,
            explain_circuits=_explain_circuits(base, n, t, construction),
            register_roles=dict(roles),
            counting_qubits=1 if construction == ITERATIVE else t,
            multiplier_blocks=multiplier_blocks(n, construction),
            circuit_runs=i + 1,
        )
        if factors is not None:
            break

    assert result is not None  # bases is never empty for a supported n
    result.sim_time_ms = total_ms
    return result


# ---------------------------------------------------------------------------
# Input stage: is there anything here for Shor to attack?
# ---------------------------------------------------------------------------

_MODULUS_FIELDS = ("n", "modulus", "rsa_modulus")
_GROUP_FIELDS = ("p", "g", "generator", "group_order", "curve")


def shor_input_stage(public_material: dict) -> dict:
    """The pipeline's first step, run on whatever public material the attacker intercepted.

    Shor's algorithm needs hidden *period* structure: an RSA modulus N (order finding of
    a^x mod N), or a discrete-logarithm group (finite field / elliptic curve). This looks for
    either among the public fields and reports whether the attack applies. It does not
    try to reinterpret arbitrary bytes (keys, ciphertexts) as integers to factor: an
    encapsulation key or a ciphertext is not a modulus.
    """
    fields = sorted(public_material)
    modulus = next((public_material[k] for k in _MODULUS_FIELDS if k in public_material), None)
    if isinstance(modulus, int) and not isinstance(modulus, bool) and modulus > 3:
        if modulus % 2 == 0:
            reason = f"N = {modulus} is even: one division by 2 factors it classically."
        elif modulus in SHOR_SUPPORTED_N:
            reason = f"Found an RSA modulus N = {modulus}: order finding of a^x mod N applies."
        else:
            reason = f"Found an RSA modulus N = {modulus}: Shor applies in principle, but this N is outside the simulated set {list(SHOR_SUPPORTED_N)}."
        return {"applicable": modulus % 2 == 1, "target": "rsa_modulus", "n": modulus, "fields_seen": fields, "reason": reason}
    group = [k for k in _GROUP_FIELDS if k in public_material]
    if group:
        return {
            "applicable": True,
            "target": "discrete_log_group",
            "n": None,
            "fields_seen": fields,
            "reason": f"Found discrete-logarithm group parameters ({', '.join(group)}): Shor's discrete-log variant applies in principle (not implemented here).",
        }
    return {
        "applicable": False,
        "target": None,
        "n": None,
        "fields_seen": fields,
        "reason": "No RSA modulus and no discrete-logarithm group in the public material: there is no "
        "factoring or period-finding problem for Shor's algorithm to solve.",
    }
