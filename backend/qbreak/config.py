"""Environment-driven limits and enabled miniature attack sizes."""

import os


def _integer_list(name: str, default: str) -> list[int]:
    raw = os.getenv(name, default)
    try:
        values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError(f"{name} must be a comma-separated list of integers.") from exc
    if not values:
        raise ValueError(f"{name} must enable at least one value.")
    return values


ENABLED_KEY_BITS: list[int] = _integer_list("QBREAK_KEY_BITS", "4")
ENABLED_MODULI: list[int] = _integer_list("QBREAK_MODULI", "15")
MAX_SHOTS = 4096
MAX_AES_TEXT_CHARS = 200
MAX_RSA_TEXT_CHARS = 80
