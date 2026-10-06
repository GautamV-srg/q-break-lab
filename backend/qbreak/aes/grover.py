"""Grover key search against MiniAES: the quantum adversary of the symmetric breach test.

The adversary intercepts the ciphertext and, depending on the attack condition, knows a
piece of the plaintext (see `qbreak.aes.conditions`). It never sees the key. It builds a
quantum circuit that holds EVERY possible key at once, runs the MiniAES cipher reversibly
inside the circuit on all of them simultaneously, and flips the sign ("marks") of exactly
those keys that satisfy the condition:

    known_beginning   the key turns the known first blocks into the observed ciphertext
    known_substring   ... the known text, at ANY of its possible positions
    ciphertext_only   the key decrypts every first-of-byte block to ASCII text

Grover's diffuser then turns those sign flips into a much higher measurement
probability, so after about pi/4 * sqrt(2^k / M) rounds a measurement of the key register
returns a marked key with high probability. Quantum counting (`qbreak.aes.counting`)
estimates M first. Every measured key is then checked classically, the same way a real
attacker would check a guessed key.

Registers in the circuit (qubit i of a register always holds bit i, LSB = qubit 0):

    key    the candidate key, starting in an equal superposition of all 2^k keys
    work   scratch nibble holding the cipher's input for the block being checked
    sbox   scratch nibble holding the S-box output, then compared with the target
    match  one qubit per check in a group: 1 when the candidate key passes that check
    hit    (known_substring with several positions only) one qubit per position:
           1 when every check for that position passes
    flag   a single qubit in the |-> state that turns "marked" into a sign flip
    c      classical bits receiving the measured key

`work` and `sbox` are reused for every check and returned to |0> afterwards, so a
one-group circuit needs only key_bits + 8 + (checks) + 1 qubits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import Qubit

from qbreak.aes.cipher import INV_SBOX, RCON, SBOX, SUPPORTED_KEY_BITS
from qbreak.aes.conditions import (
    DEFAULT_MAX_PAIRS,
    PLAUSIBLE_HIGH_NIBBLES,
    AttackSpec,
    PairCheck,
    PlausibleCheck,
    check_condition,
    circuit_spec,
    full_spec,
    known_beginning_pairs,
)
from qbreak.common.simulator import SimRun, run_circuit

M_GUESS_SCHEDULE: tuple[int, ...] = (1, 2, 4, 8)
"""Guesses for the unknown number of matching keys M, tried in order when counting is off."""

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

CONDITION_ROLES: dict[str, dict[str, str]] = {
    "known_beginning": {},
    "known_substring": {
        "match": "One qubit per known block at the position being checked: set to 1 when "
        "the candidate key encrypts that block to the ciphertext block there.",
        "hit": "One qubit per possible position of the known text: set to 1 when every "
        "block at that position matches. The key is marked if ANY position hits.",
    },
    "ciphertext_only": {
        "work": "Scratch nibble: holds an intercepted ciphertext block XOR the second "
        "round key, i.e. the cipher run backwards.",
        "sbox": "Scratch nibble: holds the inverse S-box output XOR K0, the decrypted "
        "block for this candidate key.",
        "match": "One qubit per distinct first-of-byte ciphertext block: set to 1 when the "
        "candidate key decrypts it to a high nibble of ASCII text (2-7).",
    },
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
    condition: str = "known_beginning"
    spec: AttackSpec | None = None
    counting: object | None = None
    """A `qbreak.aes.counting.CountingResult` when quantum counting chose the iterations."""
    noise_p: float | None = None


# --------------------------------------------------------------------------- helpers


def _check_key_bits(key_bits: int) -> None:
    if key_bits not in SUPPORTED_KEY_BITS:
        raise ValueError(f"key_bits must be one of {SUPPORTED_KEY_BITS}, got {key_bits!r}")


def _bit(value: int, i: int) -> int:
    return (value >> i) & 1


def _as_spec(spec_or_pairs: AttackSpec | list[tuple[int, int]], key_bits: int) -> AttackSpec:
    """Accept an AttackSpec, or (as before) a plain list of known (plain, cipher) pairs."""
    if isinstance(spec_or_pairs, AttackSpec):
        if spec_or_pairs.key_bits != key_bits:
            raise ValueError("AttackSpec key size does not match key_bits")
        return spec_or_pairs
    pairs = list(spec_or_pairs)
    if not pairs:
        raise ValueError("The oracle needs at least one known pair")
    return AttackSpec("known_beginning", key_bits, (tuple(PairCheck(p, c) for p, c in pairs),))


def _registers(key_bits: int, spec: AttackSpec) -> list[QuantumRegister]:
    regs = [
        QuantumRegister(key_bits, "key"),
        QuantumRegister(4, "work"),
        QuantumRegister(4, "sbox"),
        QuantumRegister(spec.max_group, "match"),
    ]
    if len(spec.groups) > 1:
        regs.append(QuantumRegister(len(spec.groups), "hit"))
    regs.append(QuantumRegister(1, "flag"))
    return regs


def _h_qubit(key: QuantumRegister, key_bits: int, j: int) -> Qubit:
    """Key qubit holding bit j of the high nibble H (bits 4-7 for 10/12-bit keys)."""
    return key[min(key_bits, 8) - 4 + j]


def _rotl_controlled(qc: QuantumCircuit, ctrl: Qubit, reg: QuantumRegister, by: int, inverse: bool = False) -> None:
    """Rotate a nibble register left by 1 or 2 bits when `ctrl` is 1 (controlled swaps)."""
    if by == 2:
        qc.cswap(ctrl, reg[0], reg[2])
        qc.cswap(ctrl, reg[1], reg[3])
        return
    swaps = [(3, 2), (2, 1), (1, 0)]
    for a, b in reversed(swaps) if inverse else swaps:
        qc.cswap(ctrl, reg[a], reg[b])


def _lookup(qc: QuantumCircuit, table: tuple[int, ...], src: list[Qubit], dst: QuantumRegister) -> None:
    """dst ^= table[src] as a lookup table: one multi-controlled X per (input, set output bit)."""
    for v in range(16):
        targets = [j for j in range(4) if _bit(table[v], j)]
        if not targets:
            continue
        zeros = [src[i] for i in range(4) if not _bit(v, i)]
        if zeros:
            qc.x(zeros)
        for j in targets:
            qc.mcx(list(src), dst[j])
        if zeros:
            qc.x(zeros)


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
       (12-bit keys: rotate `work` left by A, using controlled swaps on key bits 10-11.)
    2. SubNibble as a lookup table: for each of the 16 possible inputs v, write S[v]
       into `sbox` when work == v (flip the 0-bits of v, multi-controlled X, flip back).
    3. RotateBits costs no gates: it only relabels which qubit holds which output bit.
       (10/12-bit keys: the extra rotation by B uses controlled swaps on key bits 8-9.)
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
    if key_bits >= 12:
        _rotl_controlled(qc, key[10], work, 1)
        _rotl_controlled(qc, key[11], work, 2)
    # 2. sbox = SBOX[work]  (out-of-place lookup table)
    _lookup(qc, SBOX, list(work), sbox)
    # 3. RotateBits: relabelling only, no gates (plus the key-selected extra rotation).
    if key_bits >= 10:
        _rotl_controlled(qc, key[8], sbox, 1)
        _rotl_controlled(qc, key[9], sbox, 2)
    # 4. sbox_j <- s_j XOR H_j XOR NOT t_j
    for j in range(4):
        qc.cx(_h_qubit(key, key_bits, j), sbox[j])
        t_j = _bit(RCON, (j + 1) % 4) ^ _bit(c, (j + 1) % 4)
        if t_j == 0:
            qc.x(sbox[j])
    return qc


def _compute_decrypt(
    c: int,
    key_bits: int,
    key: QuantumRegister,
    work: QuantumRegister,
    sbox: QuantumRegister,
) -> QuantumCircuit:
    """Reversible MiniAES decryption of one ciphertext block C into `sbox`.

    1. work = C XOR K1, where K1 = rotl(H) XOR RCON: load the constant C XOR RCON, then
       XOR in key bit H_(i-1) on work[i].
    2. Undo RotateBits: the key-selected extra rotation by B (10/12-bit) with controlled
       swaps; the fixed rotate-by-one is again only a relabelling of the lookup inputs.
    3. Inverse S-box lookup into `sbox`, undo the input rotation by A (12-bit), and XOR
       K0 in: sbox now holds the decrypted block D_k(C).
    """
    qc = QuantumCircuit(key, work, sbox, name=f"Decrypt C={c:X}")
    for i in range(4):
        if _bit(c ^ RCON, i):
            qc.x(work[i])
    for i in range(4):
        qc.cx(_h_qubit(key, key_bits, (i - 1) % 4), work[i])
    if key_bits >= 10:
        _rotl_controlled(qc, key[9], work, 2)
        _rotl_controlled(qc, key[8], work, 1, inverse=True)
    # rotr by one: bit j of the S-box input is work[(j + 1) % 4]
    _lookup(qc, INV_SBOX, [work[(j + 1) % 4] for j in range(4)], sbox)
    if key_bits >= 12:
        _rotl_controlled(qc, key[11], sbox, 2)
        _rotl_controlled(qc, key[10], sbox, 1, inverse=True)
    for i in range(4):
        qc.cx(key[i], sbox[i])
    return qc


def _write_check(qc: QuantumCircuit, check: PairCheck | PlausibleCheck, sbox: QuantumRegister, target: Qubit) -> None:
    """XOR the check's outcome (held in `sbox` after its compute step) into `target`."""
    if isinstance(check, PairCheck):
        qc.mcx(list(sbox), target)
        return
    for v in sorted(PLAUSIBLE_HIGH_NIBBLES):  # mutually exclusive patterns, so XOR = OR
        zeros = [sbox[i] for i in range(4) if not _bit(v, i)]
        if zeros:
            qc.x(zeros)
        qc.mcx(list(sbox), target)
        if zeros:
            qc.x(zeros)


