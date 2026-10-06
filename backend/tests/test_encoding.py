import pytest

from qbreak.common.encoding import (
    chunks_to_text,
    int_to_key_str,
    key_str_to_int,
    nibbles_to_text,
    text_to_chunks,
    text_to_nibbles,
)


@pytest.mark.parametrize("text", ["", "Hi", "Quantum ☕", "🔐 breach test"])
def test_nibble_round_trip(text: str) -> None:
    assert nibbles_to_text(text_to_nibbles(text)) == text


@pytest.mark.parametrize("text", ["", "Hi", "Quantum ☕", "🔐 breach test"])
def test_chunk_round_trip(text: str) -> None:
    chunks, bit_length = text_to_chunks(text)
    assert chunks_to_text(chunks, bit_length) == text


def test_exact_encoding_examples() -> None:
    assert text_to_nibbles("Hi") == [4, 8, 6, 9]
    assert text_to_chunks("Hi") == ([2, 2, 0, 6, 4, 4], 16)


@pytest.mark.parametrize("key", range(16))
def test_every_four_bit_key_round_trip(key: int) -> None:
    key_string = int_to_key_str(key, 4)
    assert key_str_to_int(key_string, 4) == key


@pytest.mark.parametrize("key", ["101", "10101", "10x1"])
def test_invalid_key_strings_raise(key: str) -> None:
    with pytest.raises(ValueError):
        key_str_to_int(key, 4)


def test_odd_nibbles_and_invalid_utf8_raise() -> None:
    with pytest.raises(ValueError, match="even"):
        nibbles_to_text([4])
    with pytest.raises(ValueError, match="UTF-8"):
        nibbles_to_text([0xF, 0xF])
