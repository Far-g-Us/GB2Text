"""Тесты F1: симулятор textbox (core/textbox.py) + хук инжектора."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.textbox import fit_report, segment_width, split_lines


class TestSplitLines:
    def test_plain_wrap(self):
        assert split_lines("AB CD EF", 5) == ["AB CD", "EF"]

    def test_newline_forces_break(self):
        assert split_lines("AB\nCD", 10) == ["AB", "CD"]

    def test_tokens_not_split(self):
        assert split_lines("A [END] B", 5) == ["A", "[END]", "B"]

    def test_long_word_hard_split(self):
        assert split_lines("ABCDEFGH", 3) == ["ABC", "DEF", "GH"]

    def test_empty_and_spaces(self):
        assert split_lines("", 5) == [""]
        assert split_lines("   ", 5) == [""]

    def test_width_floor(self):
        assert split_lines("AB", 0) == ["A", "B"]
        assert split_lines("AB", -3) == ["A", "B"]

    def test_token_with_spaces_around(self):
        assert split_lines("X {VAR} Y", 6) == ["X", "{VAR}", "Y"]

    def test_percent_token(self):
        assert split_lines("100%s done", 6) == ["100%s", "done"]

    def test_token_inside_word(self):
        assert split_lines("AB[END]CD", 20) == ["AB[END]CD"]
        assert split_lines("AB[END]CD", 4) == ["AB", "[END", "]CD"]

    def test_unclosed_bracket_no_hang(self):
        assert split_lines("[", 10) == ["["]
        assert split_lines("a [ b", 2) == ["a", "[", "b"]

    def test_hard_split_flushes_current(self):
        assert split_lines("AB CDEFGH", 5) == ["AB", "CDEFG", "H"]


class TestSegmentWidth:
    def test_max_length_priority(self):
        assert segment_width({"max_length": 10, "fixed_width": 8}) == 10

    def test_fixed_width_fallback(self):
        assert segment_width({"fixed_width": 8}) == 7

    def test_no_data(self):
        assert segment_width({}) is None
        assert segment_width({"fixed_width": 1}) is None

    def test_non_int_ignored(self):
        assert segment_width({"max_length": "10"}) is None
        assert segment_width({"max_length": True}) is None
        assert segment_width({"max_length": 0}) == 0
        assert segment_width({"fixed_width": True}) is None
        assert segment_width({}) is None


class TestFitReport:
    def test_ok_short(self):
        [entry] = fit_report({"max_length": 10}, ["AB CD"])
        assert entry == {"index": 0, "ok": True, "overflow_chars": 0, "lines_used": 1}

    def test_long_word_fails(self):
        [entry] = fit_report({"max_length": 5}, ["ABCDEFGH"])
        assert entry["ok"] is False
        assert entry["overflow_chars"] == 8 - 5
        assert entry["lines_used"] == 2

    def test_explicit_width_beats_segment(self):
        [entry] = fit_report({"max_length": 2}, ["ABCDE"], width=10)
        assert entry["ok"] is True

    def test_no_width_no_noise(self):
        [entry] = fit_report({}, ["anything at all here"])
        assert entry == {"index": 0, "ok": True, "overflow_chars": 0, "lines_used": 1}

    def test_non_string_coerced(self):
        [entry] = fit_report({"max_length": 10}, [None])
        assert entry["ok"] is True

    def test_token_longer_than_width(self):
        [entry] = fit_report({"max_length": 3}, ["[LONGTOKEN]"])
        assert entry["ok"] is False

    def test_indexes(self):
        report = fit_report({"max_length": 2}, ["A", "TOOLONGTEXT"])
        assert [r["index"] for r in report] == [0, 1]
        assert report[0]["ok"] is True
        assert report[1]["ok"] is False

    def test_zero_width(self):
        [entry] = fit_report({"max_length": 0}, ["A"])
        assert entry["ok"] is False
        assert entry["overflow_chars"] == 1
        [empty] = fit_report({"max_length": 0}, [""])
        assert empty["ok"] is True

    def test_none_translations(self):
        assert fit_report({"max_length": 10}, None) == []

    def test_bank_segment_no_data(self):
        report = fit_report({"name": "bank", "bank_meta": {}}, ["anything"])
        assert report[0]["ok"] is True


class TestInjectorHook:
    def _injector(self, path):
        from core.injector import TextInjector

        return TextInjector(path)

    def test_fit_report_on_segment(self):
        from core.decoder import CharMapDecoder
        from tests.test_injector import SIMPLE_CHARMAP, _build_test_rom

        class P:
            def __init__(self, segments):
                self._segments = segments

            def get_text_segments(self, rom):
                return self._segments

        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = self._injector(path)
            seg = {
                "name": "t",
                "start": 0x4000,
                "end": 0x4010,
                "decoder": CharMapDecoder(SIMPLE_CHARMAP),
                "max_length": 2,
            }
            assert inj.last_fit_report == []
            assert inj.inject_segment("t", ["AB", "TOOLONGTEXT"], P([seg]), segments=[seg]) is True
            assert len(inj.last_fit_report) == 2
            assert inj.last_fit_report[0]["ok"] is True
            assert inj.last_fit_report[1]["ok"] is False
            # report-only: запись произошла, несмотря на overflow в отчёте
            assert bytes(inj.modified_data[0x4000:0x4002]) == b"AB"
        finally:
            os.unlink(path)

    def test_fit_reset_in_language_entries(self):
        from tests.test_injector import _build_test_rom

        path = _build_test_rom({})
        try:
            inj = self._injector(path)
            inj.last_fit_report = [{"index": 0}]
            inj.last_spellcheck_report = [{"index": 0}]
            assert inj.inject_language_block("en", [], object()) is False
            assert inj.last_fit_report == []
            assert inj.last_spellcheck_report == []
            assert inj.inject_interleaved_language("en", [], object()) is False
            assert inj.last_fit_report == []
        finally:
            os.unlink(path)

    def test_reports_coexist(self):
        from core.decoder import CharMapDecoder
        from core.injector import TextInjector
        from tests.test_injector import SIMPLE_CHARMAP, _build_test_rom

        path = _build_test_rom({0x4000: b"AB\x00CD\x00"})
        try:
            inj = TextInjector(path)

            class P:
                def get_text_segments(self, rom):
                    return [seg]

            seg = {
                "name": "t",
                "start": 0x4000,
                "end": 0x4010,
                "decoder": CharMapDecoder(SIMPLE_CHARMAP),
                "max_length": 2,
            }
            inj.inject_segment("t", ["AB", "CD"], P(), segments=[seg])
            assert inj.last_fit_report != []
            assert inj.last_spellcheck_report == []
            assert inj.last_overflow_report == []
        finally:
            os.unlink(path)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
