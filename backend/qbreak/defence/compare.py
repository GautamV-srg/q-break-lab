"""Compare the three defences and recommend, from measured values plus cited static properties."""

from __future__ import annotations

from typing import Any

from qbreak.config import (
    BB84_BATCH_QUBITS,
    BB84_DEFAULT_RAW_QUBITS,
    BB84_MAX_CHANNEL_NOISE,
    BB84_MAX_QBER_THRESHOLD,
    BB84_MAX_RAW_QUBITS,
    BB84_MIN_QBER_THRESHOLD,
    BB84_MIN_RAW_QUBITS,
    BB84_QBER_THRESHOLD,
    BB84_SAMPLE_FRACTION,
    DEFENCE_METHODS,
    MAX_DEFENCE_TEXT_CHARS,
)
from qbreak.defence.types import BB84_HONESTY_NOTE, CITATIONS, MLKEM_HONESTY_NOTE

METHOD_LABELS = {"aes256": "AES-256", "mlkem": "ML-KEM-768", "bb84": "BB84 QKD"}

STATIC_ROWS: list[dict[str, str]] = [
    {
        "label": "Quantum-safe, and why",
        "aes256": "Yes: Grover only halves the effective strength, 256 → about 128 bits.",
        "mlkem": "Yes: Module-LWE lattice problem; no known efficient quantum attack.",
        "bb84": "Yes: physics; measuring a photon disturbs its state.",
    },
    {"label": "Detects eavesdroppers", "aes256": "No", "mlkem": "No", "bb84": "Yes (QBER)"},
    {
        "label": "Key-exchange problem solved",
        "aes256": "No (needs a way to share the key)",
        "mlkem": "Yes",
        "bb84": "Yes",
    },
    {"label": "Special hardware", "aes256": "None", "mlkem": "None", "bb84": "Photon source + quantum channel"},
    {"label": "Distance", "aes256": "Unlimited", "mlkem": "Unlimited", "bb84": "~100 km fibre without trusted relays"},
    {"label": "Maturity", "aes256": "Standard for decades (FIPS 197)", "mlkem": "NIST FIPS 203 (2024)", "bb84": "Niche deployments"},
]
"""Cited properties that do not depend on this run (the measured rows are added per run)."""

VERDICT_TEXT = {
    "infeasible": "Infeasible (not executed; cited estimate)",
    "not_applicable": "Not applicable (Shor finds nothing to attack)",
    "detected": "Detected (executed; key discarded)",
    "undetected_low_intercept": "Under threshold (executed; leak removed by privacy amplification)",
}

HONESTY_NOTES: list[str] = [
    "No Grover circuit is run on AES-256 and no Shor circuit on ML-KEM: those verdicts are a cited "
    "feasibility estimate and an applicability check, and say so.",
    "ML-KEM: " + MLKEM_HONESTY_NOTE,
    "BB84: " + BB84_HONESTY_NOTE,
    "\"Quantum-safe\" means no known efficient quantum attack, not proven unbreakable.",
]


def _metrics(bundle: dict[str, Any] | None) -> dict[str, Any]:
    return (bundle or {}).get("public_metrics") or {"sizes": {}, "timings_ms": {}}


def _ms(timings: dict[str, float], *names: str) -> str:
    total = sum(timings.get(n, 0.0) for n in names)
    return f"{total:.1f} ms" if any(n in timings for n in names) else "n/a"


def overhead_row(bundles: dict[str, Any], verdicts: dict[str, Any]) -> dict[str, str]:
    """The measured overhead row, from the public metrics each bundle carries."""
    row = {"label": "Overhead (measured)"}
    a = _metrics(bundles.get("aes256"))
    if bundles.get("aes256"):
        s, t = a["sizes"], a["timings_ms"]
        row["aes256"] = f"key {s.get('key_bytes', 32)} B, ciphertext {s.get('ciphertext_bytes', '?')} B, {_ms(t, 'keygen', 'encrypt')}"
    else:
        row["aes256"] = "not run"
    m = _metrics(bundles.get("mlkem"))
    if bundles.get("mlkem"):
        s, t = m["sizes"], m["timings_ms"]
        row["mlkem"] = (
            f"public key {s.get('encapsulation_key_bytes', '?')} B, KEM ct {s.get('kem_ciphertext_bytes', '?')} B, "
            f"ciphertext {s.get('ciphertext_bytes', '?')} B, {_ms(t, 'keygen', 'encaps', 'encrypt')}"
        )
    else:
        row["mlkem"] = "not run"
    b = _metrics(bundles.get("bb84"))
    channel = (bundles.get("bb84") or {}).get("channel") or {}
    if bundles.get("bb84"):
        s, t = b["sizes"], b["timings_ms"]
        raw = s.get("raw_qubits") or channel.get("raw_qubits")
        sifted = s.get("sifted_bits")
        frac = f", sifted {sifted / raw:.0%}" if raw and sifted else ""
        row["bb84"] = f"{raw} raw qubits{frac}, final key {s.get('final_key_bits', 256)} bits, {_ms(t, 'key_exchange', 'encrypt')}"
    elif "bb84" in verdicts:
        ev = verdicts["bb84"]["evidence"]
        row["bb84"] = f"{ev['raw_qubits']} raw qubits, sifted {ev['sifted_bits'] / ev['raw_qubits']:.0%} (re-attack run)"
    else:
        row["bb84"] = "not run"
    return row


