"""
AC1: мягкий spellcheck-гейт на инжекте (core/injector.py).

Проверяется, что каждая операция записи перед codepath-ветвлением
прогоняет переводы через _run_spellcheck_gate, опечатки аккумулируются в
last_spellcheck_report, а сама запись НИКОГДА не блокируется гейтом.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.decoder import CharMapDecoder
from core.injector import TextInjector
from tests.test_injector import SIMPLE_CHARMAP, _build_test_rom


def _typo_everywhere(text, lang="auto", **kwargs):
    """Детерминированный фейк check_text: ровно одна опечатка на непустую строку."""
    if not isinstance(text, str):
        return []
    t = text.strip()
    if not t:
        return []
    return [(0, len(t), t[:12], ["sug"])]


def _clean(text, lang="auto", **kwargs):
    """Фейк check_text без опечаток."""
    return []


def _plugin(segments):
    class P:
        def get_text_segments(self, rom):
            return segments

    return P()


def _enc_plugin(meta):
    class Enc:
        def encode(self, text):
            return text.encode("ascii")

    class P:
        def get_pointer_table_meta(self):
            return meta

        def make_text_encoder(self):
            return Enc()

    return P()


def _seg(name, start, end, **extra):
    s = {
        "name": name,
        "start": start,
        "end": end,
        "decoder": CharMapDecoder(SIMPLE_CHARMAP),
        "compression": None,
    }
    s.update(extra)
    return s


def _patch_rom(path, chunks: dict[int, bytes]) -> None:
    with open(path, "r+b") as f:
        for offset, raw in chunks.items():
            f.seek(offset)
            f.write(raw)


class TestGateNormalPath:
    def test_soft_gate_reports_and_writes(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("test", ["XY", "worng"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.modified_data[0x4000] == 0x58
            assert inj.modified_data[0x4001] == 0x59
            assert len(inj.last_spellcheck_report) == 2
            e = next(r for r in inj.last_spellcheck_report if r["word"] == "worng")
            assert e["index"] == 1
            assert e["text"] == "worng"
            assert e["suggestions"] == ["sug"]
            assert isinstance(e["start"], int) and isinstance(e["end"], int)
        finally:
            os.unlink(path)

    def test_clean_text_empty_report(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _clean)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("test", ["XY", "AB"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_report_reset_between_injects(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            plugin = _plugin([seg])
            assert inj.inject_segment("test", ["wrong", "X"], plugin,
                                      segments=[seg]) is True
            assert len(inj.last_spellcheck_report) == 2
            monkeypatch.setattr("core.spell_checker.check_text", _clean)
            assert inj.inject_segment("test", ["X", "Y"], plugin,
                                      segments=[seg]) is True
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_report_reset_on_early_return_clears_stale(self):
        """P2: ранний return не оставляет stale-отчёт от прошлой операции."""
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            inj.last_spellcheck_report = [{"word": "stale"}]

            class NoMeta:
                def get_pointer_table_meta(self):
                    return None

            assert inj.inject_language_block("en", ["X"], NoMeta()) is False
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_no_report_when_segment_not_found(self, monkeypatch):
        """Гейт не заполняет отчёт, если сегмент не найден (записи не будет)."""
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("missing", ["wrong", "X"], _plugin([seg]),
                                      segments=[seg]) is False
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_skip_long_false_still_writes_but_no_report(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("test", ["XY", "xz"], _plugin([seg]),
                                      segments=[seg], skip_long=False) is True
            assert inj.modified_data[0x4000] == 0x58
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_gate_unit_skips_non_strings(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00"})
        try:
            inj = TextInjector(path)
            inj._run_spellcheck_gate([None, 3, b"bad", "ok"], skip_long=True)
            assert [r["text"] for r in inj.last_spellcheck_report] == ["ok"]
        finally:
            os.unlink(path)

    def test_gate_unit_empty_or_strict(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00"})
        try:
            inj = TextInjector(path)
            inj._run_spellcheck_gate([], skip_long=True)
            assert inj.last_spellcheck_report == []
            inj._run_spellcheck_gate(["worng"], skip_long=False)
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)


class TestGateInjectPaths:
    def test_fixed_width(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"ABCDEFGH"})
        try:
            inj = TextInjector(path)
            seg = _seg("fw", 0x4000, 0x4008, fixed_width=2)
            assert inj.inject_segment("fw", ["X", "worng", "Y", "Z"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.modified_data[0x4000] == 0x58
            assert len(inj.last_spellcheck_report) == 4
        finally:
            os.unlink(path)

    def test_compressed(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"\x99\x88"})
        try:
            inj = TextInjector(path)
            seg = {
                "name": "comp",
                "start": 0x4000,
                "end": 0x4002,
                "compression": "huffman",
                "encoder": lambda text: b"\x12\x34",
            }
            assert inj.inject_segment("comp", ["ziptypo"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.modified_data[0x4000] == 0x12
            assert len(inj.last_spellcheck_report) == 1
        finally:
            os.unlink(path)

    def test_pointer_dialogues(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = {
                "name": "dialogue",
                "start": 0x4000,
                "end": 0x4008,
                "kind": "pointer_dialogues",
                "decoder": CharMapDecoder(SIMPLE_CHARMAP),
                "terminator": b"\x00",
                "manifest": [
                    {"target": 0x4000, "free_after": 3, "original": "AB",
                     "raw": b"AB\x00"},
                    {"target": 0x4004, "free_after": 3, "original": "CD",
                     "raw": b"CD\x00"},
                ],
            }
            assert inj.inject_segment("dialogue", ["X", "worng"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.modified_data[0x4000] == 0x58
            assert len(inj.last_spellcheck_report) == 2
        finally:
            os.unlink(path)

    def test_bank_segment(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4020: b"AB\x00", 0x4030: b"CD\x00"})
        _patch_rom(path, {
            0x4000: (0x20).to_bytes(4, "little") + (0x30).to_bytes(4, "little"),
        })
        try:
            inj = TextInjector(path)
            seg = {
                "name": "bank",
                "start": 0x4000,
                "end": 0x4040,
                "compression": None,
                "decoder": CharMapDecoder(SIMPLE_CHARMAP),
                "bank_meta": {
                    "offsets": [0x20, 0x30],
                    "offsets_idx": [0, 1],
                    "count": 2,
                    "relocate": False,
                },
            }
            assert inj.inject_segment("bank", ["X", "worng"], _plugin([seg]),
                                      segments=[seg]) is True
            assert inj.modified_data[0x4020] == 0x58
            assert len(inj.last_spellcheck_report) == 2
        finally:
            os.unlink(path)

    def test_language_block(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"\x00\x00" + b"AB\x00\x00" + b"CD\x00\x00"})
        _patch_rom(path, {0x3000: struct.pack("<II", 0x08004000, 0x08004002)})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x3000, "count": 2, "blocks": [(0, 2, "en")]}
            plugin = _enc_plugin(meta)
            segs = [
                _seg("cvas_en_0", 0x4002, 0x4004),
                _seg("cvas_en_1", 0x4004, 0x4008),
            ]
            assert inj.inject_language_block("en", ["X", "Y"], plugin,
                                             segments=segs) is True
            assert inj.modified_data[0x4002] == 0x58
            assert inj.modified_data[0x4005] == 0x59
            assert struct.unpack("<I", bytes(inj.modified_data[0x3000:0x3004]))[0] == 0x08004002
            assert struct.unpack("<I", bytes(inj.modified_data[0x3004:0x3008]))[0] == 0x08004005
            assert len(inj.last_spellcheck_report) == 2
        finally:
            os.unlink(path)

    def test_interleaved_language(self, monkeypatch):
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00\x00" + b"CD\x00\x00"})
        _patch_rom(path, {0x3000: struct.pack("<III", 0x08004000, 0x08004000, 0x08004004)})
        try:
            inj = TextInjector(path)
            meta = {
                "table": 0x3000,
                "count": 2,
                "lang_slots": {"en": 0},
                "index_of": lambda idx, slot: idx * 2 + slot,
            }
            plugin = _enc_plugin(meta)
            segs = [
                {"lang": "en", "index": 0, "start": 0x4000, "end": 0x4004,
                 "injectable": True, "decoder": CharMapDecoder(SIMPLE_CHARMAP)},
                {"lang": "en", "index": 1, "start": 0x4004, "end": 0x4008,
                 "injectable": True, "decoder": CharMapDecoder(SIMPLE_CHARMAP)},
            ]
            assert inj.inject_interleaved_language("en", ["X", "worng"], plugin,
                                                   segments=segs) is True
            assert inj.modified_data[0x4000] == 0x58
            assert len(inj.last_spellcheck_report) == 2
        finally:
            os.unlink(path)

    def test_language_block_delegation_runs_gate_once(self, monkeypatch):
        """Делегирование block→interleaved не должно задваивать отчёт."""
        monkeypatch.setattr("core.spell_checker.check_text", _typo_everywhere)
        path = _build_test_rom({0x4000: b"AB\x00\x00" + b"CD\x00\x00"})
        _patch_rom(path, {0x3000: struct.pack("<III", 0x08004000, 0x08004000, 0x08004004)})
        try:
            inj = TextInjector(path)
            meta = {
                "table": 0x3000,
                "count": 2,
                "lang_slots": {"en": 0},
                "index_of": lambda idx, slot: idx * 2 + slot,
            }
            plugin = _enc_plugin(meta)
            segs = [
                {"lang": "en", "index": 0, "start": 0x4000, "end": 0x4004,
                 "injectable": True, "decoder": CharMapDecoder(SIMPLE_CHARMAP)},
                {"lang": "en", "index": 1, "start": 0x4004, "end": 0x4008,
                 "injectable": True, "decoder": CharMapDecoder(SIMPLE_CHARMAP)},
            ]
            assert inj.inject_language_block("en", ["X", "worng"], plugin,
                                             segments=segs) is True
            assert len(inj.last_spellcheck_report) == 2
        finally:
            os.unlink(path)


class TestGateRealChecker:
    @pytest.mark.slow
    def test_real_typos_reported_and_write_proceeds(self):
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("test", ["XY", "Это превет мир!"],
                                      _plugin([seg]), segments=[seg]) is True
            assert inj.modified_data[0x4000] == 0x58
            words = [r["word"] for r in inj.last_spellcheck_report]
            assert "превет" in words
        finally:
            os.unlink(path)

    @pytest.mark.slow
    def test_tokens_not_flagged(self):
        """Токен-строки у реального check_text не дают опечаток (без словаря)."""
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            inj._run_spellcheck_gate(
                ["[END] [LINE] %s {PLAYER} 12345", "[END] 123 456"],
                skip_long=True)
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)


def _bank_rom():
    """Синтетический ROM с банковым сегментом: таблица + 2 сообщения + FF-зона."""
    return _build_test_rom({
        0x40: struct.pack("<II", 12, 20),
        0x4C: b"HA\x00",
        0x54: b"YO\x00",
        0x80: b"\xFF" * 32,
    })


def _bank_seg(**extra):
    seg = {
        "name": "bank",
        "start": 0x40,
        "end": 0xC0,
        "decoder": CharMapDecoder(SIMPLE_CHARMAP),
        "bank_meta": {
            "offsets": [12, 20],
            "relocate": True,
            "free_zones": [(0x80, 0xA0)],
        },
    }
    seg.update(extra)
    return seg


class TestCoverageGaps:
    """Добивка покрытия core/injector.py синтетикой (без коммерческих ROM)."""

    def test_init_type_error(self):
        with pytest.raises(TypeError):
            TextInjector(123)

    def test_get_segments_cache_hit(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            plugin = _plugin([seg])
            assert inj._get_segments(plugin) == [seg]
            assert inj._get_segments(plugin) == [seg]
        finally:
            os.unlink(path)

    def test_inject_guards(self):
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment("x", [], None, segments=[seg]) is False
            assert inj.inject_segment(
                "nope", ["a"], _plugin([seg]), segments=[seg]) is False
            seg2 = _seg("test", 0x4000, 0x4010, injectable=False)
            assert inj.inject_segment(
                "test", ["AB"], _plugin([seg2]), segments=[seg2]) is False
            assert inj.inject_segment(
                "test", ["a", "b", "c"], _plugin([seg]), segments=[seg]) is False
            path2 = _build_test_rom({0x4000: b"\x00" * 16})
            try:
                inj2 = TextInjector(path2)
                assert inj2.inject_segment(
                    "test", [], _plugin([seg]), segments=[seg]) is True
            finally:
                os.unlink(path2)
        finally:
            os.unlink(path)

    def test_inject_no_segments_arg(self):
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment(
                "test", ["AB", "CD"], _plugin([seg])) is True
        finally:
            os.unlink(path)

    def test_compressed_empty_and_boom(self):
        enc = lambda t: t.encode("ascii")  # noqa: E731
        seg = {"name": "c", "start": 0x4000, "end": 0x4010, "encoder": enc}
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_segment(
                "c", [], _plugin([seg]), segments=[seg]) is True

            def boom(t):
                raise ValueError("nope")

            seg2 = {"name": "c", "start": 0x4000, "end": 0x4010, "encoder": boom}
            assert inj.inject_segment(
                "c", ["AB"], _plugin([seg2]), segments=[seg2]) is False
        finally:
            os.unlink(path)

    def test_save_writes_file(self, tmp_path):
        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            out = str(tmp_path / "out.gba")
            inj.save(out)
            assert os.path.exists(out)
        finally:
            os.unlink(path)

    def test_gate_checker_exception_isolated(self, monkeypatch):
        import core.spell_checker as sc_mod

        def boom(*args, **kwargs):
            raise RuntimeError("dict down")

        monkeypatch.setattr(sc_mod, "check_text", boom)
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            inj._run_spellcheck_gate(["hello"])
            assert inj.last_spellcheck_report == []
        finally:
            os.unlink(path)

    def test_collect_unmapped_chars(self):
        import types

        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            fake1 = types.SimpleNamespace(last_unmapped_chars=["ä", "ä"])
            fake2 = types.SimpleNamespace(last_unmapped_chars=["ö"])
            inj._segment_cache[object()] = [
                {"decoder": fake1}, {"decoder": object()},
                {"decoder": None}, {"decoder": fake2}]
            assert inj.collect_unmapped_chars() == ["ä", "ö"]
            assert fake1.last_unmapped_chars == []
            assert fake2.last_unmapped_chars == []
        finally:
            os.unlink(path)

    def test_compressed_multi_and_toolong(self):
        seg = {"name": "c", "start": 0x4000, "end": 0x4010,
               "encoder": lambda t: t.encode("ascii")}
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_segment(
                "c", ["AB", "CD"], _plugin([seg]), segments=[seg]) is True
            seg2 = {"name": "c", "start": 0x4000, "end": 0x4010,
                    "encoder": lambda t: b"X" * 100}
            assert inj.inject_segment(
                "c", ["AB"], _plugin([seg2]), segments=[seg2]) is False
            assert inj.inject_segment(
                "c", ["AB"], _plugin([seg2]), segments=[seg2],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_no_decoder_paths(self, monkeypatch):
        import core.scanner as sc_mod

        def boom(*args, **kwargs):
            raise RuntimeError("no scan")

        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            seg = {"name": "n", "start": 0, "end": 16}
            monkeypatch.setattr(sc_mod, "auto_detect_charmap", boom)
            assert inj.inject_segment(
                "n", ["AB"], _plugin([seg]), segments=[seg]) is False
            seg2 = {"name": "n", "start": 0, "end": 16, "decoder": object()}
            assert inj.inject_segment(
                "n", ["AB"], _plugin([seg2]), segments=[seg2]) is False
        finally:
            os.unlink(path)

    def test_encode_fail_and_toolong(self):
        class BoomDec:
            def encode(self, text):
                raise ValueError("nope")

            def decode(self, *args):
                return "AB"

        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010)
            seg["decoder"] = BoomDec()
            assert inj.inject_segment(
                "test", ["X", "Y"], _plugin([seg]), segments=[seg]) is False
            assert inj.inject_segment(
                "test", ["X", "Y"], _plugin([seg]), segments=[seg],
                skip_long=False) is False
            seg2 = _seg("test", 0x4000, 0x4010)
            assert inj.inject_segment(
                "test", ["TOOLONGTEXT", "x"], _plugin([seg2]), segments=[seg2],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_fixed_slot_branches(self):
        data = {0x4000: b"ABCDEFGH" b"IJKLMNOP"}
        path = _build_test_rom(data)
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4010, fixed_width=8, record_count=2)
            assert inj.inject_segment(
                "test", ["12345678", "x"], _plugin([seg]),
                segments=[seg]) is True
            assert inj.inject_segment(
                "test", ["12345678", "x"], _plugin([seg]), segments=[seg],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_inject_message_bounds(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            with pytest.raises(ValueError):
                inj._inject_message(-1, b"A", 1)
        finally:
            os.unlink(path)

    def test_bank_fit_and_mismatch(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg()
            assert inj.inject_segment(
                "bank", ["HA", "YO"], _plugin([seg]), segments=[seg]) is True
            assert inj.inject_segment(
                "bank", ["a", "b", "c"], _plugin([seg]),
                segments=[seg]) is False
        finally:
            os.unlink(path)
        path2 = _build_test_rom({
            0x40: struct.pack("<II", 12, 20),
            0x4C: b"HA\x00",
        })
        try:
            inj2 = TextInjector(path2)
            seg2 = _bank_seg()
            assert inj2.inject_segment(
                "bank", ["a", "b"], _plugin([seg2]), segments=[seg2]) is False
            seg3 = _bank_seg(bank_meta={"offsets": []})
            assert inj2.inject_segment(
                "bank", [], _plugin([seg3]), segments=[seg3]) is True
        finally:
            os.unlink(path2)

    def test_bank_encode_fail(self):
        class BoomDec:
            def encode(self, text):
                raise ValueError("nope")

            def decode(self, *args):
                return "HA"

        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg()
            seg["decoder"] = BoomDec()
            assert inj.inject_segment(
                "bank", ["X", "Y"], _plugin([seg]), segments=[seg]) is False
            assert inj.inject_segment(
                "bank", ["X", "Y"], _plugin([seg]), segments=[seg],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_bank_toolong_paths(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg(bank_meta={"offsets": [12, 20]})
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([seg]),
                segments=[seg]) is True
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([seg]), segments=[seg],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_bank_relocate_success(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg()
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([seg]),
                segments=[seg]) is True
            assert bytes(inj.modified_data[0x80:0x8A]) == b"WAYTOOLONG"
            assert bytes(inj.modified_data[0x44:0x48]) == struct.pack("<I", 0x40)
        finally:
            os.unlink(path)

    def test_bank_relocate_guards(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg()
            assert inj._inject_bank_record_relocate(
                seg, 99, b"AB", True) is False
            seg0 = _bank_seg(bank_meta={"offsets": [12], "offsets_idx": [0]})
            assert inj._inject_bank_record_relocate(
                seg0, 0, b"AB", True) is False
        finally:
            os.unlink(path)

    def test_bank_relocate_far_zone(self):
        import struct as _st

        chunks = {
            0x40: _st.pack("<I", 8),
            0x48: b"Hi\x00",
            0x200: b"\xFF" * 16,
        }
        path = _build_test_rom(chunks)
        try:
            inj = TextInjector(path)
            seg = _bank_seg(start=0x40, end=0xC0, bank_meta={
                "offsets": [8], "offsets_idx": [1],
                "max_reloc_offset": 0x10, "free_zones": [(0x200, 0x210)]})
            inj._bank_segments = [seg]
            assert inj._inject_bank_record_relocate(
                seg, 0, b"AB", True) is False
        finally:
            os.unlink(path)

    def test_bank_free_scan_loop(self):
        chunks = {0x200: b"\x41\x41" + b"\xFF" * 12}
        path = _build_test_rom(chunks)
        try:
            inj = TextInjector(path)
            inj._bank_segments = []
            seg = _bank_seg(start=0x40, end=0xC0, bank_meta={
                "offsets": [], "free_zones": [(0x200, 0x20C)]})
            assert inj._find_bank_free_block(
                seg, 4, orig_abs=0, table_idx=1) == 0x202
        finally:
            os.unlink(path)

    def test_occupied_and_interval(self):
        path = _build_test_rom({0: struct.pack("<I", 8), 8: b"AB\x00"})
        try:
            inj = TextInjector(path)
            inj._bank_segments = [{}]
            assert inj._occupied_intervals() == []
            seg = _bank_seg(start=0, end=64, bank_meta={"table_count": 1})
            inj._bank_segments = [seg]
            assert inj._occupied_intervals() == [(8, 10)]
            seg_far = _bank_seg(start=0, end=64, bank_meta={"table_count": 9000})
            inj._bank_segments = [seg_far]
            assert (8, 10) in inj._occupied_intervals()
            assert inj._interval_free((15, 25), [(10, 20)], 0) is False
            assert inj._interval_free((30, 40), [(10, 20)], 0) is True
            assert inj._interval_free((0, 3), [(0, 5)], 0) is True
            seg2 = _bank_seg(start=0x40, end=0xC0, bank_meta={
                "offsets": [], "free_zones": [(0x300, 0x310)]})
            assert inj._find_bank_free_block(
                seg2, 4, orig_abs=0, table_idx=1) is None
        finally:
            os.unlink(path)

    def test_find_taken_overlap(self):
        path = _build_test_rom({0x202: b"\xFF" * 8})
        try:
            inj = TextInjector(path)
            inj._bank_segments = []
            inj._taken_free_blocks = [(0x202, 0x20A)]
            seg = _bank_seg(start=0x40, end=0xC0, bank_meta={
                "offsets": [], "free_zones": [(0x200, 0x220)]})
            assert inj._find_bank_free_block(
                seg, 4, orig_abs=9, table_idx=1) is None
        finally:
            os.unlink(path)
        path2 = _build_test_rom({0: b"\xFF\xFF\xFF\xFF"})
        try:
            inj2 = TextInjector(path2)
            seg2 = _bank_seg(start=0, end=64, bank_meta={"table_count": 1})
            inj2._bank_segments = [seg2]
            assert inj2._occupied_intervals() == []
        finally:
            os.unlink(path2)

    def test_bank_record_bound(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj._bank_record_bound(bytearray(b"ABCD"), 0, 4, {}) == 4
            assert inj._bank_record_bound(
                bytearray(b"\x01AB"), 0, 3, {1: 1}) == 3
        finally:
            os.unlink(path)

    def test_extract_bank_messages_branches(self):
        path = _build_test_rom({8: b"AB\x00"})
        try:
            inj = TextInjector(path)
            base = {"name": "b", "start": 0, "end": 64,
                    "decoder": CharMapDecoder(SIMPLE_CHARMAP)}
            seg = dict(base, bank_meta={"offsets": [1000], "offsets_idx": [100]})
            assert inj._extract_bank_messages(seg) == []
            seg2 = dict(base, bank_meta={"offsets": [8], "offsets_idx": [0]})
            path2 = None
            try:
                import struct as _st2

                path2 = _build_test_rom(
                    {0: _st2.pack("<I", 0xFFFFFFFF), 8: b"AB\x00"})
                inj2 = TextInjector(path2)
                msgs = inj2._extract_bank_messages(seg2)
                assert len(msgs) == 1
            finally:
                if path2:
                    os.unlink(path2)
            seg3 = dict(base, bank_meta={"offsets": [8], "offsets_idx": [0]})
            path3 = _build_test_rom({0: struct.pack("<I", 8), 8: b"\x00"})
            try:
                inj3 = TextInjector(path3)
                assert inj3._extract_bank_messages(seg3) == []
            finally:
                os.unlink(path3)

            class BoomDec:
                def _decode_one(self, data, s, e):
                    raise RuntimeError("nope")

            seg4 = dict(base, bank_meta={"offsets": [8], "offsets_idx": [0]},
                        decoder=BoomDec())
            path4 = _build_test_rom({0: struct.pack("<I", 8), 8: b"AB\x00"})
            try:
                inj4 = TextInjector(path4)
                msgs = inj4._extract_bank_messages(seg4)
                assert len(msgs) == 1 and msgs[0]["text"] == ""
            finally:
                os.unlink(path4)
        finally:
            os.unlink(path)

    def test_pointer_dialogues_branches(self):
        path = _build_test_rom({0x4000: b"\x00" * 32})
        try:
            inj = TextInjector(path)
            seg = {"name": "p", "start": 0, "end": 16, "decoder": None,
                   "kind": "pointer_dialogues"}
            assert inj.inject_segment(
                "p", ["a"], _plugin([seg]), segments=[seg]) is False
            dec = CharMapDecoder(SIMPLE_CHARMAP)
            seg2 = {"name": "p", "start": 0x4000, "end": 0x4020,
                    "decoder": dec, "kind": "pointer_dialogues",
                    "manifest": [{"target": 0x4000, "free_after": 16}]}
            assert inj.inject_segment(
                "p", ["A", "B"], _plugin([seg2]), segments=[seg2]) is False
            assert inj.inject_segment(
                "p", [], _plugin([seg2]), segments=[{**seg2, "manifest": []}]) is True
            seg3 = {**seg2, "manifest": [{
                "target": 0x4000, "free_after": 16,
                "raw": b"AB", "original": "AB"}]}
            assert inj.inject_segment(
                "p", ["AB"], _plugin([seg3]), segments=[seg3]) is True
            assert bytes(inj.modified_data[0x4000:0x4003]) == b"AB\xff"

            class BoomDec:
                def encode(self, text):
                    raise ValueError("nope")

            seg4 = {**seg2, "decoder": BoomDec()}
            assert inj.inject_segment(
                "p", ["X"], _plugin([seg4]), segments=[seg4]) is False
            assert inj.inject_segment(
                "p", ["X"], _plugin([seg4]), segments=[seg4],
                skip_long=False) is False
            assert inj.inject_segment(
                "p", ["A" * 40], _plugin([seg2]), segments=[seg2],
                skip_long=False) is False
        finally:
            os.unlink(path)

    def test_extract_no_trailing_terminator(self):
        path = _build_test_rom({0x4000: b"AB\x00CD"})
        try:
            inj = TextInjector(path)
            seg = _seg("test", 0x4000, 0x4005)
            msgs = inj._extract_original_messages(seg)
            assert [m["text"] for m in msgs] == ["AB", "CD"]
        finally:
            os.unlink(path)

    def test_fixed_slots_branches(self):
        path = _build_test_rom(
            {0x4000: b"AB\x00CD\x00" + b"\x00" * 8})
        try:
            inj = TextInjector(path)
            msgs = inj._extract_original_messages(
                _seg("test", 0x4000, 0x4010, fixed_width=8, record_count=10))
            assert isinstance(msgs, list)

            class BoomDec:
                def decode(self, *args):
                    raise RuntimeError("nope")

            seg2 = _seg("test", 0x4000, 0x4010, fixed_width=8, record_count=2)
            seg2["decoder"] = BoomDec()
            assert inj._extract_original_messages(seg2) == []
        finally:
            os.unlink(path)

    def test_language_block_guards(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_language_block("en", [], object()) is False
            assert inj.inject_language_block(
                "en", [], _enc_plugin({"table": "x", "count": 2})) is False
            assert inj.inject_language_block(
                "en", [], _enc_plugin({"table": 1})) is False
        finally:
            os.unlink(path)

    def test_language_block_mismatch_paths(self):
        import struct as _st

        chunks = {
            0x100: _st.pack("<III", 0x08000200, 0x08000300, 0x08000400),
            0x200: b"AB\x00",
            0x300: b"CD\x00",
            0x400: b"EF\x00",
        }
        path = _build_test_rom(chunks)
        try:
            inj = TextInjector(path)
            meta = {"table": 0x100, "count": 3, "blocks": [(0, 3, "en")]}
            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            plug = _enc_plugin(meta)
            assert inj.inject_language_block(
                "en", ["X", "Y"], plug, segments=segs) is False
            bad = _build_test_rom(
                {0x100: _st.pack("<II", 0x08FFFFFF, 0x08FFFFFF)})
            try:
                inj2 = TextInjector(bad)
                meta2 = {"table": 0x100, "count": 2, "blocks": [(0, 2, "en")]}
                assert inj2.inject_language_block(
                    "en", ["X", "Y"], _enc_plugin(meta2),
                    segments=segs) is False
            finally:
                os.unlink(bad)
        finally:
            os.unlink(path)

    def test_language_block_no_encoder_and_ranges(self):
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)

            class NoEnc:
                def get_pointer_table_meta(self):
                    return {"table": 0x100, "count": 2,
                            "blocks": [(0, 2, "en")]}

                def get_text_segments(self, rom):
                    return []

            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            assert inj.inject_language_block(
                "en", ["X", "Y"], NoEnc(), segments=segs) is False
            assert inj._block_ranges(
                [(5, 2, "en")], [], [0x100] * 4, 4, 0x8000) == [(0, 0)]
        finally:
            os.unlink(path)

    def test_language_block_relocate_fail(self, monkeypatch):
        import core.pointer_table as pt_mod

        monkeypatch.setattr(pt_mod, "find_free_space", lambda *a, **k: None)
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x100, "count": 2, "blocks": [(0, 2, "en")]}
            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            assert inj.inject_language_block(
                "en", ["X" * 0x200, "Y" * 0x200], _enc_plugin(meta),
                segments=segs) is False
        finally:
            os.unlink(path)

    def test_interleave_guards(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)

            class BadMeta:
                def get_pointer_table_meta(self):
                    return {"table": 0, "count": 1,
                            "lang_slots": {"en": 0}, "index_of": "x"}

            assert inj.inject_interleaved_language("en", ["a"], BadMeta()) is False

            class NoSegs:
                def get_pointer_table_meta(self):
                    return {"table": 0, "count": 1,
                            "lang_slots": {"en": 0},
                            "index_of": lambda i, s: i}

                def get_text_segments(self, rom):
                    return []

            assert inj.inject_interleaved_language("en", ["a"], NoSegs()) is False

            class NoEnc(NoSegs):
                pass

            assert inj.inject_interleaved_language(
                "en", [], NoEnc(),
                segments=[{"lang": "en", "index": 0}]) is False
        finally:
            os.unlink(path)

    def test_interleave_missing_idx_and_boom(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x180, "count": 1, "lang_slots": {"en": 0},
                    "index_of": lambda i, s: i}
            segs = [{"lang": "en", "index": 1, "start": 0x100, "end": 0x110}]
            assert inj.inject_interleaved_language(
                "en", ["a"], _enc_plugin(meta), segments=segs) is False

            class BoomEnc:
                def encode(self, text):
                    raise RuntimeError("nope")

            class BoomPlug:
                def get_pointer_table_meta(self):
                    return meta

                def make_text_encoder(self):
                    return BoomEnc()

            segs2 = [{"lang": "en", "index": 0, "start": 0x100, "end": 0x110}]
            assert inj.inject_interleaved_language(
                "en", ["a"], BoomPlug(), segments=segs2) is False
        finally:
            os.unlink(path)

    def test_language_block_table_guards(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_language_block(
                "en", [], _enc_plugin(
                    {"table": -1, "count": 2, "blocks": [(0, 2, "en")]}),
                segments=[]) is False
            assert inj.inject_language_block(
                "en", [], _enc_plugin(
                    {"table": 0x100, "count": 2, "blocks": [(2, 1, "en")]}),
                segments=[]) is False
            assert inj.inject_language_block(
                "en", [], _enc_plugin(
                    {"table": 0x100, "count": 2, "blocks": [(0, 2, "fr")]}),
                segments=[]) is False
        finally:
            os.unlink(path)

    def test_language_block_segs_mismatch(self):
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x100, "count": 2, "blocks": [(0, 2, "en")]}
            segs = [{"name": "cvas_en_0", "start": 0x200, "end": 0x210}]
            assert inj.inject_language_block(
                "en", ["X", "Y"], _enc_plugin(meta), segments=segs) is False
        finally:
            os.unlink(path)

    def test_language_block_encoder_boom(self):
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)

            class BoomEnc:
                def encode(self, text):
                    raise ValueError("nope")

            class BoomPlug:
                def get_pointer_table_meta(self):
                    return {"table": 0x100, "count": 2,
                            "blocks": [(0, 2, "en")]}

                def make_text_encoder(self):
                    return BoomEnc()

            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            assert inj.inject_language_block(
                "en", ["X", "Y"], BoomPlug(), segments=segs) is False
        finally:
            os.unlink(path)

    def test_language_block_pad_tail(self):
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x100, "count": 2, "blocks": [(0, 2, "en")]}
            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            assert inj.inject_language_block(
                "en", ["", ""], _enc_plugin(meta), segments=segs) is True
        finally:
            os.unlink(path)

    def test_language_block_relocate_success(self):
        path = _build_test_rom({
            0x100: struct.pack("<II", 0x08000200, 0x08000300),
            0x400: b"\xFF" * 0x500,
        })
        try:
            inj = TextInjector(path)
            meta = {"table": 0x100, "count": 2, "blocks": [(0, 2, "en")]}
            segs = [
                {"name": "cvas_en_0", "start": 0x200, "end": 0x210},
                {"name": "cvas_en_1", "start": 0x300, "end": 0x310},
            ]
            assert inj.inject_language_block(
                "en", ["X" * 0x200, "Y" * 0x200], _enc_plugin(meta),
                segments=segs) is True
        finally:
            os.unlink(path)

    def test_block_ranges_branches(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj._block_ranges(
                [(0, 1, "en")], [], [0x100, 0x200, 0x300], 3, 0x8000
            ) == [(0x100, 0x200)]
            assert inj._block_ranges(
                [(0, 2, "en")],
                [{"name": "cvas_fr_0", "start": 0, "end": 0x50},
                 {"name": "cvas_en_0", "start": 0x200, "end": 0x280}],
                [0x100, 0x200], 2, 0x8000,
            ) == [(0x100, 0x280)]
        finally:
            os.unlink(path)

    def test_interleave_meta_guards(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_interleaved_language("en", [], object()) is False
            assert inj.inject_interleaved_language(
                "en", [], _enc_plugin({"table": "x", "count": 1})) is False

            class NoSlots:
                def get_pointer_table_meta(self):
                    return {"table": 0, "count": 1}

            assert inj.inject_interleaved_language("en", [], NoSlots()) is False
            meta0 = {"table": 0, "count": 0, "lang_slots": {"en": 0},
                     "index_of": lambda i, s: i}
            assert inj.inject_interleaved_language(
                "en", [], _enc_plugin(meta0), segments=[]) is False
        finally:
            os.unlink(path)

    def test_interleave_two_segs_loop(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x180, "count": 1, "lang_slots": {"en": 0},
                    "index_of": lambda i, s: i}
            segs = [
                {"lang": "fr", "index": 0, "start": 0, "end": 8},
                {"lang": "en", "index": 0, "start": 0x100, "end": 0x104},
            ]
            assert inj.inject_interleaved_language(
                "en", ["Z"], _enc_plugin(meta), segments=segs) is True
        finally:
            os.unlink(path)

    def test_interleave_catalog_skip_and_value_error(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            meta = {"table": 0x180, "count": 1, "lang_slots": {"en": 0},
                    "index_of": lambda i, s: i}
            segs = [{"lang": "en", "index": 0, "start": 0x100, "end": 0x110,
                     "injectable": False}]
            assert inj.inject_interleaved_language(
                "en", ["Z"], _enc_plugin(meta), segments=segs) is False

            class ValueEnc:
                def encode(self, text):
                    raise ValueError("nope")

            class ValuePlug:
                def get_pointer_table_meta(self):
                    return meta

                def make_text_encoder(self):
                    return ValueEnc()

            segs2 = [{"lang": "en", "index": 0, "start": 0x100, "end": 0x110}]
            assert inj.inject_interleaved_language(
                "en", ["Z"], ValuePlug(), segments=segs2) is False
        finally:
            os.unlink(path)

    def test_interleave_expand(self):
        chunks = {0x100: b"\x00" * 16, 0x180: b"\x00" * 4}
        path = _build_test_rom(chunks)
        try:
            inj = TextInjector(path)
            before = len(inj.modified_data)
            meta = {"table": 0x180, "count": 1, "lang_slots": {"en": 0},
                    "index_of": lambda i, s: i}
            segs = [{"lang": "en", "index": 0, "start": 0x100, "end": 0x110}]
            assert inj.inject_interleaved_language(
                "en", ["A" * 32], _enc_plugin(meta), segments=segs) is True
            assert len(inj.modified_data) > before
        finally:
            os.unlink(path)

    def test_bank_empty_and_relocate_fail(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg(bank_meta={"offsets": []})
            assert inj.inject_segment(
                "bank", [], _plugin([seg]), segments=[seg]) is True
            tiny = _bank_seg(bank_meta={
                "offsets": [12, 20], "relocate": True,
                "free_zones": [(0x80, 0x84)]})
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([tiny]),
                segments=[tiny]) is True
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([tiny]),
                segments=[tiny], skip_long=False) is False
        finally:
            os.unlink(path)

    def test_bank_relocate_protected_and_mocked(self, monkeypatch):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            prot = _bank_seg(bank_meta={
                "offsets": [12, 20], "offsets_idx": [5, 1], "relocate": True,
                "free_zones": [(0x80, 0xA0)], "protected_records": [0x4C]})
            assert inj._inject_bank_record_relocate(
                prot, 0, b"WAYTOOLONG", True) is False
            far = _bank_seg(bank_meta={
                "offsets": [8], "offsets_idx": [1],
                "max_reloc_offset": 0x10, "free_zones": [(0x200, 0x210)]})
            monkeypatch.setattr(
                inj, "_find_bank_free_block", lambda *a, **k: 0x200)
            assert inj._inject_bank_record_relocate(
                far, 0, b"AB", True) is False
        finally:
            os.unlink(path)

    def test_bank_relocate_guard_false(self):
        path = _bank_rom()
        try:
            inj = TextInjector(path)
            seg = _bank_seg(bank_meta={
                "offsets": [12, 20], "offsets_idx": [0, 100000],
                "relocate": True, "free_zones": [(0x80, 0xA0)]})
            assert inj.inject_segment(
                "bank", ["HA", "WAYTOOLONG"], _plugin([seg]),
                segments=[seg]) is True
        finally:
            os.unlink(path)

    def test_occupied_append_and_scan_miss(self):
        path = _build_test_rom({0: struct.pack("<I", 8), 8: b"AB\x00"})
        try:
            inj = TextInjector(path)
            seg = _bank_seg(start=0, end=64, bank_meta={"table_count": 1})
            inj._bank_segments = [seg]
            assert inj._occupied_intervals() == [(8, 10)]
            seg2 = _bank_seg(start=0x40, end=0xC0, bank_meta={
                "offsets": [], "free_zones": [(0x300, 0x310)]})
            assert inj._find_bank_free_block(
                seg2, 4, orig_abs=0, table_idx=1) is None
            assert inj._interval_free((0, 3), [(0, 5)], 0) is True
        finally:
            os.unlink(path)

    def test_extract_oob_and_raise(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            dec = CharMapDecoder(SIMPLE_CHARMAP)
            seg = {"name": "b", "start": 0, "end": 64, "decoder": dec,
                   "bank_meta": {"offsets": [40000], "offsets_idx": [9000]}}
            assert inj._extract_bank_messages(seg) == []

            class BoomDec:
                def decode(self, *args):
                    raise RuntimeError("nope")

            seg2 = {"name": "t", "start": 0x4000, "end": 0x4010,
                    "decoder": BoomDec()}
            path2 = _build_test_rom({0x4000: b"AB\x00CD\x00"})
            try:
                inj2 = TextInjector(path2)
                msgs = inj2._extract_original_messages(seg2)
                assert len(msgs) == 2 and all(m["text"] == "" for m in msgs)
            finally:
                os.unlink(path2)
        finally:
            os.unlink(path)

    def test_pointer_direct_calls(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            dec = CharMapDecoder(SIMPLE_CHARMAP)
            assert inj._inject_pointer_dialogues(
                {"decoder": None, "manifest": [{"target": 0, "free_after": 8}]},
                ["a"], True) is False
            assert inj._inject_pointer_dialogues(
                {"decoder": dec, "manifest": []}, [], True) is True
            seg = {"decoder": dec, "pointer_encoder": lambda t: t.encode("ascii"),
                   "manifest": [{"target": 0x4000, "free_after": 16}],
                   "terminator": b"\xff"}
            path2 = _build_test_rom({0x4000: b"\x00" * 16})
            try:
                inj2 = TextInjector(path2)
                assert inj2._inject_pointer_dialogues(seg, ["AB"], True) is True
            finally:
                os.unlink(path2)
        finally:
            os.unlink(path)

    def test_language_block_no_segments_arg(self):
        path = _build_test_rom({0x100: struct.pack("<II", 0x08000200, 0x08000300)})
        try:
            inj = TextInjector(path)

            class SegPlug:
                def get_pointer_table_meta(self):
                    return {"table": 0x100, "count": 2,
                            "blocks": [(0, 2, "en")]}

                def get_text_segments(self, rom):
                    return []

                def make_text_encoder(self):
                    class Enc:
                        def encode(self, text):
                            return text.encode("ascii")

                    return Enc()

            assert inj.inject_language_block("en", ["X", "Y"], SegPlug()) is False
        finally:
            os.unlink(path)

    def test_language_block_no_such_lang(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            assert inj.inject_language_block(
                "en", [], _enc_plugin(
                    {"table": 0x100, "count": 2, "blocks": [(0, 2, "fr")]}),
                segments=[]) is False
        finally:
            os.unlink(path)

    def test_pointer_and_extract_direct(self):
        path = _build_test_rom({})
        try:
            inj = TextInjector(path)
            dec = CharMapDecoder(SIMPLE_CHARMAP)
            assert inj._inject_pointer_dialogues(
                {"decoder": None, "manifest": [{"target": 0, "free_after": 8}]},
                ["a"], True) is False
            assert inj._inject_pointer_dialogues(
                {"decoder": dec, "manifest": []}, [], True) is True
            seg = {"decoder": dec,
                   "pointer_encoder": lambda t: t.encode("ascii"),
                   "manifest": [{"target": 0x4000, "free_after": 16}],
                   "terminator": b"\xff"}
            path2 = _build_test_rom({0x4000: b"\x00" * 16})
            try:
                inj2 = TextInjector(path2)
                assert inj2._inject_pointer_dialogues(seg, ["AB"], True) is True
            finally:
                os.unlink(path2)
            big = {"name": "b", "start": 0, "end": 64, "decoder": dec,
                   "bank_meta": {"offsets": [40000], "offsets_idx": [9000]}}
            assert inj._extract_bank_messages(big) == []

            class BoomDec:
                def decode(self, *args):
                    raise RuntimeError("nope")

            nseg = {"name": "t", "start": 0x4000, "end": 0x4010,
                    "decoder": BoomDec()}
            path3 = _build_test_rom({0x4000: b"AB\x00CD\x00"})
            try:
                inj3 = TextInjector(path3)
                msgs = inj3._extract_original_messages(nseg)
                assert len(msgs) == 2 and all(m["text"] == "" for m in msgs)
            finally:
                os.unlink(path3)
        finally:
            os.unlink(path)

    def test_interleave_full_no_expand(self):
        chunks = {0: b"\x41" * 0x8000,
                  0x100: b"\x00" * 16,
                  0x180: b"\x00" * 4}
        path = _build_test_rom(chunks)
        try:
            inj = TextInjector(path)
            meta = {"table": 0x180, "count": 1, "lang_slots": {"en": 0},
                    "index_of": lambda i, s: i}
            segs = [{"lang": "en", "index": 0, "start": 0x100, "end": 0x110}]
            assert inj.inject_interleaved_language(
                "en", ["A" * 200], _enc_plugin(meta), segments=segs,
                expand_if_full=False) is False
        finally:
            os.unlink(path)
