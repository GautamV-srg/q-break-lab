"""Conversions shared by the miniature symmetric and RSA test modules."""


def text_to_nibbles(text: str) -> list[int]:
    """Encode UTF-8 text as high-nibble-first four-bit integers."""
    return [nibble for byte in text.encode("utf-8") for nibble in (byte >> 4, byte & 0xF)]


def nibbles_to_text(nibbles: list[int]) -> str:
    """Decode high-nibble-first integers as UTF-8 text."""
    if len(nibbles) % 2:
        raise ValueError("Nibble data must contain an even number of values.")
    if any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 15 for value in nibbles):
        raise ValueError("Each nibble must be an integer from 0 to 15.")
    data = bytes((nibbles[index] << 4) | nibbles[index + 1] for index in range(0, len(nibbles), 2))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Nibble data is not valid UTF-8 text.") from exc


def text_to_chunks(text: str, bits: int = 3) -> tuple[list[int], int]:
    """Encode UTF-8 text as fixed-width, MSB-first integer chunks."""
    _validate_chunk_bits(bits)
    data = text.encode("utf-8")
    bit_length = len(data) * 8
    bitstream = "".join(f"{byte:08b}" for byte in data)
    chunks = [int(bitstream[index : index + bits].ljust(bits, "0"), 2) for index in range(0, bit_length, bits)]
    return chunks, bit_length


def chunks_to_text(chunks: list[int], bit_length: int, bits: int = 3) -> str:
    """Decode fixed-width, MSB-first chunks using the original bit length."""
    _validate_chunk_bits(bits)
    if not isinstance(bit_length, int) or isinstance(bit_length, bool) or bit_length < 0:
        raise ValueError("bit_length must be a non-negative integer.")
    maximum = (1 << bits) - 1
    if any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum for value in chunks):
        raise ValueError(f"Each chunk must be an integer from 0 to {maximum}.")
    available_bits = len(chunks) * bits
    if bit_length > available_bits:
        raise ValueError("bit_length exceeds the supplied chunk data.")
    if bit_length % 8:
        raise ValueError("bit_length must describe a whole number of bytes.")
    bitstream = "".join(f"{value:0{bits}b}" for value in chunks)[:bit_length]
    data = bytes(int(bitstream[index : index + 8], 2) for index in range(0, bit_length, 8))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Chunk data is not valid UTF-8 text.") from exc


def key_str_to_int(key: str, key_bits: int) -> int:
    """Validate an MSB-first binary key string and return its integer value."""
    if len(key) != key_bits:
        raise ValueError(f"Key must contain exactly {key_bits} bits.")
    if any(character not in "01" for character in key):
        raise ValueError("Key may contain only 0 and 1.")
    return int(key, 2)


def int_to_key_str(key: int, key_bits: int) -> str:
    """Format an integer as an exact-width, MSB-first binary key string."""
    if not isinstance(key_bits, int) or isinstance(key_bits, bool) or key_bits <= 0:
        raise ValueError("key_bits must be a positive integer.")
    if not isinstance(key, int) or isinstance(key, bool) or not 0 <= key < 1 << key_bits:
        raise ValueError(f"Key must be an integer from 0 to {(1 << key_bits) - 1}.")
    return f"{key:0{key_bits}b}"


def _validate_chunk_bits(bits: int) -> None:
    if not isinstance(bits, int) or isinstance(bits, bool) or bits <= 0:
        raise ValueError("bits must be a positive integer.")
