"""Generic-путь: отказ пустого перевода должен попадать в last_affix_report.

Раньше отказ был молчаливым (core/injector.py, generic-ветка): запись
оставалась английской, переводчик не видел отказа, а census считал
расхождение порчей байтов. Семантика та же, что у `empty_translation`
в pointer-пути, поэтому причина переиспользуется.
"""
import tempfile
from pathlib import Path

from core.injector import TextInjector


class _Plugin:
    pass


def _run(meta, original_text, translation, skip_long=True):
    seg = dict(meta or {})
    seg.setdefault('name', 'seg')
    seg.setdefault('start', 0x1000)
    seg.setdefault('fixed_width', None)
    seg.setdefault('pad_byte', 0xFF)
    seg.setdefault('terminators', [0xFF])
    seg.setdefault('decoder', None)

    with tempfile.TemporaryDirectory() as td:
        rom = Path(td) / 'synthetic.gb'
        rom.write_bytes(b'\x00' * 0x4000)
        inj = TextInjector(str(rom))
        inj._get_segments = lambda pl: [seg]
        inj._extract_original_messages = lambda s: [
            {'offset': 0, 'length': len(original_text),
             'text': original_text}]
        ok = inj.inject_segment('seg', [translation], _Plugin(),
                                skip_long=skip_long)
        return ok, list(inj.last_affix_report)


def test_generic_blank_translation_reported():
    ok, report = _run({}, 'Library', '   ')
    assert ok is False
    assert len(report) == 1
    assert report[0]['reason'] == 'empty_translation'
    assert report[0]['offset'] == 0x1000
    assert report[0]['index'] == 0
    assert report[0]['room'] == len('Library')
    assert report[0]['length'] == 3
    # `original` — текст ИСХОДНОГО окна, а не перевода. Это ключ, по которому
    # read-back census опознаёт отказ: адрес инжектора байтовый, а адрес
    # экстрактора — один байт на символ (у Zelda с многобайтовыми токенами они
    # расходятся на несколько байт на запись), а индекс инжектора после
    # `_drop_junk_windows` перестаёт совпадать с позицией экстрактора.
    assert report[0]['original'] == 'Library'
    assert report[0]['text'] == '   '


def test_generic_blank_translation_reported_without_skip_long():
    """Ветка skip_long=False: отчёт виден, даже когда сегмент провален.

    Раньше эта ветка не была покрыта ни одним тестом, поэтому контракт
    «отказ виден переводчику даже при провале всего сегмента» держался
    только на словах.
    """
    ok, report = _run({}, 'Library', '   ', skip_long=False)
    assert ok is False
    assert [r['reason'] for r in report] == ['empty_translation']


def test_generic_empty_translation_reported():
    ok, report = _run({}, 'Library', '')
    assert ok is False
    assert report[0]['reason'] == 'empty_translation'


def test_generic_real_translation_not_reported():
    _, report = _run({}, 'Library', 'Lib')
    assert [r for r in report if r['reason'] == 'empty_translation'] == []


def test_generic_original_blank_allows_blank():
    """Пустой оригинал — не отказ: там пустота законна."""
    _, report = _run({}, '    ', '   ')
    assert [r for r in report if r['reason'] == 'empty_translation'] == []


def test_fixed_slot_blank_translation_is_legacy_allowed():
    """Инвариант: fixed-слот НЕ отказывает пустому переводу.

    Гейт защищён `not is_fixed` намеренно: blank фиксированного слота —
    легаси-семантика (WL4, Pokémon names/attacks). Если следующий рефакторинг
    расширит гейт на fixed-слоты, эти записи молча останутся английскими;
    тест роняет сборку до того, как это случится.
    """
    _, report = _run({'fixed_width': 8}, 'Library', '   ')
    assert [r for r in report if r['reason'] == 'empty_translation'] == []


def test_report_resets_between_segments():
    with tempfile.TemporaryDirectory() as td:
        rom = Path(td) / 'synthetic.gb'
        rom.write_bytes(b'\x00' * 0x4000)
        inj = TextInjector(str(rom))
        seg = {'name': 'seg', 'start': 0x1000, 'fixed_width': None,
               'pad_byte': 0xFF, 'terminators': [0xFF], 'decoder': None}
        inj._get_segments = lambda pl: [seg]
        inj._extract_original_messages = lambda s: [
            {'offset': 0, 'length': 3, 'text': 'abc'}]
        inj.last_affix_report = [{'reason': 'stale'}]
        inj.inject_segment('seg', ['xyz'], _Plugin(), skip_long=True)
        assert [r for r in inj.last_affix_report
                if r['reason'] == 'stale'] == []


def _record_injector():
    """Инжектор для проверки сброса отчёта на record-путях."""
    tmp = tempfile.TemporaryDirectory()
    rom = Path(tmp.name) / 'synthetic.gb'
    rom.write_bytes(b'\x00' * 0x4000)
    inj = TextInjector(str(rom))
    return tmp, inj


class _RecordPlugin:
    def get_pointer_table_meta(self):
        return None

    def get_text_segments(self, rom):
        return []


def test_language_block_resets_affix_report():
    """`inject_language_block` обязан сбрасывает
    `last_affix_report` нарегу вместе отказа предыдущего
    сегмента: сценарий отчёт относится к
    текущему сегменту, а это — ложный отказ.
    """
    tmp, inj = _record_injector()
    try:
        inj.last_affix_report = [{'reason': 'stale', 'index': 7}]
        inj.inject_language_block('seg', ['x'], _RecordPlugin())
        assert [r for r in inj.last_affix_report
                if r.get('reason') == 'stale'] == []
    finally:
        tmp.cleanup()


def test_interleaved_language_resets_affix_report():
    """То же для `inject_interleaved_language`."""
    tmp, inj = _record_injector()
    try:
        inj.last_affix_report = [{'reason': 'stale', 'index': 7}]
        inj.inject_interleaved_language('seg', ['x'], _RecordPlugin())
        assert [r for r in inj.last_affix_report
                if r.get('reason') == 'stale'] == []
    finally:
        tmp.cleanup()
