"""Регрессионные тесты full-игр FF4/FF5 Advance (фиксы извлечения текста)

1. FF4 (BZ4E): база указателей 0x2E3670 (а не 0x2E98BC). Старая база давала
   сдвиг 0x624C, обрезая строки внутри слова ('rtant room'). Также отсекаются
   одиночные глифы charmap-каталога ('あ', '[C280]') и hex-only записи.
2. FF5: отсекаются мусорные хвостовые сегменты из областей данных/заполнения
   (2+ Hex-токенов в декодированном тексте, доля чистого текста < 30%).

Инварианты считаны эмпирически с USA ROM из test_roms/.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.rom import GameBoyROM
from plugins.gba_ff4_advance import FF4_TEXT_DATA_START, FF4AdvancePlugin
from plugins.gba_ff5_advance import FF5AdvancePlugin

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FF4_PATH = os.path.join(BASE, "test_roms", "Final Fantasy IV Advance (USA).gba")
FF5_PATH = os.path.join(BASE, "test_roms", "Final Fantasy V Advance (USA).gba")

TOK = re.compile(r'\[[0-9A-F]{2,6}\]')


def _strip_ff(text):
    """Убирает Hex-токены [FF]/[FE] и пробельные символы."""
    return re.sub(r'\[(FF|FE)\]', '', text).replace(' ', '').replace('\t', '').replace('\n', '')


def _decode_all(plugin, rom, segments):
    return [
        segment['decoder'].decode(rom.data, segment['start'], segment['end'] - segment['start'])
        for segment in segments
    ]


@pytest.fixture(scope="module")
def ff4():
    return FF4AdvancePlugin()


@pytest.fixture(scope="module")
def ff4_rom():
    if not os.path.exists(FF4_PATH):
        pytest.skip(f'Нет ROM: {os.path.basename(FF4_PATH)}')
    return GameBoyROM(FF4_PATH)


@pytest.fixture(scope="module")
def ff4_segments(ff4, ff4_rom):
    return ff4.get_text_segments(ff4_rom)


@pytest.fixture(scope="module")
def ff5():
    return FF5AdvancePlugin()


@pytest.fixture(scope="module")
def ff5_rom():
    if not os.path.exists(FF5_PATH):
        pytest.skip(f'Нет ROM: {os.path.basename(FF5_PATH)}')
    return GameBoyROM(FF5_PATH)


@pytest.fixture(scope="module")
def ff5_segments(ff5, ff5_rom):
    return ff5.get_text_segments(ff5_rom)


class TestFF4PointerBase:
    """Корень фикса: база указателей FF4 = таблица - 0x10."""

    def test_data_start_is_base_not_block_start(self):
        # База НЕ должна быть 0x2E98BC (это сдвигало строки на 0x624C)
        assert FF4_TEXT_DATA_START == 0x2E3670
        assert FF4_TEXT_DATA_START != 0x2E98BC

    def test_no_midword_truncation(self, ff4, ff4_segments, ff4_rom):
        # Полная строка диалога должна извлекаться целиком (не 'rtant room!')
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        assert any('Important room!' in t for t in texts), "Полный диалог не найден"

    def test_important_room_intact(self, ff4, ff4_segments, ff4_rom):
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        full = [t for t in texts if 'Important room!' in t]
        assert full, "Полная строка 'Important room!' должна извлекаться"
        # и строка начинается с самого начала диалога, а не со сдвинутого куска
        assert any('Lali-ho! No!' in t for t in texts)

    def test_menu_strings_preserved(self, ff4, ff4_segments, ff4_rom):
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        assert 'English' in texts
        assert 'Load Game' in texts
        assert 'Save 3' in texts


class TestFF4NoiseFilter:
    def test_no_single_glyphs(self, ff4, ff4_segments, ff4_rom):
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        singles = [t for t in texts if len(t) == 1]
        assert singles == []

    def test_no_hex_tokens(self, ff4, ff4_segments, ff4_rom):
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        for t in texts:
            assert not TOK.fullmatch(t), f"Hex-only запись проскочила: {t!r}"

    def test_dialogue_quality(self, ff4, ff4_segments, ff4_rom):
        texts = _decode_all(ff4, ff4_rom, ff4_segments)
        with_glyph = [t for t in texts if 'Lali-ho' in t or 'Cecil' in t or 'Mystery' in t]
        assert with_glyph


class TestFF5NoiseFilter:
    def test_no_binary_segments(self, ff5, ff5_segments, ff5_rom):
        """Сегменты с 2+ Hex-токенами (бинарные данные/заполнение) отсечены."""
        texts = _decode_all(ff5, ff5_rom, ff5_segments)
        heavy = [t for t in texts if len(TOK.findall(t)) >= 2]
        assert heavy == []

    def test_no_ff_fill_tails(self, ff5, ff5_segments, ff5_rom):
        texts = _decode_all(ff5, ff5_rom, ff5_segments)
        # Гибантские хвосты из области заполнения 0xFF (араров): строка была бы
        # чистым [FF][FE]-repeat. После удаления токенов смыи осталась пустая строка.
        ff_only = [t for t in texts if _strip_ff(t) == '']
        assert ff_only == []

    def test_no_giant_segments(self, ff5, ff5_segments, ff5_rom):
        texts = _decode_all(ff5, ff5_rom, ff5_segments)
        assert all(len(t) < 100000 for t in texts)

    def test_real_dialogues_preserved(self, ff5, ff5_segments, ff5_rom):
        texts = _decode_all(ff5, ff5_rom, ff5_segments)
        assert any('BARTZ' in t for t in texts)
        assert any('Kelger' in t for t in texts)
        assert any('drakenvale' in t.lower() or 'Drakenvale' in t for t in texts)
        assert len(texts) > 6000


def _roundtrip(rom, segments):
    """decode(encode(text)) == text для всех сегментов."""
    failures = []
    for segment in segments:
        raw = rom.data[segment['start']:segment['end']]
        decoded = segment['decoder'].decode(raw, 0, len(raw))
        if not decoded:
            continue
        encoded = segment['decoder'].encode(decoded)
        redecoded = segment['decoder'].decode(encoded, 0, len(encoded))
        if redecoded != decoded:
            failures.append((decoded[:60], redecoded[:60], len(encoded)))
    return failures


class TestFF4Encoder:
    def test_roundtrip_all_segments(self, ff4, ff4_segments, ff4_rom):
        failures = _roundtrip(ff4_rom, ff4_segments)
        assert failures == [], f"Round-trip разъехался на {len(failures)} сегментах: {failures[:5]}"

    def test_control_codes_roundtrip(self, ff4):
        dec = ff4._decoder
        cecil = bytes([0x22, 0x01, 0x12, 0x08, 0x0A])  # C e c i l по чармапу FF4
        raw = bytes([0xC5, 0x96]) + cecil + bytes([0xC5, 0xAC])
        text = dec.decode(raw, 0, len(raw))
        assert text == '[LINEBREAK_DIALOGUE]Cecil[CLEAN_BOX]'
        assert dec.encode(text) == raw

    def test_hex_token_roundtrip(self, ff4):
        dec = ff4._decoder
        raw = bytes([0xC2, 0x80, 0x9A])  # неизвестные байты -> hex-токены
        text = dec.decode(raw, 0, len(raw))
        assert text == '[C280][9A]'
        assert dec.encode(text) == raw

    def test_inject_segment_noop(self, ff4_rom):
        from core.injector import TextInjector
        plugin = FF4AdvancePlugin()
        injector = TextInjector(FF4_PATH)
        segments = plugin.get_text_segments(injector.rom)
        for seg in segments:
            msgs = injector._extract_original_messages(seg)
            if len(msgs) == 1 and msgs[0]['text'] and msgs[0]['offset'] == 0:
                text = msgs[0]['text']
                break
        else:
            pytest.fail("Не найден ни один одиночный сегмент FF4 для no-op инжекции")
        encoded = seg['decoder'].encode(text)
        ok = injector.inject_segment(seg['name'], [text], plugin, segments=segments)
        assert ok is True
        assert bytes(injector.modified_data[seg['start']:seg['start'] + len(encoded)]) == encoded


class TestFF5Encoder:
    def test_roundtrip_all_segments(self, ff5, ff5_segments, ff5_rom):
        failures = _roundtrip(ff5_rom, ff5_segments)
        assert failures == [], f"Round-trip разъехался на {len(failures)} сегментах: {failures[:5]}"

    def test_control_codes_roundtrip(self, ff5):
        dec = ff5._decoder
        bartz = bytes([0x27, 0x2C, 0x2F, 0x1D, 0x41])  # B A R T Z по чармапу FF5
        raw = bytes([0xC2, 0xB3]) + bartz + bytes([0xC2, 0xB7])
        text = dec.decode(raw, 0, len(raw))
        assert text == '[BARTZ_NAME]BARTZ[CLEAN_BOX]'
        assert dec.encode(text) == raw

    def test_inject_segment_noop(self, ff5_rom):
        from core.injector import TextInjector
        plugin = FF5AdvancePlugin()
        injector = TextInjector(FF5_PATH)
        segments = plugin.get_text_segments(injector.rom)
        for seg in segments:
            msgs = injector._extract_original_messages(seg)
            if len(msgs) == 1 and msgs[0]['text'] and msgs[0]['offset'] == 0:
                text = msgs[0]['text']
                break
        else:
            pytest.fail("Не найден ни один одиночный сегмент FF5 для no-op инжекции")
        encoded = seg['decoder'].encode(text)
        ok = injector.inject_segment(seg['name'], [text], plugin, segments=segments)
        assert ok is True
        assert bytes(injector.modified_data[seg['start']:seg['start'] + len(encoded)]) == encoded
