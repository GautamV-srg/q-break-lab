"""Round 3 — Defence: protect, blind re-attack, compare."""

from __future__ import annotations

import ast
import base64
import inspect
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import qbreak.defence.aes256 as aes256_mod
import qbreak.defence.bb84 as bb84_mod
import qbreak.defence.mlkem as mlkem_mod
import qbreak.defence.reattack as reattack_mod
from qbreak.api.main import app
from qbreak.api.schemas import (
    DefenceInfoResponse,
    ProtectResponse,
    ReattackResponse,
)
from qbreak.defence.aes256 import protect_aes256
from qbreak.defence.bb84 import eavesdrop_exchange, protect_bb84, run_exchange
from qbreak.defence.mlkem import derive_aes_key, protect_mlkem
from qbreak.defence.types import SECRET_FIELD_NAMES, gcm_open, unb64
from qbreak.experiments.aggregate import build_series
from qbreak.rsa.shor import shor_input_stage

client = TestClient(app)
MESSAGE = "Meet at the north gate at 9 — bring the ledger."


def _keys(obj: object) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def _secret_forms(secret: bytes) -> list[str]:
    return [base64.b64encode(secret).decode(), secret.hex(), secret.hex().upper()]


# --- protect: round trips --------------------------------------------------


def test_aes256_roundtrip() -> None:
    r = protect_aes256(MESSAGE)
    assert r.status == "protected" and r.roundtrip_ok
    assert r.sizes["key_bytes"] == 32 and r.sizes["nonce_bytes"] == 12
    assert r.sizes["ciphertext_bytes"] == len(MESSAGE.encode()) + 16
    assert len(unb64(r.bundle["nonce_b64"])) == 12
    assert {"keygen", "encrypt"} <= set(r.timings_ms)


def test_mlkem_roundtrip_and_sizes() -> None:
    r = protect_mlkem(MESSAGE)
    assert r.status == "protected" and r.roundtrip_ok
    assert r.sizes["encapsulation_key_bytes"] == 1184  # FIPS 203, ML-KEM-768
    assert r.sizes["kem_ciphertext_bytes"] == 1088
    assert r.sizes["shared_secret_bytes"] == 32
    assert {"keygen", "encaps", "encrypt", "decaps"} <= set(r.timings_ms)
    assert any("educational" in step.lower() for step in r.steps)


def test_mlkem_bundle_decrypts_only_with_the_shared_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, bytes] = {}
    real = mlkem_mod.ML_KEM_768.encaps

    def spy(ek: bytes):
        secret, ct = real(ek)
        captured["secret"] = secret
        return secret, ct

    monkeypatch.setattr(mlkem_mod.ML_KEM_768, "encaps", spy)
    r = protect_mlkem(MESSAGE)
    b = r.bundle
    plain = gcm_open(derive_aes_key(captured["secret"]), unb64(b["nonce_b64"]), unb64(b["ciphertext_b64"]))
    assert plain.decode() == MESSAGE


def test_bb84_clean_channel_accepted_with_matching_keys() -> None:
    ex = run_exchange(1024, seed=11)
    assert ex.qber == 0 and ex.qber_all_sifted == 0
    assert ex.accepted and ex.alice_key == ex.bob_key and len(ex.alice_key) == 32
    assert ex.final_key_bits == 256
    r = protect_bb84(MESSAGE, seed=11)
    assert r.status == "protected" and r.roundtrip_ok and r.bundle is not None


def test_bb84_full_intercept_aborted_near_25_percent() -> None:
    ex = run_exchange(2048, eve=True, eve_intercept_fraction=1.0, seed=5)
    assert not ex.accepted and ex.alice_key is None
    assert abs(ex.qber - 0.25) < 0.06
    assert abs(ex.qber_all_sifted - 0.25) < 0.04
    r = protect_bb84(MESSAGE, eve=True, seed=5)
    assert r.status == "aborted" and r.bundle is None and not r.roundtrip_ok
    assert "discard" in r.extra["qkd"]["reason"]


def test_bb84_qber_scales_with_intercept_fraction() -> None:
    qbers = [run_exchange(2048, eve=f > 0, eve_intercept_fraction=f, seed=21).qber_all_sifted for f in (0.0, 0.4, 1.0)]
    assert qbers[0] < qbers[1] < qbers[2]
    assert abs(qbers[1] - 0.10) < 0.04