def _compute_check(check: PairCheck | PlausibleCheck, key_bits: int, key, work, sbox) -> QuantumCircuit:
    if isinstance(check, PairCheck):
        return _compute_pair(check.plain, check.cipher, key_bits, key, work, sbox)
    return _compute_decrypt(check.cipher, key_bits, key, work, sbox)


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
    return known_beginning_pairs(known_plain, cipher)[: max(1, max_pairs)]


def build_oracle(
    spec_or_pairs: AttackSpec | list[tuple[int, int]], key_bits: int, controlled: bool = False
) -> QuantumCircuit:
    """The Grover oracle: flip the sign of every key that satisfies the attack condition.

    For each group (one position of the known text, or the single group of the other
    conditions) and each check i in it: run the cipher check, copy its result into
    match[i], then run the check backwards so `work` and `sbox` return to |0>.

    One group: a multi-controlled X from all `match` qubits onto the |-> flag multiplies
    the amplitude of every fully matching key by -1.
    Several groups: the matches of each group are ANDed into its `hit` qubit (and then
    uncomputed so `match` is reused); the flag flips when ANY hit is set, computed as
    NOT(all hits are 0). Finally everything is recomputed backwards so no garbage stays
    entangled with the key.

    controlled=True adds a last one-qubit register `ctrl` that gates only the sign flip
    itself: the compute/uncompute halves cancel exactly when the flip is skipped, so this
    is the controlled oracle that quantum counting needs, at almost no extra cost.
    """
    _check_key_bits(key_bits)
    spec = _as_spec(spec_or_pairs, key_bits)
    regs = _registers(key_bits, spec)
    if controlled:
        regs.append(QuantumRegister(1, "ctrl"))
    qc = QuantumCircuit(*regs, name="Oracle")
    names = {r.name: r for r in regs}
    key, work, sbox, match, flag = (names[n] for n in ("key", "work", "sbox", "match", "flag"))
    hit = names.get("hit")
    ctrl = [names["ctrl"][0]] if controlled else []

    def mark_check(i: int, check: PairCheck | PlausibleCheck) -> None:
        compute = _compute_check(check, key_bits, key, work, sbox)
        qc.compose(compute, inplace=True)
        _write_check(qc, check, sbox, match[i])
        qc.compose(compute.inverse(), inplace=True)

    def group_matches(group: tuple) -> None:
        for i, check in enumerate(group):
            mark_check(i, check)

    def group_unmatches(group: tuple) -> None:
        for i, check in reversed(list(enumerate(group))):
            mark_check(i, check)

    if hit is None:
        group = spec.groups[0]
        group_matches(group)
        qc.mcx(list(match[: len(group)]) + ctrl, flag[0])
        group_unmatches(group)
        return qc

    for g, group in enumerate(spec.groups):
        group_matches(group)
        qc.mcx(list(match[: len(group)]), hit[g])
        group_unmatches(group)
    qc.x(hit)
    qc.mcx(list(hit) + ctrl, flag[0])  # flips when NO position hits ...
    qc.x(hit)
    if ctrl:
        qc.cx(ctrl[0], flag[0])  # ... and a second flip turns that into "ANY position hits"
    else:
        qc.x(flag[0])
    for g, group in reversed(list(enumerate(spec.groups))):
        group_matches(group)
        qc.mcx(list(match[: len(group)]), hit[g])
        group_unmatches(group)
    return qc


