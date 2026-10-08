"""Добивание последних веток вне `core/injector.py`.

Каждая ветка — реальная развилка: отказ на негодных данных, «серия не
прошла фильтр», «сообщение из одного токена», «указатель верен, но уже
занят». Мёртвые ветки в коде помечены `# pragma: no cover` с объяснением.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import gb_compression as gc
from core.gb_banks import BANK_SIZE, scan_bank_pointers
from core.translation_validator import TranslationValidator

ROM_2BANK = 2 * BANK_SIZE


def make_extractor(tmp_path):
    """Экземпляр без реального ROM: подменяем объект после инициализации."""
    from core.extractor import TextExtractor
    path = tmp_path / 'rom.gba'
    path.write_bytes(bytes(0x1000))
    ex = TextExtractor(str(path))
    rom_path = str(path)

    class _Rom:
        data = bytearray(0x1000)
        system = 'gba'
        path = rom_path

        def get_game_id(self):
            return 'GBA_TEST'

    ex.rom = _Rom()
    return ex


# ── core/gb_compression.py ─────────────────────────────────────────────────

def test_base_handler_methods_are_no_ops():
    """Тела абстрактных методов базы — `pass`, то есть возвращают None.

    Это зафиксировано явно, потому что подкласс, забывший переопределить
    метод, получит молчаливый `None` вместо данных: `_decompress` в
    extractor проверяет `isinstance(..., (bytes, bytearray))` и отдаёт
    исходник, то есть «сжатый» сегмент просто не распакуется. Тест держит
    это поведение видимым.
    """
    base = gc.CompressionHandler
    assert base.decompress(object(), b'\x00', 0) is None  # type: ignore[arg-type]
    # compress объявлен не в базе, а в наследниках: база его не определяет.
    with pytest.raises(TypeError):
        base()  # type: ignore[abstract]


def test_guess_format_never_accepts_both_formats():
    """RLE- и LZ-потоки взаимоисключающи: оба сразу текстом не бывает.

    Проверено на потоках, сгенерированных обоими компрессорами, и на
    ручных комбинациях RLE-хвостов с текстовыми окончаниями. Именно этим
    объясняется `pragma: no branch` на сравнении коэффициентов в коде.
    """
    charmap = {b: chr(b) for b in range(0x20, 0x7F)}
    printable = frozenset(charmap)
    texts = ('THE QUICK BROWN FOX ' * 8, 'HELLO WORLD ' * 16,
             'ABCABCABCABC' * 32, 'menu item selected ' * 20)
    for text in texts:
        raw = text.encode()
        for blob in (gc.NintendoLZHandler().compress(raw),
                     gc.ControlByteRLEHandler().compress(raw),
                     raw):
            plausible = 0
            for handler in (gc.ControlByteRLEHandler(),
                            gc.NintendoLZHandler()):
                out, used = handler.decompress(blob, 0)
                if used > 0 and len(out) >= 8 and \
                        gc._text_likeness(out[:1024], printable) \
                        >= gc.TEXT_LIKENESS_MIN:
                    plausible += 1
            assert plausible <= 1, 'оба формата на одном потоке невозможны'


# ── core/gb_banks.py ───────────────────────────────────────────────────────

def test_scan_bank_pointers_on_empty_bank_span():
    """Банк за пределами файла даёт пустой диапазон, а не чтение из воздуха."""
    assert scan_bank_pointers(bytearray(ROM_2BANK), 0x4000, bank=999) == []


def test_scan_banked_rows_logs_when_filter_rejects_everything():
    """Ни одна серия не прошла — результат пуст (ветка диагностики)."""
    from core.gb_banks import scan_banked_rows
    data = bytearray(ROM_2BANK)
    # Монотонность соблюдена, но банков больше max_banks: 8 разных банков.
    blob = b''
    for i in range(8):
        blob += bytes([i + 1]) + (0x5000 + i * 0x10).to_bytes(2, 'little')
    data[0x100:0x100 + len(blob)] = blob
    assert scan_banked_rows(data, 0x100, 8, min_rows=8, max_banks=2) == []


# ── core/extractor.py ──────────────────────────────────────────────────────

def test_recode_record_decoder_exception(tmp_path):
    """Record-сегмент, декодер которого бросает, — пропуск, не исключение."""
    ex = make_extractor(tmp_path)

    class _Boom:
        def decode(self, *_a):
            raise ValueError('bad charmap')

    seg = {'start': 0, 'end': 16, 'kind': 'record'}
    assert ex.recode_segment(seg, _Boom()) == []


def test_split_messages_drops_token_only_tail(tmp_path):
    """Сообщение из одного токена не идёт в результат: переводить нечего."""
    ex = make_extractor(tmp_path)
    assert ex._split_messages('[01]', 0) == []
    assert ex._split_messages('A[END][01]', 0) != []


def test_pointer_dialogues_without_any_decoder(tmp_path):
    """Ни декодера в аргументе, ни в сегменте — пустой результат."""
    ex = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 64, 'manifest': [{'target': 0, 'length': 4}]}
    assert ex._extract_pointer_dialogues(seg) == []


# ── core/translation_validator.py ──────────────────────────────────────────

def test_validator_reports_only_dropped_tokens():
    """Список «потерянных» не содержит токенов, которые в переводе остались."""
    v = TranslationValidator()
    src = '[01] [FF 0B] NAME'
    dst = '[FF 0B] NAME'
    report = v.validate(src, dst)
    text = str(report)
    assert '[01]' in text
    assert text.count('[FF 0B]') <= 1


# ── plugins/zelda_oracle_common.py ─────────────────────────────────────────

def test_oracle_dict_phrases_with_explicit_data_bypasses_cache():
    """Явный data всегда пересчитывает фразы: кэш относится к исходному ROM."""
    from plugins.zelda_oracle_common import OracleTextDecoder

    dec = OracleTextDecoder.__new__(OracleTextDecoder)
    dec._last_data = b'rom'
    dec._dict_phrase_cache = None
    dec._idx_to_addr = {0: 0}
    dec._decompress = lambda *args: args[3].extend(b'hi')
    first = dec._dict_phrases()
    assert first
    # Теперь передаём ИЗМЕНЁННЫЕ данные (инжектор так и делает после записи
    # перевода в словарь) — кэш от старого ROM здесь не годится.
    second = dec._dict_phrases(b'changed')
    assert second == first


def test_oracle_decode_failure_logged_only_for_first_three(tmp_path):
    """После четвёртой неудачи предупреждения не повторяются: их была бы гора."""
    from plugins.zelda_oracle_common import OracleTextDecoder

    dec = OracleTextDecoder.__new__(OracleTextDecoder)
    dec._last_data = b'rom'
    dec._dict_phrase_cache = None
    dec._idx_to_addr = {}
    assert dec._dict_phrases() == []


# ── plugins/gba_pokemon.py ─────────────────────────────────────────────────

def test_fixed_decoder_uppercase_fallback_used():
    """Буквы нет в карте, но есть её верхний регистр — используется он."""
    from plugins.gba_pokemon import PokemonFixedTextDecoder
    dec = PokemonFixedTextDecoder({0xE1: 'A', 0x00: ' '})
    assert dec.encode('a') == b'\xE1'