def test_bb84_channel_noise_raises_qber() -> None:
    ex = run_exchange(2048, channel_noise=0.15, seed=3)
    assert abs(ex.qber_all_sifted - 0.15) < 0.04
    assert not ex.accepted


def test_bb84_runs_through_the_shared_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    real = bb84_mod.run_circuit

    def spy(qc, **kwargs):
        calls.append((qc.num_qubits, kwargs.get("method")))
        return real(qc, **kwargs)

    monkeypatch.setattr(bb84_mod, "run_circuit", spy)
    run_exchange(256, eve=True, seed=1)
    assert calls and all(method == "stabilizer" for _, method in calls)
    assert max(width for width, _ in calls) <= 64


def test_bb84_preview_and_evidence() -> None:
    r = protect_bb84(MESSAGE, seed=2)
    qkd = r.extra["qkd"]
    assert len(qkd["photon_preview"]) == 16
    assert set(qkd["photon_preview"][0]) == {"alice_bit", "alice_basis", "eve_basis", "bob_basis", "bob_bit", "kept", "error"}
    ev = r.extra["evidence"]
    assert ev["simulator_method"] == "stabilizer" and ev["circuits"] >= 1 and ev["qubits_per_circuit"] <= 64
    assert ev["example_circuit"]["drawing"] and ev["example_circuit"]["qasm"].startswith("OPENQASM")


def test_bb84_validates_limits() -> None:
    with pytest.raises(ValueError):
        run_exchange(10)
    with pytest.raises(ValueError):
        run_exchange(1024, eve=True, eve_intercept_fraction=1.5)


# --- blindness ---------------------------------------------------------------


def test_protect_response_contains_no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets: list[bytes] = []
    real_aes_key = aes256_mod.AESGCM.generate_key

    class SpyAESGCM:  # AESGCM is a Rust type; swap the module's reference instead
        @staticmethod
        def generate_key(bit_length: int) -> bytes:
            key = real_aes_key(bit_length)
            secrets.append(key)
            return key

    real_encaps = mlkem_mod.ML_KEM_768.encaps
    real_keygen = mlkem_mod.ML_KEM_768.keygen

    def spy_encaps(ek: bytes):
        ss, ct = real_encaps(ek)
        secrets.extend([ss, derive_aes_key(ss)])
        return ss, ct

    def spy_keygen():
        ek, dk = real_keygen()
        secrets.append(dk)
        return ek, dk

    real_amplify = bb84_mod.privacy_amplify

    def spy_amplify(bits):
        key = real_amplify(bits)
        secrets.append(key)
        return key

    monkeypatch.setattr(aes256_mod, "AESGCM", SpyAESGCM)
    monkeypatch.setattr(mlkem_mod.ML_KEM_768, "encaps", spy_encaps)
    monkeypatch.setattr(mlkem_mod.ML_KEM_768, "keygen", spy_keygen)
    monkeypatch.setattr(bb84_mod, "privacy_amplify", spy_amplify)

    res = client.post("/api/defence/protect", json={"plaintext": MESSAGE, "bb84": {"seed": 4}})
    assert res.status_code == 200
    body = res.json()
    assert len(secrets) >= 5  # AES key, ML-KEM dk + secret + derived key, BB84 keys
    text = json.dumps(body)
    for secret in secrets:
        for form in _secret_forms(secret):
            assert form not in text
    for result in body["results"].values():
        bundle = result["bundle"]
        assert bundle is not None
        assert SECRET_FIELD_NAMES.isdisjoint(_keys(bundle))
        assert MESSAGE not in json.dumps(bundle)
    assert SECRET_FIELD_NAMES.isdisjoint(_keys(body) - {"plaintext_bytes"})


def _bundles() -> dict:
    body = client.post("/api/defence/protect", json={"plaintext": MESSAGE, "bb84": {"seed": 8}}).json()
    return {m: r["bundle"] for m, r in body["results"].items()}


@pytest.mark.parametrize("field", ["key_b64", "plaintext", "shared_secret_b64", "decapsulation_key_b64", "bb84_key"])
def test_reattack_rejects_secret_fields_in_bundles(field: str) -> None:
    bundles = _bundles()
    for method in ("aes256", "mlkem", "bb84"):
        tampered = {**bundles, method: {**bundles[method], field: "AAAA"}}
        res = client.post("/api/defence/reattack", json={"bundles": tampered})
        assert res.status_code == 422, (method, field)


