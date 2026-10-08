"""Хвост fixed-слота при сокращении перевода: pad_byte против старых байтов.

Дефект (WL4): слот фиксированной ширины добивался СТАРЫМИ байтами исходной
записи, поэтому `Entry Passage` → `Entr` извлекалось обратно как
`Entr  Passage` — длина сходилась, и round-trip это не ловил. Теперь хвост
заполняется `pad_byte`, и как есть сохраняется только под `has_mid_alias`,
где хвост действительно является второй записью (на неё смотрит чужой
указатель).

Тест синтетический и не требует ROM: ROM-регрессия живёт в
`tests/test_realrom_pipeline.py::test_shortened_text_roundtrip`, но там весь
прогон помечен `rom_required` и в CI без `test_game/` пропускается — ветка
прод-кода оставалась непокрытой.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector

BASE = 0x40
WIDTH = 14
END = BASE + WIDTH
SLOT = b'Entry Passage\xff'


class _SlotDecoder:
    """Декодер как у WL4: 0xFF — граница записи, дальше не читается."""

    def decode(self, data, start, length):
        chunk = bytes(data[start:start + length])
        return chunk.split(b'\xff')[0].decode('ascii', 'replace')

    def encode(self, text):
        # 0xFF — и пробел, и терминатор: хвостовой пробел кодируется как
        # конец строки, и 'So ' физически не читается обратно.
        return bytes(0xFF if ch == ' ' else ord(ch) for ch in text)


class _TruncatingDecoder:
    """Декодер, который всегда срезает хвост — граница записи на 0x00."""

    def decode(self, data, start, length):
        chunk = bytes(data[start:start + length])
        return chunk.split(b'\x00')[0].decode('ascii', 'replace')

    def encode(self, text):
        return text.encode('ascii')


class _ShortDecoder:
    """Декодер с сигнатурой `decode(data)` — второй вызываемый вариант."""

    def decode(self, data):
        return bytes(data).split(b'\xff')[0].decode('ascii', 'replace')

    def encode(self, text):
        return text.encode('ascii')


class _RaisingDecoder:
    def decode(self, data, start, length):
        return ''

    def encode(self, text):
        raise ValueError('нечем кодировать')


def _plugin(segments):
    class P:
        def get_text_segments(self, rom):
            return segments

    return P()


class _NonStoppingDecoder:
    """Декодер, который НЕ обрывается на паде — как реальный WL4.

    `_SlotDecoder` обрывает чтение на `0xFF` сам, поэтому для него rstrip в
    гейте нерелевантен, и на нём нельзя проверить, что гейт использует
    НОРМИРОВАННЫЙ `pad_byte`. Здесь `0xFF` читается как `?`, то есть
    единственный способ увидеть срез — он сам.
    """

    def decode(self, data, start, length):
        chunk = bytes(data[start:start + length])
        return chunk.replace(b'\xff', b'?').decode('ascii', 'replace')

    def encode(self, text):
        return bytes(0xFF if ch == ' ' else ord(ch) for ch in text)


def _segment(*, pad_byte=0xFF, has_mid_alias=False,
             decoder=None) -> dict:
    return {
        'name': 'slot',
        'kind': 'record',
        'start': BASE,
        'end': END,
        'fixed_width': WIDTH,
        'pad_byte': pad_byte,
        'terminators': [],
        'decoder': decoder if decoder is not None else _SlotDecoder(),
        'has_mid_alias': has_mid_alias,
    }


def _injector(seg: dict) -> TextInjector:
    inj = TextInjector.__new__(TextInjector)

    class _FakeROM:
        def __init__(self, data):
            self.data = bytearray(data)

    inj.rom = _FakeROM(bytearray(0x200))
    inj.original_data = bytearray(0x200)
    inj.modified_data = bytearray(0x200)
    inj._segment_cache = {}
    inj._bank_segments = []
    inj._taken_free_blocks = []
    inj._written_spans = []
    inj.logger = logging.getLogger('test')
    for attr in ('last_overflow_report', 'last_relocate_report',
                 'last_overlap_report', 'last_spellcheck_report',
                 'last_fit_report', 'last_unmapped_chars',
                 'last_affix_report', 'last_mid_alias_report',
                 'last_align_report'):
        setattr(inj, attr, [] if attr != 'last_align_report' else {})
    inj.rom.data[BASE:END] = SLOT
    inj.original_data[BASE:END] = SLOT
    inj.modified_data[BASE:END] = SLOT
    return inj


def _inject(seg: dict, translation: str) -> TextInjector:
    inj = _injector(seg)
    assert inj.inject_segment('slot', [translation], _plugin([seg]),
                              segments=[seg]) is True
    return inj


def test_short_translation_pads_tail_with_pad_byte():
    """Хвост слота — pad_byte, а не остатки исходной записи."""
    inj = _inject(_segment(), 'Entr')
    window = bytes(inj.modified_data[BASE:END])
    assert window == b'Entr' + b'\xff' * (WIDTH - 4)
    # Старые байты 'Passage' не должны выживать в хвосте.
    assert b'Passage' not in window


def test_mid_alias_keeps_original_tail():
    """Под has_mid_alias хвост — чужая запись, её сохраняем как есть."""
    inj = _inject(_segment(has_mid_alias=True), 'Entr')
    window = bytes(inj.modified_data[BASE:END])
    assert window == b'Entr\xff Passage\xff'
    assert len(window) == WIDTH


def test_tail_boundary_one_byte_short():
    """Перевод ровно на байт короче слота: после EOS остаётся один pad."""
    inj = _inject(_segment(), 'X' * (WIDTH - 1))
    window = bytes(inj.modified_data[BASE:END])
    assert window == b'X' * (WIDTH - 1) + b'\xff'
    assert len(window) == WIDTH


def test_slot_wide_translation_is_refused():
    """Перевод ровно по ширине слота отвергается: последний байт — терминатор.

    `max_length` по умолчанию `width - 1`, поэтому доступная длина перевода на
    байт меньше слота. Это ограничение задокументировано, а не побочный эффект
    новой ветки, — но именно оно делает `width - 1` настоящей границей.
    """
    seg = _segment()
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['Y' * WIDTH], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT


def test_out_of_range_pad_byte_falls_back():
    """pad_byte вне 0..255 — молчаливый откат на дефолт, не исключение."""
    inj = _inject(_segment(pad_byte=0x100), 'Entr')
    window = bytes(inj.modified_data[BASE:END])
    assert window == b'Entr' + b'\xff' * (WIDTH - 4)


def test_trailing_space_translation_is_refused():
    """Перевод, обрезаемый при чтении, НЕ пишется (WL4: пробел = 0xFF).

    Запись прошла бы успешно, а в игре показала бы `So` вместо `So ` —
    расхождение увидел бы только переводчик. Отказ виден в отчёте.
    """
    seg = _segment()
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['So '], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT
    assert len(inj.last_affix_report) == 1
    report = inj.last_affix_report[0]
    assert report['reason'] == 'trailing_truncated'
    assert report['read_back'] == 2


def test_substituted_char_is_not_refused():
    """Замена символа на ближайший — не обрезка: отказа быть не должно.

    Критерий смотрит на ПРЕФИКС и на УКОРОЧЕНИЕ. Подстановка неотображаемого
    символа длину не меняет, поэтому под отказ не попадает: это принципиально
    разный дефект, и лечится он не здесь.

    ВАЖНО, чего этот тест НЕ утверждает: что подстановку сообщает
    `last_unmapped_chars`. У `PokemonFixedTextDecoder` и `Gen1FixedDecoder`
    (plugins/gba_pokemon.py, plugins/gb_pokemon_gen1.py) при `strict=False`
    неотображаемый символ молча заменяется пробелом, а атрибута
    `last_unmapped_chars` у них нет вообще — то есть по факту такой перевод
    пишется в слот пустыми и НИКАК не сообщается. Это открытый долг, см.
    ROADMAP. Тест фиксирует узость критерия, а не исправность отчётности.
    """
    class _SubstitutingDecoder:
        def decode(self, data, start, length):
            chunk = bytes(data[start:start + length])
            return chunk.split(b'\xff')[0].decode('ascii', 'replace')

        def encode(self, text):
            return text.replace('Z', 'Q').encode('ascii')

    seg = _segment(decoder=_SubstitutingDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['Zebra'], _plugin([seg]),
                              segments=[seg]) is True
    assert inj.last_affix_report == []


def test_nontruncating_decoder_signature_is_supported():
    """Декодер с сигнатурой decode(data) тоже проверяется, а не падает."""
    seg = _segment(decoder=_ShortDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['So '], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT


def test_raising_encoder_does_not_crash_gate():
    """Энкодер бросает исключение — это уже отказ по кодированию, не падение."""
    seg = _segment(decoder=_RaisingDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT


def test_truncation_check_skipped_when_read_back_is_longer():
    """Декодер, развернувший символ в токен, не должен ронять перевод."""
    class _ExpandingDecoder:
        def decode(self, data, start, length):
            return bytes(data[start:start + length]).hex().upper()

        def encode(self, text):
            return text.encode('ascii')

    seg = _segment(decoder=_ExpandingDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['AB'], _plugin([seg]),
                              segments=[seg]) is True
    assert inj.last_affix_report == []


def test_zero_boundary_decoder_is_not_refused():
    """Граница 0x00 вместо 0xFF: гейт проверяется и не срабатывает зря."""
    seg = _segment(pad_byte=0x00, decoder=_TruncatingDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['So'], _plugin([seg]),
                              segments=[seg]) is True
    assert inj.last_affix_report == []


def test_all_padding_translation_has_own_reason():
    """Перевод, целиком съеденный падом, — не «обрезанный хвост».

    Отказ верный по сути (слот стал бы пустым, и запись выпала бы из
    манифеста), но `trailing_truncated` с `written=0` вводит в заблуждение:
    обрезать нечего. Поэтому у него своя причина.
    """
    seg = _segment()
    inj = _injector(seg)
    assert inj.inject_segment('slot', [' '], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT
    assert len(inj.last_affix_report) == 1
    assert inj.last_affix_report[0]['reason'] == 'all_padding'


def test_gate_uses_normalized_pad_byte():
    """Битой pad_byte в гейте и в записи обязан давать ОДНО значение.

    Раньше гейт брал сырое `segment.get('pad_byte')` (None при отсутствии
    ключа) и молча не срезал хвост, а запись падила уже по нормализованному —
    исходный WL4-дефект проскакивал бы на таких сегментах. Декодер здесь
    НЕ обрывается на паде: без среза хвоста `So ` прочитался бы как `So?`
    той же длины, отказа бы не было, и тест был бы зелёным на неверном коде.
    """
    seg = _segment(pad_byte=0x100, decoder=_NonStoppingDecoder())
    inj = _injector(seg)
    assert inj.inject_segment('slot', ['So '], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data[BASE:END]) == SLOT
    assert inj.last_affix_report[0]['reason'] == 'trailing_truncated'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
