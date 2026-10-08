"""Отчёт о записях, оставленных оригиналом: ни одна причина не теряется.

Сбор вынесен в `GBTextExtractorGUI._collect_overflow_report`, потому что
`_show_overflow_report` создаёт диалог, а проверять надо именно состав отчёта.
Смысл теста: отказ инжектора, который не дошёл до переводчика, — это ровно тот
дефект, ради которого отказ и вводился. Инжектор пишет причину в
`last_affix_report`, но если GUI её не показывает, переводчик видит «принято»,
а в игре — оригинал.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gui.main_window import GBTextExtractorGUI


class _I18n:
    """Реальные английские шаблоны из `locales/en/messages.json`.

    Не заглушка: если ключа нет, будет KeyError — и тест упадёт. Именно этим
    был плох исходный баг (новая причина отказа без строки в локали), плюс
    `.format(**fields)` проверит, что набор плейсхолдеров совпадает с тем, что
    передаёт GUI.
    """

    def __init__(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'locales', 'en', 'messages.json'),
                  encoding='utf-8') as fh:
            self._messages = json.load(fh)

    def t(self, key, *args, **kwargs):
        template = self._messages[key]
        # Настоящий i18n форматирует шаблон сам, когда есть kwargs; здесь
        # форматирование делает вызывающий код, поэтому повторяем это поведение
        # для ключей, которые передают параметры (`inject.overflow.line*`).
        if kwargs:
            return template.format(**kwargs)
        return template


class _Injector:
    def __init__(self, **reports):
        self.last_overflow_report = reports.get('overflow', [])
        self.last_overlap_report = reports.get('overlap', [])
        self.last_mid_alias_report = reports.get('mid_alias', [])
        self.last_affix_report = reports.get('affix', [])


def _gui(reports) -> GBTextExtractorGUI:
    gui = GBTextExtractorGUI.__new__(GBTextExtractorGUI)
    gui.i18n = _I18n()
    gui.text_injector = _Injector(**reports)
    return gui


@pytest.mark.parametrize('reason,marker', [
    ('trailing_raw_token', 'raw token'),
    ('trailing_truncated', 'shorter than written'),
    ('all_padding', 'nothing in the translation can be read back'),
    ('empty_translation', 'no non-space characters'),
])
def test_every_affix_reason_reaches_the_report(reason: str, marker: str) -> None:
    gui = _gui({'affix': [{'segment': 'seg', 'offset': 64, 'room': 13,
                           'reason': reason, 'written': 4, 'chars': 3,
                           'read_back': 2}]})
    report = gui._collect_overflow_report()
    assert len(report) == 1
    assert report[0]['target'] == 64
    assert report[0]['free_after'] == 13
    assert 'seg' in report[0]['text']
    assert marker in report[0]['text']


def test_truncated_reason_counts_are_characters() -> None:
    """В сообщении — СИМВОЛЫ, а не байты.

    `written` в отчёте инжектора это len(trans_bytes), то есть байты, и на
    двухбайтовой charmap (SJIS, Pokemon PK/MN) «2 of 3 characters» было бы
    ложью. Поэтому шаблон получает `chars` = len(перевода).
    """
    gui = _gui({'affix': [{'segment': 'wl4_so_sleepy', 'offset': 1, 'room': 9,
                           'reason': 'trailing_truncated',
                           'written': 9, 'chars': 3, 'read_back': 2}]})
    text = gui._collect_overflow_report()[0]['text']
    assert 'wl4_so_sleepy' in text
    assert '2 of 3 characters survive' in text
    assert '9' not in text.replace('wl4_so_sleepy', '')


def test_unknown_affix_reason_falls_back_with_slug() -> None:
    """Неизвестная причина показывается нейтрально, но reason не теряется.

    Раньше строка отбрасывалась целиком, и отчёт молчал — ровно тот дефект,
    который здесь чинится. Теперь slug попадает в текст как диагностика.
    """
    gui = _gui({'affix': [{'segment': 'seg', 'offset': 1, 'room': 2,
                           'reason': 'что-то новое'}]})
    report = gui._collect_overflow_report()
    assert len(report) == 1
    assert 'что-то новое' in report[0]['text']
    assert 'seg' in report[0]['text']
    assert report[0]['kind'] == 'reason'


def test_non_dict_entries_are_ignored() -> None:
    gui = _gui({'affix': ['мусор', None, 42],
                'overlap': ['мусор'],
                'mid_alias': [None]})
    assert gui._collect_overflow_report() == []


def test_non_int_counts_fall_back_to_zero() -> None:
    gui = _gui({'affix': [{'segment': 'seg', 'offset': 'x', 'room': None,
                           'reason': 'trailing_truncated',
                           'written': 'y', 'chars': None,
                           'read_back': None}]})
    report = gui._collect_overflow_report()
    assert report[0]['target'] == 0
    assert report[0]['free_after'] == 0
    assert '0 of 0 characters survive' in report[0]['text']


def test_reason_rows_use_their_own_line_template() -> None:
    """Строка-причина не должна утверждать про длину.

    Общий шаблон даёт «needs N bytes, M available»; для отказа это ложь (не
    записано не из-за длины, а потому что перевод непредставим), и `need=0`
    читался бы как «проблема не в размере». Кнопка Copy уносит такую строку
    в баг-трекер, поэтому проверяется именно рендер, а не только сбор.
    """
    gui = _gui({'affix': [{'segment': 'seg', 'offset': 0xB4A2, 'room': 9,
                           'reason': 'trailing_truncated',
                           'written': 3, 'chars': 3, 'read_back': 2}]})
    report = gui._collect_overflow_report()
    line = gui._overflow_report_lines(report)[0]
    assert 'bytes' not in line
    assert '0xB4A2' in line
    assert 'seg' in line


def test_all_report_sources_are_merged() -> None:
    gui = _gui({
        'overflow': [{'target': 1, 'text': 'overflow row'}],
        'overlap': [{'offset': 2, 'length': 3, 'room': 4, 'segment': 'o'}],
        'mid_alias': [{'offset': 5, 'room': 6, 'written': 7, 'segment': 'm'}],
        'affix': [{'segment': 'a', 'offset': 8, 'room': 9,
                   'reason': 'trailing_truncated', 'written': 1,
                   'read_back': 0}],
    })
    report = gui._collect_overflow_report()
    assert [row['target'] for row in report] == [1, 2, 5, 8]
    assert 'another pointer' in report[2]['text']
    assert 'shorter than written' in report[3]['text']
    # Строки-причины несут свой kind, переполнение — нет.
    assert 'kind' in report[2] and 'kind' in report[3]
    assert 'kind' not in report[1]


def test_empty_injector_yields_empty_report() -> None:
    assert _gui({})._collect_overflow_report() == []


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
