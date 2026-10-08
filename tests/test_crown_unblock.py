"""Crown unblock (б): strict-encode, пустые слоты, кириллица (синтетика)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from plugins.gba_pokemon import (
    CHARMAP_FIRERED,
    CHARMAP_POKEMON_GBA,
    CYRILLIC_FIRERED,
    PokemonFixedTextDecoder,
    PokemonTextDecoder,
    _encode_pokemon_text,
)


class TestStrict:
    def test_dialogue_default_fallback(self):
        out = _encode_pokemon_text("A\U0001F600", CHARMAP_FIRERED)
        assert out == bytes([0xBB, 0x00])

    def test_dialogue_strict_raises(self):
        with pytest.raises(ValueError):
            _encode_pokemon_text("A\U0001F600", CHARMAP_FIRERED, strict=True)
        assert _encode_pokemon_text("AB", CHARMAP_FIRERED, strict=True) == bytes([0xBB, 0xBC])

    def test_decoder_strict_passthrough(self):
        dec = PokemonTextDecoder(CHARMAP_FIRERED)
        assert dec.encode("AB") == bytes([0xBB, 0xBC])
        with pytest.raises(ValueError):
            dec.encode("A\U0001F600", strict=True)

    def test_fixed_strict(self):
        dec = PokemonFixedTextDecoder(CHARMAP_FIRERED)
        with pytest.raises(ValueError):
            dec.encode("\U0001F600", strict=True)

    def test_fixed_cyrillic_roundtrip(self):
        dec = PokemonFixedTextDecoder(CHARMAP_FIRERED)
        for text in ("ПРИВЕТ", "Жук", "Ё"):
            raw = dec.encode(text, strict=True)
            assert dec.decode(raw, 0, len(raw)) == text


class TestCyrillicTable:
    def test_size_and_disjoint(self):
        assert len(CYRILLIC_FIRERED) == 66
        assert not (set(CYRILLIC_FIRERED) & set(CHARMAP_POKEMON_GBA))
        assert not (set(CYRILLIC_FIRERED) & {0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB9})
        controls = {0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF, 0x00}
        assert not (set(CYRILLIC_FIRERED) & controls)

    def test_values_unique(self):
        vals = list(CYRILLIC_FIRERED.values())
        assert len(set(vals)) == 66
        assert "А" in vals and "я" in vals and "Ё" in vals and "ё" in vals

    def test_roundtrip(self):
        dec = PokemonTextDecoder(CHARMAP_FIRERED)
        for text in ("ПРИВЕТ", "мир", "Ёё"):
            raw = dec.encode(text, strict=True)
            assert dec.decode(raw, 0, len(raw)) == text

    def test_no_shadow_in_base(self):
        for ch in CYRILLIC_FIRERED.values():
            assert ch not in CHARMAP_POKEMON_GBA.values()


class TestEmptySlotAlignment:
    def _segment(self, targets):
        class ToyDecoder:
            def decode(self, data, start, length):
                chunk = bytes(data[start:start + length])
                if not chunk.strip(b"\xff\x00"):
                    return ""
                return chunk.split(b"\xff")[0].decode("ascii")

            def encode(self, text):
                return text.encode("ascii")

        return {
            "name": "toy_dialogues",
            "kind": "pointer_dialogues",
            "decoder": ToyDecoder(),
            "terminator": b"\xff",
            "manifest": [{"target": t, "free_after": 16} for t in targets],
        }

    def _injector(self, blobs):
        from core.injector import TextInjector

        class FakeROM:
            def __init__(self, data):
                self.data = data

        inj = TextInjector.__new__(TextInjector)
        import logging

        inj.rom = FakeROM(bytearray(256))
        inj.original_data = bytearray(256)
        inj.modified_data = bytearray(256)
        inj._segment_cache = {}
        inj._bank_segments = []
        inj._taken_free_blocks = []
        inj._written_spans = []
        inj.last_overflow_report = []
        inj.last_relocate_report = []
        inj.last_overlap_report = []
        inj.last_spellcheck_report = []
        inj.last_fit_report = []
        inj.last_unmapped_chars = []
        inj.logger = logging.getLogger("test")
        for addr, blob in blobs.items():
            inj.rom.data[addr:addr + len(blob)] = blob
            inj.modified_data[addr:addr + len(blob)] = blob
        return inj

    def test_aligned_roundtrip(self):
        seg = self._segment([16, 32, 48])
        inj = self._injector({16: b"AB\xff", 32: b"\xff", 48: b"CD\xff"})
        assert inj._inject_pointer_dialogues(seg, ["AB", "CD"], True) is True
        assert bytes(inj.modified_data[16:19]) == b"AB\xff"
        assert bytes(inj.modified_data[32:33]) == b"\xff"
        assert bytes(inj.modified_data[48:51]) == b"CD\xff"

    def test_extra_translation_rejected(self):
        seg = self._segment([16, 32])
        inj = self._injector({16: b"AB\xff", 32: b"\xff"})
        assert inj._inject_pointer_dialogues(seg, ["AB", "CD", "EF"], True) is False

    def test_shortage_rejected(self):
        seg = self._segment([16, 32, 48])
        inj = self._injector({16: b"AB\xff", 32: b"CD\xff", 48: b"EF\xff"})
        assert inj._inject_pointer_dialogues(seg, ["AB"], True) is False

    def test_exact_still_works(self):
        seg = self._segment([16, 32])
        inj = self._injector({16: b"AB\xff", 32: b"CD\xff"})
        assert inj._inject_pointer_dialogues(seg, ["AB", "CD"], True) is True

    def test_bad_input(self):
        seg = self._segment([16])
        inj = self._injector({})
        assert inj._align_translations_to_manifest(seg, "xx") is None
        assert inj._align_translations_to_manifest({"manifest": []}, []) is None
        assert inj._align_translations_to_manifest(
            {"manifest": [], "decoder": seg["decoder"]}, []) == []
        assert inj._inject_pointer_dialogues({"decoder": None, "manifest": []}, [], True) is False

    def test_broken_slots_treated_empty(self):
        class BoomDecoder:
            def decode(self, data, start, length):
                raise RuntimeError("boom")

            def encode(self, text):
                return text.encode("ascii")

        # Слот 16 содержит "AB" и при этом НЕ декодируется. Раньше такой слот
        # считался пустым (align трактует исключение как пустой текст), и
        # пустой перевод записывался в него — то есть запись затиралась без
        # отказа. Теперь гейт `empty_translation` сверяется с содержимым
        # pristine ROM, поэтому непустой слот с пустым переводом ОТКАЗЫВАЕТСЯ:
        # стирать «AB» молча нельзя. Ожидаемое значение False — это и есть
        # починка, а не регресс.
        seg = self._segment([16, 32])
        seg["decoder"] = BoomDecoder()
        # free_after=16, поэтому «пустой» слот 32 заполняем целиком 0xFF:
        # слот из одних терминаторов пуст и стирать его нечего.
        inj = self._injector({16: b"AB\xff", 32: b"\xff" * 16})
        # skip_long=True понижает отказ до ПРОПУСКА записи, поэтому сегмент в
        # целом остаётся успешным — судить надо по отчёту: отказан только слот
        # с живым текстом (16), пустой (32) законен и записан.
        assert inj._inject_pointer_dialogues(seg, [], True) is True
        offsets = [a.get("offset") for a in (inj.last_affix_report or [])]
        assert offsets == [16], offsets
        # Байты непустого слота не тронуты.
        assert bytes(inj.modified_data[16:16 + 3]) == b"AB\xff"

        # Слот, пустой и в pristine ROM, по-прежнему принимает пустой перевод.
        seg2 = self._segment([16])
        seg2["decoder"] = BoomDecoder()
        inj2 = self._injector({16: b"\xff" * 16})
        assert inj2._inject_pointer_dialogues(seg2, [""], True) is True
        assert not (inj2.last_affix_report or []), (
            'пустой слот принимает пустой перевод без отказа')

        bad = dict(seg)
        bad["manifest"] = [{"target": None, "free_after": 0}, {"target": 99999, "free_after": 16}]
        inj3 = self._injector({})
        assert inj3._align_translations_to_manifest(bad, []) == ["", ""]


class TestDialogueRelocation:
    BASE = 0x08000000

    def _seg(self, entries):
        class ToyDecoder:
            def decode(self, data, start, length):
                chunk = bytes(data[start:start + length])
                if not chunk.strip(b"\xff\x00"):
                    return ""
                return chunk.split(b"\xff")[0].decode("ascii")

            def encode(self, text):
                return text.encode("ascii")

        return {"name": "toy_dialogues", "kind": "pointer_dialogues",
                "decoder": ToyDecoder(), "terminator": b"\xff",
                "manifest": entries}

    def _ptr(self, target):
        return (target + self.BASE).to_bytes(4, "little")

    def test_relocate_long_message(self):
        helper = TestEmptySlotAlignment()
        blobs = {16: b"AB\xff", 64: self._ptr(16)}
        inj = helper._injector(blobs)
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64]}])
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is True
        dest = int.from_bytes(inj.modified_data[64:68], "little") - self.BASE
        assert bytes(inj.modified_data[dest:dest + 17]) == b"ABCDEFGHIJKLMNOP\xff"
        # Старый блок освобождается: все его слоты переписаны, он больше не
        # адресуем. Оставленный там оригинал маскировал бы перенос — при
        # обратном извлечении манифест (статический) читает старый target и
        # показывал бы оригинал вместо перевода. Признак «здесь был перенос»
        # теперь — нули на старом месте.
        assert bytes(inj.modified_data[16:24]) == b"\x00" * 8
        assert seg["decoder"].decode(inj.modified_data, dest, 17) == "ABCDEFGHIJKLMNOP"
        assert inj.last_relocate_report == [
            {"target": 16, "dest": dest, "pointers": [64],
             "skipped_pointers": [], "relocated": True}]

    def test_relocate_no_slots_overflow(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff"})
        seg = self._seg([{"target": 16, "free_after": 8}])
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is False
        assert len(inj.last_overflow_report) == 1
        assert bytes(inj.modified_data[16:19]) == b"AB\xff"

    def test_relocate_stale_pointer_refused(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 64: self._ptr(0x9999)})
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64]}])
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is False
        assert bytes(inj.modified_data[64:68]) == self._ptr(0x9999)
        assert bytes(inj.modified_data) == bytes(inj.rom.data)

    def test_relocate_mixed_slots_subset(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 64: self._ptr(16),
                                72: self._ptr(0x9999)})
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64, 72]}])
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is True
        dest = int.from_bytes(inj.modified_data[64:68], "little") - self.BASE
        assert bytes(inj.modified_data[dest:dest + 17]) == b"ABCDEFGHIJKLMNOP\xff"
        assert bytes(inj.modified_data[72:76]) == self._ptr(0x9999)
        assert inj.last_relocate_report[-1]["skipped_pointers"] == [72]

    def test_relocate_disabled(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 64: self._ptr(16)})
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64]}])
        assert inj._inject_pointer_dialogues(
            seg, ["ABCDEFGHIJKLMNOP"], True, relocate=False) is False
        assert len(inj.last_overflow_report) == 1
        assert bytes(inj.modified_data[64:68]) == self._ptr(16)

    def test_relocate_empty_terminator_refused(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 64: self._ptr(16)})
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64]}])
        seg["terminator"] = b""
        assert inj._inject_pointer_dialogues(
            seg, ["ABCDEFGHIJKLMNOP"], True) is False
        assert len(inj.last_overflow_report) == 1
        assert bytes(inj.modified_data[64:68]) == self._ptr(16)

    def test_relocate_reinject_idempotent(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 64: self._ptr(16)})
        seg = self._seg([{"target": 16, "free_after": 8, "slots": [64]}])
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is True
        first = bytes(inj.modified_data)
        assert inj._inject_pointer_dialogues(seg, ["ABCDEFGHIJKLMNOP"], True) is True
        assert bytes(inj.modified_data) == first
        assert len(inj.last_overflow_report) == 0
        assert inj.last_relocate_report[-1]["relocated"] is False

    def test_relocate_shared_cell_second_skips(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff", 32: b"CD\xff", 64: self._ptr(16)})
        seg = self._seg([
            {"target": 16, "free_after": 8, "slots": [64]},
            {"target": 32, "free_after": 8, "slots": [64]},
        ])
        assert inj._inject_pointer_dialogues(
            seg, ["ABCDEFGHIJKLMNOP", "QRSTUVWXYZ123456"], True) is True
        assert len(inj.last_overflow_report) == 1

    def test_foreign_segment_range_skips(self):
        helper = TestEmptySlotAlignment()
        inj = helper._injector({16: b"AB\xff"})
        seg = self._seg([{"target": 16, "free_after": 8}])
        inj._segment_cache["other"] = [
            {"name": "fixed_names", "start": 18, "end": 64}]
        assert inj._inject_pointer_dialogues(seg, ["ABCD"], True) is False
        assert bytes(inj.modified_data[16:19]) == b"AB\xff"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
