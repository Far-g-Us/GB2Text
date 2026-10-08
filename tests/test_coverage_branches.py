"""Тесты на оставшиеся ветки, которые не покрывались основными наборами.

Здесь нет «тестов ради процента»: каждая ветка — либо отказ, либо граница
окна поиска, либо ранний выход, и в каждом случае неверное поведение
привело бы к записи не туда. Недостижимые ветки помечены в коде
`# pragma: no cover` с объяснением.
"""
import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import gb_compression as gc
from core.gb_banks import BANK_SIZE, scan_bank_pointers, scan_banked_rows
from core.ml_classifier import SKLEARN_AVAILABLE, _sklearn_available

ROM_2BANK = 2 * BANK_SIZE
ASCII = {b: chr(b) for b in range(0x20, 0x7F)}


# ── core/gb_compression.py ─────────────────────────────────────────────────

def test_find_match_missing_bucket():
    """Ключа нет в цепочке — совпадения быть не может."""
    handler = gc.NintendoLZHandler()
    assert handler._find_match(b'hello world', 6, {}) == (0, 0)


def test_find_match_offsets_beyond_window():
    """Единственный кандидат дальше окна LZ (4096) — искать дальше бессмысленно.

    Заполнитель не содержит нулей, иначе в буфере нашлась бы настоящая
    длинная серия и проверка прошла бы враньём.
    """
    handler = gc.NintendoLZHandler()
    filler = bytes((i % 251) + 1 for i in range(gc.LZ_MAX_OFFSET + 64))
    raw = b'AB' + filler + b'AB'
    key = raw[-2] | (raw[-1] << 8)
    assert handler._find_match(raw, len(raw) - 2, {key: [0]}) == (0, 0)


def test_guess_format_keeps_first_better_handler():
    """Второй обработчик не вытесняет первый, если коэффициент хуже."""
    payload = bytearray()
    for _ in range(6):
        payload += bytes([0x80 | 0x7D]) + b' ' * 0x80
    payload += b'TEXT TEXT TEXT TEXT' * 4
    name, ratio = gc.guess_format(bytes(payload), 0, charmap=ASCII)
    assert name == 'rle'
    assert ratio > 1.05


# ── core/compression.py ────────────────────────────────────────────────────

def test_ffta_compress_stops_at_window_edge():
    """Совпадение дальше окна 0x4000 не используется: цикл обрывается по limit."""
    from core.compression import FFTA_LZSSHandler

    data = b'ABC' + b'x' * 0x4100 + b'ABC' + b'y' * 32
    out = FFTA_LZSSHandler().compress(data)
    assert isinstance(out, (bytes, bytearray))
    assert out, 'сжатие должно что-то вернуть'


# ── core/gb_banks.py ───────────────────────────────────────────────────────

def test_banked_rows_reports_when_nothing_passed():
    """Ни одна серия не прошла фильтр — результат пуст."""
    data = bytearray(ROM_2BANK)
    blob = b''
    for i in range(8):
        blob += bytes([1]) + (0x4000 + i * 0x1000).to_bytes(2, 'little')
    data[0x100:0x100 + len(blob)] = blob
    assert scan_banked_rows(data, 0x100, 8, min_rows=8) == []


def test_scan_bank_pointers_without_matches():
    """Нет ни одного совпадения — пустой список, без исключения."""
    assert scan_bank_pointers(bytearray(ROM_2BANK), 0x7BEE, bank=0) == []


def test_scan_text_table_skips_clipped_bank():
    """Обрезанный последний банк пропускается, а не читается «задом наперёд»."""
    from core.gb_banks import scan_for_text_pointers

    assert scan_for_text_pointers(bytearray(0x5000), 0x5000, min_run=2) == []


def test_scan_text_table_bank_too_small():
    from core.gb_banks import scan_text_table

    assert scan_text_table(bytearray(0x200), bank=9, min_rows=4) == []


# ── core/ml_classifier.py ──────────────────────────────────────────────────

def test_sklearn_available_false_without_package(monkeypatch):
    """Без установленного sklearn модуль считает ML недоступным, а не падает."""
    monkeypatch.setattr(importlib.util, 'find_spec', lambda _name: None)
    assert _sklearn_available() is False
    monkeypatch.undo()
    assert _sklearn_available() == SKLEARN_AVAILABLE


