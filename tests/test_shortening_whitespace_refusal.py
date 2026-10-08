"""Oracle: 92 записи теряются, потому что перевод — ОДИН пробел.

Измерено на `test_game/Legend of Zelda, The - Oracle of Seasons (USA).gbc`,
сегмент `oracle_seasons_dict`: было 1024 записи, стало 932. Все 92 — записи,
у которых `_shorten` дал единственный пробел (исходник короче 4 символов):

    ' the ' -> ' '   room=6   20 74 68 65 20 00 -> 20 00 00 00 00 00
    ' Ring' -> ' '   room=6   20 52 69 6e 67 00 -> 20 00 00 00 00 00

После записи окно содержит только пробел и нули, и ЭКСТРАКТОР отбрасывает
такую запись как junk. То есть инжектор записал ровно то, что попросили, но
запись исчезла из манифеста. Это НЕ порча байтов и НЕ молчаливый отказ: это
корректная запись бессмысленного перевода.

Почему инжектор не отказал: гейт пустого перевода в generic-пути есть
(`core/injector.py:624`), а в pointer-пути (`_inject_pointer_dialogues`) его
нет вовсе. Отмечу честно: `is_ignorable(' ')` = True, поэтому гейт на
`is_ignorable` пробелный перевод поймал бы — отсутствие гейта, а не
непригодность признака, и есть причина потери 92 записей.

Критерий: перевод, из которого не остаётся ни одного непробельного символа,
представить нельзя — писать нечего, и запись потеряется при обратном
извлечении. Такой перевод обязан ОТКАЗЫВАТЬСЯ с причиной `empty_translation`.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ORACLE_ROM = 'Legend of Zelda, The - Oracle of Seasons (USA).gbc'
GAME_DIR = ROOT / 'test_game'
SEG = 'oracle_seasons_dict'


def _rom() -> Path:
    path = GAME_DIR / ORACLE_ROM
    if not path.is_file():
        pytest.skip(f'нет ROM {ORACLE_ROM} в test_game/')
    return path


def _run_blank(rom: Path):
    """Переводит весь сегмент одиночным пробелом, возвращает (before, after)."""
    from core.extractor import TextExtractor
    from core.injector import TextInjector

    src = TextExtractor(str(rom))
    results = src.extract()
    plugin = src.plugin
    before = len(results.get(SEG) or [])

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / ('w' + rom.suffix)
        shutil.copy(rom, work)
        inj = TextInjector(str(work))
        segmeta = {s['name']: s for s in inj._get_segments(plugin)
                   if isinstance(s, dict)}
        meta = segmeta[SEG]
        values = [' ' for _ in (meta.get('manifest') or [])]
        inj.inject_translations(SEG, values, plugin)
        out = Path(td) / ('o' + rom.suffix)
        inj.save(str(out))
        after = len((TextExtractor(str(out)).extract()).get(SEG) or [])

    return before, after, meta


class TestRefusedRecordsRoundTripCleanly:
    """Отказанные записи обязаны читаться обратно РОВНО как были.

    После гейта census относит такие записи к `third_value_corrupted`
    (`after != expected`), хотя это ложная тревога: перевод намеренно не
    записан, поэтому в ROM лежит оригинал, и обратное извлечение обязано
    дать исходный текст. Если это так — дефект закрыт по-настоящему, и
    категория `third_value` должна исключать отказанные адреса, а не
    считать их порчей.
    """

    def test_refused_records_read_back_as_original(self):
        """Extract-only сегмент: ни одного байта не писается.

        Словарь Oracle of Seasons цитируется всеми
        текстовыми записями, поэтому `inject_segment`
        отказывает целиком сегмента, а не послойно
        слотом. Отсутствие — проверка, что все 1024
        записи читаются как оригинал.
        """
        rom = _rom()
        from core.extractor import TextExtractor
        from core.injector import TextInjector

        src = TextExtractor(str(rom))
        results = src.extract()
        plugin = src.plugin
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            meta = segmeta[SEG]
            values = [' ' for _ in (meta.get('manifest') or [])]
            ok = inj.inject_translations(SEG, values, plugin)
            out = Path(td) / ('o' + rom.suffix)
            inj.save(str(out))
            after = TextExtractor(str(out)).extract()

        assert ok is False, (
            'extract-only сегмент обязан отказать, но '
            f'inject_translations вернул True: {ok}')
        assert len(after.get(SEG) or []) == len(results[SEG]), (
            'число записей изменилось: '
            f"{len(results[SEG])} -> {len(after.get(SEG) or [])}")
        mismatches = [(a.get('target_addr'), a['text'], b['text'])
                      for a, b in zip(results[SEG], after.get(SEG) or [],
                                      strict=False)
                      if a['text'] != b['text']]
        assert not mismatches, (
            'отказ обязан записать, но байты '
            f'изменились у {len(mismatches)} записей: '
            f'{mismatches[:3]}')

    def test_blank_translation_is_refused(self):
        """Пустой перевод в общий словарь отказывается.

        Словарь Oracle of Seasons общий: все 1024 слота
        цитируются, сегмент extract-only. Отказ обязан
        целиком сегмента, и причина отказа
        попала в `last_affix_report` со своим именем, так
        что есть и в census, и в GUI.
        """
        rom = _rom()
        from core.extractor import TextExtractor
        from core.injector import TextInjector

        src = TextExtractor(str(rom))
        src.extract()
        plugin = src.plugin
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            meta = segmeta[SEG]
            values = [' ' for _ in (meta.get('manifest') or [])]
            ok = inj.inject_translations(SEG, values, plugin)
            reasons = {a.get('reason')
                       for a in (inj.last_affix_report or [])}

        assert meta.get('injectable') is False, (
            'сегмент словаря должен быть '
            'extract-only')
        assert meta.get('not_writable_reason') == 'shared_dictionary', (
            'причина отказа не зафиксирована: '
            f"{meta.get('not_writable_reason')}")
        assert ok is False, (
            'extract-only сегмент обязан отказать, но '
            f'inject_translations вернул True: {ok}')
        assert reasons == {'shared_dictionary'}, (
            'отказ extract-only должен попасть в отчёт '
            f'со своим именем, так чтобы его видели '
            f'и census, и GUI: {reasons}')

    def test_refusal_keeps_every_record(self):
        """После отказа записи остаются в манифесте — это и есть починка."""
        before, after, _ = _run_blank(_rom())
        assert after == before, (
            f'{SEG}: {before} -> {after}; после отказа записи не должны '
            'исчезать, иначе гейт не закрыл дефект')

    def test_refusal_leaves_bytes_intact(self):
        """Отказ не должен трогать байты."""
        rom = _rom()
        from core.extractor import TextExtractor
        from core.injector import TextInjector

        src = TextExtractor(str(rom))
        src.extract()
        plugin = src.plugin
        original = rom.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            meta = segmeta[SEG]
            values = [' ' for _ in (meta.get('manifest') or [])]
            inj.inject_translations(SEG, values, plugin)
            out = Path(td) / ('o' + rom.suffix)
            inj.save(str(out))
            patched = out.read_bytes()

        changed = sum(1 for a, b in zip(original, patched, strict=False)
                      if a != b)
        assert changed == 0, (
            f'отказ изменил {changed} байт — он обязан оставить ROM как есть')

    def test_blank_is_treated_as_ignorable(self):
        """`is_ignorable` — ДРУГОЙ критерий; гейт намеренно не на нём.

        Гейт `empty_translation` построен на `translation.strip()` плюс
        содержимое pristine-окна, а не на `is_ignorable`. Причина в том, что
        `' '` не всегда пустая запись: у игр с фиксированной сеткой пробел —
        значимый символ (WL4: пробел = байт `0xFF` = граница записи). Здесь
        фиксируем лишь факт, что оба значения считаются игнорируемыми, чтобы
        изменение поведения `is_ignorable` было замечено.
        """
        from core.decoder import is_raw_token_text_ignorable as is_ignorable

        assert is_ignorable(' ') is True
        assert is_ignorable('') is True

    def test_segment_uses_pointer_path(self):
        from core.extractor import TextExtractor
        from core.injector import TextInjector

        rom = _rom()
        src = TextExtractor(str(rom))
        src.extract()
        segmeta = {s['name']: s for s in
                   TextInjector(str(rom))._get_segments(src.plugin)
                   if isinstance(s, dict)}
        assert segmeta[SEG].get('kind') == 'pointer_dialogues', (
            'дефект зафиксирован на pointer-пути; если путь изменился, тест '
            'нужно пересмотреть')

    def test_blank_slot_of_romhack_stays_allowed(self):
        """Пустой слот в pristine ROM — легитимная запись, гейт молчит.

        ROM-хаки со сдвигом окон держат часть слотов пустыми, и
        `_align_translations_to_manifest` подставляет в них "". Отказ по
        причине `empty_translation` здесь был бы ложным: стирать нечего, и
        запись в манифесте не потеряется.
        """
        rom = _rom()
        from core.extractor import TextExtractor
        from core.injector import TextInjector

        src = TextExtractor(str(rom))
        src.extract()
        plugin = src.plugin
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            meta = segmeta[SEG]
            pad = meta.get('pad_byte')
            pad = pad if isinstance(pad, int) else 0
            # Пустым считаем слот из одних ПАДОВ — это подмножество того, что
            # считает пустым гейт (он учитывает ещё и терминаторы), поэтому
            # ассерт «гейт молчит» тут безопасен. Случай «пуст только по
            # терминаторам» (`FF FF`) этим ROM-тестом не покрыт — он держится
            # на синтетике в tests/test_pointer_empty_translation.py.
            data = rom.read_bytes()
            blank_slots = []
            for entry in meta.get('manifest') or []:
                addr = entry.get('target')
                room = entry.get('free_after')
                if not isinstance(addr, int) or not isinstance(room, int):
                    continue
                if not data[addr:addr + room].strip(bytes([pad])):
                    blank_slots.append(entry)
            if not blank_slots:
                pytest.skip('в этом ROM нет пустых слотов — сценарий не покрыт')
            values = ['' for _ in (meta.get('manifest') or [])]
            inj.inject_translations(SEG, values, plugin)
            reasons = [a.get('reason')
                       for a in (inj.last_affix_report or [])]
        assert 'empty_translation' not in reasons, (
            f'пустых слотов {len(blank_slots)}, гейт сработал — он не должен '
            'отказывать по слоту, который в pristine ROM уже пуст')
