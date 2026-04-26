"""Modbus data type decoding and encoding utilities."""

import struct
from typing import Tuple


def decode_uint16(raw_value: int, multiplier: float = 1.0) -> float:
    """Decode a uint16 register value with optional multiplier.

    Args:
        raw_value: Raw uint16 value (0-65535).
        multiplier: Value to multiply the result by (default 1.0).

    Returns:
        Decoded float value.
    """
    return raw_value * multiplier


def decode_uint32(high_word: int, low_word: int, multiplier: float = 1.0) -> float:
    """Decode a uint32 register value from two consecutive uint16 words (big-endian).

    Args:
        high_word: High 16 bits of the 32-bit value.
        low_word: Low 16 bits of the 32-bit value.
        multiplier: Value to multiply the result by (default 1.0).

    Returns:
        Decoded float value.
    """
    combined = (high_word << 16) | low_word
    return combined * multiplier


def decode_int32(high_word: int, low_word: int, multiplier: float = 1.0) -> float:
    """Decode a signed int32 register value from two consecutive uint16 words (big-endian).

    Args:
        high_word: High 16 bits of the 32-bit value.
        low_word: Low 16 bits of the 32-bit value.
        multiplier: Value to multiply the result by (default 1.0).

    Returns:
        Decoded signed float value.
    """
    # Combine as unsigned first
    combined = (high_word << 16) | low_word
    # Convert to signed if negative (bit 31 set)
    if combined & 0x80000000:
        combined -= 0x100000000
    return combined * multiplier


def encode_uint16(value: float, reg_type: str = "uint16") -> int:
    """Encode a value to uint16 for writing to a register.

    Args:
        value: Numeric value to encode.
        reg_type: Target register type ('uint16', 'uint32_hi', etc.).

    Returns:
        Encoded uint16 value (0-65535).
    """
    return int(value) & 0xFFFF


def encode_uint32(value: float, reg_type: str = "uint32") -> Tuple[int, int]:
    """Encode a value to two consecutive uint16 registers (big-endian).

    Args:
        value: Numeric value to encode.
        reg_type: Target register type ('uint32', 'int32').

    Returns:
        Tuple of (high_word, low_word) as uint16 values.
    """
    int_value = int(value) & 0xFFFFFFFF
    high_word = (int_value >> 16) & 0xFFFF
    low_word = int_value & 0xFFFF
    return high_word, low_word


def encode_int32(value: float, reg_type: str = "int32") -> Tuple[int, int]:
    """Encode a signed value to two consecutive uint16 registers (big-endian).

    Args:
        value: Signed numeric value to encode.
        reg_type: Target register type ('int32').

    Returns:
        Tuple of (high_word, low_word) as uint16 values.
    """
    # Convert to 32-bit signed representation
    int_value = int(value) & 0xFFFFFFFF
    if int_value > 0x7FFFFFFF:
        int_value -= 0x100000000

    high_word = (int_value >> 16) & 0xFFFF
    low_word = int_value & 0xFFFF
    return high_word, low_word


def decode_register(raw_high: int, raw_low: int, reg_type: str, multiplier: float = 1.0) -> float:
    """Generic register decoder that dispatches to the correct type handler.

    Args:
        raw_high: High word of the register value.
        raw_low: Low word of the register value (for multi-word types).
        reg_type: Register data type ('uint16', 'uint32', 'int32').
        multiplier: Value to multiply the result by.

    Returns:
        Decoded float value.
    """
    if reg_type == "uint16":
        return decode_uint16(raw_high, multiplier)
    elif reg_type == "uint32":
        return decode_uint32(raw_high, raw_low, multiplier)
    elif reg_type == "int32":
        return decode_int32(raw_high, raw_low, multiplier)
    else:
        # Default to uint16 decoding
        return decode_uint16(raw_high, multiplier)


def encode_register(value: float, reg_type: str) -> Tuple[int, int]:
    """Generic register encoder that dispatches to the correct type handler.

    Args:
        value: Value to encode.
        reg_type: Target register type ('uint16', 'uint32', 'int32').

    Returns:
        Tuple of (high_word, low_word) as uint16 values.
    """
    if reg_type == "uint16":
        hi, lo = encode_uint32(value)  # For single register, high=0, low=value
        return value & 0xFFFF, 0
    elif reg_type in ("uint32", "int32"):
        if reg_type == "uint32":
            return encode_uint32(value)
        else:
            return encode_int32(value)
    else:
        # Default to uint16 encoding
        return value & 0xFFFF, 0
