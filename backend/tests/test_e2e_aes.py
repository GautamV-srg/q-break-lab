import pytest
from fastapi.testclient import TestClient

pytest.importorskip("qbreak.aes.cipher")
pytest.importorskip("qbreak.aes.grover")

from qbreak.api.main import app

client = TestClient(app)


@pytest.mark.parametrize("message", ["Hi judges!", "Quantum ☕", "aaaa"])
@pytest.mark.parametrize("key", [f"{value:04b}" for value in range(16)])
def test_every_four_bit_key_end_to_end(key: str, message: str) -> None:
    encrypted = client.post("/api/aes/encrypt", json={"plaintext": message, "key": key, "key_bits": 4})
    assert encrypted.status_code == 200
    attacked = client.post("/api/aes/attack", json={"key_bits": 4, "known_plaintext": message[:3], "ciphertext_nibbles": encrypted.json()["ciphertext_nibbles"], "shots": 1024, "seed": 42})
    assert attacked.status_code == 200
    report = attacked.json()
    assert key in report["recovered_keys"]
    if report["unique"]:
        assert report["decrypted_text"] == message
    else:
        assert "Several keys fit" in " ".join(report["warnings"])


@pytest.mark.slow
@pytest.mark.parametrize("key_bits,key", [(6, "101011"), (8, "10100101")])
def test_larger_enabled_keys(key_bits: int, key: str) -> None:
    from qbreak.config import ENABLED_KEY_BITS

    if key_bits not in ENABLED_KEY_BITS:
        pytest.skip(f"{key_bits}-bit tests are not enabled")
    message = "Hi judges!"
    encrypted = client.post("/api/aes/encrypt", json={"plaintext": message, "key": key, "key_bits": key_bits})
    attacked = client.post("/api/aes/attack", json={"key_bits": key_bits, "known_plaintext": message[:3], "ciphertext_nibbles": encrypted.json()["ciphertext_nibbles"], "shots": 1024, "seed": 42})
    assert attacked.status_code == 200
    assert key in attacked.json()["recovered_keys"]


def test_attack_does_not_use_classical_matching_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from qbreak.aes import cipher

    encrypted = client.post("/api/aes/encrypt", json={"plaintext": "Hi judges!", "key": "1001", "key_bits": 4}).json()

    def forbidden(*args, **kwargs):
        raise AssertionError("attack path accessed matching_keys")

    monkeypatch.setattr(cipher, "matching_keys", forbidden)
    response = client.post("/api/aes/attack", json={"key_bits": 4, "known_plaintext": "Hi ", "ciphertext_nibbles": encrypted["ciphertext_nibbles"], "shots": 1024, "seed": 42})
    assert response.status_code == 200
