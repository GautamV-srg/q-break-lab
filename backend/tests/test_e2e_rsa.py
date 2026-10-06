import pytest
from fastapi.testclient import TestClient

pytest.importorskip("qbreak.rsa.minirsa")
pytest.importorskip("qbreak.rsa.shor")

from qbreak.api.main import app
from qbreak.config import ENABLED_MODULI

client = TestClient(app)


@pytest.mark.parametrize("n", ENABLED_MODULI)
def test_enabled_modulus_end_to_end(n: int) -> None:
    if n >= 21:
        pytest.skip("N >= 21 is covered by the slow local test run")
    generated = client.post("/api/rsa/keygen", json={"n": n})
    assert generated.status_code == 200
    e = generated.json()["e"]
    encrypted = client.post("/api/rsa/encrypt", json={"plaintext": "Hi judges!", "n": n, "e": e})
    assert encrypted.status_code == 200
    attacked = client.post("/api/rsa/attack", json={"n": n, "e": e, "ciphertext": encrypted.json()["ciphertext"], "bit_length": encrypted.json()["bit_length"], "shots": 1024, "seed": 42})
    assert attacked.status_code == 200
    assert attacked.json()["decrypted_text"] == "Hi judges!"


@pytest.mark.slow
@pytest.mark.parametrize("n", [n for n in ENABLED_MODULI if n >= 21])
def test_larger_enabled_modulus_end_to_end(n: int) -> None:
    generated = client.post("/api/rsa/keygen", json={"n": n}).json()
    encrypted = client.post("/api/rsa/encrypt", json={"plaintext": "Hi judges!", "n": n, "e": generated["e"]}).json()
    attacked = client.post("/api/rsa/attack", json={"n": n, "e": generated["e"], "ciphertext": encrypted["ciphertext"], "bit_length": encrypted["bit_length"], "shots": 1024, "seed": 42})
    assert attacked.status_code == 200
    assert attacked.json()["decrypted_text"] == "Hi judges!"


def test_attack_does_not_use_victim_factor_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from qbreak.rsa import minirsa

    generated = client.post("/api/rsa/keygen", json={"n": 15}).json()
    encrypted = client.post("/api/rsa/encrypt", json={"plaintext": "Hi", "n": 15, "e": generated["e"]}).json()

    def forbidden(*args, **kwargs):
        raise AssertionError("attack path accessed victim key generation")

    monkeypatch.setattr(minirsa, "generate_keypair", forbidden)
    monkeypatch.setattr(minirsa, "SUPPORTED_MODULI", {})
    response = client.post("/api/rsa/attack", json={"n": 15, "e": generated["e"], "ciphertext": encrypted["ciphertext"], "bit_length": encrypted["bit_length"], "shots": 1024, "seed": 42})
    assert response.status_code == 200
