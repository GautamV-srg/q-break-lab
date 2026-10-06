"""Shared pytest configuration for Q-Break."""

import os

# Quantum counting adds ~2-3 s to every 4-bit attack; keep the suite fast. Counting tests
# call it directly or pass counting=True, so they still exercise it.
os.environ.setdefault("QBREAK_COUNTING_MAX_KEY_BITS", "0")