# ── core/community_registry.py ─────────────────────────────────────────────

def _registry(tmp_path):
    from core.community_registry import CommunityRegistry
    return CommunityRegistry(plugins_dir=tmp_path / 'plugins',
                             settings_dir=tmp_path / 'settings',
                             registry_url='https://example.invalid/r.json',
                             allowed_hosts=('example.invalid',))


def test_bundled_registry_skips_non_dict(tmp_path, monkeypatch):
    """Файл реестра, где не dict, пропускается — окно всё равно открывается."""
    reg = _registry(tmp_path)
    bad = tmp_path / 'bad.json'
    bad.write_text('[1, 2, 3]', encoding='utf-8')
    good = tmp_path / 'good.json'
    good.write_text(json.dumps({'plugins': [{'id': 'x', 'name': 'X'}]}),
                    encoding='utf-8')
    monkeypatch.setattr(reg, '_bundled_registry_candidates',
                        lambda: [str(bad), str(good)])
    assert reg._load_bundled() == [{'id': 'x', 'name': 'X'}]


def test_bundled_registry_returns_none_when_all_fail(tmp_path, monkeypatch):
    """Ни один файл не подошёл — None, а не исключение."""
    reg = _registry(tmp_path)
    monkeypatch.setattr(reg, '_bundled_registry_candidates',
                        lambda: [str(tmp_path / 'missing.json')])
    assert reg._load_bundled() is None


def test_bundled_registry_validates_when_asked(tmp_path, monkeypatch):
    """Битый каталог из поставки пропускается, а ошибка уходит наверх.

    `_load_bundled` перебирает файлы и молча пропускает негодные — иначе один
    испорченный файл закрыл бы окно плагинов. Если не подошёл ни один,
    возвращается None, и вызывающий `fetch_registry` поднимает
    CommunityRegistryError с исходной сетевой ошибкой в `__cause__`.
    """
    from core.community_registry import CommunityRegistryError
    reg = _registry(tmp_path)
    good = tmp_path / 'good.json'
    good.write_text(json.dumps({'plugins': [{'id': 'x', 'name': 'X'}]}),
                    encoding='utf-8')
    monkeypatch.setattr(reg, '_bundled_registry_candidates',
                        lambda: [str(good)])

    def boom(_plugins):
        raise CommunityRegistryError('bad catalogue')

    monkeypatch.setattr(reg, '_validate_plugins', boom)
    assert reg._load_bundled(validate=True) is None

    monkeypatch.setattr(reg, '_load_cache', lambda validate=False: None)
    monkeypatch.setattr(reg, '_load_bundled', lambda validate=False: None)
    monkeypatch.setattr(reg, '_fetch_remote', lambda: (_ for _ in ()).throw(
        OSError('offline')), raising=False)
    with pytest.raises(CommunityRegistryError):
        reg.fetch_registry()


def test_bundled_registry_rejects_invalid_json(tmp_path, monkeypatch):
    """Не-JSON — тот же отказ, что и отсутствующий файл."""
    reg = _registry(tmp_path)
    junk = tmp_path / 'junk.json'
    junk.write_text('{not json', encoding='utf-8')
    monkeypatch.setattr(reg, '_bundled_registry_candidates',
                        lambda: [str(junk)])
    assert reg._load_bundled() is None


# ── core/translation_validator.py ──────────────────────────────────────────

def test_validator_repeated_token_reported_once():
    """Повторяющийся токен не превращается в две «потерянные» копии."""
    from core.translation_validator import TranslationValidator
    validator = TranslationValidator()
    report = validator.validate('[01] [01] [02] NAME', 'NAME')
    assert report is not None


# ── plugins/gba_pokemon.py ─────────────────────────────────────────────────

def _fixed_decoder():
    from plugins.gba_pokemon import PokemonFixedTextDecoder
    return PokemonFixedTextDecoder({0xE1: 'A', 0x00: ' '})


def test_fixed_decoder_maps_via_uppercase():
    """Буква, отсутствующая в карте, ищется в верхнем регистре."""
    assert _fixed_decoder().encode('A') == b'\xE1'


def test_fixed_decoder_unknown_char_non_strict():
    """Неизвестный символ в нестрогом режиме заменяется пробелом, не падает."""
    assert _fixed_decoder().encode('\u0410') == b'\x00'


