"""Quantum counting: estimate how many keys M satisfy the attack condition, before Grover.

Grover needs about pi/4 * sqrt(N/M) iterations, but M is unknown to the attacker.
Quantum counting runs phase estimation on the Grover operator G = Diffuser * Oracle
(the very same oracle the attack uses) and reads M off the measured phase.

Our diffuser is I - 2|s><s| = -(2|s><s| - I), so G = -G_textbook. G_textbook rotates by
angle theta in the plane of marked/unmarked keys, with sin^2(theta/2) = M/N, so its
eigenvalues are e^(+-i theta). Ours are therefore e^(i(pi +- theta)). Phase estimation
with t counting qubits measures y ~ 2^t * phi with phi = (pi +- theta) / 2pi, and

    M = N * sin^2(theta/2) = N * cos^2(pi * phi)

Both eigenphases (y and 2^t - y) give the same M, so the estimate does not depend on
which of the two the measurement lands on.

Reading M off the single most frequent y is limited by the 1/2^t phase resolution. We
therefore also use every shot: for each whole number M = 0..N the phase-estimation
outcome distribution is known exactly (a Fejer kernel around each eigenphase, with the
uniform start state split equally between the two eigenvectors), and we accept the M
with the highest likelihood of the observed histogram. This is classical post-processing
of the measured counts only.

Cost: t counting qubits plus 2^t - 1 controlled Grover operators. Only the sign flips
(the oracle's final multi-controlled X and the diffuser's multi-controlled Z) need the
control qubit; the compute/uncompute halves cancel when the flip is skipped.

Like the attack, counting never receives the key: it only uses the AttackSpec built from
intercepted data, and it does not call `cipher.matching_keys`.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit.library import QFTGate

from qbreak.aes.conditions import AttackSpec
from qbreak.common.simulator import run_circuit

COUNTING_MAX_KEY_BITS: int = int(os.getenv("QBREAK_COUNTING_MAX_KEY_BITS", "4"))
"""Largest key size where the attack runs quantum counting before Grover by default.

