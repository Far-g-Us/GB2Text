"""Отказ на переводе, заканчивающемся raw-токеном.

Экстрактор отбрасывает хвостовой token-only прогон из отображения, поэтому
перевод `in[F6]` (FF5, запись `in[F6]a!`) не пережил бы round-trip: при
обратном извлечении из окна `08 05 f6 0d` читалось бы `in`, то есть молча
терялся и символ, и токен. Раньше инжектор писал такой перевод и сообщал
об успехе.

Проверяется сам предикат отказа и то, что инжектор пишет отчёт, а не байты.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector

ROM_SIZE = 512


class _AsciiDecoder:
    def decode(self, data, start, length):
        return bytes(data[start:start + length]).split(b'\x00')[0].decode(
            'ascii', 'replace')

    def encode(self, text):
        return text.encode('ascii')


class _DummyPlugin:
    """Заглушка: `inject_translations` отказывает на `plugin=None`."""
    is_stub = False


def _injector() -> TextInjector:
    inj = TextInjector.__new__(TextInjector)

    class _FakeROM:
        data: bytearray

        def __init__(self, data):
            self.data = bytearray(data)

    inj.rom = _FakeROM(bytearray(ROM_SIZE))
    inj.original_data = bytearray(ROM_SIZE)
    inj.modified_data = bytearray(ROM_SIZE)
    inj._segment_cache = {}
    inj._bank_segments = []
    inj._taken_free_blocks = []
    inj._written_spans = []
    inj.last_overflow_report = []
    inj.last_relocate_report = []
    inj.last_overlap_report = []
    inj.last_affix_report = []
    inj.last_spellcheck_report = []
    inj.last_fit_report = []
    inj.last_unmapped_chars = []
    inj.logger = logging.getLogger('test')
    return inj


@pytest.mark.parametrize(('effective', 'window', 'refused'), [
    # Хвостовой токен, которого в исходном окне не было: отказ.
    ('in[F6]', 'in[F6]a!', True),
    ('[AC]', '[AC]x', True),
    # Хвостовой токен с пробелом после него — тоже хвостовой.
    ('in[F6] ', 'in[F6]a!', True),
    # Токен был и остался хвостовым: отказ не нужен, обе стороны теряют его
    # одинаково, побайтовая проверка окна остаётся зелёной.
    ('[AC]', '[AC]', False),
    ('in[F6]a!', 'in[F6]a!', False),
    ('a[01][02]b', 'a[01][02]b', False),
    # Токен в середине — не хвостовой.
    ('in[F6]a!', 'in[F6]a!', False),
    ('[01]x', '[01]y', False),
    # Хвостовой токен совпал случайно, но в исходном хвост другой.
    ('[01]', '[01][02]', True),
    ('a[01][02]', 'a[01][02]x', True),
    # Вообще без токенов.
    ('hi', 'hi', False),
])
def test_ends_with_raw_token_predicate(effective, window, refused):
    assert TextInjector._ends_with_raw_token(effective, window) is refused


def test_refused_translation_is_not_written_and_reported():
    seg = {
        'name': 'toy', 'start': 16, 'end': 32,
        'decoder': _AsciiDecoder(), 'terminator': b'\x00',
        'terminators': [0x00], 'pad_byte': 0x00,
    }
    inj = _injector()
    # Окно `in[F6]a!` кодируется как есть; перевод обрезан до `in[F6]`.
    inj.rom.data[16:27] = b'in[F6]a!\x00' + bytes(4)
    inj.modified_data[16:27] = b'in[F6]a!\x00' + bytes(4)
    inj.original_data[16:27] = b'in[F6]a!\x00' + bytes(4)

    results = {'toy': [{'offset': 0, 'length': 8, 'text': 'in[F6]a!'}]}
    ok = inj.inject_translations(
        'toy', ['in[F6]'], _DummyPlugin(), segments=[seg], results=results)

    reasons = [r.get('reason') for r in (inj.last_affix_report or [])]
    assert 'trailing_raw_token' in reasons, inj.last_affix_report
    # Байты не тронуты: исходный текст на месте.
    assert bytes(inj.modified_data[16:24]) == b'in[F6]a!'
    assert ok is False


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
