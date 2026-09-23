"""DTE v3: coder, byte-builder, masked encode, пилот toy-кириллица (без ROM)."""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.dte import (
    ASCII_CODER,
    TextCoder,
    build_byte_table,
    build_for_translation,
    decode,
    decode_bytes,
    encode,
    encode_bytes,
)

_CYR: dict[str, int] = {chr(0x410 + i): 0x80 + i for i in range(32)}
_CYR.update({chr(0x430 + i): 0xA0 + i for i in range(32)})
_CYR.update({"Ё": 0x9F, "ё": 0xBF, " ": 0x20, "\n": 0xFD})
_CYR_REV = {v: k for k, v in _CYR.items()}


def _toy_encode(ch: str) -> int:
    if ch in _CYR:
        return _CYR[ch]
    code = ord(ch)
    if 0x20 <= code <= 0x7E:
        return code
    raise ValueError(f"unmapped: {ch!r}")


def _toy_decode(code: int) -> str:
    if isinstance(code, bool) or not isinstance(code, int) or code < 0 or code > 255:
        raise ValueError(f"byte out of range: {code!r}")
    if code in _CYR_REV:
        return _CYR_REV[code]
    if 0x20 <= code <= 0x7E:
        return chr(code)
    raise ValueError(f"unmapped byte: {code:#x}")


TOY = TextCoder(_toy_encode, _toy_decode)


def _any(value: object) -> Any:
    return value


class TestCoder:
    def test_ascii_strict(self):
        assert ASCII_CODER.encode_char("A") == 0x41
        assert ASCII_CODER.decode_char(0x41) == "A"
        for bad in ("ab", "", 5, None):
            with pytest.raises(ValueError):
                ASCII_CODER.encode_char(_any(bad))
        with pytest.raises(ValueError):
            ASCII_CODER.encode_char("Привет"[0])
        for bad in (True, -1, 256, "x", None):
            with pytest.raises(ValueError):
                ASCII_CODER.decode_char(_any(bad))

    def test_toy(self):
        assert TOY.encode_char("П") != ord("П")
        assert TOY.decode_char(TOY.encode_char("Ж")) == "Ж"
        with pytest.raises(ValueError):
            TOY.encode_char("😀")
        with pytest.raises(ValueError):
            TOY.decode_char(0x00)

    def test_coder_type_gates(self):
        for bad in (None, "x", 5):
            with pytest.raises(TypeError):
                encode("AB", {"AB": 0x80}, _any(bad))
            with pytest.raises(TypeError):
                decode(b"\x80", {"AB": 0x80}, _any(bad))
        from core.dte import DTEHandler

        with pytest.raises(TypeError):
            DTEHandler({}, _any("x"))

    def test_rogue_coder(self):
        rogue = TextCoder(lambda ch: 300, lambda code: "?")
        with pytest.raises(ValueError):
            encode("AB", {}, rogue)
        truthy = TextCoder(lambda ch: True, lambda code: "?")
        with pytest.raises(ValueError):
            encode("AB", {}, truthy)


class TestMaskedEncode:
    def test_hostile_table(self):
        table = {"AI": 0x90}
        raw = encode("[WAIT]", table)
        assert raw == b"[WAIT]"
        assert decode(raw, table) == "[WAIT]"

    def test_adjacent_and_edges(self):
        table = {"AI": 0x90}
        assert decode(encode("[WAIT][WAIT]", table), table) == "[WAIT][WAIT]"
        assert decode(encode("A[WAIT]", table), table) == "A[WAIT]"

    def test_token_only_and_empty(self):
        assert encode("[WAIT]", {}) == b"[WAIT]"
        assert encode("", {"AB": 0x80}) == b""

    def test_unclosed_opener(self):
        table = {"CD": 0x81}
        assert encode("[ACD", table) == bytes([0x5B, 0x41, 0x81])


class TestByteTable:
    def test_roundtrip(self):
        table = build_byte_table([b"\x01\x02\x01\x02", b"\x01\x02"], [0x80, 0x81])
        assert table.get((1, 2)) == 0x80
        data = b"\x01\x02\x01\x02\x03"
        assert decode_bytes(encode_bytes(data, table), table) == data

    def test_overlap(self):
        table = build_byte_table([b"\x05\x05\x05"] * 5, [0x80])
        assert decode_bytes(encode_bytes(b"\x05\x05\x05", table), table) == b"\x05\x05\x05"

    def test_literal_collision_loud(self):
        table = {(1, 2): 0x80}
        with pytest.raises(ValueError):
            encode_bytes(b"\x80", table)
        assert decode_bytes(b"\x01", table) == b"\x01"

    def test_disjoint_loud(self):
        with pytest.raises(ValueError):
            build_byte_table([b"\x01\x02"] * 5, [0x01, 0x80])

    def test_disjoint_empty_table(self):
        with pytest.raises(ValueError):
            build_byte_table([b"\x01"], [0x01, 0x80])

    def test_max_pairs(self):
        assert build_byte_table([b"\x01\x02"] * 5, [0x80], max_pairs=0) == {}
        with pytest.raises(ValueError):
            build_byte_table([b"\x01\x02"] * 5, [0x80], max_pairs=-1)
        with pytest.raises(TypeError):
            build_byte_table([b"\x01\x02"] * 5, [0x80], max_pairs=_any("1"))

    def test_bad_cost(self):
        for bad in (0, -2, True, "2", None):
            with pytest.raises(ValueError):
                build_byte_table([b"\x01\x02"] * 5, [0x80], table_entry_cost=_any(bad))

    def test_bad_frags(self):
        with pytest.raises(TypeError):
            build_byte_table(_any("xx"), [0x80])
        with pytest.raises(TypeError):
            build_byte_table([_any("xx")], [0x80])

    def test_bad_free(self):
        with pytest.raises(ValueError):
            build_byte_table([b"\x01\x02"] * 5, [0x80, 0x80])
        with pytest.raises(ValueError):
            build_byte_table([b"\x01\x02"] * 5, [0x00])
        with pytest.raises(TypeError):
            build_byte_table([b"\x01\x02"] * 5, [True])

    def test_dup_codes(self):
        from core.dte import _checked_rev

        with pytest.raises(ValueError):
            _checked_rev({(1, 2): 0x80, (3, 4): 0x80})
        with pytest.raises(ValueError):
            decode_bytes(b"\x80", _any({(1, 2): 0x80, (3, 4): 0x80}))


