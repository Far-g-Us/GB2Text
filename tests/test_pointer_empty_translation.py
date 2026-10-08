"""Синтетический тест гейта `empty_translation` в pointer-пути.

ROM не требуется: собираем фиктивный сегмент `pointer_dialogues` с манифестом
и декодером, как у Pokemon GBA / Oracle of Seasons, и проверяем контракт гейта:

* перевод без непробельных символов ОТКАЗЫВАЕТСЯ с причиной
  `empty_translation` и НЕ трогает байты;
* отказ виден в `last_affix_report`, поэтому переводчик увидит причину, а не
  решит, что перевод просто не применился;
* слот, пустой ещё в pristine ROM, отказом НЕ считается — у ROM-хаков со
  сдвигом окон это легитимная запись (`_align_translations_to_manifest`
  подставляет туда `""`);
* обычный перевод, который влезает, пишется как раньше.

ROM-gated проверка того же дефекта на реальном Oracle of Seasons — в
`tests/test_shortening_whitespace_refusal.py`.
"""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = 0x200
SLOT = 8
ORIGINAL = b'ORIGINL'


def _decoder():
    from core.decoder import CharMapDecoder

    charmap = {0x00: '\x00', 0xFF: '\x00'}
    for i in range(0x20, 0x7F):
        charmap[i] = chr(i)
    return CharMapDecoder(charmap)


class _Harness:
    """Инжектор поверх буфера в памяти — без файловой системы и ROM."""

    def __init__(self, slots: int, originals: list[bytes] | None = None):
        from core.injector import TextInjector

        buf = bytearray(b'\x00' * 0x1000)
        manifest = []
        for i in range(slots):
            start = BASE + i * SLOT
            if originals is None:
                buf[start:start + len(ORIGINAL)] = ORIGINAL
            else:
                buf[start:start + len(originals[i])] = originals[i]
            manifest.append({'target': start, 'free_after': SLOT,
                             'slots': []})

        impl = TextInjector.__new__(TextInjector)
        impl.rom = type('R', (), {'data': bytes(buf)})()
        impl.modified_data = bytearray(buf)
        impl.logger = logging.getLogger('syn')
        impl.last_affix_report = []
        impl.last_overflow_report = []
        impl.last_overlap_report = []
        impl.last_relocate_report = []
        impl._tracked_spans_inst = []
        impl._free_starts_cache = None

        self.impl = impl
        self.manifest = manifest
        self.segment = {
            'name': 'syn_dialog',
            'kind': 'pointer_dialogues',
            'start': BASE,
            'end': BASE + slots * SLOT,
            'decoder': _decoder(),
            'compression': None,
            'terminators': [0x00, 0xFF],
            'manifest': manifest,
            'terminator': b'\x00\xff',
        }

    def inject(self, translations: list[str]) -> bool:
        return bool(self.impl._inject_pointer_dialogues(
            self.segment, translations, skip_long=True))

    @property
    def offsets(self) -> list:
        return [a.get('offset') for a in (self.impl.last_affix_report or [])]

    @property
    def reasons(self) -> list:
        return [a.get('reason') for a in (self.impl.last_affix_report or [])]

    def window(self, index: int) -> bytes:
        start = BASE + index * SLOT
        return bytes(self.impl.modified_data[start:start + SLOT])


class TestEmptyTranslationGatePointerPath:
    """Контракт гейта в pointer-пути."""

    def test_blank_refused_with_reason(self):
        h = _Harness(1)
        assert h.inject([' ']) is False
        assert h.reasons == ['empty_translation']

    def test_empty_string_refused(self):
        h = _Harness(1)
        assert h.inject(['']) is False
        assert h.reasons == ['empty_translation']

    def test_refusal_leaves_bytes(self):
        h = _Harness(1)
        before = h.window(0)
        h.inject([' '])
        assert h.window(0) == before

    def test_mixed_batch_refuses_only_blank(self):
        """В пакете отказывается ТОЛЬКО пустой слот; остальные пишутся.

        `skip_long=True` понижает отказ до пропуска записи — это штатная
        семантика гейта, аналогичная `trailing_raw_token`. Поэтому проверяем
        отчёт и содержимое соседних окон, а не возвращаемое значение.
        """
        h = _Harness(3)
        h.inject(['Hello', '  ', 'World'])
        assert h.offsets == [BASE + SLOT], (
            f'отказан только пустой слот, получено {h.offsets}')
        assert h.window(1).startswith(ORIGINAL), (
            f'окно отказанного слота должно остаться оригиналом, '
            f'получено {h.window(1)!r}')
        assert h.window(0).startswith(b'Hello'), 'соседний перевод записан'
        assert h.window(2).startswith(b'World'), 'соседний перевод записан'

    def test_skip_long_false_fails_whole_segment(self):
        """Без `skip_long` отказ на пустом переводе валит сегмент целиком."""
        h = _Harness(3)
        ok = bool(h.impl._inject_pointer_dialogues(
            h.segment, ['Hello', '  ', 'World'], skip_long=False))
        assert ok is False, 'skip_long=False обязан провалить сегмент'
        assert h.window(0).startswith(ORIGINAL), (
            'откат сегмента обязан вернуть и соседние записи: '
            f'{h.window(0)!r}')

    def test_terminator_only_slot_is_empty(self):
        """Слот из одних 0xFF пуст: стирать нечего, гейт молчит.

        У pointer-сегментов хвост заполнен терминаторами, а не падом, поэтому
        проверка «только пад» сочла бы такой слот непустым и отказала бы
        напрасно.
        """
        h = _Harness(1, originals=[b'\xff' * SLOT])
        h.inject([' '])
        assert 'empty_translation' not in h.reasons

    def test_slot_with_text_after_terminators_is_not_empty(self):
        """Но слот с настоящим текстом ДОЛЖЕН давать отказ."""
        h = _Harness(1, originals=[b'AB\xff\xff\xff\xff\xff\xff'])
        h.inject([' '])
        assert 'empty_translation' in h.reasons

    def test_blank_slot_of_romhack_allowed(self):
        """Пустой слот в pristine ROM — легитимная запись, гейт молчит."""
        h = _Harness(1, originals=[b''])
        assert h.reasons == []
        h.impl.last_affix_report = []
        h.inject(['  '])
        assert 'empty_translation' not in h.reasons, (
            'слот был пуст и до перевода — стирать нечего, отказ ложный')

    def test_non_blank_translation_still_writes(self):
        h = _Harness(1)
        h.inject(['Hi'])
        assert 'empty_translation' not in h.reasons
        assert h.window(0).startswith(b'Hi'), (
            f'обычный перевод обязан записаться, в окне {h.window(0)!r}')

    def test_report_carries_offset_and_room(self):
        """Отчёт обязан нести адрес и размер — по ним GUI строит строку."""
        h = _Harness(2)
        h.inject([' ', ' '])
        assert h.offsets == [BASE, BASE + SLOT]
        for item in (h.impl.last_affix_report or []):
            assert item.get('room') == SLOT
            assert item.get('segment') == 'syn_dialog'
