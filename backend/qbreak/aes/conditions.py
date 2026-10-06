"""Attacker knowledge for the symmetric breach test: the three attack conditions.

Every condition is turned into an `AttackSpec`: a list of *groups* of *checks*. A key
is a candidate when ANY group has ALL of its checks true.

    known_beginning   one group of (plain, cipher) pair checks taken from the start
                      of the message (the original attack)
    known_substring   one group of pair checks per position where the known text could
                      sit in the message (position unknown to the attacker)
    ciphertext_only   one group of "plausibility" checks: each ciphertext nibble in a
                      high (first-of-byte) position must decrypt to a high nibble of
                      ASCII text (0x20-0x7F)

Everything here is derived from intercepted data only (ciphertext, plus known text when
the condition has some). Nothing in this module receives or derives the key, and it does
not call `cipher.matching_keys`.

Alignment for known_substring: MiniAES encrypts whole 4-bit blocks independently, and
text is UTF-8 bytes (two blocks per byte), so a known substring can only start at a
byte boundary. We search every byte-aligned (hence block-aligned) offset. Sub-block
alignment (the text starting part-way through a nibble) is out of scope: no encrypted
block would line up with the known bits, so there is no (plain block, cipher block)
pair to check, and a byte-oriented text encoding never produces it.
"""

from __future__ import annotations

from dataclasses import dataclass

from qbreak.aes.cipher import SUPPORTED_KEY_BITS, decrypt_nibble, encrypt_nibble

CONDITIONS: tuple[str, ...] = ("known_beginning", "known_substring", "ciphertext_only")

PLAUSIBLE_HIGH_NIBBLES: frozenset[int] = frozenset(range(0x2, 0x8))
"""High nibbles of the plausibility alphabet: bytes 0x20-0x7F (printable ASCII + DEL).

A decryption is plausible when every byte lands in this range, which only constrains
the high nibble of each byte, so the check is per ciphertext nibble at even positions.
"""

PLAUSIBILITY_ALPHABET = "ASCII text, bytes 0x20-0x7F"

DEFAULT_MAX_PAIRS: dict[int, int] = {4: 2, 6: 3, 8: 3, 10: 3, 12: 3}
"""How many distinct known blocks go inside the circuit, per key size."""

ANCILLA_BUDGET: dict[int, int] = {4: 6, 6: 6, 8: 5, 10: 4, 12: 3}
"""Most `match` + `hit` qubits the circuit may use, per key size (memory doubles per qubit)."""


@dataclass(frozen=True)
class PairCheck:
    """True when the candidate key encrypts plain nibble `plain` to `cipher`."""

    plain: int
    cipher: int

    def holds(self, key: int, key_bits: int) -> bool:
        return encrypt_nibble(self.plain, key, key_bits) == self.cipher


@dataclass(frozen=True)
class PlausibleCheck:
    """True when the candidate key decrypts `cipher` to a high nibble of ASCII text."""

    cipher: int

    def holds(self, key: int, key_bits: int) -> bool:
        return decrypt_nibble(self.cipher, key, key_bits) in PLAUSIBLE_HIGH_NIBBLES


Check = PairCheck | PlausibleCheck


@dataclass(frozen=True)
class AttackSpec:
    """What a key must satisfy: ANY group with ALL checks true."""

    condition: str
    key_bits: int
    groups: tuple[tuple[Check, ...], ...]
    offsets: tuple[int, ...] = ()
    """known_substring only: the byte offsets (in characters) that stayed possible."""

    @property
    def max_group(self) -> int:
        return max(len(g) for g in self.groups)

    def fits(self, key: int) -> bool:
        return any(all(c.holds(key, self.key_bits) for c in g) for g in self.groups)

    def evaluations_per_key(self) -> int:
        """Single-block cipher evaluations to test one key against every check."""
        return sum(len(g) for g in self.groups)


def check_condition(condition: str) -> None:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}, got {condition!r}")


def _check_key_bits(key_bits: int) -> None:
    if key_bits not in SUPPORTED_KEY_BITS:
        raise ValueError(f"key_bits must be one of {SUPPORTED_KEY_BITS}, got {key_bits!r}")


def _check_nibbles(values: list[int]) -> None:
    for v in values:
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 0xF:
            raise ValueError(f"Nibbles must be integers 0..15, got {v!r}")


def distinct_pairs(plain: list[int], cipher: list[int]) -> list[tuple[int, int]] | None:
    """Distinct (plain, cipher) pairs in order, or None if no key could produce them.

    Each key is a permutation of the 16 nibbles, so the pairs are impossible when one
    plain nibble meets two cipher nibbles or two plain nibbles meet one cipher nibble.
    """
    forward: dict[int, int] = {}
    backward: dict[int, int] = {}
    for p, c in zip(plain, cipher):
        if forward.setdefault(p, c) != c or backward.setdefault(c, p) != p:
            return None
    return list(forward.items())