def build_comparison(bundles: dict[str, Any], verdicts: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(STATIC_ROWS[0])]
    rows.append({"label": "Re-attack verdict", **{m: VERDICT_TEXT.get(verdicts[m]["verdict"], verdicts[m]["verdict"]) if m in verdicts else "not run" for m in DEFENCE_METHODS}})
    rows.extend(dict(r) for r in STATIC_ROWS[1:5])
    rows.append(overhead_row(bundles, verdicts))
    rows.append(dict(STATIC_ROWS[5]))
    return {"rows": rows}


RULES: dict[str, str] = {
    "layered_default": "Use ML-KEM-768 to agree keys over ordinary networks and AES-256-GCM to encrypt the data "
    "(best together, which is exactly what the ML-KEM defence here does). Reserve BB84 for high-security fixed "
    "links where photon hardware exists and detecting eavesdroppers matters.",
    "bb84_under_threshold": "Use ML-KEM-768 + AES-256-GCM as the default. BB84 still works on fixed links, but "
    "this run's eavesdropper stayed under the QBER threshold: rely on privacy amplification, keep the threshold "
    "conservative and monitor the error rate over time.",
    "bb84_unavailable": "Use ML-KEM-768 to agree keys and AES-256-GCM to encrypt the data. BB84 did not produce a "
    "key in this run (aborted or not requested); it needs photon hardware and a quiet quantum channel.",
}


def recommend(bundles: dict[str, Any], verdicts: dict[str, Any]) -> dict[str, str]:
    """Simple, transparent rules; returns the text and the rule that fired."""
    if verdicts.get("bb84", {}).get("verdict") == "undetected_low_intercept":
        rule = "bb84_under_threshold"
    elif not bundles.get("bb84"):
        rule = "bb84_unavailable"
    else:
        rule = "layered_default"
    return {"text": RULES[rule], "rule": rule}


def defence_info() -> dict[str, Any]:
    """Everything the UI shows before any run: static rows, citations, limits, honesty notes."""
    return {
        "methods": [{"id": m, "label": METHOD_LABELS[m]} for m in DEFENCE_METHODS],
        "comparison": {"rows": [dict(r) for r in STATIC_ROWS]},
        "citations": [{"id": k, "text": v} for k, v in CITATIONS.items()],
        "bb84": bb84_limits(),
        "max_text_chars": MAX_DEFENCE_TEXT_CHARS,
        "honesty_notes": list(HONESTY_NOTES),
        "rules": dict(RULES),
    }


def bb84_limits() -> dict[str, Any]:
    return {
        "defaults": {
            "eve": False,
            "eve_intercept_fraction": 1.0,
            "channel_noise": 0.0,
            "raw_qubits": BB84_DEFAULT_RAW_QUBITS,
            "qber_threshold": BB84_QBER_THRESHOLD,
            "seed": None,
        },
        "min_raw_qubits": BB84_MIN_RAW_QUBITS,
        "max_raw_qubits": BB84_MAX_RAW_QUBITS,
        "batch_qubits": BB84_BATCH_QUBITS,
        "qber_threshold": BB84_QBER_THRESHOLD,
        "min_qber_threshold": BB84_MIN_QBER_THRESHOLD,
        "max_qber_threshold": BB84_MAX_QBER_THRESHOLD,
        "max_channel_noise": BB84_MAX_CHANNEL_NOISE,
        "sample_fraction": BB84_SAMPLE_FRACTION,
        "final_key_bits": 256,
    }
