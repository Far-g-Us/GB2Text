"""Ветки основного цикла `extract()` и границы декомпрессора.

Цикл извлечения должен переживать битые сегменты: не-dict, строки вместо
чисел, запись без декодера, декодер, бросающий исключение или возвращающий
не строку. Раньше такой сегмент ронял всё извлечение, и пользователь терял
переводы остальных игр из-за одного битого окна.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractor import TextExtractor

ROM = 0x2000


class _Decoder:
    def __init__(self, result='TEXT', raises=None):
        self._result = result
        self._raises = raises

    def decode(self, data, start, length):
        if self._raises is not None:
            raise self._raises
        return self._result


class _Plugin:
    """Плагин, отдающий заранее заданные сегменты."""

    def __init__(self, segments):
        self._segments = segments

    def get_text_segments(self, rom):
        return list(self._segments)


class _PluginManager:
    def __init__(self, segments):
        self._plugin = _Plugin(segments)

    def get_plugin(self, *args, **kwargs):
        return self._plugin


def make(tmp_path, segments) -> TextExtractor:
    path = tmp_path / 'rom.gba'
    path.write_bytes(bytes(ROM))
    extractor = TextExtractor(str(path),
                              plugin_manager=_PluginManager(segments))
    rom_path = str(path)

    class _Rom:
        data = bytearray(ROM)
        system = 'gba'
        path = rom_path

        def get_game_id(self):
            return 'GBA_TEST'

    extractor.rom = _Rom()
    return extractor


def test_extract_skips_non_dict_segment(tmp_path):
    """Не-dict в списке сегментов пропускается, а не роняет извлечение."""
    ex = make(tmp_path, ['oops', {'name': 'ok', 'start': 0, 'end': 8,
                                  'decoder': _Decoder()}])
    out = ex.extract()
    assert 'ok' in out


def test_extract_skips_broken_bounds(tmp_path):
    """Битые name/start/end пропускаются: без name результат некуда положить."""
    segments = [
        {'start': 0, 'end': 8, 'decoder': _Decoder()},          # нет name
        {'name': 5, 'start': 0, 'end': 8},                        # name не строка
        {'name': 'b1', 'start': True, 'end': 8},                  # bool вместо int
        {'name': 'b2', 'start': 0, 'end': 'x'},
        {'name': 'good', 'start': 0, 'end': 8, 'decoder': _Decoder()},
    ]
    out = make(tmp_path, segments).extract()
    assert set(out) == {'good'}


def test_extract_record_without_raw_text_and_decoder(tmp_path):
    """Record-сегмент без raw_text и без декодера — пропуск, не исключение."""
    seg = {'name': 'rec', 'start': 0, 'end': 8, 'kind': 'record'}
    assert make(tmp_path, [seg]).extract() == {}


def test_extract_record_decoder_raises(tmp_path):
    """Сбой декодирования record-сегмента пропускается с предупреждением."""
    seg = {'name': 'rec', 'start': 0, 'end': 8, 'kind': 'record',
           'decoder': _Decoder(raises=ValueError('bad'))}
    assert make(tmp_path, [seg]).extract() == {}


def test_extract_record_raw_text_not_string(tmp_path):
    """Готовый raw_text не строка — отказ, а не текст в отчёте."""
    seg = {'name': 'rec', 'start': 0, 'end': 8, 'kind': 'record',
           'raw_text': 123}
    assert make(tmp_path, [seg]).extract() == {}


def test_extract_record_uses_ready_raw_text(tmp_path):
    """Готовый raw_text используется как есть, без обращения к ROM."""
    seg = {'name': 'rec', 'start': 0, 'end': 8, 'kind': 'record',
           'raw_text': 'READY'}
    assert make(tmp_path, [seg]).extract() == {'rec': [{'offset': 0,
                                                        'text': 'READY'}]}


def test_extract_record_with_decoder(tmp_path):
    """Record-сегмент декодируется из ROM, когда raw_text нет."""
    seg = {'name': 'rec', 'start': 0, 'end': 8, 'kind': 'record',
           'decoder': _Decoder(result='DECODED')}
    out = make(tmp_path, [seg]).extract()
    assert out == {'rec': [{'offset': 0, 'text': 'DECODED'}]}


def test_extract_pointer_dialogues_requires_decoder(tmp_path):
    """pointer_dialogues без декодера — пусто, а не падение."""
    seg = {'name': 'pd', 'start': 0, 'end': 64, 'kind': 'pointer_dialogues',
           'manifest': [{'target': 0, 'length': 4}]}
    # Сегмент попадает в результат с ПУСТЫМ списком: он виден в GUI, но
    # ничего не даёт, и переводчик не считает его потерянным.
    assert make(tmp_path, [seg]).extract() == {'pd': []}


def test_extract_pointer_dialogues_bad_max_decode(tmp_path):
    """Не-числовой max_decode_len заменяется безопасным значением."""
    seg = {'name': 'pd', 'start': 0, 'end': 64, 'kind': 'pointer_dialogues',
           'max_decode_len': True, 'decoder': _Decoder(result='A'),
           'manifest': [{'target': 0, 'length': 4}]}
    out = make(tmp_path, [seg]).extract()
    assert 'pd' in out


# ── _decompress: не-байты вместо распакованных данных ─────────────────────

def test_decompress_named_handler_returning_non_bytes(tmp_path):
    """Обработчик, вернувший не байты, — исходные данные и предупреждение."""
    ex = make(tmp_path, [])

    import core.compression as comp
    original = comp.get_compression_handler

    class _Bad:
        def decompress(self, data, start):
            return ('nope', 1)

    comp.get_compression_handler = lambda name: _Bad()
    try:
        assert ex._decompress(bytearray(b'abcd'), 'rle') == b'abcd'
    finally:
        comp.get_compression_handler = original


def test_decompress_object_returning_non_bytes(tmp_path):
    """Тот же отказ для объекта с методом decompress."""
    ex = make(tmp_path, [])

    class _BadObj:
        def decompress(self, data, start):
            return 'nope', 0

    assert ex._decompress(bytearray(b'abcd'), _BadObj()) == b'abcd'


def test_decompress_named_handler_raising(tmp_path):
    """Исключение при распаковке — исходные данные, а не потеря сегмента."""
    ex = make(tmp_path, [])

    import core.compression as comp
    original = comp.get_compression_handler

    class _Boom:
        def decompress(self, data, start):
            raise RuntimeError('no tree')

    comp.get_compression_handler = lambda name: _Boom()
    try:
        assert ex._decompress(bytearray(b'abcd'), 'rle') == b'abcd'
    finally:
        comp.get_compression_handler = original


def test_decompress_object_raising(tmp_path):
    ex = make(tmp_path, [])

    class _BoomObj:
        def decompress(self, data, start):
            raise RuntimeError('boom')

    assert ex._decompress(bytearray(b'abcd'), _BoomObj()) == b'abcd'


def test_decompress_unknown_compression_type(tmp_path):
    """Неизвестный тип сжатия — данные без изменений."""
    ex = make(tmp_path, [])
    # обработчика с таким именем нет — данные без изменений
    assert ex._decompress(bytearray(b'abcd'), 'huffman') == b'abcd'
    assert ex._decompress(bytearray(b'abcd'), 42) == b'abcd'


def test_decompress_none_is_passthrough(tmp_path):
    ex = make(tmp_path, [])
    assert ex._decompress(bytearray(b'abcd'), None) == b'abcd'
