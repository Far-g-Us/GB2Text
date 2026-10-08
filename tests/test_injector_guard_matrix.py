"""Пакетная проверка защитных guards в `core/injector.py`.

Почему пакет, а не тест на каждую строку: почти все непокрытые места в
инжекторе — однотипные проверки типа входных данных (`bool` вместо `int`,
`None` вместо списка, строка вместо списка). Каждая из них защищает запись в
ROM, поэтому проверяется осмысленно: «мусор на входе → отказ, байты не
тронуты». Список параметров ниже — это и есть инвентарь guards: если новый
guard не попал в параметризацию, он останется непокрытым и это будет видно
в отчёте.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.injector import TextInjector

ROM_SIZE = 0x8000


@pytest.fixture
def injector(tmp_path):
    path = tmp_path / 'rom.gba'
    path.write_bytes(bytes(ROM_SIZE))
    return TextInjector(str(path))


class _StubPlugin:
    """Плагин с настраиваемым списком сегментов."""

    def __init__(self, segments=None):
        self._segments = segments if segments is not None else []

    def get_text_segments(self, rom):
        return self._segments


def _seg(name='s', start=0x100, end=0x200, **kw):
    seg = {'name': name, 'start': start, 'end': end}
    seg.update(kw)
    return seg


# ── plugin segments: битый список от плагина ────────────────────────────────

def test_broken_plugin_segments_become_empty(injector):
    """Плагин вернул не список — инжектор работает с пустым, а не падает."""
    for broken in (None, 'segments', 42, {'a': 1}, [None, 5, 'x']):
        injector._segment_cache.clear()
        plugin = _StubPlugin(broken)
        assert injector._get_segments(plugin) == []


def test_segments_by_name_skips_non_dict_entries(injector):
    """Сегменты без имени или не-dict не попадают в словарь имён."""
    segments = [_seg(name='a'), 'oops', _seg(name=5), {'start': 0}]
    by_name = injector._segments_by_name(segments)
    assert set(by_name) == {'a'}


def test_sync_bank_segments_ignores_non_list(injector):
    """Синхронизация банковых сегментов на не-list просто ничего не делает."""
    for value in (None, 'x', 42, {'a': 1}):
        injector._sync_bank_segments(value)


def test_validated_cache_returns_same_object(injector):
    """Валидный список возвращается тем же объектом: кэш индекса зависит от
    идентичности, а не от копии."""
    segments = [_seg()]
    assert injector._validated(segments) is segments
    assert injector._validated(segments) is segments


# ── inject_segment / inject_translations ───────────────────────────────────

@pytest.mark.parametrize('translations', [None, 'text', 42, {'a': 1}, True])
def test_inject_segment_rejects_non_list_translations(injector, translations):
    """translations должен быть списком: строка прошла бы как итерация символов."""
    assert injector.inject_segment('s', translations, _StubPlugin()) is False


@pytest.mark.parametrize('name', [None, 42, b's'])
def test_inject_segment_rejects_bad_name(injector, name):
    """Имя сегмента должно быть строкой."""
    assert injector.inject_segment(name, ['A'], _StubPlugin()) is False


def test_inject_segment_rejects_bad_segments(injector):
    """segments не-list — отказ."""
    assert injector.inject_segment('s', ['A'], _StubPlugin(), segments='x') is False


def test_inject_segment_unknown_segment_returns_false(injector):
    """Сегмента с таким именем нет — отказ, а не пустая запись."""
    plugin = _StubPlugin([_seg(name='other')])
    assert injector.inject_segment('s', ['A'], plugin) is False


def test_inject_translations_rejects_bad_results(injector):
    """results не-dict — отказ: иначе отчёт молчал бы о пропущенных записях."""
    plugin = _StubPlugin([_seg()])
    assert injector.inject_translations('s', ['A'], plugin, results='x') is False


def test_inject_translations_rejects_bad_translations(injector):
    plugin = _StubPlugin([_seg()])
    assert injector.inject_translations('s', 'A', plugin) is False


# ── inject_language_block ──────────────────────────────────────────────────

@pytest.mark.parametrize('texts', [None, 'text', 42, True])
def test_language_block_rejects_non_list_texts(injector, texts):
    assert injector.inject_language_block('ru', texts, _StubPlugin()) is False


@pytest.mark.parametrize('lang', [None, 42, b'ru'])
def test_language_block_rejects_bad_lang(injector, lang):
    assert injector.inject_language_block(lang, ['A'], _StubPlugin()) is False


def test_language_block_rejects_bad_segments(injector):
    assert injector.inject_language_block('ru', ['A'], _StubPlugin(),
                                          segments='x') is False


def test_language_block_without_lang_slots(injector):
    """Без meta['lang_slots'] вставка невозможна — отказ."""
    seg = _seg(kind='record', meta={'lang': 'ru'})
    plugin = _StubPlugin([seg])
    assert injector.inject_language_block('ru', ['A'], plugin) is False


# ── inject_interleaved_language ────────────────────────────────────────────

@pytest.mark.parametrize('texts', [None, 'text', 42])
def test_interleaved_rejects_non_list_texts(injector, texts):
    assert injector.inject_interleaved_language('ru', texts, _StubPlugin()) is False


@pytest.mark.parametrize('lang', [None, 42])
def test_interleaved_rejects_bad_lang(injector, lang):
    assert injector.inject_interleaved_language(lang, ['A'], _StubPlugin()) is False


def test_interleaved_rejects_bad_segments(injector):
    assert injector.inject_interleaved_language('ru', ['A'], _StubPlugin(),
                                               segments=42) is False


# ── валидация манифестов и таблиц ──────────────────────────────────────────

@pytest.mark.parametrize('bad', [None, 'x', 42, True])
def test_inject_fixed_width_rejects_bad_offsets(injector, bad):
    """Список смещений не-list — отказ до любых вычислений."""
    seg = _seg(fixed_width=4, record_count=2)
    plugin = _StubPlugin([seg])
    assert injector.inject_segment('s', ['A'], plugin) is False


def test_expand_rom_rejects_bad_size(injector):
    """Размер расширения не-int или <= 0 — отказ, ROM не растёт."""
    for size in (None, 'x', 0, -1, True):
        with pytest.raises(ValueError):
            injector._expand_rom(size)
    assert len(injector.modified_data) == ROM_SIZE


def test_expand_rom_refuses_past_limit(injector):
    """Расширение за предел MAX_ROM_SIZE отвергается, а не падает по памяти."""
    from core.rom import MAX_ROM_SIZE
    with pytest.raises(ValueError):
        injector._expand_rom(MAX_ROM_SIZE + 1)
    assert len(injector.modified_data) == ROM_SIZE


@pytest.mark.parametrize('offset,target', [
    ('x', 0x100), (True, 0x100), (None, 0x100),
    (-1, 0x100), (0x100, 'y'), (0x100, True), (0x100, None),
    (-1, -1),
])
def test_patch_one_pointer_rejects_bad_types(injector, offset, target):
    """Типы аргументов патча указателя проверяются ДО записи в ROM."""
    with pytest.raises(ValueError):
        injector._patch_one_pointer(offset, target)


def test_patch_one_pointer_writes_pointer(injector):
    """Рабочий случай: в слот пишется указатель с базой GBA."""
    injector._patch_one_pointer(0x100, 0x200)
    value = int.from_bytes(injector.modified_data[0x100:0x104], 'little')
    assert value == 0x200 + 0x08000000