def test_reattack_rejects_top_level_secrets() -> None:
    bundles = _bundles()
    assert client.post("/api/defence/reattack", json={"bundles": bundles, "plaintext": MESSAGE}).status_code == 422
    assert client.post("/api/defence/reattack", json={"bundles": bundles, "key": "00"}).status_code == 422
    channel = {**bundles["bb84"]["channel"], "alice_bits": [0, 1]}
    tampered = {**bundles, "bb84": {**bundles["bb84"], "channel": channel}}
    assert client.post("/api/defence/reattack", json={"bundles": tampered}).status_code == 422


def test_reattack_module_never_imports_secrets() -> None:
    src = Path(reattack_mod.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            imported |= {f"{node.module}.{alias.name}" for alias in node.names}
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
    forbidden_modules = ("qbreak.defence.aes256", "qbreak.defence.mlkem", "kyber_py", "cryptography", "qbreak.services")
    assert not any(name.startswith(forbidden_modules) for name in imported), imported
    forbidden_names = {"protect_bb84", "run_exchange", "gcm_open", "gcm_seal", "privacy_amplify", "derive_aes_key", "AESGCM"}
    assert forbidden_names.isdisjoint(name.rsplit(".", 1)[-1] for name in imported)


def test_reattack_signatures_have_no_secrets() -> None:
    forbidden = {"key", "plaintext", "shared_secret", "decapsulation_key", "secret", "alice_bits", "final_key"}
    for fn in (reattack_mod.attack_aes256, reattack_mod.attack_mlkem, reattack_mod.attack_bb84, eavesdrop_exchange, shor_input_stage):
        assert forbidden.isdisjoint(inspect.signature(fn).parameters)


def test_eavesdrop_view_carries_no_bits() -> None:
    view = eavesdrop_exchange(256, seed=1)
    assert {"alice_bit", "bob_bit"}.isdisjoint(_keys(view["photon_preview"]))
    assert {"alice_key", "bob_key"}.isdisjoint(_keys(view))


# --- re-attack verdicts --------------------------------------------------------


def test_verdicts_match_the_brief() -> None:
    res = client.post("/api/defence/reattack", json={
        "bundles": _bundles(), "bb84_attack": {"seed": 9}, "original_attack": {"cipher": "miniaes"},
    })
    assert res.status_code == 200
    body = res.json()
    ReattackResponse.model_validate(body)
    v = body["verdicts"]
    assert v["aes256"]["verdict"] == "infeasible" and v["aes256"]["executed"] is False
    assert v["aes256"]["evidence"]["required"]["logical_qubits"] == 6681
    assert "GLRS16" in v["aes256"]["citations"]
    assert v["mlkem"]["verdict"] == "not_applicable" and v["mlkem"]["executed"] is False
    assert v["mlkem"]["evidence"]["shor_input_stage"]["applicable"] is False
    assert "no known efficient quantum attack" in v["mlkem"]["explanation"]
    assert "unbreakable" not in json.dumps(v["mlkem"]).lower()
    assert "FIPS203" in v["mlkem"]["citations"]
    assert v["bb84"]["verdict"] == "detected" and v["bb84"]["executed"] is True
    assert v["bb84"]["evidence"]["qber"] > 0.11
    assert body["before"]["cipher"] == "miniaes"
    labels = [row["label"] for row in body["comparison"]["rows"]]
    assert "Re-attack verdict" in labels and "Overhead (measured)" in labels and "Detects eavesdroppers" in labels
    assert body["recommendation"]["rule"] == "layered_default"


def test_bb84_low_intercept_is_reported_honestly() -> None:
    res = client.post("/api/defence/reattack", json={"bundles": {"bb84": None}, "bb84_attack": {"eve_intercept_fraction": 0.1, "seed": 4}})
    assert res.status_code == 200
    v = res.json()["verdicts"]["bb84"]
    assert v["verdict"] == "undetected_low_intercept"
    assert v["evidence"]["expected_eve_info_bits"] > 0
    assert "privacy amplification" in v["explanation"]
    assert res.json()["recommendation"]["rule"] == "bb84_under_threshold"


def test_shor_input_stage() -> None:
    assert shor_input_stage({"n": 15, "e": 3})["applicable"] is True
    assert shor_input_stage({"encapsulation_key_b64": "AAAA", "kem_ciphertext_b64": "AAAA"})["applicable"] is False


# --- API contract ---------------------------------------------------------------


def test_protect_contract_shapes() -> None:
    res = client.post("/api/defence/protect", json={"plaintext": "Hi", "methods": ["mlkem", "bb84"], "bb84": {"eve": True, "seed": 1}})
    assert res.status_code == 200
    body = ProtectResponse.model_validate(res.json())
    assert body.results.aes256 is None
    assert body.results.mlkem.parameter_set == "ML-KEM-768"
    assert body.results.bb84.status == "aborted" and body.results.bb84.bundle is None
    assert body.results.bb84.qkd.qber > 0.11


def test_protect_validation() -> None:
    assert client.post("/api/defence/protect", json={"plaintext": ""}).status_code == 422
    assert client.post("/api/defence/protect", json={"plaintext": "x" * 1001}).status_code == 422
    assert client.post("/api/defence/protect", json={"plaintext": "x", "methods": ["rsa4096"]}).status_code == 422
    assert client.post("/api/defence/protect", json={"plaintext": "x", "bb84": {"raw_qubits": 10**6}}).status_code == 422
    assert client.post("/api/defence/reattack", json={"bundles": {}}).status_code == 422


def test_info_config_and_openapi() -> None:
    info = client.get("/api/defence/info")
    assert info.status_code == 200
    DefenceInfoResponse.model_validate(info.json())
    assert info.json()["bb84"]["qber_threshold"] == 0.11
    config = client.get("/api/config").json()
    assert config["defence_methods"] == ["aes256", "mlkem", "bb84"]
    assert config["defence_bb84"]["defaults"]["raw_qubits"] == 1024
    spec = client.get("/openapi.json").json()
    for path in ("/api/defence/protect", "/api/defence/reattack", "/api/defence/info"):
        assert path in spec["paths"]
    for model in ("ProtectRequest", "ProtectResponse", "ReattackRequest", "ReattackResponse", "DefenceInfoResponse"):
        assert model in spec["components"]["schemas"]


def test_evaluation_serves_defence_series() -> None:
    from qbreak.defence.experiments import bb84_qber_vs_eve, defence_overhead

    records = bb84_qber_vs_eve(fractions=(0.0, 1.0), raw_qubits=512, repeats=1) + defence_overhead(lengths=(8,), repeats=1)
    eve = build_series("bb84_qber_vs_eve", records)
    assert not eve["empty"] and eve["rows"][-1]["theory_qber"] == 0.25
    overhead = build_series("defence_overhead", records)
    assert {row["method"] for row in overhead["rows"]} == {"aes256", "mlkem", "bb84"}
    for name in ("bb84_qber_vs_eve", "bb84-qber-vs-noise", "bb84_key_rate", "defence_overhead"):
        assert client.get(f"/api/evaluation/{name}").status_code == 200


# --- experiment sweeps (slow) ---------------------------------------------------


@pytest.mark.slow
def test_bb84_qber_sweep_tracks_theory() -> None:
    from qbreak.defence.experiments import bb84_qber_vs_eve, bb84_qber_vs_noise

    for row in build_series("bb84_qber_vs_eve", bb84_qber_vs_eve(raw_qubits=2048, repeats=3))["rows"]:
        assert abs(row["qber_all_sifted"] - row["theory_qber"]) < 0.04
    for row in build_series("bb84_qber_vs_noise", bb84_qber_vs_noise(raw_qubits=2048, repeats=3))["rows"]:
        assert abs(row["qber_all_sifted"] - row["theory_qber"]) < 0.04


@pytest.mark.slow
def test_bb84_key_rate_sweep() -> None:
    from qbreak.defence.experiments import bb84_key_rate

    rows = build_series("bb84_key_rate", bb84_key_rate())["rows"]
    clean = [r for r in rows if r["channel_noise"] == 0 and r["raw_qubits"] >= 1024]
    assert clean and all(r["acceptance_rate"] == 1.0 for r in clean)
    assert all(0.4 < r["sifted_fraction"] < 0.6 for r in rows)
