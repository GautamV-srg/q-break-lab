"""Defence experiments, written as records in the shared results schema.

Registered in ``qbreak.experiments.runner`` (``--only bb84_qber_vs_eve`` etc.) and collapsed
into series by ``qbreak.experiments.aggregate``:

- ``bb84_qber_vs_eve``   QBER vs Eve's intercept fraction 0→1, with the theory fraction/4
- ``bb84_qber_vs_noise`` QBER vs channel noise, with the 11% threshold
- ``bb84_key_rate``      final key bits per raw qubit, by raw qubits and noise
- ``defence_overhead``   sizes and timings of the three defences, by message length

Records use ``cipher`` = ``bb84`` / ``aes256`` / ``mlkem`` and ``size`` = {"key_bits": 256}
(every defence ends in a 256-bit AES key). Experiment-specific values sit under ``extra``.
"""

from __future__ import annotations

from qbreak.config import BB84_QBER_THRESHOLD
from qbreak.defence.aes256 import protect_aes256
from qbreak.defence.bb84 import run_exchange, theory_qber
from qbreak.defence.mlkem import protect_mlkem
from qbreak.experiments.schema import make_record

BASE_SEED = 1234
SIZE = {"key_bits": 256}
EVE_FRACTIONS: tuple[float, ...] = tuple(round(0.1 * i, 1) for i in range(11))
NOISE_LEVELS: tuple[float, ...] = (0.0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
RAW_SIZES: tuple[int, ...] = (256, 512, 1024, 2048, 4096)
OVERHEAD_LENGTHS: tuple[int, ...] = (16, 100, 1000)


def _bb84_record(experiment: str, ex, seed: int, **extra) -> dict:
    return make_record(
        experiment, "bb84", SIZE, seed=seed, success=ex.accepted,
        quantum={"qubits": ex.max_width, "circuits": sum(ex.stage_circuits.values()), "raw_qubits": ex.raw_bits},
        noise={"model": "depolarizing" if ex.channel_noise else "ideal", "p": ex.channel_noise or None, "backend": None},
        extra={
            "eve_intercept_fraction": ex.eve_intercept_fraction if ex.eve else 0.0,
            "channel_noise": ex.channel_noise,
            "qber": ex.qber,
            "qber_all_sifted": ex.qber_all_sifted,
            "theory_qber": theory_qber(ex.eve_intercept_fraction if ex.eve else 0.0, ex.channel_noise),
            "qber_threshold": ex.qber_threshold,
            "detected": ex.qber > ex.qber_threshold,
            "accepted": ex.accepted,
            "raw_qubits": ex.raw_bits,
            "sifted_bits": ex.sifted_bits,
            "sample_bits": ex.sample_bits,
            "final_key_bits": ex.final_key_bits,
            "secure_bits_estimate": max(ex.secure_bits_estimate, 0),
            "sim_time_ms": ex.sim_time_ms,
            **extra,
        },
    )


def bb84_qber_vs_eve(fractions: tuple[float, ...] = EVE_FRACTIONS, raw_qubits: int = 2048, repeats: int = 5, seed: int = BASE_SEED) -> list[dict]:
    """Measured QBER against Eve's intercept fraction (theory: fraction / 4)."""
    records = []
    for i, fraction in enumerate(fractions):
        for r in range(repeats):
            s = seed + 100 * i + r
            ex = run_exchange(raw_qubits, eve=fraction > 0, eve_intercept_fraction=fraction, seed=s)
            records.append(_bb84_record("bb84_qber_vs_eve", ex, s))
    return records


def bb84_qber_vs_noise(levels: tuple[float, ...] = NOISE_LEVELS, raw_qubits: int = 2048, repeats: int = 5, seed: int = BASE_SEED) -> list[dict]:
    """Measured QBER against channel noise, next to the abort threshold."""
    records = []
    for i, p in enumerate(levels):
        for r in range(repeats):
            s = seed + 100 * i + r
            ex = run_exchange(raw_qubits, channel_noise=p, seed=s)
            records.append(_bb84_record("bb84_qber_vs_noise", ex, s))
    return records


def bb84_key_rate(raw_sizes: tuple[int, ...] = RAW_SIZES, levels: tuple[float, ...] = (0.0, 0.02, 0.05), repeats: int = 3, seed: int = BASE_SEED) -> list[dict]:
    """Final key bits per raw qubit (0 when the exchange aborts), by raw qubits and noise."""
    records = []
    for i, raw in enumerate(raw_sizes):
        for j, p in enumerate(levels):
            for r in range(repeats):
                s = seed + 1000 * i + 100 * j + r
                ex = run_exchange(raw, channel_noise=p, seed=s)
                records.append(_bb84_record("bb84_key_rate", ex, s, key_rate=ex.final_key_bits / raw, secure_rate=max(ex.secure_bits_estimate, 0) / raw))
    return records


def defence_overhead(lengths: tuple[int, ...] = OVERHEAD_LENGTHS, repeats: int = 5, seed: int = BASE_SEED) -> list[dict]:
    """Sizes and timings of AES-256, ML-KEM-768 and BB84, by message length."""
    from qbreak.defence.bb84 import protect_bb84

    records = []
    for i, n in enumerate(lengths):
        message = ("Quantum-safe hello! " * (n // 20 + 1))[:n]
        for r in range(repeats):
            s = seed + 100 * i + r
            for method, result in (
                ("aes256", protect_aes256(message)),
                ("mlkem", protect_mlkem(message)),
                ("bb84", protect_bb84(message, seed=s, raw_qubits=1024 if n < 1000 else 2048)),
            ):
                records.append(make_record(
                    "defence_overhead", method, SIZE, seed=s, success=result.roundtrip_ok,
                    extra={"plaintext_chars": n, "status": result.status, "sizes": result.sizes,
                           "timings_ms": result.timings_ms, "qber_threshold": BB84_QBER_THRESHOLD},
                ))
    return records


EXPERIMENTS = {
    "bb84_qber_vs_eve": bb84_qber_vs_eve,
    "bb84_qber_vs_noise": bb84_qber_vs_noise,
    "bb84_key_rate": bb84_key_rate,
    "defence_overhead": defence_overhead,
}

QUICK_ARGS: dict[str, dict] = {
    "bb84_qber_vs_eve": {"fractions": (0.0, 0.5, 1.0), "raw_qubits": 1024, "repeats": 2},
    "bb84_qber_vs_noise": {"levels": (0.0, 0.05, 0.15), "raw_qubits": 1024, "repeats": 2},
    "bb84_key_rate": {"raw_sizes": (512, 1024), "levels": (0.0,), "repeats": 1},
    "defence_overhead": {"lengths": (16,), "repeats": 1},
}
