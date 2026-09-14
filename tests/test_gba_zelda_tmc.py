"""Тесты банковой (bank-record) экстракции/инжекции Zelda: The Minish Cap (BZME)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gba_zelda_tmc import (
    TMC_CONTROL_CODE_PARAMS,
    TMCTextDecoder,
    ZeldaTMCPlugin,
    _scan_banks,
)

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms',
    'Legend of Zelda, The - The Minish Cap (USA).gba',
)


@pytest.fixture(scope="module")
def tmc_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Legend of Zelda, The - The Minish Cap (USA).gba")
    return GameBoyROM(ROM_PATH)


@pytest.fixture(scope="module")
def plugin() -> ZeldaTMCPlugin:
    return ZeldaTMCPlugin()


def _record_bytes(rom: GameBoyROM, seg: dict) -> list[tuple[int, bytes]]:
    """Оригинальные байты каждой записи банка (до терминатора 0x00)."""
    cc = seg['bank_meta']['control_codes']
    records = []
    for rel in seg['bank_meta']['offsets']:
        t = seg['start'] + rel
        j = t
        while j < seg['end'] and rom.data[j] != 0x00:
            if rom.data[j] in cc:
                j += 1 + cc[rom.data[j]]
            else:
                j += 1
        records.append((rel, bytes(rom.data[t:j])))
    return records


class TestScanBanks:
    def test_scan_finds_banks(self, tmc_rom):
        banks = _scan_banks(tmc_rom.data, (0x9B0000, 0x9FB000))
        assert len(banks) >= 40
        for bank in banks:
            assert 0x9B0000 <= bank['base'] < 0x9FB000
            assert bank['record_end'] <= len(tmc_rom.data)
            assert bank['n'] == len(bank['offsets'])
            assert bank['n'] >= 1

    def test_scan_offsets_valid(self, tmc_rom):
        banks = _scan_banks(tmc_rom.data, (0x9B0000, 0x9FB000))
        for bank in banks:
            vals = bank['offsets']
            assert vals == sorted(vals)
            assert vals[0] >= bank['n'] * 4
            for v in vals:
                t = bank['base'] + v
                assert t < len(tmc_rom.data)
                assert tmc_rom.data[t] not in (0x00, 0xFF)


class TestPluginSegments:
    def test_segments_present(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        assert len(segments) >= 40
        names = [s['name'] for s in segments]
        assert len(names) == len(set(names)), 'имена сегментов не уникальны'

    def test_segments_sorted_and_not_overlapping(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        for i in range(len(segments) - 1):
            assert segments[i]['end'] <= segments[i + 1]['start'], (
                f'пересечение: {segments[i]["name"]} end={segments[i]["end"]:X} > '
                f'next start={segments[i + 1]["start"]:X}'
            )

    def test_segment_shape(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        for seg in segments:
            assert seg['bank_meta']['offsets']
            assert seg['bank_meta']['count'] == len(seg['bank_meta']['offsets'])
            assert seg['bank_meta']['control_codes'] == TMC_CONTROL_CODE_PARAMS
            assert seg['compression'] is None
            assert seg['decoder'] is not None

    def test_bank_decoder_puts_end_after_each_record(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = segments[0]
        data = tmc_rom.data[seg['start']:seg['end']]
        text = seg['decoder'].decode(data, 0, len(data))
        parts = text.split('[END]')
        assert len(parts) == seg['bank_meta']['count'] + 1
        assert parts[0] or data[0] in (0x00, 0xFF)


class TestDecoderEncoder:
    def test_roundtrip_all_records_byte_identical(self, plugin, tmc_rom):
        """decode → encode == оригинальные байты для всех записей всех банков."""
        segments = plugin.get_text_segments(tmc_rom)
        checked = 0
        for seg in segments:
            for rel, orig_bytes in _record_bytes(tmc_rom, seg):
                text = seg['decoder']._decode_one(
                    tmc_rom.data, seg['start'] + rel, seg['start'] + rel + len(orig_bytes))
                enc = seg['decoder'].encode(text)
                assert enc == orig_bytes, f'{seg["name"]} rel={rel:X}: {text!r}'
                checked += 1
        assert checked > 500

    def test_decode_control_codes_atomic(self, plugin):
        # [06 00] — контрольный код с параметром 0x00; не является концом записи.
        # [MENUSEP] (0xFF) декодируется в текст и не разрезает запись.
        data = bytes([0x06, 0x00, 0x20, 0xFF, 0x00])
        dec = TMCTextDecoder({0x20: ' '}, offsets=[0])
        text = dec.decode(data, 0, len(data))
        assert text == '[06 00] [MENUSEP][END]'

    def test_encode_control_codes(self, plugin):
        dec = TMCTextDecoder({0x20: ' '})
        assert dec.encode('[06 00] [END]') == bytes([0x06, 0x00, 0x20, 0x00])
        assert dec.encode('[01 04 14]') == bytes([0x01, 0x04, 0x14])
        assert dec.encode('[MENUSEP]') == bytes([0xFF])

    def test_encode_unknown_char_raises(self, plugin):
        dec = TMCTextDecoder({0x20: ' '})
        with pytest.raises(ValueError):
            dec.encode('привет')


TMC_RELOC_BANK = 0x9B281C          # имена NPC, свободная зона 0x9B2E52
TMC_RELOC_REC = 4                  # 'Percy' (5 байт) → 'PERCY!!' (7 байт)
TMC_RELOC_ZONE = 0x9B2E52
TMC_PROTECTED_BANK = 0x9DC6E8      # protected рекорд 0x9DC903
TMC_PROTECTED_REC = 5


class TestBankRelocate:
    def _texts(self, plugin, seg, inj):
        return [
            seg['decoder']._decode_one(
                inj.original_data, seg['start'] + rel,
                inj._bank_record_bound(
                    inj.original_data, seg['start'] + rel,
                    seg['bank_meta']['record_end'],
                    seg['bank_meta']['control_codes']))
            for rel in seg['bank_meta']['offsets']
        ]

    def test_relocate_moves_record_into_free_zone(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = next(s for s in segments if s['start'] == TMC_RELOC_BANK)
        inj = TextInjector(ROM_PATH)
        try:
            texts = self._texts(plugin, seg, inj)
            texts[TMC_RELOC_REC] = 'PERCY!!'
            ok = inj.inject_segment(seg['name'], texts, plugin,
                                    skip_long=False, segments=segments)
            assert ok
            idx = seg['bank_meta']['offsets_idx'][TMC_RELOC_REC]
            slot = seg['start'] + 4 * idx
            assert int.from_bytes(inj.modified_data[slot:slot + 4], 'little') \
                == TMC_RELOC_ZONE - seg['start']
            assert bytes(inj.modified_data[TMC_RELOC_ZONE:TMC_RELOC_ZONE + 7]) \
                == b'PERCY!!'
            assert inj.modified_data[TMC_RELOC_ZONE + 7] == 0x00
        finally:
            del inj

    def test_relocate_rescanned_bank_is_found(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = next(s for s in segments if s['start'] == TMC_RELOC_BANK)
        inj = TextInjector(ROM_PATH)
        try:
            texts = self._texts(plugin, seg, inj)
            texts[TMC_RELOC_REC] = 'PERCY!!'
            assert inj.inject_segment(seg['name'], texts, plugin,
                                      skip_long=False, segments=segments)
            banks = _scan_banks(bytes(inj.modified_data), (0x9B0000, 0x9FB000))
            assert any(b['base'] == TMC_RELOC_BANK for b in banks)
            relocated = next(b for b in banks if b['base'] == TMC_RELOC_BANK)
            assert relocated['offsets'] != sorted(relocated['offsets'])
        finally:
            del inj

    def test_relocate_idempotent(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = next(s for s in segments if s['start'] == TMC_RELOC_BANK)
        inj = TextInjector(ROM_PATH)
        try:
            texts = self._texts(plugin, seg, inj)
            texts[TMC_RELOC_REC] = 'PERCY!!'
            assert inj.inject_segment(seg['name'], texts, plugin,
                                      skip_long=False, segments=segments)
            first = bytes(inj.modified_data)
            assert inj.inject_segment(seg['name'], texts, plugin,
                                      skip_long=False, segments=segments)
            assert bytes(inj.modified_data) == first
        finally:
            del inj

    def test_relocate_never_moves_protected_record(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = next(s for s in segments if s['start'] == TMC_PROTECTED_BANK)
        inj = TextInjector(ROM_PATH)
        try:
            texts = self._texts(plugin, seg, inj)
            texts[TMC_PROTECTED_REC] = texts[TMC_PROTECTED_REC] + '!!!' * 20
            idx = seg['bank_meta']['offsets_idx'][TMC_PROTECTED_REC]
            slot = seg['start'] + 4 * idx
            before = bytes(inj.modified_data[slot:slot + 4])
            ok = inj.inject_segment(seg['name'], texts, plugin,
                                    skip_long=False, segments=segments)
            assert ok is False
            after = bytes(inj.modified_data[slot:slot + 4])
            assert after == before
            assert inj.modified_data == inj.original_data
        finally:
            del inj

    def test_relocate_no_free_space_skips(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = next(s for s in segments if not s['bank_meta']['free_zones'])
        inj = TextInjector(ROM_PATH)
        try:
            texts = self._texts(plugin, seg, inj)
            texts[0] = texts[0] + '?' * 30
            texts[1] = 'TEST'
            ok = inj.inject_segment(seg['name'], texts, plugin,
                                    skip_long=True, segments=segments)
            assert ok
            assert bytes(inj.modified_data) != bytes(inj.original_data)
            assert bytes(inj.modified_data[seg['bank_meta']
                                           ['record_end']:seg['bank_meta']
                                           ['zone_end']]) == \
                bytes(inj.original_data[seg['bank_meta']
                                        ['record_end']:seg['bank_meta']
                                        ['zone_end']])
        finally:
            del inj
        segments = plugin.get_text_segments(tmc_rom)
        seg = segments[0]
        original = _record_bytes(tmc_rom, seg)
        texts = ['TEST'] + [
            seg['decoder']._decode_one(tmc_rom.data, seg['start'] + rel,
                                       seg['start'] + rel + len(b))
            for rel, b in original[1:]
        ]
        inj = TextInjector(ROM_PATH)
        try:
            ok = inj.inject_segment(seg['name'], texts, plugin, skip_long=False,
                                    segments=segments)
            assert ok
            rel0, ob0 = original[0]
            t0 = seg['start'] + rel0
            len0 = len(ob0)
            window = bytes(inj.modified_data[t0:t0 + len0])
            assert window[:4] == b'TEST'
            assert window[4:] == b'\x00' * (len0 - 4)
            for rel, ob in original[1:]:
                t = seg['start'] + rel
                assert bytes(inj.modified_data[t:t + len(ob)]) == ob, \
                    f'запись rel={rel:X} изменена незаконно'
        finally:
            del inj

    def test_inject_too_long_skipped_but_others_inserted(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = segments[0]
        original = _record_bytes(tmc_rom, seg)
        texts = ['X' * (len(original[0][1]) + 10)] + [
            seg['decoder']._decode_one(tmc_rom.data, seg['start'] + rel,
                                       seg['start'] + rel + len(b))
            for rel, b in original[1:]
        ]
        texts[1] = 'TEST'
        inj = TextInjector(ROM_PATH)
        try:
            ok = inj.inject_segment(seg['name'], texts, plugin, skip_long=True,
                                    segments=segments, relocate=False)
            assert ok
            assert bytes(inj.modified_data) != bytes(inj.original_data)
            # длинная удалена полностью, короткая TEST вставлена
            r1, b1 = original[1]
            assert bytes(inj.modified_data[seg['start'] + r1:
                                           seg['start'] + r1 + len(b1)])[:4] == b'TEST'
            r0, b0 = original[0]
            assert bytes(inj.modified_data[seg['start'] + r0:
                                           seg['start'] + r0 + len(b0)]) == b0
        finally:
            del inj

    def test_inject_replaces_one_record_with_test(self, plugin, tmc_rom):
        """Замена одной короткой записи детерминирована, остальные не тронуты."""
        segments = plugin.get_text_segments(tmc_rom)
        seg = segments[0]
        original = _record_bytes(tmc_rom, seg)
        target_idx = 1
        target_rel, target_bytes = original[target_idx]
        if len(target_bytes) < 4:
            pytest.skip('первый банк слишком мал для этой проверки')
        texts = [
            seg['decoder']._decode_one(tmc_rom.data, seg['start'] + rel,
                                       seg['start'] + rel + len(b))
            for rel, b in original
        ]
        texts[target_idx] = 'TEST'
        inj = TextInjector(ROM_PATH)
        try:
            ok = inj.inject_segment(seg['name'], texts, plugin, skip_long=False,
                                    segments=segments)
            assert ok
            assert bytes(inj.modified_data) != bytes(inj.original_data)
            t = seg['start'] + target_rel
            assert bytes(inj.modified_data[t:t + len(target_bytes)])[:4] == b'TEST'
        finally:
            del inj

    def test_inject_too_long_rejects_segment_without_skip(self, plugin, tmc_rom):
        segments = plugin.get_text_segments(tmc_rom)
        seg = segments[0]
        original = _record_bytes(tmc_rom, seg)
        texts = ['X' * (len(original[0][1]) + 10)] + ['Y'] * (len(original) - 1)
        inj = TextInjector(ROM_PATH)
        try:
            ok = inj.inject_segment(seg['name'], texts, plugin, skip_long=False,
                                    segments=segments, relocate=False)
            assert ok is False
            assert inj.modified_data == inj.original_data
        finally:
            del inj

    def test_inject_roundtrip_identity_all_banks(self, plugin, tmc_rom):
        """Полный round-trip: извлечь → вставить те же строки → байты зоны не изменились."""
        inj = TextInjector(ROM_PATH)
        segments = inj._get_segments(plugin)
        try:
            for seg in segments:
                texts = [
                    seg['decoder']._decode_one(
                        tmc_rom.data, seg['start'] + rel, seg['start'] + rel + len(b))
                    for rel, b in _record_bytes(tmc_rom, seg)
                ]
                ok = inj.inject_segment(seg['name'], texts, plugin, skip_long=False,
                                        segments=segments)
                assert ok, f'{seg["name"]}: inject вернул False'
                assert bytes(inj.modified_data[seg['start']:seg['end']]) == \
                    bytes(inj.original_data[seg['start']:seg['end']]), \
                    f'{seg["name"]}: round-trip изменил байты'
        finally:
            del inj

    def test_full_pipeline_extract_inject_roundtrip(self, plugin, tmc_rom):
        """Пайплайн через публичные API TextExtractor.extract → inject: банк с
        [MENUSEP] не должен разрезаться на большее число сообщений."""
        ext = TextExtractor(ROM_PATH)
        try:
            results = ext.extract()
        finally:
            del ext
        bank = 'zelda_tmc_bank_09B9A48'
        if bank not in results:
            pytest.skip('в этом ROM банк с [MENUSEP] отсутствует')
        texts = [m['text'] for m in results[bank]]
        assert any('[MENUSEP]' in t for t in texts), 'ожидали запись с [MENUSEP]'
        inj = TextInjector(ROM_PATH)
        try:
            segments = inj._get_segments(plugin)
            seg = next(s for s in segments if s['name'] == bank)
            assert len(texts) == seg['bank_meta']['count'], \
                f'экстрактор разрезал записи: {len(texts)} != {seg["bank_meta"]["count"]}'
            ok = inj.inject_segment(bank, texts, plugin, skip_long=False,
                                    segments=segments)
            assert ok
            assert bytes(inj.modified_data[seg['start']:seg['end']]) == \
                bytes(inj.original_data[seg['start']:seg['end']])
        finally:
            del inj
