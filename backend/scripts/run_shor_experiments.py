"""Run the Shor experiments and write records + chart series.

Usage (from backend/):
    python scripts/run_shor_experiments.py                 # everything
    python scripts/run_shor_experiments.py --only scaling noise --quick

Records go to <out>/<experiment>/<name>.json in the shared results schema
(see qbreak.rsa.experiments); the chart series go to <out>/shor_series.json.
The fake-backend runs need ``pip install qiskit-ibm-runtime``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qbreak.rsa import experiments as ex  # noqa: E402

EXPERIMENTS = ("scaling", "noise", "fake_backend", "base_success", "runs_to_factor")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "results")
    parser.add_argument("--only", nargs="+", choices=EXPERIMENTS, default=list(EXPERIMENTS))
    parser.add_argument("--quick", action="store_true", help="one seed, fewer shots and trials")
    args = parser.parse_args()

    seeds = (0,) if args.quick else (0, 1, 2)
    shots = 256 if args.quick else 1024
    jobs = {
        "scaling": lambda: ex.scaling(),
        "noise": lambda: ex.noise_sweep(seeds=seeds, shots=shots),
        "fake_backend": lambda: ex.fake_backend_runs(seeds=seeds, shots=shots),
        "base_success": lambda: ex.base_success(seeds=seeds, shots=shots),
        "runs_to_factor": lambda: ex.runs_to_factor(trials=5 if args.quick else 20),
    }
    for name in args.only:
        t0 = time.perf_counter()
        try:
            records = jobs[name]()
        except ImportError as exc:
            print(f"{name}: skipped ({exc})")
            continue
        for file_name, record in records:
            ex.write_record(record, args.out, file_name)
        print(f"{name}: {len(records)} records in {time.perf_counter() - t0:.1f} s")

    series = ex.shor_series(ex.load_records(args.out))
    path = args.out / "shor_series.json"
    path.write_text(json.dumps(series, indent=2) + "\n", encoding="utf-8")
    print(f"series -> {path}")


if __name__ == "__main__":
    main()
