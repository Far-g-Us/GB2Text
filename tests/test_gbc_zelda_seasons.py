"""
Тесты для плагина The Legend of Zelda: Oracle of Seasons (GBC, US).

Синтетический ROM: проверяется конструктор таблиц, декодер/енкодер на
29 контрольных записях (словарь, контрольные коды, Unicode, символы),
а также контракт плагина. Реальный ROM — интеграция на легально-owned ROM.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from plugins.gbc_zelda_seasons import OracleOfSeasonsPlugin
from plugins.zelda_oracle_common import OracleTextDecoder

_BASE1 = 0x80000
_TEXT_TABLE = 0x70000
_GROUP_STRUCT = 0x70200
_TEXT_BASE1_TABLE = 0xFCFE2
_TEXT_BASE2_TABLE = 0xFCFFA
_LANGUAGE_TABLE = 0xFD012
_NUM_HIGH = 0x64
_LAST_GROUP_SIZE = 0x1D

_RAW_RECORDS = [
    b'Hello World!',            # r0
    b'\x01test',                # r1  [NL]test
    b'A\x5cB',                  # r2  A~B
    b'Hello ',                  # r3  dict target
    b'\x0c\x18Say',             # r4  [STOP]Say
    b'\x02\x03World',           # r5  dict ref → r3
    b'\x07\x05TheEnd',          # r6  [JUMP(DICT0_05)]TheEnd
    b'\x06\x00',                # r7  kanji 姫
    b'\x09\x03Colored',         # r8  [COL(3)]Colored
    b'\x0a\x00and',             # r9  [LINK]and
    b'\x0a\x08X',               # r10 [X_0A][X_08]X
    b'\x10\x11',                # r11 [CIRCLE][CLUB]
    b'\xb8\xb9\xba\xbb',       # r12 [ABTN][BBTN]
    b'\x0d\x05wait',            # r13 [WAIT(5)]wait
    b'\x0e\x07sfx',             # r14 [SFX(0x07)]sfx
    b'\x0f\x01call',            # r15 [CALL(DICT0_01)]call
    b'\x7e\x7f',                # r16 [TRIANGLE][RECTANGLE]
    b'\x0b\x02chfx',            # r17 [CHARSFX(0x02)]chfx
    b'\xa0\x80',                # r18 àÀ
    b'\x06\xfftag',             # r19 [ITEM(0x7F)]tag
    b'\x0c\x00sp',              # r20 [SPEED(0)]sp
    b'\x0c\x10op',              # r21 [OPT]op
    b'\x0c\x08n1',              # r22 [NUM1]n1
    b'\x0c\x30n2',              # r23 [NUM2]n2
    b'\x0c\x28hp',              # r24 [HEARTPIECE]hp
    b'\x0c\x38sl',              # r25 [SLOW]sl
    b'\x0c\x22po',              # r26 [POS(2)]po
    b'\x0c\xfdcm',              # r27 [CMD(0xFD)]cm
    b'\x02\x00dict0text',       # r28 dict ref → r0 + literal
]

_EXPECTED = [
    'Hello World!',
    '[NL]test',
    'A~B',
    'Hello ',
    '[STOP]Say',
    'Hello World',
    '[JUMP(DICT0_05)]TheEnd',
    '姫',
    '[COL(3)]Colored',
    '[LINK]and',
    '[X_0A][X_08]X',
    '[CIRCLE][CLUB]',
    '[ABTN][BBTN]',
    '[WAIT(5)]wait',
    '[SFX(0x07)]sfx',
    '[CALL(DICT0_01)]call',
    '[TRIANGLE][RECTANGLE]',
    '[CHARSFX(0x02)]chfx',
    'àÀ',
    '[ITEM(0x7F)]tag',
    '[SPEED(0)]sp',
    '[OPT]op',
    '[NUM1]n1',
    '[NUM2]n2',
    '[HEARTPIECE]hp',
    '[SLOW]sl',
    '[POS(2)]po',
    '[CMD(0xFD)]cm',
    'Hello World!dict0text',
]

# encode(decode(raw)) == raw для всех, кроме dict-расширения
_NON_ROUNDTRIP = {5, 28}


def _record_offset(i: int) -> int:
    return sum(len(r) + 1 for r in _RAW_RECORDS[:i])


def _build_synthetic_rom() -> bytes:
    rom = bytearray(0x100000)

    # Table pointers (3-byte LE: pos16 then bank)
    rom[_TEXT_BASE1_TABLE] = 0x20
    rom[_TEXT_BASE1_TABLE + 1] = 0x00
    rom[_TEXT_BASE1_TABLE + 2] = 0x00

    rom[_TEXT_BASE2_TABLE] = 0x24
    rom[_TEXT_BASE2_TABLE + 1] = 0x00
    rom[_TEXT_BASE2_TABLE + 2] = 0x00

    rom[_LANGUAGE_TABLE] = 0x00
    rom[_LANGUAGE_TABLE + 1] = 0x00
    rom[_LANGUAGE_TABLE + 2] = 0x1C

    # textTable: 0x64 dw → all point to group struct at offset 0x0200
    for i in range(_NUM_HIGH):
        off = _TEXT_TABLE + i * 2
        rom[off] = 0x00
        rom[off + 1] = 0x02

    # Pack records at _BASE1, accumulate offsets
    offsets = []
    addr = _BASE1
    for rec in _RAW_RECORDS:
        offsets.append(addr - _BASE1)
        rom[addr:addr + len(rec)] = rec
        rom[addr + len(rec)] = 0x00
        addr += len(rec) + 1

    # Group struct: 29 dw
    for j, off in enumerate(offsets):
        gaddr = _GROUP_STRUCT + j * 2
        rom[gaddr] = off & 0xFF
        rom[gaddr + 1] = (off >> 8) & 0xFF

    return bytes(rom)


z = chr(0)

def _build_adjacent_rom() -> bytes:
    rom = bytearray(0x100000)
    rom[_TEXT_BASE1_TABLE] = 0x20
    rom[_TEXT_BASE1_TABLE + 1] = 0x00
    rom[_TEXT_BASE1_TABLE + 2] = 0x00
    rom[_TEXT_BASE2_TABLE] = 0x24
    rom[_TEXT_BASE2_TABLE + 1] = 0x00
    rom[_TEXT_BASE2_TABLE + 2] = 0x00
    rom[_LANGUAGE_TABLE] = 0x00
    rom[_LANGUAGE_TABLE + 1] = 0x00
    rom[_LANGUAGE_TABLE + 2] = 0x1C
    for i in range(_NUM_HIGH):
        off = _TEXT_TABLE + i * 2
        rom[off] = 0x00
        rom[off + 1] = 0x02
    rom[_BASE1] = ord('A')
    rom[_BASE1 + 1:_BASE1 + 4] = b'CD' + z.encode()
    rom[_GROUP_STRUCT] = 0x00
    rom[_GROUP_STRUCT + 1] = 0x00
    rom[_GROUP_STRUCT + 2] = 0x01
    rom[_GROUP_STRUCT + 3] = 0x00
    return bytes(rom)

class _FakeROM:
    """Minimal object with .data attribute (avoids full GameBoyROM init)."""

    def __init__(self, data: bytes):
        self.data = data

    def __len__(self):
        return len(self.data)


SYN_ROM = _build_synthetic_rom()
SYN_DEC = OracleTextDecoder()

# --- Plugin contract ---


class TestOraclePluginContract:
    def test_matches_us_id(self):
        assert re.search(
            OracleOfSeasonsPlugin().game_id_pattern,
            'GBC_ZELDADINAZ7E',
        )

    def test_rejects_wrong_id(self):
        assert not re.search(
            OracleOfSeasonsPlugin().game_id_pattern,
            'GBC_ZELDADINAUS',
        )

    def test_terminators(self):
        assert OracleOfSeasonsPlugin().get_terminators('oracle_seasons') == [0x00]


# --- Table / index construction ---


class TestOracleInit:
    def test_bases(self):
        SYN_DEC._init(SYN_ROM)
        assert SYN_DEC._text_base1 == _BASE1
        assert SYN_DEC._text_base2 == 0x90000
        assert SYN_DEC._text_table == _TEXT_TABLE

    def test_index_count(self):
        SYN_DEC._init(SYN_ROM)
        assert len(SYN_DEC._idx_to_addr) == _LAST_GROUP_SIZE
        assert len(SYN_DEC._addr_to_index) == len(_RAW_RECORDS)

    def test_text_range(self):
        SYN_DEC._init(SYN_ROM)
        assert SYN_DEC._text_start == _BASE1
        assert SYN_DEC._text_end == _BASE1 + _record_offset(len(_RAW_RECORDS) - 1) + 1


# --- Decode ---


class TestOracleDecode:
    def test_all_records(self):
        for i, (raw, exp) in enumerate(zip(_RAW_RECORDS, _EXPECTED, strict=True)):
            offset = sum(len(r) + 1 for r in _RAW_RECORDS[:i])
            addr = _BASE1 + offset
            end = addr + len(raw)
            text = SYN_DEC.decode(SYN_ROM, addr, end - addr)
            assert text == exp, f'record {i}'

    def test_no_unmapped_chars(self):
        SYN_DEC.last_unmapped_chars.clear()
        for i, raw in enumerate(_RAW_RECORDS):
            offset = sum(len(r) + 1 for r in _RAW_RECORDS[:i])
            addr = _BASE1 + offset
            SYN_DEC.decode(SYN_ROM, addr, len(raw) + 1)
        assert SYN_DEC.last_unmapped_chars == []


# --- Build manifest ---


class TestOracleManifest:
    def test_count(self):
        m = SYN_DEC.build_manifest(SYN_ROM)
        assert len(m) == len(_RAW_RECORDS)

    def test_targets(self):
        m = SYN_DEC.build_manifest(SYN_ROM)
        assert m[0]['target'] == _BASE1
        expected_last = _BASE1 + sum(len(r) + 1 for r in _RAW_RECORDS[:-1])
        assert m[-1]['target'] == expected_last

    def test_free_after_includes_terminator(self):
        m = SYN_DEC.build_manifest(SYN_ROM)
        for rec, raw in zip(m, _RAW_RECORDS, strict=True):
            assert rec['free_after'] == len(raw) + 1

    def test_decode_through_manifest(self):
        m = SYN_DEC.build_manifest(SYN_ROM)
        for rec, exp in zip(m, _EXPECTED, strict=True):
            text = SYN_DEC.decode(SYN_ROM, rec['target'], rec['free_after'])
            assert text == exp

    def test_adjacent_record_without_terminator(self):
        dec = OracleTextDecoder()
        rom = _build_adjacent_rom()
        m = dec.build_manifest(rom)
        assert len(m) == 2
        assert m[0]['target'] == _BASE1
        assert m[0]['free_after'] == 1
        assert m[1]['target'] == _BASE1 + 1
        assert m[1]['free_after'] == 3
        assert dec.decode(rom, m[0]['target'], m[0]['free_after']) == 'A'
        assert dec.decode(rom, m[1]['target'], m[1]['free_after']) == 'CD'


# --- Encode round-trip (text → bytes) ---


class TestOracleEncode:
    def test_roundtrip_all(self):
        m = SYN_DEC.build_manifest(SYN_ROM)
        for i, rec in enumerate(m):
            text = SYN_DEC.decode(SYN_ROM, rec['target'], rec['free_after'])
            enc = SYN_DEC.encode(text)
            raw = SYN_ROM[rec['target']:rec['target'] + rec['free_after']]
            assert raw[-1] == 0
            if i in _NON_ROUNDTRIP:
                assert enc != raw[:-1]
                continue
            assert enc == raw[:-1], f'record {i}: encode mismatch'

    def test_trailing_space(self):
        assert OracleTextDecoder().encode('abc ') == b'abc '

    def test_apostrophe(self):
        assert OracleTextDecoder().encode("it's") == b"it's"

    def test_backslash_is_0x5c(self):
        assert OracleTextDecoder().encode('~') == b'\x5c'

    def test_symbol_bytes(self):
        dec = OracleTextDecoder()
        for tok, byte in [
            ('[CIRCLE]', 0x10), ('[CLUB]', 0x11), ('[DIAMOND]', 0x12),
            ('[SPADE]', 0x13), ('[HEART]', 0x14), ('[UP]', 0x15),
            ('[DOWN]', 0x16), ('[LEFT]', 0x17), ('[RIGHT]', 0x18),
            ('[TIMES]', 0x19),
        ]:
            assert dec.encode(tok) == bytes([byte]), tok

    def test_kanji(self):
        dec = OracleTextDecoder()
        assert dec.encode('姫') == b'\x06\x00'
        assert dec.encode('剣') == b'\x06\x35'

    def test_col(self):
        enc = OracleTextDecoder().encode('[COL(3)]Hi')
        assert enc == b'\x09\x03Hi'

    def test_speed(self):
        enc = OracleTextDecoder().encode('[SPEED(2)]x')
        assert enc == b'\x0c\x02x'

    def test_item(self):
        enc = OracleTextDecoder().encode('[ITEM(0x7F)]x')
        assert enc == b'\x06\xffx'

    def test_hex_token(self):
        enc = OracleTextDecoder().encode('[X_3F]')
        assert enc == b'\x3f'

    def test_unknown_param_x_0a(self):
        dec = OracleTextDecoder()
        addr = _BASE1 + _record_offset(10)
        text = dec.decode(SYN_ROM, addr, len(_RAW_RECORDS[10]) + 1)
        assert text == '[X_0A][X_08]X'
        assert dec.encode(text) == _RAW_RECORDS[10]

    def test_label_fallback_high_param(self):
        dec = OracleTextDecoder()
        assert dec.encode('[JUMP(0xFC)]x') == b'\x07\xfcx'
        assert dec.encode('[CALL(0xFD)]y') == b'\x0f\xfdy'

    def test_compressed_uses_dict_reference(self):
        dec = OracleTextDecoder()
        dec._init(SYN_ROM)
        enc = dec.encode_compressed('Hello World!')
        assert enc == b'\x02\x00'

    def test_compressed_split_literal(self):
        dec = OracleTextDecoder()
        dec._init(SYN_ROM)
        enc = dec.encode_compressed('Hello there')
        assert enc in (b'Hello there', b'\x02\x03there')
        assert enc != b'Hello there' or len(b'Hello there') == len(enc)

    def test_compressed_never_larger_than_literal(self):
        dec = OracleTextDecoder()
        dec._init(SYN_ROM)
        for text in ('Hello World!', 'Hello there', 'A~B', '[STOP]Say',
                     'TheEnd', 'Colored', 'and', 'X', 'wait', 'sfx', 'call',
                     'chfx', 'tag', 'po'):
            lit = dec.encode_literal(text)
            cmp = dec.encode_compressed(text)
            assert len(cmp) <= len(lit), text

    def test_compressed_decode_equals_literal(self):
        dec = OracleTextDecoder()
        dec._init(SYN_ROM)
        for i, (_raw, exp) in enumerate(zip(_RAW_RECORDS, _EXPECTED,
                                           strict=True)):
            if i in _NON_ROUNDTRIP:
                continue
            cmp = dec.encode_compressed(exp)
            lit = dec.encode_literal(exp)
            buf = bytearray(SYN_ROM)
            addr = 0x98000
            buf[addr:addr + len(cmp)] = cmp
            out = bytearray()
            dec._decompress(bytes(buf), addr, len(cmp), out, 0, {addr})
            assert bytes(out) == lit, (
                f'record {i}: greedy changed encoded bytes')

    def test_spec_rev_within_decode_range(self):
        from plugins.zelda_oracle_common import _SPEC_CHAR_TABLE, _SPEC_REV
        dec = OracleTextDecoder()
        assert len(_SPEC_REV) == 34
        for ch, byte in _SPEC_REV.items():
            assert dec.encode(ch) == bytes([byte]), ch
            assert (0x80 <= byte < 0x91) or (0xA0 <= byte < 0xB1), (
                f'{ch!r} -> 0x{byte:02X} vne decode-diapazona')
            assert _SPEC_CHAR_TABLE[byte - 0x80] == ch, ch


# --- Token grammar ---


class TestOracleTokenGrammar:
    def test_split_messages_safe(self):
        """Bracket tokens never produce '[XX]' hex or bare '\n' or '[END]'."""
        dec = OracleTextDecoder()
        for i, raw in enumerate(_RAW_RECORDS):
            addr = _BASE1 + _record_offset(i)
            text = dec.decode(SYN_ROM, addr, len(raw) + 1)
            for part in text.split('[NL]'):
                assert not re.fullmatch(r'\[[0-9A-Fa-f]{2}\]', part)
                assert '\n' not in part
                assert part != '[END]'


# --- Segment shape (synthetic ROM) ---


class TestOracleSegmentShape:
    def test_single_segment(self):
        segs = OracleOfSeasonsPlugin().get_text_segments(_FakeROM(SYN_ROM))
        assert len(segs) == 1
        seg = segs[0]
        assert seg['name'] == 'oracle_seasons'
        assert seg['kind'] == 'pointer_dialogues'
        assert seg['start'] == _BASE1
        expected_pool_end = _BASE1 + sum(len(r) + 1 for r in _RAW_RECORDS)
        assert seg['end'] == expected_pool_end
        assert seg['terminator'] == b'\x00'
        assert seg['terminators'] == [0x00]
        assert len(seg['manifest']) == len(_RAW_RECORDS)

    def test_decoder_in_segment(self):
        segs = OracleOfSeasonsPlugin().get_text_segments(_FakeROM(SYN_ROM))
        dec = segs[0]['decoder']
        assert isinstance(dec, OracleTextDecoder)

    def test_garbage_rom_returns_empty(self):
        segs = OracleOfSeasonsPlugin().get_text_segments(
            _FakeROM(bytes(0x100000)))
        assert segs == []


# --- Real ROM integration (skipped if ROM absent) ---

OOS_ROM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms',
    'Legend of Zelda, The - Oracle of Seasons (USA).gbc',
)


def _has_oos_rom() -> bool:
    return os.path.exists(OOS_ROM)


class TestOracleRealROM:
    @pytest.fixture
    def real_rom(self):
        if not _has_oos_rom():
            pytest.skip('OoS ROM не найден (легально-owned только)')
        return GameBoyROM(OOS_ROM)

    @pytest.fixture
    def real_plugin(self):
        return OracleOfSeasonsPlugin()

    @pytest.fixture
    def real_segments(self, real_rom, real_plugin):
        return real_plugin.get_text_segments(real_rom)

    def test_segments_non_empty(self, real_segments):
        assert len(real_segments) >= 1

    def test_segment_kind(self, real_segments):
        seg = real_segments[0]
        assert seg['kind'] == 'pointer_dialogues'
        assert seg['start'] == 0x73382

    def test_manifest_large(self, real_segments):
        assert len(real_segments[0]['manifest']) >= 2000

    def test_first_record_decodes(self, real_segments, real_rom):
        seg = real_segments[0]
        dec = seg['decoder']
        rec = seg['manifest'][0]
        text = dec.decode(real_rom.data, rec['target'], rec['free_after'])
        assert isinstance(text, str)
        assert len(text) > 0

    def test_decode_all_no_crash(self, real_segments, real_rom):
        seg = real_segments[0]
        dec = seg['decoder']
        fails = 0
        for rec in seg['manifest']:
            try:
                text = dec.decode(real_rom.data, rec['target'], rec['free_after'])
                assert isinstance(text, str)
            except Exception:
                fails += 1
        assert fails == 0

    @pytest.mark.rom_required
    @pytest.mark.slow
    def test_real_rom_roundtrip(self):
        """extract → inject (те же тексты) → extract: идентичные тексты."""
        import shutil
        import tempfile

        from core.extractor import TextExtractor
        from core.injector import TextInjector

        if not _has_oos_rom():
            pytest.skip('OoS ROM не найден (легально-owned только)')
        plugin = OracleOfSeasonsPlugin()
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, 'roundtrip.gbc')
            shutil.copyfile(OOS_ROM, work)
            rom = GameBoyROM(OOS_ROM)
            segments = plugin.get_text_segments(rom)
            before = TextExtractor(OOS_ROM, rom=rom).extract()
            injector = TextInjector(work)
            assert len(segments) == 1
            seg = segments[0]
            texts = [m['text'] for m in before.get(seg['name'], [])]
            assert injector.inject_segment(seg['name'], texts, plugin,
                                           segments=segments)
            injector.save(work)

            after = TextExtractor(work, rom=GameBoyROM(work)).extract()
            before_texts = [m['text'] for m in before.get(seg['name'], [])]
            after_texts = [m['text'] for m in after.get(seg['name'], [])]
            assert before_texts == after_texts