def build_diffuser(key_bits: int, controlled: bool = False) -> QuantumCircuit:
    """Grover's diffuser on the key register: 'inversion about the mean'.

    H and X on every key qubit, a multi-controlled Z (H, multi-controlled X, H on the
    last qubit), then X and H again. It reflects all amplitudes about their average,
    which grows the amplitude of the keys the oracle marked with a minus sign.

    controlled=True adds a one-qubit `ctrl` register that gates only the multi-controlled
    Z (the H/X layers around it cancel when it is skipped).
    """
    _check_key_bits(key_bits)
    key = QuantumRegister(key_bits, "key")
    regs = [key] + ([QuantumRegister(1, "ctrl")] if controlled else [])
    qc = QuantumCircuit(*regs, name="Diffuser")
    ctrl = [regs[1][0]] if controlled else []
    qc.h(key)
    qc.x(key)
    qc.h(key[-1])
    qc.mcx(list(key[:-1]) + ctrl, key[-1])
    qc.h(key[-1])
    qc.x(key)
    qc.h(key)
    return qc


def optimal_iterations(key_bits: int, num_solutions: int = 1) -> int:
    """Number of Grover rounds that maximises success: floor(pi/4 * sqrt(2^k / M))."""
    if num_solutions < 1:
        raise ValueError("num_solutions must be at least 1")
    return max(1, math.floor(math.pi / 4 * math.sqrt(2**key_bits / num_solutions)))


