"""Mosca's quantum-risk inequality: is data encrypted today safe long enough?

- X: years the data must stay secret (its shelf life),
- Y: years needed to migrate the systems to post-quantum cryptography,
- Z: years until a cryptographically relevant quantum computer exists.

If X + Y > Z, an adversary who records encrypted traffic today ("harvest now,
decrypt later") can decrypt it while it still has to be secret. The inputs are
the user's own assumptions; this module makes no forecast of Z.
"""

from __future__ import annotations

from math import isfinite

INEQUALITY = "X + Y > Z"
MAX_YEARS = 200.0

# Illustrative starting values for the UI, not a forecast: a decade-long
# confidentiality need, a multi-year migration, and an assumed Z.
DEFAULTS: dict[str, float] = {"x": 10.0, "y": 6.0, "z": 15.0}

EXPLANATION = (
    "Mosca's inequality: if X (how many years your data must stay confidential) plus Y (how many "
    "years it takes to migrate your systems to quantum-safe cryptography) is greater than Z (how "
    "many years until a cryptographically relevant quantum computer exists), you are at risk: "
    "traffic harvested and stored today could be decrypted while it still has to be secret. Z is "
    "uncertain, so the inputs are your assumptions; this calculator does not forecast them."
)

CITATION = {
    "authors": "Michele Mosca",
    "title": "Cybersecurity in an Era with Quantum Computers: Will We Be Ready?",
    "venue": "IEEE Security & Privacy 16(5), 38–41 (2018)",
    "year": 2018,
    "url": "https://doi.org/10.1109/MSP.2018.3761723",
}


def _years(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number of years")
    if not 0 <= value <= MAX_YEARS:
        raise ValueError(f"{name} must be between 0 and {MAX_YEARS:g} years")
    return float(value)


def _fmt(years: float) -> str:
    return f"{years:g} year" + ("" if years == 1 else "s")


def mosca_risk(x: float, y: float, z: float) -> dict:
    """Evaluate X + Y > Z.

    Returns ``{at_risk, margin, verdict_text, inequality, x, y, z, exposure}``
    where ``margin = Z − (X + Y)`` (negative when at risk) and ``exposure`` is
    the number of years harvested data stays readable-and-sensitive (0 if safe).
    """
    x, y, z = _years("X", x), _years("Y", y), _years("Z", z)
    total = x + y
    margin = z - total
    at_risk = total > z
    if at_risk:
        verdict = (
            f"At risk: X + Y = {_fmt(total)} > Z = {_fmt(z)}. Data encrypted today must stay secret "
            f"for {_fmt(x)} and migration takes {_fmt(y)}, so traffic harvested now could be "
            f"decrypted up to {_fmt(-margin)} before it stops being sensitive. Start migrating to "
            "post-quantum cryptography now."
        )
    elif margin == 0:
        verdict = (
            f"On the boundary: X + Y = Z = {_fmt(z)}, so there is no margin. Any delay in migration "
            "or an earlier quantum computer puts this data at risk."
        )
    else:
        verdict = (
            f"Not at risk under these assumptions: X + Y = {_fmt(total)} ≤ Z = {_fmt(z)}, a margin "
            f"of {_fmt(margin)}. The margin shrinks if migration overruns or Z arrives sooner."
        )
    return {
        "at_risk": at_risk,
        "margin": margin,
        "verdict_text": verdict,
        "inequality": INEQUALITY,
        "x": x,
        "y": y,
        "z": z,
        "exposure": max(0.0, -margin),
    }


def mosca_info() -> dict:
    """Defaults, explanation and citation for the UI."""
    return {
        "inequality": INEQUALITY,
        "defaults": dict(DEFAULTS),
        "max_years": MAX_YEARS,
        "explanation": EXPLANATION,
        "citation": dict(CITATION),
        "default_result": mosca_risk(**DEFAULTS),
    }