Counting costs 2^t - 1 controlled Grover operators on t extra qubits, i.e. more
simulator time than the attack itself; above this size the attack falls back to
trying M = 1, 2, 4, 8.
"""


def counting_enabled(key_bits: int) -> bool:
    return key_bits <= COUNTING_MAX_KEY_BITS


def counting_qubits(key_bits: int) -> int:
    """t = k/2 + 2 counting qubits: enough phase resolution to tell M = 1 from M = 0."""
    return key_bits // 2 + 2


@dataclass
class CountingOutcome:
    """One measured counting value and the M it implies."""

    y: int
    count: int
    phase: float
    m_estimate: float


@dataclass
class CountingResult:
    """The quantum-counting estimate of M plus the evidence behind it."""

    key_bits: int
    counting_qubits: int
    estimated_m: float
    """M read off the most frequent outcome alone: N cos^2(pi y / 2^t)."""
    estimated_m_rounded: int
    """The accepted whole-number estimate: the maximum-likelihood M given every shot."""
    phase: float
    y: int
    controlled_grover_calls: int
    outcomes: list[CountingOutcome]
    counts: dict[str, int]
    circuit: QuantumCircuit
    num_qubits: int
    transpiled_depth: int
    sim_time_ms: float
    derivation: list[str]


def m_from_phase(phase: float, key_bits: int) -> float:
    """M = N cos^2(pi * phase) for our sign convention of the Grover operator."""
    return (2**key_bits) * math.cos(math.pi * phase) ** 2


def outcome_distribution(m: int, key_bits: int, t: int) -> np.ndarray:
    """Exact probability of each counting outcome y = 0..2^t-1 when M = m keys are marked."""
    n_keys = 2**key_bits
    theta = 2 * math.asin(math.sqrt(m / n_keys))
    size = 2**t
    y = np.arange(size)
    probs = np.zeros(size)
    for phase in ((math.pi + theta) / (2 * math.pi), (math.pi - theta) / (2 * math.pi)):
        delta = phase - y / size
        amp = np.exp(2j * np.pi * np.outer(delta, np.arange(size))).sum(axis=1) / size
        probs += 0.5 * np.abs(amp) ** 2
    return probs


def maximum_likelihood_m(counts: dict[str, int], key_bits: int, t: int) -> tuple[int, list[tuple[int, float]]]:
    """The whole number M = 0..N whose outcome distribution best explains the histogram.

    Returns (best M, [(M, log-likelihood)] for the best few, best first).
    """
    observed = np.zeros(2**t)
    for bits, n in counts.items():
        observed[int(bits, 2)] += n
    scores = []
    for m in range(2**key_bits + 1):
        probs = np.clip(outcome_distribution(m, key_bits, t), 1e-12, None)
        scores.append((m, float(observed @ np.log(probs))))
    scores.sort(key=lambda s: -s[1])
    return scores[0][0], scores[:4]


def controlled_grover_operator(spec: AttackSpec, key_bits: int) -> QuantumCircuit:
    """One Grover operator (oracle then diffuser) controlled by a last `ctrl` qubit."""
    from qbreak.aes.grover import _registers, build_diffuser, build_oracle

    regs = _registers(key_bits, spec)
    ctrl = QuantumRegister(1, "ctrl")
    qc = QuantumCircuit(*regs, ctrl, name="c-G")
    qc.compose(build_oracle(spec, key_bits, controlled=True), qubits=qc.qubits, inplace=True)
    qc.compose(build_diffuser(key_bits, controlled=True), qubits=list(regs[0]) + [ctrl[0]], inplace=True)
    return qc


def build_counting_circuit(spec: AttackSpec, key_bits: int, t: int | None = None) -> QuantumCircuit:
    """Phase estimation of the Grover operator with t counting qubits.

    count[j] controls G^(2^j); the inverse QFT turns the phases into a measured integer
    y ~ 2^t * phi, read into the single classical register `c` (MSB first).
    """
    from qbreak.aes.grover import _registers

    if t is None:
        t = counting_qubits(key_bits)
    regs = _registers(key_bits, spec)
    count = QuantumRegister(t, "count")
    creg = ClassicalRegister(t, "c")
    qc = QuantumCircuit(count, *regs, creg, name="Quantum counting")
    key, flag = regs[0], regs[-1]
    system = [q for r in regs for q in r]
    cg = controlled_grover_operator(spec, key_bits).to_gate(label="c-Grover")
    qc.h(count)
    qc.h(key)
    qc.x(flag)
    qc.h(flag)
    for j in range(t):
        for _ in range(2**j):
            qc.append(cg, system + [count[j]])
    qc.append(QFTGate(t).inverse(), list(count))
    qc.measure(count, creg)
    return qc


def run_quantum_counting(
    spec: AttackSpec,
    key_bits: int,
    shots: int = 1024,
    seed: int | None = None,
    t: int | None = None,
    noise_p: float | None = None,
) -> CountingResult:
    """Run quantum counting and turn the most frequent outcome into an estimate of M."""
    if t is None:
        t = counting_qubits(key_bits)
    qc = build_counting_circuit(spec, key_bits, t)
    sim = run_circuit(qc, shots=shots, seed=seed, noise_p=noise_p)
    ranked = sorted(sim.counts.items(), key=lambda kv: (-kv[1], kv[0]))
    outcomes = [
        CountingOutcome(y=int(b, 2), count=n, phase=int(b, 2) / 2**t, m_estimate=m_from_phase(int(b, 2) / 2**t, key_bits))
        for b, n in ranked
    ]
    best = outcomes[0]
    m_rounded, likelihoods = maximum_likelihood_m(sim.counts, key_bits, t)
    n_keys = 2**key_bits
    derivation = [
        f"Counting register: t = {t} qubits, so the phase is read to 1/{2**t}; "
        f"{2**t - 1} controlled Grover operators were applied.",
        f"Most frequent outcome y = {best.y} ({best.count}/{shots} shots) → phase φ = y/2^t = "
        f"{best.y}/{2**t} = {best.phase:.4f}.",
        "Our Grover operator is −(2|s⟩⟨s| − I)·Oracle, so its eigenphase is π ± θ with "
        "sin²(θ/2) = M/N; hence M = N·cos²(πφ).",
        f"Peak reading: M ≈ {n_keys}·cos²(π·{best.phase:.4f}) = {best.m_estimate:.2f}.",
    ]
    for o in outcomes[1:4]:
        mirror = abs(o.m_estimate - best.m_estimate) < 1e-9
        derivation.append(
            f"Also seen: y = {o.y} ({o.count} shots) → M ≈ {o.m_estimate:.2f}"
            + (" (the mirror phase 1 − φ: same M)." if mirror else ".")
        )
    derivation.append(
        f"Using every shot: M = {m_rounded} explains the histogram best "
        f"(log-likelihood {likelihoods[0][1]:.1f}) → accept M = {m_rounded}."
    )
    derivation.extend(f"Rejected M = {m}: log-likelihood {ll:.1f}." for m, ll in likelihoods[1:3])
    if m_rounded == 0:
        derivation.append("M = 0 means no key satisfies the condition; Grover would assume M = 1 anyway.")
    return CountingResult(
        key_bits=key_bits,
        counting_qubits=t,
        estimated_m=best.m_estimate,
        estimated_m_rounded=m_rounded,
        phase=best.phase,
        y=best.y,
        controlled_grover_calls=2**t - 1,
        outcomes=outcomes[:16],
        counts=sim.counts,
        circuit=qc,
        num_qubits=qc.num_qubits,
        transpiled_depth=sim.transpiled.depth() or 0,
        sim_time_ms=sim.sim_time_ms,
        derivation=derivation,
    )
