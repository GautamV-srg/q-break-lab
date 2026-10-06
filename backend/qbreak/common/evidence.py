"""Convert Qiskit circuits and measurements into JSON-ready evidence."""

from collections.abc import Callable

from qiskit import QuantumCircuit, qasm3

_MAX_QASM_UNITARY_QUBITS = 6


def _truncate(text: str, limit: int, note: str) -> str:
    return text if len(text) <= limit else text[:limit] + note


def circuit_info(
    logical: QuantumCircuit,
    transpiled: QuantumCircuit,
    register_roles: dict[str, str],
    explain_circuits: list[tuple[str, QuantumCircuit]],
) -> dict:
    """Build circuit metrics, readable drawings, and best-effort OpenQASM."""
    drawings = [{"title": "Full attack circuit", "text": _truncate(str(logical.draw(output="text", fold=-1)), 60_000, "\n… drawing truncated …")}]
    drawings.extend(
        {"title": title, "text": _truncate(str(circuit.decompose().draw(output="text", fold=120)), 60_000, "\n… drawing truncated …")}
        for title, circuit in explain_circuits
    )
    widest_unitary = max((inst.operation.num_qubits for inst in transpiled.data if inst.operation.name == "unitary"), default=0)
    if widest_unitary > _MAX_QASM_UNITARY_QUBITS:
        # Exporting would synthesise each 2^k-dimensional block into gates (seconds to minutes from 7 qubits up).
        qasm = f"// OpenQASM export skipped: the circuit contains {widest_unitary}-qubit permutation blocks; exporting them would require synthesising each into thousands of gates."
    else:
        try:
            qasm = _truncate(qasm3.dumps(transpiled), 200_000, "\n// … QASM truncated …")
        except Exception:
            qasm = None
    return {
        "num_qubits": logical.num_qubits,
        "num_clbits": logical.num_clbits,
        "depth": logical.depth() or 0,
        "transpiled_depth": transpiled.depth() or 0,
        "gate_counts": {str(name): int(count) for name, count in transpiled.count_ops().items()},
        "registers": [{"name": register.name, "size": register.size, "role": register_roles.get(register.name, "Quantum work register")} for register in logical.qregs],
        "drawings": drawings,
        "qasm": qasm,
    }


def measurement(counts: dict[str, int], shots: int, interpret: Callable[[str], str]) -> dict:
    """Build a sorted measurement summary with at most sixteen outcomes."""
    top = [
        {"bitstring": bits, "value": int(bits, 2), "count": count, "probability": count / shots, "meaning": interpret(bits)}
        for bits, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:16]
    ]
    return {"shots": shots, "counts": counts, "top": top}
