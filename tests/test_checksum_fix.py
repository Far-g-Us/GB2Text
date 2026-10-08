"""CRC/checksum fixer: проверка и починка ROM, битых сторонним hex-редактором.

Инжектор пересчитывает checksum'ы сам, но ручная правка — типичный сценарий
хакерства, и после неё загрузчик/эмулятор отвергает ROM. Модуль чинит заголовок
и (для GB/GBC) глобальную сумму, ничего не зная о содержимом.

Ключевые решения, зафиксированные тестами:
- у GBA ROM глобальной суммы НЕТ: 0x14E-0x14F лежат значения из внутреннего
  регистра, и их проверка объявляла бы битой любую коммерческую GBA ROM;
- резервные 0x0BE-0x0BF формально обязаны быть 0x0000, но на реальной ROM
  (`Moemon Fire Red ruRevival`) там 0x3C/0x2A при рабочем complement — значит
  их не проверяем и не затираем;
- починка атомарна и не пишет файл, когда чинить нечего (mtime не меняется).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.checksum_fix import FixError, inspect, repair
from core.rom import GameBoyROM


def _header_ok(path: str) -> bool:
    return GameBoyROM(path).validate_header()


def _calc(blob: bytearray) -> int:
    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - blob[addr] - 1) & 0xFF
    return checksum


def _gb(size: int = 0x400) -> bytearray:
    """ROM с ОБОИМИ корректными checksum'ами.

    Глобальная сумма — сумма всех байт, поэтому её нельзя вычислить до записи
    в 0x14E-0x14F: сначала ставим заголовок, потом сумму, и она уже не меняет
    саму себя (эти два байта из суммы исключены).
    """
    blob = bytearray(size)
    blob[0x014D] = _calc(blob)
    total = sum(blob) & 0xFFFF
    blob[0x014E] = (total >> 8) & 0xFF
    blob[0x014F] = total & 0xFF
    return blob


def test_clean_rom_is_valid(tmp_path: Path) -> None:
    rom = tmp_path / 'clean.gb'
    rom.write_bytes(bytes(_gb(0x200)))
    report = inspect(rom)
    assert report.valid is True
    assert report.wrong_offsets == []
    assert report.system == 'gb'


def test_broken_header_detected_and_repaired(tmp_path: Path) -> None:
    blob = _gb(0x200)
    rom = tmp_path / 'broken.gb'
    rom.write_bytes(bytes(blob))
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is False
    fixed = repair(rom)
    assert fixed.valid is True
    assert fixed.wrong_offsets == []
    assert _header_ok(str(rom)) is True


def test_broken_global_checksum_detected_and_repaired(tmp_path: Path) -> None:
    """Глобальная сумма ловится по СОДЕРЖИМОМУ, а не только по заголовку.

    Правка байта в середине ROM не меняет header-checksum, но меняет сумму
    всех байт — а именно на это ругается загрузчик.
    """
    blob = _gb(0x400)
    rom = tmp_path / 'global.gb'
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is True
    blob[0x0200] ^= 0xFF
    rom.write_bytes(bytes(blob))
    broken = inspect(rom)
    assert broken.valid is False
    assert broken.global_ok is False
    assert repair(rom).valid is True


def test_gba_complement_detected_and_repaired(tmp_path: Path) -> None:
    blob = bytearray(0x200)
    blob[0x0BD] = (0 - sum(blob[0x0A0:0x0BD]) - 0x19) & 0xFF
    rom = tmp_path / 'a.gba'
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is True
    blob[0x0BD] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is False
    assert repair(rom).valid is True


def test_gba_has_no_global_checksum_check(tmp_path: Path) -> None:
    """0x14E-0x14F у GBA — не глобальная сумма; их мусор не считается полом.

    Раньше проверка суммы байт файла объявляла битой каждую коммерческую GBA
    ROM, потому что там по 0x14E-0x14F лежит значение из внутреннего регистра.
    """
    blob = bytearray(0x200)
    blob[0x0BD] = (0 - sum(blob[0x0A0:0x0BD]) - 0x19) & 0xFF
    blob[0x014E] = 0xDE
    blob[0x014F] = 0xAD
    rom = tmp_path / 'b.gba'
    rom.write_bytes(bytes(blob))
    report = inspect(rom)
    assert report.valid is True
    assert report.global_ok is True


def test_gba_reserved_bytes_preserved(tmp_path: Path) -> None:
    """Резервные 0x0BE-0x0BF не проверяются и не затираются починкой.

    На реальной ROM (`Moemon Fire Red ruRevival`) там 0x3C/0x2A при рабочем
    complement, и `recalculate_checksums` их обнуляет. Починка checksum'ов не
    должна затирать эти данные молча.
    """
    blob = bytearray(0x200)
    blob[0x0BE] = 0x3C
    blob[0x0BF] = 0x2A
    blob[0x0BD] = (0 - sum(blob[0x0A0:0x0BD]) - 0x19) & 0xFF
    rom = tmp_path / 'hack.gba'
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is True
    blob[0x0BD] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert repair(rom).valid is True
    assert rom.read_bytes()[0x0BE] == 0x3C
    assert rom.read_bytes()[0x0BF] == 0x2A


def test_repair_is_noop_when_valid(tmp_path: Path) -> None:
    rom = tmp_path / 'ok.gb'
    rom.write_bytes(bytes(_gb(0x200)))
    before = rom.stat().st_mtime_ns
    report = repair(rom)
    assert report.valid is True
    assert rom.stat().st_mtime_ns == before


def test_repair_restores_file_byte_for_byte(tmp_path: Path) -> None:
    """Починка возвращает файл к исходному побайтово, а не «почти правильному».

    Проверка на «изменились только байты checksum'ов» была бы слабее и
    неверна: глобальная сумма включает 0x14D, поэтому порча заголовка тянет за
    собой и её. После починки оба восстанавливаются, и весь остальной файл
    обязан совпасть с исходным побайтово — это и есть гарантия «починил
    checksum, содержимое не тронул».
    """
    blob = _gb(0x400)
    rom = tmp_path / 'only.gb'
    rom.write_bytes(bytes(blob))
    original = bytes(blob)
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert repair(rom).valid is True
    assert rom.read_bytes() == original


def test_repair_touches_nothing_outside_checksum_fields(tmp_path: Path) -> None:
    """Порча заголовка чинится в 0x14D и 0x14E-0x14F, больше нигде."""
    blob = _gb(0x400)
    rom = tmp_path / 'scope.gb'
    rom.write_bytes(bytes(blob))
    original = bytes(blob)
    blob[0x0135] ^= 0x01          # байт заголовка, участвующий в 0x14D
    rom.write_bytes(bytes(blob))
    assert repair(rom).valid is True
    after = rom.read_bytes()
    assert after[0x0135] != original[0x0135]      # содержимое не «чинится»
    assert _calc(after) == after[0x014D]           # заголовок сходится заново
    assert (after[0x014E] << 8 | after[0x014F]) == \
        (sum(after) - after[0x014E] - after[0x014F]) & 0xFFFF
    # 0x135 — это тот самый порченный байт: его «чинить» нельзя, он не checksum.
    outside = [i for i in range(len(original))
               if original[i] != after[i]
               and i not in (0x0135, 0x014D, 0x014E, 0x014F)]
    assert outside == []


def test_missing_file_raises_fix_error(tmp_path: Path) -> None:
    try:
        inspect(tmp_path / 'нет.gb')
    except FixError as exc:
        assert 'нечитаемый' in str(exc)
    else:
        raise AssertionError('ожидался FixError')


def test_tiny_file_raises_fix_error(tmp_path: Path) -> None:
    rom = tmp_path / 'tiny.gb'
    rom.write_bytes(bytes(16))
    try:
        inspect(rom)
    except FixError as exc:
        assert 'слишком мал' in str(exc)
    else:
        raise AssertionError('ожидался FixError')


def test_temp_file_is_cleaned_after_success(tmp_path: Path) -> None:
    rom = tmp_path / 'ro.gb'
    blob = _gb(0x200)
    rom.write_bytes(bytes(blob))
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    repair(rom)
    assert not list(tmp_path.glob('*.chksum.tmp'))
    assert not list(tmp_path.glob('*.tmp'))


def test_failed_write_leaves_no_tmp_and_rom_intact(tmp_path, monkeypatch) -> None:
    """Исключение записи: tmp удаляется, исходный ROM не тронут.

    Раньше тест с этим названием звал `repair()` на УСПЕШНОЙ починке и проверял
    лишь отсутствие tmp — ветка `except OSError` → `unlink` → `raise FixError` не
    была покрыта вообще.
    """
    rom = tmp_path / 'fail.gb'
    blob = _gb(0x200)
    blob[0x014D] ^= 0xFF
    broken = bytes(blob)
    rom.write_bytes(broken)

    def boom(self, data):
        raise OSError('диск заполнен')

    monkeypatch.setattr(Path, 'write_bytes', boom)
    try:
        repair(rom)
    except FixError as exc:
        assert 'не удалось записать' in str(exc)
    else:
        raise AssertionError('ожидался FixError')
    assert rom.read_bytes() == broken
    assert not list(tmp_path.glob('*.chksum.tmp'))


def test_repair_refuses_when_it_cannot_fix(tmp_path, monkeypatch) -> None:
    """Починка проверяется ДО записи: сбойный пересчёт не коммитится.

    Раньше файл перезаписывался, и только потом читался обратно: сбойный
    `recalculate_checksums` оставлял на диске недопочиненный ROM без
    исключения и без бэкапа, а исходные байты были потеряны безвозвратно.
    """
    rom = tmp_path / 'stubborn.gb'
    blob = _gb(0x200)
    blob[0x014D] ^= 0xFF
    broken = bytes(blob)
    rom.write_bytes(broken)

    # Сломана именно ЗАПИСЬ, а не проверка: подменяем `recalculate_checksums`
    # так, чтобы он писал неверное значение. Проверки остаются настоящими —
    # иначе «сломанная» проверка сравняла бы 0x42 с 0x42 и объявила успех.
    def broken_recalc(self, data):
        data[0x014D] = 0x42
        data[0x014E] = 0x42
        data[0x014F] = 0x42

    monkeypatch.setattr(GameBoyROM, 'recalculate_checksums', broken_recalc)
    try:
        repair(rom)
    except FixError as exc:
        assert 'не сошлась' in str(exc)
        assert 'файл не тронут' in str(exc)
    else:
        raise AssertionError('ожидался FixError')
    assert rom.read_bytes() == broken
    assert not list(tmp_path.glob('*.chksum.tmp'))


def test_gbc_system_is_detected_and_validated(tmp_path: Path) -> None:
    """Ветка gbc: тот же байт 0x14D, но система определяется по CGB-флагу."""
    blob = bytearray(0x200)
    blob[0x0143] = 0x80          # CGB-флаг: система определяется как gbc
    blob[0x014D] = _calc(blob)
    total = sum(blob) & 0xFFFF
    blob[0x014E] = (total >> 8) & 0xFF
    blob[0x014F] = total & 0xFF
    rom = tmp_path / 'c.gbc'
    rom.write_bytes(bytes(blob))
    report = inspect(rom)
    assert report.system == 'gbc'
    assert report.valid is True
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert inspect(rom).valid is False
    assert repair(rom).valid is True


def test_report_as_dict_shape(tmp_path: Path) -> None:
    rom = tmp_path / 'd.gb'
    rom.write_bytes(bytes(_gb(0x200)))
    data = inspect(rom).as_dict()
    assert set(data) >= {'path', 'system', 'valid', 'stored', 'expected',
                         'wrong_offsets', 'global_ok'}
    assert data['valid'] is True


def test_inspect_accepts_str_path(tmp_path: Path) -> None:
    rom = tmp_path / 's.gb'
    rom.write_bytes(bytes(_gb(0x200)))
    assert inspect(str(rom)).valid is True


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
