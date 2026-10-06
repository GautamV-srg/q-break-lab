"""End-to-end smoke test of the full Q-Break loop through the HTTP API.

    ATTACK (Grover on MiniAES / Shor on MiniRSA) -> PROTECT -> RE-ATTACK -> COMPARE

Runs once for a symmetric message and once for an RSA message, printing PASS/FAIL per
stage. Exit code 0 only if every stage passes.

Usage (from backend/):
    python scripts/smoke_full_loop.py                       # against http://127.0.0.1:8000
    python scripts/smoke_full_loop.py --base-url https://...  # against a deploy
    python scripts/smoke_full_loop.py --in-process          # no server needed (FastAPI TestClient)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

SYMMETRIC_MESSAGE = "Hi judges!"
RSA_MESSAGE = "Hi"
EXPECTED = {"aes256": "infeasible", "mlkem": "not_applicable", "bb84": "detected"}


class Smoke:
    def __init__(self, http) -> None:
        self.http = http
        self.failures = 0

    def post(self, path: str, body: dict) -> dict:
        res = self.http.post(path, json=body)
        if res.status_code != 200:
            raise RuntimeError(f"{path} -> HTTP {res.status_code}: {res.text[:300]}")
        return res.json()

    def stage(self, name: str, check: Callable[[], str]) -> bool:
        try:
            detail = check()
            print(f"  PASS  {name}: {detail}", flush=True)
            return True
        except Exception as exc:  # noqa: BLE001 - report every failure and keep going
            self.failures += 1
            print(f"  FAIL  {name}: {exc}", flush=True)
            return False


def attack_symmetric(s: Smoke, message: str) -> tuple[str, dict]:
    enc = s.post("/api/aes/encrypt", {"plaintext": message, "key": "1011", "key_bits": 4})
    att = s.post("/api/aes/attack", {
        "key_bits": 4, "condition": "known_beginning", "known_plaintext": message[:3],
        "ciphertext_nibbles": enc["ciphertext_nibbles"], "seed": 7,
    })
    assert att["verdict"] == "breached", f"verdict {att['verdict']}"
    assert att["decrypted_text"] == message, f"decrypted {att['decrypted_text']!r}"
    return f"Grover recovered key {att['key']} and read {att['decrypted_text']!r}", {"cipher": "miniaes", "verdict": "breached"}


def attack_rsa(s: Smoke, message: str) -> tuple[str, dict]:
    keys = s.post("/api/rsa/keygen", {"n": 15})
    enc = s.post("/api/rsa/encrypt", {"plaintext": message, "n": keys["n"], "e": keys["e"]})
    att = s.post("/api/rsa/attack", {
        "n": keys["n"], "e": keys["e"], "ciphertext": enc["ciphertext"], "bit_length": enc["bit_length"], "seed": 7,
    })
    assert att["decrypted_text"] == message, f"decrypted {att['decrypted_text']!r}"
    return f"Shor factored N=15 into {att['factors']} and read {att['decrypted_text']!r}", {"cipher": "minirsa", "verdict": "breached"}


def run_loop(s: Smoke, label: str, message: str, attack: Callable[[Smoke, str], tuple[str, dict]]) -> None:
    print(f"\n== {label}: {message!r}")
    state: dict = {}

    def do_attack() -> str:
        detail, state["original"] = attack(s, message)
        return detail

    def do_protect() -> str:
        body = s.post("/api/defence/protect", {"plaintext": message, "bb84": {"seed": 1}})
        results = body["results"]
        for method in ("aes256", "mlkem", "bb84"):
            r = results[method]
            assert r["status"] == "protected" and r["roundtrip_ok"], f"{method}: {r['status']}"
            assert message not in str(r["bundle"]), f"{method} bundle leaks the plaintext"
        state["bundles"] = {m: r["bundle"] for m, r in results.items()}
        return "AES-256, ML-KEM-768 and BB84 all round-trip; bundles are public-only"

    def do_reattack() -> str:
        body = s.post("/api/defence/reattack", {
            "bundles": state["bundles"], "bb84_attack": {"seed": 2}, "original_attack": state.get("original"),
        })
        got = {m: v["verdict"] for m, v in body["verdicts"].items()}
        assert got == EXPECTED, f"verdicts {got}"
        state["reattack"] = body
        return ", ".join(f"{m} {v}" for m, v in got.items())

    def do_blind() -> str:
        tampered = {**state["bundles"], "aes256": {**state["bundles"]["aes256"], "key_b64": "AAAA"}}
        res = s.http.post("/api/defence/reattack", json={"bundles": tampered})
        assert res.status_code == 422, f"HTTP {res.status_code}"
        return "a secret field in a bundle is rejected (422)"

    def do_compare() -> str:
        body = state["reattack"]
        labels = [row["label"] for row in body["comparison"]["rows"]]
        assert "Re-attack verdict" in labels and "Overhead (measured)" in labels, labels
        assert body["recommendation"]["text"], "empty recommendation"
        before = body.get("before") or {}
        return f"{len(labels)} comparison rows; rule {body['recommendation']['rule']}; before = {before.get('cipher')} {before.get('verdict')}"

    for name, fn in (("attack", do_attack), ("protect", do_protect), ("re-attack", do_reattack), ("blindness", do_blind), ("compare", do_compare)):
        if not s.stage(name, fn):
            print("  (skipping the remaining stages of this loop)")
            break


def main() -> int:
    parser = argparse.ArgumentParser(description="Q-Break full-loop smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--in-process", action="store_true", help="use FastAPI's TestClient instead of a running server")
    args = parser.parse_args()
    if args.in_process:
        from fastapi.testclient import TestClient

        from qbreak.api.main import app

        http = TestClient(app)
        where = "in-process"
    else:
        import httpx

        http = httpx.Client(base_url=args.base_url, timeout=120)
        where = args.base_url
    s = Smoke(http)
    print(f"Q-Break full-loop smoke test ({where})")
    s.stage("health", lambda: s.http.get("/api/health").json()["status"])
    run_loop(s, "Symmetric (Grover on MiniAES)", SYMMETRIC_MESSAGE, attack_symmetric)
    run_loop(s, "Public key (Shor on MiniRSA)", RSA_MESSAGE, attack_rsa)
    print("\nRESULT:", "PASS" if s.failures == 0 else f"FAIL ({s.failures} stage(s) failed)")
    return 0 if s.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