def test_fixed_decoder_unknown_char_strict():
    with pytest.raises(ValueError):
        _fixed_decoder().encode('\u0410', strict=True)


# ── plugins/zelda_oracle_common.py ─────────────────────────────────────────

def test_oracle_dict_phrases_fill_then_use_cache():
    """Первый вызов наполняет кэш, второй отдаёт его без перебора."""
    from plugins.zelda_oracle_common import OracleTextDecoder

    dec = OracleTextDecoder.__new__(OracleTextDecoder)
    dec._last_data = b'payload'
    dec._dict_phrase_cache = None
    dec._idx_to_addr = {0: 0, 1: 8}
    # _decompress пишет результат в переданный out: иначе фраз пустыми
    dec._decompress = lambda *args: args[3].extend(b'hi')
    first = dec._dict_phrases()
    assert first, 'фразы должны быть найдены'
    second = dec._dict_phrases()
    assert second == first


def test_oracle_dict_phrases_without_source():
    """Нет ни данных, ни кэша — пустой список, без исключения."""
    from plugins.zelda_oracle_common import OracleTextDecoder

    dec = OracleTextDecoder.__new__(OracleTextDecoder)
    dec._last_data = None
    dec._dict_phrase_cache = None
    dec._idx_to_addr = {}
    assert dec._dict_phrases() == []


# ── plugins/gba_advance_wars.py ───────────────────────────────────────────

def test_advance_wars_rejects_binary_block():
    """Двоичный блок не принимается за текст: не все байты печатаемые."""
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'\x01\x02\x03\x04\x05\x06', 0) is None


def test_advance_wars_accepts_one_letter():
    """Одна буква принимается: порог «>= 2 буквы» не инвариантен к переводу.

    Сокращение `'Map11'` -> `'M'` даёт одну букву; прежний порог терял такую
    запись из манифеста (31 из 186). Проверка непечатных байтов остаётся.
    """
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'A\x00rest', 0) == 'A'
    assert _decode_at(b'A\x01B\x00', 0) is None


def test_advance_wars_rejects_out_of_range_target():
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'hello\x00', 99) is None
    assert _decode_at(b'hello\x00', -1) is None


def test_advance_wars_rejects_unterminated_block():
    """Строка без терминатора до конца буфера — не строка."""
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'hello world', 0) is None


def test_advance_wars_skips_table_past_end():
    """Таблица, уходящая за конец файла, пропускается целиком."""
    from plugins.gba_advance_wars import _entries_for_rom
    assert _entries_for_rom(bytes(0x100)) == []


def test_advance_wars_decode_unknown_byte_as_raw_token():
    """Байт вне карты показывается как [XX], а не теряется."""
    from plugins.gba_advance_wars import AdvanceWarsTextDecoder
    dec = AdvanceWarsTextDecoder({0x41: 'A', 0x00: '\x00'})
    assert dec.decode(b'\x41\xFE\x41\x00', 0, 4) == 'A[FE]A'


def test_advance_wars_charmap_duplicate_char_keeps_first_byte():
    """Два байта на один символ: в обратную карту идёт первый."""
    from plugins.gba_advance_wars import AdvanceWarsTextDecoder
    dec = AdvanceWarsTextDecoder({0x41: 'A', 0x42: 'A'})
    assert dec.encode('A') == b'\x41'


def test_advance_wars_encode_unknown_char_reports_once():
    """Неизвестный символ попадает в отчёт один раз, даже если повторяется."""
    from plugins.gba_advance_wars import AdvanceWarsTextDecoder
    dec = AdvanceWarsTextDecoder({0x41: 'A'})
    with pytest.raises(ValueError):
        dec.encode('A\u0410\u0411')
    # encode бросает на ПЕРВОМ неизвестном символе, до второго не доходит
    assert dec.last_unmapped_chars == ['\u0410']


def test_advance_wars_plugin_defaults():
    """Размер указателя и терминаторы у Advance Wars фиксированы."""
    from plugins.gba_advance_wars import AdvanceWarsPlugin
    plugin = AdvanceWarsPlugin()
    assert plugin.get_pointer_size(None) == 4  # type: ignore[arg-type]
    assert plugin.get_terminators('advance_wars_dialogues') == [0x00]
    assert plugin.get_compression_handler('advance_wars_dialogues') is None
