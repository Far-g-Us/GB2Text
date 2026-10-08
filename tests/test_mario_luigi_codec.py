"""MLSS token codec: synthetic round-trips (no ROM)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from plugins.gba_mario_luigi_ss import MLSSTextDecoder, MLSSTextEncoder


def test_ascii_roundtrip() -> None:
    dec = MLSSTextDecoder()
    enc = MLSSTextEncoder()
    assert dec.decode(b'Hello!', 0, 6) == 'Hello!'
    assert enc.encode('Hello!') == b'Hello!'


def test_ff_tokens() -> None:
    dec = MLSSTextDecoder()
    enc = MLSSTextEncoder()
    assert dec.decode(bytes([0xFF, 0x0B]), 0, 2) == '[FF 0B]'
    assert enc.encode('[FF 0B]') == bytes([0xFF, 0x0B])
    assert dec.decode(bytes([0xFF, 0x11, 0x00]), 0, 3) == '[FF 11 00]'
    assert enc.encode('[FF 11 00]') == bytes([0xFF, 0x11, 0x00])
    assert dec.decode(bytes([0xFF]), 0, 1) == '[FF]'
    assert enc.encode('[FF]') == bytes([0xFF])


def test_glyph_tokens() -> None:
    dec = MLSSTextDecoder()
    enc = MLSSTextEncoder()
    assert dec.decode(bytes([0x15]), 0, 1) == '[G:15]'
    assert enc.encode('[G:15]') == bytes([0x15])


def test_mixed_roundtrip() -> None:
    dec = MLSSTextDecoder()
    enc = MLSSTextEncoder()
    raw = b'\x15\x03Hi\xff\x0b!'
    text = dec.decode(raw, 0, len(raw))
    assert enc.encode(text) == raw


def test_truncated_param_kept() -> None:
    dec = MLSSTextDecoder()
    enc = MLSSTextEncoder()
    assert dec.decode(bytes([0xFF, 0x11]), 0, 2) == '[FF 11]'
    assert enc.encode('[FF 11]') == bytes([0xFF, 0x11])


def test_unknown_ff_code() -> None:
    dec = MLSSTextDecoder()
    assert dec.decode(bytes([0xFF, 0x41]), 0, 2) == '[FF 41]'


def test_is_printable_bounds() -> None:
    from plugins.gba_mario_luigi_ss import _is_printable
    assert _is_printable(0x20) and _is_printable(0x7E)
    assert not _is_printable(0x1F) and not _is_printable(0x7F)
    assert not _is_printable(0x00) and not _is_printable(0x15)
    assert not _is_printable(0x80) and not _is_printable(0xFE)
    assert not _is_printable(0xFF)


def test_encoder_rejects() -> None:
    enc = MLSSTextEncoder()
    with pytest.raises(ValueError):
        enc.encode('[you]')
    with pytest.raises(ValueError):
        enc.encode('[oops')
    with pytest.raises(ValueError):
        enc.encode('caf\u00e9')
