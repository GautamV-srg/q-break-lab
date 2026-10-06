"""Defence orchestration: protect (organization side) and the blind re-attack (attacker side)."""

from __future__ import annotations

from qbreak.api.schemas import ProtectRequest, ReattackRequest
from qbreak.defence.compare import build_comparison, recommend


def protect(req: ProtectRequest) -> dict:
    """Apply each requested defence to the message. Returns public bundles, never keys."""
    from qbreak.defence.aes256 import protect_aes256
    from qbreak.defence.bb84 import protect_bb84
    from qbreak.defence.mlkem import protect_mlkem

    results: dict[str, dict] = {}
    for method in req.methods:
        if method == "aes256":
            results["aes256"] = protect_aes256(req.plaintext).to_dict()
        elif method == "mlkem":
            results["mlkem"] = protect_mlkem(req.plaintext).to_dict()
        else:
            o = req.bb84
            results["bb84"] = protect_bb84(
                req.plaintext,
                eve=o.eve,
                eve_intercept_fraction=o.eve_intercept_fraction,
                channel_noise=o.channel_noise,
                raw_qubits=o.raw_qubits,
                qber_threshold=o.qber_threshold,
                seed=o.seed,
            ).to_dict()
    return {"results": results}


def reattack(req: ReattackRequest) -> dict:
    """The same quantum adversary against each public bundle; then compare and recommend."""
    from qbreak.defence.reattack import (
        attack_aes256,
        attack_bb84,
        attack_mlkem,
        original_context,
    )

    bundles = {name: (None if b is None else b.model_dump(exclude_none=True)) for name, b in (
        ("aes256", req.bundles.aes256), ("mlkem", req.bundles.mlkem), ("bb84", req.bundles.bb84))}
    verdicts: dict[str, dict] = {}
    if bundles["aes256"]:
        verdicts["aes256"] = attack_aes256(bundles["aes256"])
    if bundles["mlkem"]:
        verdicts["mlkem"] = attack_mlkem(bundles["mlkem"])
    if "bb84" in req.bundles.model_fields_set:
        a = req.bb84_attack
        verdicts["bb84"] = attack_bb84(
            bundles["bb84"],
            eve_intercept_fraction=a.eve_intercept_fraction,
            channel_noise=a.channel_noise,
            raw_qubits=a.raw_qubits,
            seed=a.seed,
        )
    if not verdicts:
        raise ValueError("Nothing to re-attack: pass at least one non-null bundle (bb84 may be null)")
    return {
        "verdicts": verdicts,
        "comparison": build_comparison(bundles, verdicts),
        "recommendation": recommend(bundles, verdicts),
        "before": original_context(None if req.original_attack is None else req.original_attack.model_dump()),
    }
