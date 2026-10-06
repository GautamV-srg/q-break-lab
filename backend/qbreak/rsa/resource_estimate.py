"""What breaking real RSA would take: published resource estimates, cited.

Nothing here is measured by Q-Break and no number is invented. Each figure is
either **published** (quoted from the cited paper, for the key size the paper
states) or **formula** (the paper's own published cost formula evaluated at the
requested modulus size). Physical-qubit counts and runtimes are published only
for 2048-bit RSA and are not extrapolated to other sizes.
"""

from __future__ import annotations

from math import log2

from qbreak.rsa.shor import SHOR_SUPPORTED_N, qubit_counts, work_qubits

CITATIONS: dict[str, dict] = {
    "gidney_ekera_2021": {
        "authors": "Craig Gidney and Martin Ekerå",
        "title": "How to factor 2048 bit RSA integers in 8 hours using 20 million noisy qubits",
        "venue": "Quantum 5, 433 (2021); arXiv:1905.09749 (2019)",
        "year": 2021,
        "url": "https://doi.org/10.22331/q-2021-04-15-433",
    },
    "gidney_2025": {
        "authors": "Craig Gidney",
        "title": "How to factor 2048 bit RSA integers with less than a million noisy qubits",
        "venue": "arXiv:2505.15917 (2025)",
        "year": 2025,
        "url": "https://arxiv.org/abs/2505.15917",
    },
    "shor_1997": {
        "authors": "Peter W. Shor",
        "title": (
            "Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms "
            "on a Quantum Computer"
        ),
        "venue": "SIAM Journal on Computing 26(5), 1484–1509 (1997); arXiv:quant-ph/9508027",
        "year": 1997,
        "url": "https://arxiv.org/abs/quant-ph/9508027",
    },
    "beauregard_2003": {
        "authors": "Stéphane Beauregard",
        "title": "Circuit for Shor's algorithm using 2n+3 qubits",
        "venue": "Quantum Information and Computation 3(2), 175–185 (2003); arXiv:quant-ph/0205095",
        "year": 2003,
        "url": "https://arxiv.org/abs/quant-ph/0205095",
    },
    "griffiths_niu_1996": {
        "authors": "Robert B. Griffiths and Chi-Sheng Niu",
        "title": "Semiclassical Fourier Transform for Quantum Computation",
        "venue": "Physical Review Letters 76, 3228 (1996); arXiv:quant-ph/9511007",
        "year": 1996,
        "url": "https://arxiv.org/abs/quant-ph/9511007",
    },
}

HARDWARE_ASSUMPTIONS = {
    "physical_gate_error_rate": 1e-3,
    "surface_code_cycle_time_us": 1.0,
    "control_reaction_time_us": 10.0,
    "connectivity": "square grid, nearest-neighbour",
    "citation": "gidney_ekera_2021",
    "quote": (
        "physical gate error rate of 10^-3, a surface code cycle time of 1 microsecond, and a "
        "reaction time of 10 microseconds"
    ),
}

HONESTY_NOTE = (
    "Q-Break factors toy moduli (N ≤ 77) on a classical simulator. The real-scale figures below "
    "are quoted from, or computed with the formulas of, the cited papers; Q-Break did not measure "
    "them, and no physical-qubit or runtime figure is extrapolated beyond the 2048-bit case the "
    "papers report."
)

MIN_BITS, MAX_BITS = 8, 16384


def _published_2048() -> list[dict]:
    return [
        {
            "name": "Physical qubits (RSA-2048)",
            "value": 20_000_000,
            "unit": "noisy physical qubits",
            "kind": "published",
            "citation": "gidney_ekera_2021",
            "quote": "factor 2048 bit RSA integers in 8 hours using 20 million noisy qubits",
        },
        {
            "name": "Runtime (RSA-2048)",
            "value": 8,
            "unit": "hours",
            "kind": "published",
            "citation": "gidney_ekera_2021",
            "quote": "factor 2048 bit RSA integers in 8 hours using 20 million noisy qubits",
        },
        {
            "name": "Physical qubits, later estimate (RSA-2048)",
            "value": 1_000_000,
            "unit": "noisy physical qubits (upper bound: 'less than a million')",
            "kind": "published",
            "citation": "gidney_2025",
            "quote": (
                "a 2048 bit RSA integer could be factored in less than a week by a quantum "
                "computer with less than a million noisy qubits"
            ),
        },
        {
            "name": "Runtime, later estimate (RSA-2048)",
            "value": 7,
            "unit": "days (upper bound: 'less than a week')",
            "kind": "published",
            "citation": "gidney_2025",
            "quote": "factored in less than a week",
        },
    ]


