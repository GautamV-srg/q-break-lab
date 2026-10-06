"""The shared experiments-results schema (defined by Backend A; Backend B conforms to it).

Every experiment run — Grover or Shor — is stored as ONE JSON record of this shape under
`results/<experiment>/<file>.json`, where `results/` is `QBREAK_RESULTS_DIR` (default:
`backend/results`). The aggregator (`qbreak.experiments.aggregate`) collapses records
into chart-ready series for the Evaluation page.

    {
      "schema_version": 1,
      "experiment": "grover_iteration_curve | grover_noise_sweep | grover_fake_backend |
                     grover_scaling | grover_success_rate | grover_counting_accuracy |
                     grover_classical_comparison | shor_noise_sweep | shor_base_success |
                     shor_scaling | shor_classical_comparison | ...",
      "cipher": "miniaes | minirsa",
      "size": {"key_bits": 8}            # or {"modulus": 15}
      "condition": "known_beginning | known_substring | ciphertext_only | null",
      "seed": 1234,                       # int or null
      "success": true,                    # bool or null: did the attack recover the secret?
      "p_success": 0.83,                  # float in [0, 1] or null: probability mass on the secret
      "quantum": {"oracle_calls": 12, "iterations": 3, "qubits": 18, "depth": 540,
                  "transpiled_depth": 1517, "gate_counts": {}},
      "classical": {"evaluations": 128},  # classical tries / trial divisions / multiplications
      "noise": {"model": "ideal | depolarizing | fake_backend", "p": 0.01, "backend": null},
      "extra": {},                        # free-form, experiment-specific values (x-axis etc.)
      "timestamp": "ISO-8601 UTC"
    }

Backend B usage (do not edit this module; import it):

    from qbreak.experiments.schema import make_record, append_record
    append_record(make_record("shor_noise_sweep", "minirsa", {"modulus": 15}, seed=1,
                              success=True, p_success=0.4, quantum={...},
                              noise={"model": "depolarizing", "p": 0.01, "backend": None}))
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

RESULT_SCHEMA: dict = {
    "schema_version": "int (currently 1)",
    "experiment": "str: experiment family, e.g. grover_noise_sweep or shor_base_success",
    "cipher": "'miniaes' | 'minirsa'",
    "size": "{'key_bits': int} | {'modulus': int}",
    "condition": "'known_beginning' | 'known_substring' | 'ciphertext_only' | null",
    "seed": "int | null",
    "success": "bool | null",
    "p_success": "float in [0, 1] | null",
    "quantum": "{oracle_calls?, iterations?, qubits?, depth?, transpiled_depth?, gate_counts?, ...}",
    "classical": "{evaluations?: int, ...}",
    "noise": "{model: 'ideal' | 'depolarizing' | 'fake_backend', p: float | null, backend: str | null}",
    "extra": "dict: experiment-specific values",
    "timestamp": "ISO-8601 UTC string",
}
"""Field-by-field description of a record, for docs and for Backend B to mirror."""

CIPHERS = ("miniaes", "minirsa")
CONDITIONS = ("known_beginning", "known_substring", "ciphertext_only", None)
NOISE_MODELS = ("ideal", "depolarizing", "fake_backend")


def results_dir() -> Path:
    """Where records live: QBREAK_RESULTS_DIR, or backend/results next to the package."""
    env = os.getenv("QBREAK_RESULTS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "results"


def make_record(
    experiment: str,
    cipher: str,
    size: dict,
    *,
    condition: str | None = None,
    seed: int | None = None,
    success: bool | None = None,
    p_success: float | None = None,
    quantum: dict | None = None,
    classical: dict | None = None,
    noise: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a validated record in the shared shape."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "experiment": experiment,
        "cipher": cipher,
        "size": dict(size),
        "condition": condition,
        "seed": seed,
        "success": success,
        "p_success": None if p_success is None else float(p_success),
        "quantum": dict(quantum or {}),
        "classical": dict(classical or {}),
        "noise": {"model": "ideal", "p": None, "backend": None, **(noise or {})},
        "extra": dict(extra or {}),
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    validate_record(record)
    return record


def validate_record(record: dict) -> None:
    """Raise ValueError if a record does not follow the shared schema."""
    missing = set(RESULT_SCHEMA) - set(record)
    if missing:
        raise ValueError(f"record is missing fields: {sorted(missing)}")
    extra = set(record) - set(RESULT_SCHEMA)
    if extra:
        raise ValueError(f"record has unknown fields: {sorted(extra)} (put them under 'extra')")
    if not isinstance(record["experiment"], str) or not re.fullmatch(r"[a-z0-9_]+", record["experiment"]):
        raise ValueError("experiment must be a snake_case string")
    if record["cipher"] not in CIPHERS:
        raise ValueError(f"cipher must be one of {CIPHERS}")
    size = record["size"]
    if not (isinstance(size, dict) and len(size) == 1 and next(iter(size)) in ("key_bits", "modulus") and isinstance(next(iter(size.values())), int)):
        raise ValueError("size must be {'key_bits': int} or {'modulus': int}")
    if record["condition"] not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    p = record["p_success"]
    if p is not None and not 0 <= p <= 1:
        raise ValueError("p_success must be in [0, 1]")
    if record["noise"].get("model") not in NOISE_MODELS:
        raise ValueError(f"noise.model must be one of {NOISE_MODELS}")
    for key in ("quantum", "classical", "noise", "extra"):
        if not isinstance(record[key], dict):
            raise ValueError(f"{key} must be an object")
    json.dumps(record)  # must be JSON-serialisable


def append_record(record: dict, directory: Path | None = None) -> Path:
    """Validate and write one record to results/<experiment>/<timestamp>-<id>.json."""
    validate_record(record)
    folder = (directory or results_dir()) / record["experiment"]
    folder.mkdir(parents=True, exist_ok=True)
    stamp = record["timestamp"].replace(":", "").replace("+0000", "Z").replace("+00:00", "Z")
    path = folder / f"{stamp}-{uuid.uuid4().hex[:8]}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def load_records(directory: Path | None = None, experiment: str | None = None) -> list[dict]:
    """Every valid record under results/ (optionally one experiment), oldest first."""
    root = directory or results_dir()
    if not root.is_dir():
        return []
    folders = [root / experiment] if experiment else [p for p in root.iterdir() if p.is_dir()]
    records = []
    for folder in folders:
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                validate_record(record)
            except (ValueError, OSError):
                continue
            records.append(record)
    return sorted(records, key=lambda r: r["timestamp"])