def known_beginning_pairs(known_plain: list[int], cipher: list[int]) -> list[tuple[int, int]]:
    """All distinct pairs from a known plaintext prefix (repeats dropped, order kept)."""
    if len(known_plain) > len(cipher):
        raise ValueError("Known plaintext is longer than the ciphertext")
    _check_nibbles(list(known_plain) + list(cipher))
    seen: dict[int, int] = {}
    for p, c in zip(known_plain, cipher):
        if p in seen and seen[p] != c:
            raise ValueError("Known plaintext is inconsistent with ciphertext")
        seen.setdefault(p, c)
    if not seen:
        raise ValueError("No known plaintext pairs available")
    return list(seen.items())


def substring_offsets(known_plain: list[int], cipher: list[int]) -> list[tuple[int, list[tuple[int, int]]]]:
    """Every byte-aligned offset where the known text could sit, with its distinct pairs.

    Offsets are returned in nibbles. Offsets where the pairs contradict any permutation
    are dropped: no key could put the known text there.
    """
    if not known_plain:
        raise ValueError("No known plaintext available")
    if len(known_plain) > len(cipher):
        raise ValueError("Known plaintext is longer than the ciphertext")
    _check_nibbles(list(known_plain) + list(cipher))
    out = []
    for offset in range(0, len(cipher) - len(known_plain) + 1, 2):
        pairs = distinct_pairs(known_plain, cipher[offset : offset + len(known_plain)])
        if pairs is not None:
            out.append((offset, pairs))
    if not out:
        raise ValueError("The known text cannot appear at any position of this ciphertext")
    return out


def high_cipher_nibbles(cipher: list[int]) -> list[int]:
    """Distinct ciphertext nibbles at high (even) positions, in order of first appearance."""
    _check_nibbles(list(cipher))
    if not cipher:
        raise ValueError("No ciphertext available")
    return list(dict.fromkeys(cipher[0::2]))


def full_spec(condition: str, known_plain: list[int] | None, cipher: list[int], key_bits: int) -> AttackSpec:
    """The complete classical constraint for a condition, with no circuit-size caps.

    Used to post-filter quantum candidates and by the classical baseline.
    """
    check_condition(condition)
    _check_key_bits(key_bits)
    known = list(known_plain or [])
    if condition == "known_beginning":
        pairs = known_beginning_pairs(known, cipher)
        return AttackSpec(condition, key_bits, (tuple(PairCheck(p, c) for p, c in pairs),))
    if condition == "known_substring":
        found = substring_offsets(known, cipher)
        groups = tuple(dict.fromkeys(tuple(PairCheck(p, c) for p, c in pairs) for _, pairs in found))
        return AttackSpec(condition, key_bits, groups, offsets=tuple(o // 2 for o, _ in found))
    checks = tuple(PlausibleCheck(c) for c in high_cipher_nibbles(cipher))
    return AttackSpec(condition, key_bits, (checks,))


def circuit_spec(
    condition: str,
    known_plain: list[int] | None,
    cipher: list[int],
    key_bits: int,
    max_pairs: int | None = None,
) -> AttackSpec:
    """The constraint that goes inside the Grover oracle, within the qubit budget.

    known_beginning: the first `max_pairs` distinct pairs (as before).
    known_substring: one group per possible offset (deduplicated). With several groups
        each needs a `hit` qubit, so pairs per group shrink until groups + pairs fit the
        budget. Because a key is marked if ANY offset matches, offsets are never dropped:
        if they cannot all fit, the request is rejected with an explanation.
    ciphertext_only: up to the budget of plausibility checks (classical post-filtering
        applies the rest).

    The marked set is always a superset of the full constraint's set, so classical
    post-filtering after measurement never loses the right key.
    """
    full = full_spec(condition, known_plain, cipher, key_bits)
    budget = ANCILLA_BUDGET[key_bits]
    if max_pairs is None:
        max_pairs = DEFAULT_MAX_PAIRS[key_bits]
    max_pairs = max(1, max_pairs)
    if condition == "known_beginning":
        return AttackSpec(condition, key_bits, (full.groups[0][:max_pairs],))
    if condition == "ciphertext_only":
        return AttackSpec(condition, key_bits, (full.groups[0][:budget],))
    for per_group in range(max_pairs, 0, -1):
        groups = tuple(dict.fromkeys(g[:per_group] for g in full.groups))
        width = len(groups[0]) if len(groups) == 1 else max(len(g) for g in groups) + len(groups)
        if width <= budget:
            return AttackSpec(condition, key_bits, groups, offsets=full.offsets)
    raise ValueError(
        f"The known text could sit at {len(full.groups)} different positions; this "
        f"{key_bits}-bit simulation can only check {budget - 1} at once. Use a longer or "
        "more distinctive known substring."
    )