class TestBuildForTranslation:
    def _texts(self):
        base = "Привет мир Привет "
        return [base * 6 + "[WAIT] мир\n", base * 4 + "{VAR} %s!"]

    def test_pilot(self):
        result = build_for_translation(self._texts(), extra_used={0x00, 0xFF}, coder=TOY)
        table = result["table"]
        assert table
        assert all(isinstance(k, tuple) and len(k) == 2 for k in table)
        assert 0x5B not in table.values()
        assert 0x00 not in table.values() and 0xFF not in table.values()
        stats = result["stats"]
        assert stats["saved_bytes"] > 0
        assert stats["saved_bytes"] == stats["raw_bytes"] - stats["dte_bytes"] - stats["table_cost"]
        assert stats["table_cost"] == len(table) * 2
        assert result["free"] == sorted(result["free"])

    def test_pilot_roundtrip(self):
        result = build_for_translation(self._texts(), extra_used={0x00}, coder=TOY)
        table = result["table"]
        assert table
        for text in self._texts():
            from core.dte import _literal_runs, _masked_spans

            spans = _masked_spans(text)
            for start, end in _literal_runs(spans, len(text)):
                frag = bytes(TOY.encode_char(text[pos]) for pos in range(start, end))
                assert decode_bytes(encode_bytes(frag, table), table) == frag

    def test_token_newline_overlap(self):
        result = build_for_translation(["[a\nb]" * 8 + "ABABABAB"], extra_used={0x00})
        assert isinstance(result["table"], dict)

    def test_empty(self):
        result = build_for_translation([], extra_used=set())
        assert result == {"table": {}, "free": result["free"], "stats": {"raw_bytes": 0, "dte_bytes": 0, "table_cost": 0, "saved_bytes": 0}}

    def test_bad_inputs(self):
        with pytest.raises(TypeError):
            build_for_translation(_any("xx"), extra_used=set())
        with pytest.raises(TypeError):
            build_for_translation([_any(None)], extra_used=set())
        with pytest.raises(TypeError):
            build_for_translation(["AB"], extra_used=set(), coder=_any("x"))
        with pytest.raises(TypeError):
            build_for_translation(["AB"], extra_used=_any(5))
        with pytest.raises(ValueError):
            build_for_translation(["AB"], extra_used={True})
        with pytest.raises(ValueError):
            build_for_translation(["AB"], extra_used={0x100})
        with pytest.raises(TypeError):
            build_for_translation(["AB"], extra_used=set(), reserved=_any(5))
        with pytest.raises(ValueError):
            build_for_translation(["AB"], extra_used=set(), reserved=_any({True}))

    def test_unmapped_fail_fast(self):
        with pytest.raises(ValueError):
            build_for_translation(["Привет 😀"], extra_used={0x00}, coder=TOY)

    def test_ascii_pilot(self):
        result = build_for_translation(["ABABAB CDCD"] * 5, extra_used={0x00})
        assert result["table"].get((0x41, 0x42)) == 0x01
        assert result["stats"]["saved_bytes"] > 0


class TestHandlerCoder:
    def test_toy_roundtrip(self):
        from core.dte import DTEHandler

        texts = ["Привет " * 6]
        built = build_for_translation(texts, extra_used={0x00}, coder=TOY)
        str_table = {}
        for (b1, b2), code in built["table"].items():
            str_table[TOY.decode_char(b1) + TOY.decode_char(b2)] = code
        handler = DTEHandler(str_table, TOY)
        raw = handler.compress(texts[0])
        out, consumed = handler.decompress(raw, 0)
        assert consumed == len(raw)
        assert out == bytes(TOY.encode_char(ch) for ch in texts[0])

    def test_handler_bad_start(self):
        from core.dte import DTEHandler

        handler = DTEHandler({"AB": 0x80}, TOY)
        with pytest.raises(ValueError):
            handler.decompress(b"\x80", -1)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