def theoretical_success(key_bits: int, num_solutions: int, iterations: int) -> float:
    """Probability of measuring a marked key: sin^2((2r + 1) * theta), sin(theta) = sqrt(M/N)."""
    if num_solutions <= 0:
        return 0.0
    theta = math.asin(math.sqrt(min(1.0, num_solutions / 2**key_bits)))
    return math.sin((2 * iterations + 1) * theta) ** 2


def _grover_iteration(spec: AttackSpec, key_bits: int) -> QuantumCircuit:
    """One Grover round (boxed Oracle then boxed Diffuser), without state preparation."""
    regs = _registers(key_bits, spec)
    key = regs[0]
    qc = QuantumCircuit(*regs, name="Grover iteration")
    qc.append(build_oracle(spec, key_bits).to_gate(label="Oracle"), qc.qubits)
    qc.append(build_diffuser(key_bits).to_gate(label="Diffuser"), list(key))
    return qc


def build_grover_circuit(
    spec_or_pairs: AttackSpec | list[tuple[int, int]], key_bits: int, iterations: int
) -> QuantumCircuit:
    """The full attack circuit: superpose all keys, repeat Oracle + Diffuser, measure.

    The flag qubit is prepared in |-> (X then H) so the oracle acts as a sign flip.
    Only the key register is measured, into the single classical register `c`, so a
    measured bitstring reads directly as an MSB-first key (e.g. "1001" is key 9).
    """
    _check_key_bits(key_bits)
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    spec = _as_spec(spec_or_pairs, key_bits)
    regs = _registers(key_bits, spec)
    key, flag = regs[0], regs[-1]
    creg = ClassicalRegister(key_bits, "c")
    qc = QuantumCircuit(*regs, creg, name="Grover attack")
    oracle = build_oracle(spec, key_bits).to_gate(label="Oracle")
    diffuser = build_diffuser(key_bits).to_gate(label="Diffuser")
    qc.h(key)
    qc.x(flag)
    qc.h(flag)
    system = [q for r in regs for q in r]
    for _ in range(iterations):
        qc.append(oracle, system)
        qc.append(diffuser, list(key))
    qc.measure(key, creg)
    return qc


def register_roles(condition: str) -> dict[str, str]:
    """Plain-language role of every register, for the condition's circuit."""
    return {**REGISTER_ROLES, **CONDITION_ROLES.get(condition, {})}