def _formula_figures(bits: int) -> list[dict]:
    lg = log2(bits)
    quote = (
        "3n + 0.002n lg n logical qubits, 0.3n^3 + 0.0005n^3 lg n Toffolis, and "
        "500n^2 + n^2 lg n measurement depth"
    )
    return [
        {
            "name": "Logical qubits",
            "value": round(3 * bits + 0.002 * bits * lg),
            "unit": "logical qubits",
            "kind": "formula",
            "formula": "3n + 0.002·n·lg n",
            "citation": "gidney_ekera_2021",
            "quote": quote,
        },
        {
            "name": "Toffoli gates",
            "value": round(0.3 * bits**3 + 0.0005 * bits**3 * lg),
            "unit": "Toffoli gates",
            "kind": "formula",
            "formula": "0.3·n³ + 0.0005·n³·lg n",
            "citation": "gidney_ekera_2021",
            "quote": quote,
        },
        {
            "name": "Measurement depth",
            "value": round(500 * bits**2 + bits**2 * lg),
            "unit": "sequential measurement layers",
            "kind": "formula",
            "formula": "500·n² + n²·lg n",
            "citation": "gidney_ekera_2021",
            "quote": quote,
        },
        {
            "name": "Logical qubits, compact textbook circuit",
            "value": 2 * bits + 3,
            "unit": "logical qubits (no error-correction overhead)",
            "kind": "formula",
            "formula": "2n + 3",
            "citation": "beauregard_2003",
            "quote": "Circuit for Shor's algorithm using 2n+3 qubits",
        },
    ]


def toy_instances() -> list[dict]:
    """Q-Break's own simulated circuits, for the side-by-side with real scale."""
    return [
        {
            "n": n,
            "modulus_bits": n.bit_length(),
            "work_qubits": work_qubits(n),
            "qubits_register_2n": qubit_counts(n)["register_2n"],
            "qubits_iterative": qubit_counts(n)["iterative"],
        }
        for n in SHOR_SUPPORTED_N
    ]


def estimate_rsa_resources(modulus_bits: int = 2048) -> dict:
    """Cited resource estimate for factoring an RSA modulus of ``modulus_bits`` bits."""
    if isinstance(modulus_bits, bool) or not isinstance(modulus_bits, int):
        raise ValueError("modulus_bits must be an integer")
    if not MIN_BITS <= modulus_bits <= MAX_BITS:
        raise ValueError(f"modulus_bits must be between {MIN_BITS} and {MAX_BITS}")
    figures = _formula_figures(modulus_bits)
    if modulus_bits == 2048:
        figures = _published_2048() + figures
    largest_toy = max(SHOR_SUPPORTED_N)
    return {
        "modulus_bits": modulus_bits,
        "figures": figures,
        "published_physical_estimates_available": modulus_bits == 2048,
        "physical_estimate_note": (
            "Physical-qubit and runtime estimates are published for RSA-2048 only; they are not "
            "extrapolated to other sizes."
            if modulus_bits != 2048
            else "Published physical-qubit and runtime figures for RSA-2048 are included."
        ),
        "hardware_assumptions": HARDWARE_ASSUMPTIONS,
        "scaling": {
            "gate_complexity": "O((log N)^3) = O(n^3) with schoolbook modular arithmetic",
            "citation": "shor_1997",
            "relative_to_largest_toy": {
                "toy_modulus": largest_toy,
                "toy_bits": largest_toy.bit_length(),
                "cubic_cost_ratio": round((modulus_bits / largest_toy.bit_length()) ** 3),
            },
        },
        "iterative_phase_estimation": {
            "note": (
                "Q-Break's iterative construction reuses one counting qubit (semiclassical Fourier "
                "transform), the same idea behind the 2n + 3 qubit count of compact circuits."
            ),
            "citations": ["griffiths_niu_1996", "beauregard_2003"],
        },
        "toy_instances": toy_instances(),
        "citations": CITATIONS,
        "honesty_note": HONESTY_NOTE,
    }
