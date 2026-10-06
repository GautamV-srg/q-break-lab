from fastapi.testclient import TestClient

from qbreak.api.main import app

client = TestClient(app)


def test_health_and_config() -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["aes_key_bits"] == [4]
    assert response.json()["rsa_moduli"] == [15, 21, 33, 35, 55, 77]


def test_aes_encrypt_and_attack_mock_contract() -> None:
    encrypted = client.post("/api/aes/encrypt", json={"plaintext": "Hi judges!", "key": "1001", "key_bits": 4})
    assert encrypted.status_code == 200
    assert encrypted.json()["ciphertext_hex"] == "38ed95e20ae3e0ea0c96"
    attacked = client.post("/api/aes/attack", json={"key_bits": 4, "known_plaintext": "Hi ", "ciphertext_nibbles": encrypted.json()["ciphertext_nibbles"], "shots": 128, "seed": 7})
    assert attacked.status_code == 200
    assert attacked.json()["key"] == "1001"
    assert isinstance(attacked.json()["warnings"], list)


def test_rsa_endpoints_mock_contract() -> None:
    generated = client.post("/api/rsa/keygen", json={"n": 15})
    assert generated.status_code == 200
    assert generated.json()["victim_secret"] == {"p": 3, "q": 5, "phi": 8, "d": 3}
    encrypted = client.post("/api/rsa/encrypt", json={"plaintext": "Hi", "n": 15, "e": 3})
    assert encrypted.status_code == 200
    assert encrypted.json()["ciphertext"] == [8, 8, 0, 6, 4, 4]
    attacked = client.post("/api/rsa/attack", json={"n": 15, "e": 3, "ciphertext": encrypted.json()["ciphertext"], "bit_length": 16, "shots": 128, "seed": 7})
    assert attacked.status_code == 200
    assert attacked.json()["decrypted_text"] == "Hi"


def test_attack_requests_forbid_secrets() -> None:
    aes = client.post("/api/aes/attack", json={"key_bits": 4, "known_plaintext": "H", "ciphertext_nibbles": [3, 8], "key": "1001"})
    assert aes.status_code == 422
    rsa = client.post("/api/rsa/attack", json={"n": 15, "e": 3, "ciphertext": [8], "bit_length": 3, "p": 3})
    assert rsa.status_code == 422


def test_readable_validation_errors() -> None:
    empty = client.post("/api/aes/encrypt", json={"plaintext": "", "key": "1001", "key_bits": 4})
    assert empty.status_code == 422
    assert isinstance(empty.json()["detail"], str)
    assert client.post("/api/aes/encrypt", json={"plaintext": "Hi", "key": "xyz", "key_bits": 4}).status_code == 422
    assert client.post("/api/aes/attack", json={"key_bits": 4, "known_plaintext": "too long", "ciphertext_nibbles": [1]}).status_code == 422
    assert client.post("/api/rsa/keygen", json={"n": 22}).status_code == 422
    assert client.post("/api/rsa/attack", json={"n": 15, "e": 3, "ciphertext": [15], "bit_length": 3}).status_code == 422