def run_grover_attack(
    known_plain: list[int] | None,
    cipher: list[int],
    key_bits: int,
    shots: int = 1024,
    seed: int | None = None,
    condition: str = "known_beginning",
    counting: bool | None = None,
    noise_p: float | None = None,
) -> GroverResult:
    """Recover the MiniAES key from intercepted data under one of three attack conditions.

    There is deliberately no key argument: the attack sees only what an eavesdropper
    would (ciphertext, plus known plaintext for the two known-text conditions).

    The number M of matching keys is unknown. With `counting` on (the default for key
    sizes up to `QBREAK_COUNTING_MAX_KEY_BITS`) quantum counting estimates M first and the
    first Grover run uses pi/4 * sqrt(N/M) iterations. Otherwise (or if that run fails)
    the iteration counts for M = 1, 2, 4, 8 are tried in turn. After each run, measured
    keys that appear often enough are re-checked classically against the in-circuit
    constraint; the first run whose verified keys hold at least 40% of the shots is
    accepted. Recovered keys are those verified keys that also satisfy the FULL constraint,
    including the blocks that did not fit inside the circuit.

    `noise_p` runs the circuit under a depolarising noise model (see
    `qbreak.common.simulator.depolarizing_noise_model`). Noisy runs simulate every shot
    separately, so they skip quantum counting (unless `counting=True`) and make a single
    attempt: the point is to watch the breach degrade, not to retry until it works.
    """
    _check_key_bits(key_bits)
    check_condition(condition)
    spec = circuit_spec(condition, known_plain, cipher, key_bits)
    full = full_spec(condition, known_plain, cipher, key_bits)
    pairs = [(c.plain, c.cipher) for c in spec.groups[0] if isinstance(c, PairCheck)] if len(spec.groups) == 1 else []

    from qbreak.aes.counting import counting_enabled, run_quantum_counting

    count_result = None
    schedule: list[int] = list(M_GUESS_SCHEDULE)
    if counting is None:
        counting = counting_enabled(key_bits) and noise_p is None
    if counting:
        count_result = run_quantum_counting(spec, key_bits, shots=shots, seed=seed, noise_p=noise_p)
        schedule = [max(1, count_result.estimated_m_rounded)] + schedule
    elif condition == "ciphertext_only":
        schedule += [16, 32, 64]  # plausibility often leaves many keys
    if noise_p is not None:
        schedule = schedule[:1]  # noisy runs simulate every shot: one attempt, and let it degrade

    attempts: list[GroverAttempt] = []
    runs: list[tuple[GroverAttempt, list[int], QuantumCircuit, SimRun, float]] = []
    tried: set[int] = set()
    chosen = None
    for m_guess in schedule:
        if m_guess > 2**key_bits:
            continue
        iterations = optimal_iterations(key_bits, m_guess)
        if iterations in tried:
            continue
        tried.add(iterations)
        qc = build_grover_circuit(spec, key_bits, iterations)
        sim = run_circuit(qc, shots=shots, seed=seed, noise_p=noise_p)
        threshold = min(max(2, 0.02 * shots), max(2, 0.25 * shots / m_guess))
        ranked = sorted(sim.counts.items(), key=lambda kv: (-kv[1], kv[0]))
        candidates = [int(b, 2) for b, n in ranked if n >= threshold]
        verified = [k for k in candidates if spec.fits(k)]
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
    recovered = [k for k in attempt.verified_keys if full.fits(k)]
    explain = [
        ("One Grover iteration", _grover_iteration(spec, key_bits)),
        ("Oracle (decomposed)", build_oracle(spec, key_bits)),
        ("Diffuser", build_diffuser(key_bits)),
    ]
    sim_time = sum(r[3].sim_time_ms for r in runs) + (count_result.sim_time_ms if count_result else 0.0)
    return GroverResult(
        key_bits=key_bits,
        pairs_used=pairs,
        iterations=attempt.iterations,
        counts=attempt.counts,
        candidate_keys=candidates,
        recovered_keys=recovered,
        circuit=qc,
        transpiled=sim.transpiled,
        sim_time_ms=sim_time,
        attempts=attempts,
        explain_circuits=explain,
        register_roles=register_roles(condition),
        condition=condition,
        spec=spec,
        counting=count_result,
        noise_p=noise_p,
    )
