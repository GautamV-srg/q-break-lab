"""Grover key search against MiniAES: the quantum adversary of the symmetric breach test.

The adversary intercepts the ciphertext and knows a short piece of the plaintext (a
"crib", e.g. a standard greeting). It never sees the key. It builds a quantum circuit
that holds EVERY possible key at once, runs the MiniAES cipher reversibly inside the
circuit on all of them simultaneously, and flips the sign ("marks") of exactly those
keys that turn the known plaintext into the observed ciphertext. Grover's diffuser then
turns those sign flips into a much higher measurement probability, so after about
pi/4 * sqrt(2^k) rounds a measurement of the key register returns the secret key with
high probability. Every measured key is then checked classically, the same way a real
attacker would check a guessed key.

Registers in the circuit (qubit i of a register always holds bit i, LSB = qubit 0):

    key    the candidate key, starting in an equal superposition of all 2^k keys
    work   scratch nibble holding x = P XOR K0 for the known block being checked
    sbox   scratch nibble holding the S-box output S[x], then compared with C
    match  one qubit per known block: 1 when that block encrypts correctly
    flag   a single qubit in the |-> state that turns "match" into a sign flip
    c      classical bits receiving the measured key

`work` and `sbox` are reused for every known block and returned to |0> afterwards, so
the circuit only needs key_bits + 8 + (number of known blocks) + 1 qubits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from qbreak.aes.cipher import RCON, SBOX, SUPPORTED_KEY_BITS, encrypt_nibble
from qbreak.common.simulator import SimRun, run_circuit

DEFAULT_MAX_PAIRS: dict[int, int] = {4: 2, 6: 3, 8: 3}
"""How many distinct known blocks go inside the circuit, per key size."""

M_GUESS_SCHEDULE: tuple[int, ...] = (1, 2, 4, 8)
"""Guesses for the unknown number of matching keys M, tried in order."""

SUCCESS_MASS: float = 0.40
"""An attempt is accepted once verified keys hold at least this share of the shots."""

REGISTER_ROLES: dict[str, str] = {
    "key": "Candidate key: starts as an equal superposition of every possible key, "
    "and is the only register we measure.",
    "work": "Scratch nibble: holds the known plaintext block XOR the first round key "
    "(AddRoundKey K0), for one known block at a time.",
    "sbox": "Scratch nibble: holds the S-box output for that block, then is compared "
    "with the intercepted ciphertext block.",
    "match": "One qubit per known block: set to 1 when the candidate key encrypts that "
    "block to the observed ciphertext.",
    "flag": "Phase-kickback qubit in the |-> state: flipping it multiplies a key's "
    "amplitude by -1, which is how the oracle 'marks' the right keys.",
}


@dataclass
class GroverAttempt:
    """One run of the Grover circuit with a particular number of iterations."""

    iterations: int
    counts: dict[str, int]
    verified_keys: list[int]


@dataclass
class GroverResult:
    """Everything the Breach Report and 'Pop the Hood' need about a Grover attack."""

    key_bits: int
    pairs_used: list[tuple[int, int]]
    iterations: int
    counts: dict[str, int]
    candidate_keys: list[int]
    recovered_keys: list[int]
    circuit: QuantumCircuit
    transpiled: QuantumCircuit
    sim_time_ms: float
    attempts: list[GroverAttempt]
    explain_circuits: list[tuple[str, QuantumCircuit]]
    register_roles: dict[str, str] = field(default_factory=lambda: dict(REGISTER_ROLES))


# --------------------------------------------------------------------------- helpers


def _check_key_bits(key_bits: int) -> None:
    if key_bits not in SUPPORTED_KEY_BITS:
        raise ValueError(f"key_bits must be one of {SUPPORTED_KEY_BITS}, got {key_bits!r}")


def _bit(value: int, i: int) -> int:
    return (value >> i) & 1


def _registers(
    key_bits: int, num_pairs: int
) -> tuple[QuantumRegister, QuantumRegister, QuantumRegister, QuantumRegister, QuantumRegister]:
    return (
        QuantumRegister(key_bits, "key"),
        QuantumRegister(4, "work"),
        QuantumRegister(4, "sbox"),
        QuantumRegister(num_pairs, "match"),
        QuantumRegister(1, "flag"),
    )


def _compute_pair(
    p: int,
    c: int,
    key_bits: int,
    key: QuantumRegister,
    work: QuantumRegister,
    sbox: QuantumRegister,
) -> QuantumCircuit:
    """Reversible MiniAES check for one known block (P, C), up to the final comparison.

    Afterwards every `sbox` qubit is 1 exactly when the candidate key encrypts P to C.

    1. Load P into `work` and XOR in K0 (the low 4 key bits): work = P XOR K0.
    2. SubNibble as a lookup table: for each of the 16 possible inputs v, write S[v]
       into `sbox` when work == v (flip the 0-bits of v, multi-controlled X, flip back).
    3. RotateBits costs no gates: it only relabels which qubit holds which output bit.
    4. AddRoundKey K1 and compare with C: XOR the high key nibble H into `sbox`, then
       flip the bits where the expected constant is 0, so "all ones" means "match".
       (Algebra: block matches iff s_j XOR H_j = RCON_(j+1) XOR C_(j+1) for all j,
       indices mod 4.)
    """
    qc = QuantumCircuit(key, work, sbox, name=f"Check P={p:X}")
    # 1. work = P XOR K0
    for i in range(4):
        if _bit(p, i):
            qc.x(work[i])
    for i in range(4):
        qc.cx(key[i], work[i])
    # 2. sbox = SBOX[work]  (out-of-place lookup table)
    for v in range(16):
        targets = [j for j in range(4) if _bit(SBOX[v], j)]
        if not targets:
            continue
        zeros = [work[i] for i in range(4) if not _bit(v, i)]
        if zeros:
            qc.x(zeros)
        for j in targets:
            qc.mcx(list(work), sbox[j])
        if zeros:
            qc.x(zeros)
    # 3. RotateBits: relabelling only, no gates.
    # 4. sbox_j <- s_j XOR H_j XOR NOT t_j
    for j in range(4):
        qc.cx(key[key_bits - 4 + j], sbox[j])
        t_j = _bit(RCON, (j + 1) % 4) ^ _bit(c, (j + 1) % 4)
        if t_j == 0:
            qc.x(sbox[j])
    return qc


# --------------------------------------------------------------------------- public API


def select_known_pairs(
    known_plain: list[int], cipher: list[int], key_bits: int, max_pairs: int | None = None
) -> list[tuple[int, int]]:
    """Turn the known plaintext prefix into distinct (plain nibble, cipher nibble) pairs.

    MiniAES encrypts each nibble independently, so a repeated plaintext nibble always
    gives the same ciphertext nibble and adds no information; repeats are dropped.
    Returns the first `max_pairs` distinct pairs (default depends on key size).

    Raises ValueError if the crib is empty, longer than the ciphertext, contains
    non-nibbles, or contradicts itself (same plain nibble, different cipher nibble).
    """
    _check_key_bits(key_bits)
    if max_pairs is None:
        max_pairs = DEFAULT_MAX_PAIRS[key_bits]
    if len(known_plain) > len(cipher):
        raise ValueError("Known plaintext is longer than the ciphertext")
    seen: dict[int, int] = {}
    for p, c in zip(known_plain, cipher):
        for v in (p, c):
            if not isinstance(v, int) or not 0 <= v <= 0xF:
                raise ValueError(f"Nibbles must be integers 0..15, got {v!r}")
        if p in seen and seen[p] != c:
            raise ValueError("Known plaintext is inconsistent with ciphertext")
        seen.setdefault(p, c)
    if not seen:
        raise ValueError("No known plaintext pairs available")
    return list(seen.items())[: max(1, max_pairs)]


def build_oracle(pairs: list[tuple[int, int]], key_bits: int) -> QuantumCircuit:
    """The Grover oracle: flip the sign of every key that encrypts ALL pairs correctly.

    For each known block i: run the cipher check, copy its "all ones" result into
    match[i], then run the check backwards so `work` and `sbox` return to |0>.
    A multi-controlled X from all `match` qubits onto the |-> flag multiplies the
    amplitude of every fully matching key by -1. Finally the per-block checks are
    repeated to reset `match` to |0>, so no garbage stays entangled with the key.
    """
    _check_key_bits(key_bits)
    if not pairs:
        raise ValueError("The oracle needs at least one known pair")
    key, work, sbox, match, flag = _registers(key_bits, len(pairs))
    qc = QuantumCircuit(key, work, sbox, match, flag, name="Oracle")

    def mark_pair(i: int, p: int, c: int) -> None:
        compute = _compute_pair(p, c, key_bits, key, work, sbox)
        qc.compose(compute, inplace=True)
        qc.mcx(list(sbox), match[i])
        qc.compose(compute.inverse(), inplace=True)

    for i, (p, c) in enumerate(pairs):
        mark_pair(i, p, c)
    qc.mcx(list(match), flag[0])
    for i, (p, c) in reversed(list(enumerate(pairs))):
        mark_pair(i, p, c)
    return qc


def build_diffuser(key_bits: int) -> QuantumCircuit:
    """Grover's diffuser on the key register: 'inversion about the mean'.

    H and X on every key qubit, a multi-controlled Z (H, multi-controlled X, H on the
    last qubit), then X and H again. It reflects all amplitudes about their average,
    which grows the amplitude of the keys the oracle marked with a minus sign.
    """
    _check_key_bits(key_bits)
    key = QuantumRegister(key_bits, "key")
    qc = QuantumCircuit(key, name="Diffuser")
    qc.h(key)
    qc.x(key)
    qc.h(key[-1])
    qc.mcx(list(key[:-1]), key[-1])
    qc.h(key[-1])
    qc.x(key)
    qc.h(key)
    return qc


def optimal_iterations(key_bits: int, num_solutions: int = 1) -> int:
    """Number of Grover rounds that maximises success: floor(pi/4 * sqrt(2^k / M))."""
    if num_solutions < 1:
        raise ValueError("num_solutions must be at least 1")
    return max(1, math.floor(math.pi / 4 * math.sqrt(2**key_bits / num_solutions)))


def _grover_iteration(pairs: list[tuple[int, int]], key_bits: int) -> QuantumCircuit:
    """One Grover round (boxed Oracle then boxed Diffuser), without state preparation."""
    regs = _registers(key_bits, len(pairs))
    key = regs[0]
    qc = QuantumCircuit(*regs, name="Grover iteration")
    qc.append(build_oracle(pairs, key_bits).to_gate(label="Oracle"), qc.qubits)
    qc.append(build_diffuser(key_bits).to_gate(label="Diffuser"), list(key))
    return qc


def build_grover_circuit(
    pairs: list[tuple[int, int]], key_bits: int, iterations: int
) -> QuantumCircuit:
    """The full attack circuit: superpose all keys, repeat Oracle + Diffuser, measure.

    The flag qubit is prepared in |-> (X then H) so the oracle acts as a sign flip.
    Only the key register is measured, into the single classical register `c`, so a
    measured bitstring reads directly as an MSB-first key (e.g. "1001" is key 9).
    """
    _check_key_bits(key_bits)
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    key, work, sbox, match, flag = _registers(key_bits, len(pairs))
    creg = ClassicalRegister(key_bits, "c")
    qc = QuantumCircuit(key, work, sbox, match, flag, creg, name="Grover attack")
    oracle = build_oracle(pairs, key_bits).to_gate(label="Oracle")
    diffuser = build_diffuser(key_bits).to_gate(label="Diffuser")
    qc.h(key)
    qc.x(flag)
    qc.h(flag)
    for _ in range(iterations):
        qc.append(oracle, list(key) + list(work) + list(sbox) + list(match) + list(flag))
        qc.append(diffuser, list(key))
    qc.measure(key, creg)
    return qc


def run_grover_attack(
    known_plain: list[int],
    cipher: list[int],
    key_bits: int,
    shots: int = 1024,
    seed: int | None = None,
) -> GroverResult:
    """Recover the MiniAES key from ciphertext plus a known plaintext prefix.

    There is deliberately no key argument: the attack sees only what an eavesdropper
    would. Because the number M of keys matching the known blocks is unknown, it tries
    the iteration counts for M = 1, 2, 4, 8 in turn. After each run, measured keys
    that appear often enough are re-checked classically (re-encrypt the known blocks);
    the first run whose verified keys hold at least 40% of the shots is accepted.
    Recovered keys are those verified keys that also fit EVERY known block of the crib,
    including blocks that did not fit inside the circuit.
    """
    _check_key_bits(key_bits)
    all_pairs = select_known_pairs(known_plain, cipher, key_bits, max_pairs=16)
    pairs = all_pairs[: DEFAULT_MAX_PAIRS[key_bits]]

    def fits(k: int, pair_list: list[tuple[int, int]]) -> bool:
        return all(encrypt_nibble(p, k, key_bits) == c for p, c in pair_list)

    attempts: list[GroverAttempt] = []
    runs: list[tuple[GroverAttempt, list[int], QuantumCircuit, SimRun, float]] = []
    tried: set[int] = set()
    chosen = None
    for m_guess in M_GUESS_SCHEDULE:
        iterations = optimal_iterations(key_bits, m_guess)
        if iterations in tried:
            continue
        tried.add(iterations)
        qc = build_grover_circuit(pairs, key_bits, iterations)
        sim = run_circuit(qc, shots=shots, seed=seed)
        threshold = max(2, 0.02 * shots)
        ranked = sorted(sim.counts.items(), key=lambda kv: (-kv[1], kv[0]))
        candidates = [int(b, 2) for b, n in ranked if n >= threshold]
        verified = [k for k in candidates if fits(k, pairs)]
        attempt = GroverAttempt(iterations=iterations, counts=sim.counts, verified_keys=verified)
        attempts.append(attempt)
        mass = sum(sim.counts.get(format(k, f"0{key_bits}b"), 0) for k in verified) / shots
        runs.append((attempt, candidates, qc, sim, mass))
        if mass >= SUCCESS_MASS:
            chosen = runs[-1]
            break
    if chosen is None:
        chosen = max(runs, key=lambda r: r[4])

    attempt, candidates, qc, sim, _ = chosen
    recovered = [k for k in attempt.verified_keys if fits(k, all_pairs)]
    return GroverResult(
        key_bits=key_bits,
        pairs_used=pairs,
        iterations=attempt.iterations,
        counts=attempt.counts,
        candidate_keys=candidates,
        recovered_keys=recovered,
        circuit=qc,
        transpiled=sim.transpiled,
        sim_time_ms=sum(r[3].sim_time_ms for r in runs),
        attempts=attempts,
        explain_circuits=[
            ("One Grover iteration", _grover_iteration(pairs, key_bits)),
            ("Oracle (decomposed)", build_oracle(pairs, key_bits)),
            ("Diffuser", build_diffuser(key_bits)),
        ],
        register_roles=dict(REGISTER_ROLES),
    )
