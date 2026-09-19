"""Тесты DTE-хелпера (план 1.4, синтетика)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any

import pytest

from core.compression import CompressionHandler
from core.dte import DTEHandler, build_table, decode, derive_free_bytes, encode


class TestDeriveFreeBytes:
    def test_basic(self):
        assert derive_free_bytes({0x41, 0x42})[:3] == [0x01, 0x02, 0x03]
        assert 0x00 not in derive_free_bytes(set())
        assert 0x41 not in derive_free_bytes({0x41})

    def test_reserved(self):
        assert 0xFF not in derive_free_bytes(set(), reserved=(0x00, 0xFF))
        assert derive_free_bytes(set())[-1] == 0xFF

    def test_sorted(self):
        assert derive_free_bytes({0x10}) == sorted(derive_free_bytes({0x10}))


class TestBuildTable:
    def test_top_bigram(self):
        table = build_table(["ABABAB CDCD", "AB XY"], [0x80, 0x81])
        assert table.get("AB") == 0x80

    def test_unprofitable_dropped(self):
        table = build_table(["AB XY"], [0x80], table_entry_cost=2)
        assert table == {}

    def test_max_pairs_cap(self):
        table = build_table(["ABAB CDCD EFEF", "AB CD EF"] * 3, [0x80, 0x81, 0x82], max_pairs=2)
        assert len(table) == 2

    def test_tokens_and_newlines_excluded(self):
        table = build_table(["[AB] {CD} %s A\nB"] * 10, list(range(0x80, 0x100)))
        for pair in table:
            assert "[" not in pair and "{" not in pair and "%" not in pair
            assert "\n" not in pair

    def test_printf_variants_masked(self):
        table = build_table(["%02d items %5s %% done %"] * 10, list(range(0x80, 0x100)))
        for pair in table:
            assert "%" not in pair

    def test_unclosed_bracket_masked(self):
        table = build_table(["AB [unclosed CD EF"] * 10, list(range(0x80, 0x100)))
        for pair in table:
            assert "[" not in pair

    def test_deterministic(self):
        texts = ["AB CD AB CD", "EF AB"]
        assert build_table(texts, [0x81, 0x80]) == build_table(texts, [0x81, 0x80])

    def test_non_string_rejected(self):
        bad_texts: list[Any] = [None, "ABABAB"]
        with pytest.raises(TypeError):
            build_table(bad_texts, [0x80])
        bad_bytes: list[Any] = ["0x80"]
        with pytest.raises(TypeError):
            build_table(["ABABAB"], bad_bytes)

    def test_free_bytes_validated(self):
        with pytest.raises(ValueError):
            build_table(["ABABAB"], [0x80, 0x80])
        with pytest.raises(ValueError):
            build_table(["ABABAB"], [0x00])
        with pytest.raises(ValueError):
            build_table(["ABABAB"], [0x100])
        with pytest.raises(TypeError):
            build_table(["ABABAB"], [True])


class TestCodec:
    def test_roundtrip(self):
        table = {"AB": 0x80, "CD": 0x81}
        for text in ("AB CD AB", "XYZ", "", "A", "ABAB"):
            assert decode(encode(text, table), table) == text

    def test_greedy_overlap(self):
        table = {"AA": 0x80}
        assert encode("AAA", table) == bytes([0x80, ord("A")])
        assert decode(bytes([0x80, ord("A")]), table) == "AAA"

    def test_non_latin_raises(self):
        with pytest.raises(ValueError):
            encode("Привет", {"AB": 0x80})

    def test_empty(self):
        assert encode("", {}) == b""
        assert decode(b"", {}) == ""


class TestHandler:
    def test_subclass(self):
        assert issubclass(DTEHandler, CompressionHandler)

    def test_roundtrip(self):
        handler = DTEHandler({"AB": 0x80})
        raw = handler.compress("AB CD AB")
        assert raw == bytes([0x80, ord(" "), ord("C"), ord("D"), ord(" "), 0x80])
        decoded, consumed = handler.decompress(raw, 0)
        assert decoded.decode("utf-8") == "AB CD AB"
        assert consumed == len(raw)

    def test_decompress_offset(self):
        handler = DTEHandler({"AB": 0x80})
        raw = b"\x00\x00" + bytes([0x80])
        decoded, consumed = handler.decompress(raw, 2)
        assert decoded.decode("utf-8") == "AB"
        assert consumed == 1

    def test_bad_start(self):
        handler = DTEHandler({})
        with pytest.raises(ValueError):
            handler.decompress(b"AB", -1)
        assert handler.decompress(b"AB", 99) == (b"", 0)
        assert handler.decompress(b"AB", 2) == (b"", 0)

    def test_duplicate_codes_rejected(self):
        with pytest.raises(ValueError):
            encode("AB", {"AB": 0x80, "CD": 0x80})
        with pytest.raises(ValueError):
            decode(bytes([0x80]), {"AB": 0x80, "CD": 0x80})

    def test_literal_collision_rejected(self):
        with pytest.raises(ValueError):
            encode("a", {"ab": 0x61})


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
