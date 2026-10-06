"""Collapse experiment records (Grover and Shor) into chart-ready series.

Usage (from backend/):
    python -m qbreak.experiments.aggregate     # writes results/aggregated/*.json and *.csv

The evaluation API endpoints call `build_series` directly on the stored records, so they
never run quantum work on request.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from qbreak.experiments.schema import load_records, results_dir

SERIES_DESCRIPTIONS: dict[str, str] = {
    "scaling": "Qubits and transpiled depth vs problem size (key bits / modulus).",
    "noise": "Attack success probability vs noise level, plus fake IBM backend runs.",
    "iteration_curve": "Measured success vs Grover iterations, with the theoretical sin² envelope.",
    "success_rate": "Attack success rate across keys/seeds and conditions (and Shor per base a).",
    "comparison": "Quantum oracle calls / circuit runs vs classical tries, per problem size.",
    "counting": "Quantum-counting estimate of the number of matching keys vs the true count.",
    "bb84_qber_vs_eve": "BB84: measured QBER vs Eve's intercept fraction, with the theory fraction/4 and the abort threshold.",
    "bb84_qber_vs_noise": "BB84: measured QBER vs channel noise, with the 11% abort threshold.",
    "bb84_key_rate": "BB84: key bits per raw qubit by raw qubits and channel noise. key_rate = delivered key (always 256 bits, 0 when aborted) / raw; secure_rate = estimated extractable secret bits / raw.",
    "defence_overhead": "AES-256 / ML-KEM-768 / BB84: measured sizes and timings by message length.",
}
SERIES = tuple(SERIES_DESCRIPTIONS)


def _size(record: dict) -> int:
    return next(iter(record["size"].values()))


def _size_kind(record: dict) -> str:
    return next(iter(record["size"]))


def _construction(record: dict) -> str | None:
    """Shor circuit construction (swap / permutation / iterative); None for Grover records.

    Scaling and noise rows are split by it: the constructions are different circuits, so a
    mean over them describes none of them. Ideal success rates are pooled, since every
    construction samples the same phase distribution.
    """
    return record["extra"].get("construction")


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def _group(records: list[dict], key) -> dict:
    groups: dict = defaultdict(list)
    for r in records:
        groups[key(r)].append(r)
    return groups


def _scaling(records: list[dict]) -> list[dict]:
    rows = []
    picked = [r for r in records if r["experiment"].endswith("_scaling")]
    key = lambda r: (r["cipher"], _size_kind(r), _size(r), _construction(r))
    for (cipher, kind, size, construction), rs in sorted(_group(picked, key).items(), key=lambda kv: tuple("" if v is None else v for v in kv[0])):
        rows.append({
            "cipher": cipher, "size_kind": kind, "size": size, "construction": construction,
            "qubits": _mean([r["quantum"].get("qubits") for r in rs]),
            "depth": _mean([r["quantum"].get("depth") for r in rs]),
            "transpiled_depth": _mean([r["quantum"].get("transpiled_depth") for r in rs]),
            "iterations": _mean([r["quantum"].get("iterations") for r in rs]),
            "runs": len(rs),
        })
    return rows


def _noise(records: list[dict]) -> list[dict]:
    rows = []
    picked = [r for r in records if r["experiment"].endswith(("_noise_sweep", "_fake_backend"))]
    key = lambda r: (r["cipher"], _size(r), _construction(r), r["noise"]["model"], r["noise"].get("backend"), r["noise"].get("p"), r["extra"].get("iterations"))
    for (cipher, size, construction, model, backend, p, iterations), rs in sorted(_group(picked, key).items(), key=lambda kv: tuple("" if v is None else v for v in kv[0])):
        rows.append({
            "cipher": cipher, "size": size, "construction": construction, "model": model, "backend": backend, "p": p, "iterations": iterations,
            "p_success": _mean([r["p_success"] for r in rs]),
            "success_rate": _mean([float(r["success"]) for r in rs if r["success"] is not None]),
            "baseline": _mean([r["extra"].get("uniform_baseline") for r in rs]),
            "transpiled_depth": _mean([r["quantum"].get("transpiled_depth") for r in rs]),
            "runs": len(rs),
        })
    return rows


def _iteration_curve(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["experiment"] == "grover_iteration_curve"]
    rows = []
    for (size, it), rs in sorted(_group(picked, lambda r: (_size(r), r["extra"]["iterations"])).items()):
        rows.append({
            "key_bits": size, "iterations": it,
            "p_success": _mean([r["p_success"] for r in rs]),
            "theory": _mean([r["extra"].get("theory_p_success") for r in rs]),
            "runs": len(rs),
        })
    return rows


def _success_rate(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["experiment"] in ("grover_success_rate", "shor_base_success", "shor_success_rate")]
    rows = []
    key = lambda r: (r["cipher"], _size(r), r["condition"] or "", r["extra"].get("a", ""))
    for (cipher, size, condition, a), rs in sorted(_group(picked, key).items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        rows.append({
            "cipher": cipher, "size": size, "condition": condition or None, "a": a if a != "" else None,
            "success_rate": _mean([float(r["success"]) for r in rs if r["success"] is not None]),
            "p_success": _mean([r["p_success"] for r in rs]),
            "unique_rate": _mean([float(r["extra"]["unique"]) for r in rs if "unique" in r["extra"]]),
            "runs_to_success": _mean([r["extra"].get("runs_to_success") for r in rs]),
            "runs": len(rs),
        })
    return rows


def _comparison(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["quantum"].get("oracle_calls") is not None and r["classical"].get("evaluations") is not None
              and not r["experiment"].endswith("_scaling")]
    rows = []
    for (cipher, size, condition), rs in sorted(_group(picked, lambda r: (r["cipher"], _size(r), r["condition"] or "")).items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        n = 2**size if cipher == "miniaes" else None
        rows.append({
            "cipher": cipher, "size": size, "condition": condition or None,
            "quantum_oracle_calls": _mean([r["quantum"]["oracle_calls"] for r in rs]),
            "classical_evaluations": _mean([r["classical"]["evaluations"] for r in rs]),
            "theory_classical": (n + 1) / 2 if n else None,
            "theory_grover": (3.141592653589793 / 4) * n**0.5 if n else None,
            "runs": len(rs),
        })
    return rows


def _counting(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["experiment"] == "grover_counting_accuracy"]
    return [
        {"key_bits": _size(r), "condition": r["condition"], "true_m": r["extra"]["true_m"],
         "estimated_m": r["extra"]["estimated_m"], "peak_m_estimate": r["extra"].get("peak_m_estimate"), "correct": r["success"]}
        for r in picked
    ]


def _bb84_qber(records: list[dict], experiment: str, x: str) -> list[dict]:
    picked = [r for r in records if r["experiment"] == experiment]
    rows = []
    for value, rs in sorted(_group(picked, lambda r: r["extra"][x]).items()):
        rows.append({
            x: value,
            "qber": _mean([r["extra"]["qber"] for r in rs]),
            "qber_all_sifted": _mean([r["extra"]["qber_all_sifted"] for r in rs]),
            "theory_qber": _mean([r["extra"]["theory_qber"] for r in rs]),
            "qber_threshold": _mean([r["extra"]["qber_threshold"] for r in rs]),
            "detection_rate": _mean([float(r["extra"]["detected"]) for r in rs]),
            "acceptance_rate": _mean([float(r["extra"]["accepted"]) for r in rs]),
            "runs": len(rs),
        })
    return rows


def _bb84_key_rate(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["experiment"] == "bb84_key_rate"]
    rows = []
    key = lambda r: (r["extra"]["raw_qubits"], r["extra"]["channel_noise"])
    for (raw, noise), rs in sorted(_group(picked, key).items()):
        rows.append({
            "raw_qubits": raw, "channel_noise": noise,
            "key_rate": _mean([r["extra"]["key_rate"] for r in rs]),
            "secure_rate": _mean([r["extra"]["secure_rate"] for r in rs]),
            "sifted_fraction": _mean([r["extra"]["sifted_bits"] / raw for r in rs]),
            "acceptance_rate": _mean([float(r["extra"]["accepted"]) for r in rs]),
            "runs": len(rs),
        })
    return rows


def _defence_overhead(records: list[dict]) -> list[dict]:
    picked = [r for r in records if r["experiment"] == "defence_overhead"]
    rows = []
    for (method, chars), rs in sorted(_group(picked, lambda r: (r["cipher"], r["extra"]["plaintext_chars"])).items()):
        sizes = sorted({k for r in rs for k in r["extra"]["sizes"]})
        timings = sorted({k for r in rs for k in r["extra"]["timings_ms"]})
        rows.append({
            "method": method, "plaintext_chars": chars,
            **{f"size_{k}": _mean([r["extra"]["sizes"].get(k) for r in rs]) for k in sizes},
            **{f"ms_{k}": _mean([r["extra"]["timings_ms"].get(k) for r in rs]) for k in timings},
            "roundtrip_rate": _mean([float(r["success"]) for r in rs if r["success"] is not None]),
            "runs": len(rs),
        })
    return rows


_BUILDERS = {
    "scaling": _scaling,
    "noise": _noise,
    "iteration_curve": _iteration_curve,
    "success_rate": _success_rate,
    "comparison": _comparison,
    "counting": _counting,
    "bb84_qber_vs_eve": lambda records: _bb84_qber(records, "bb84_qber_vs_eve", "eve_intercept_fraction"),
    "bb84_qber_vs_noise": lambda records: _bb84_qber(records, "bb84_qber_vs_noise", "channel_noise"),
    "bb84_key_rate": _bb84_key_rate,
    "defence_overhead": _defence_overhead,
}


def build_series(name: str, records: list[dict] | None = None) -> dict:
    """One chart-ready series: {series, empty, rows, description}."""
    if name not in _BUILDERS:
        raise KeyError(name)
    rows = _BUILDERS[name](load_records() if records is None else records)
    return {"series": name, "empty": not rows, "rows": rows, "description": SERIES_DESCRIPTIONS[name]}


def build_all(records: list[dict] | None = None) -> dict:
    records = load_records() if records is None else records
    return {name: build_series(name, records) for name in SERIES}


def write_aggregates(directory: Path | None = None) -> Path:
    """Write results/aggregated/<series>.json and .csv, plus all.json."""
    out = (directory or results_dir()) / "aggregated"
    out.mkdir(parents=True, exist_ok=True)
    everything = build_all(load_records(directory))
    (out / "all.json").write_text(json.dumps(everything, indent=2), encoding="utf-8")
    for name, series in everything.items():
        (out / f"{name}.json").write_text(json.dumps(series, indent=2), encoding="utf-8")
        rows = series["rows"]
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            if rows:
                # Rows may differ in columns (e.g. defence_overhead per method): use their union.
                writer = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for row in rows for k in row)), restval="")
                writer.writeheader()
                writer.writerows(rows)
    return out


if __name__ == "__main__":
    print(f"wrote {write_aggregates()}")
