"""Read-only evaluation endpoints: aggregated experiment series for the Evaluation page.

These read the experiments runner's stored records (results/); they never run quantum
work on request. Regenerate with `python -m qbreak.experiments.runner`.
"""

from fastapi import APIRouter, HTTPException

from qbreak.api.schemas import EvaluationSeries
from qbreak.experiments.aggregate import SERIES, build_all, build_series
from qbreak.experiments.schema import RESULT_SCHEMA, SCHEMA_VERSION

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("")
def all_series() -> dict:
    """Every series at once, keyed by name."""
    return {"series": SERIES, "data": build_all()}


@router.get("/schema")
def schema() -> dict:
    """The shared experiments-results record schema."""
    return {"schema_version": SCHEMA_VERSION, "fields": RESULT_SCHEMA}


@router.get("/{name}", response_model=EvaluationSeries)
def one_series(name: str) -> dict:
    """One series: scaling, noise, iteration_curve (or iteration-curve), success_rate, comparison, counting."""
    key = name.replace("-", "_")
    if key not in SERIES:
        raise HTTPException(status_code=404, detail=f"Unknown series {name!r}; choose from {list(SERIES)}")
    return build_series(key)
