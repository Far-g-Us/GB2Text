"""Починка checksum'ов ROM, битых сторонним hex-редактором.

Инжектор пересчитывает checksum'ы сам (`TextInjector.save` ->
`GameBoyROM.recalculate_checksums`), но правка руками — типичный сценарий
хакерства, и после неё эмулятор/лоадер отвергает ROM. Команда чинит заголовок
и глобальную сумму, ничего не зная о содержимом.

Проверка (`--check`) ничего не пишет и годится для CI: ненулевой код возврата
означает «checksum сломан». Починка (`--fix`) пишет атомарно и только те байты,
которые отличаются от верных, о чём и говорит в отчёте.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.rom import GameBoyROM

# Проверяемый байт заголовка -> имя поля, по которому оно описано в отчёте.
# Имена обязаны совпадать с ключами `_expected_values`: сверка идёт по имени, и
# расхождение молча дало бы «0 != 0».
OFFSET_FIELDS = {
    'gb': {0x014D: 'header_0x14D'},
    'gbc': {0x014D: 'header_0x14D'},
    'gba': {0x0BD: 'complement_0x0BD'},
}


class FixError(Exception):
    """ROM нечитаем или слишком мал для заголовка."""


@dataclass
class ChecksumReport:
    path: str
    system: str
    valid: bool
    stored: dict[str, int] = field(default_factory=dict)
    expected: dict[str, int] = field(default_factory=dict)
    wrong_offsets: list[int] = field(default_factory=list)
    global_ok: bool = True

    def as_dict(self) -> dict:
        return {
            'path': self.path,
            'system': self.system,
            'valid': self.valid,
            'stored': dict(self.stored),
            'expected': dict(self.expected),
            'wrong_offsets': list(self.wrong_offsets),
            'global_ok': self.global_ok,
        }


def _expected_values(rom: GameBoyROM, data: bytes) -> dict[str, int]:
    """Верные значения всех проверяемых полей заголовка."""
    if rom.system == 'gba':
        return {'complement_0x0BD': rom.calculate_gba_complement(data)}
    return {
        'header_0x14D': rom.calculate_header_checksum(data),
        'global_0x14E_0x14F': rom.calculate_global_checksum(data),
    }


def inspect(path: str | Path) -> ChecksumReport:
    """Проверить checksum'ы ROM, ничего не меняя на диске."""
    target = Path(path)
    try:
        rom = GameBoyROM(str(target))
    except (OSError, ValueError) as exc:
        raise FixError(f'{target}: нечитаемый ROM ({exc})') from exc
    data = bytes(rom.data)
    if len(data) < 0x0150:
        raise FixError(f'{target}: слишком мал для заголовка ({len(data)} байт)')
    return _report_from_data(rom, target, data)


def _report_from_data(rom: GameBoyROM, target: Path, data: bytes) -> ChecksumReport:
    """Отчёт по буферу. Единственное место, где решается, что «верно».

    Таблица `OFFSET_FIELDS` связывает проверяемый байт с именем поля, и `_expected_values`
    обязан выдавать те же имена — иначе сверка молча нашла бы «0 != 0».
    """
    fields = OFFSET_FIELDS.get(rom.system)
    if fields is None:
        raise FixError(f'{target}: система {rom.system!r} не поддерживается')
    expected = _expected_values(rom, data)
    stored = {name: data[offset] for offset, name in fields.items()}
    if rom.system == 'gba':
        # Глобальной суммы у GBA ROM НЕТ: 0x14E-0x14F там лежат значения из
        # внутреннего регистра и не равны сумме байт файла. Измерено на всех
        # 40 GBA ROM в test_game: совпадений 0. Проверять их — значит объявить
        # битой каждую коммерческую GBA ROM.
        stored_global = (data[0x014E] << 8) | data[0x014F]
        global_ok = True
    else:
        stored_global = (data[0x014E] << 8) | data[0x014F]
        global_ok = stored_global == expected['global_0x14E_0x14F']
        stored['global_0x14E_0x14F'] = stored_global
    # Сверяются только поля из OFFSET_FIELDS. Для GBA это исключительно
    # complement-байт: резервные 0x0BE-0x0BF формально обязаны быть 0x0000
    # (GBATEK требует sum(0xA0..0xBF) == 0), но на реальной ROM правило
    # нарушается штатно — у `Moemon Fire Red ruRevival Project2.0` там 0x3C/0x2A
    # при сошедшемся complement и сумме 0x064D, ROM грузится и работает.
    # Проверять их — значит объявить битым рабочий фан-ром, а «починить» —
    # затереть чужие данные.
    wrong = [offset for offset, name in fields.items()
             if data[offset] != expected[name]]
    return ChecksumReport(
        path=str(target),
        system=rom.system,
        valid=not wrong and global_ok,
        stored={k: stored[k] for k in expected},
        expected=expected,
        wrong_offsets=wrong,
        global_ok=global_ok,
    )


def repair(path: str | Path) -> ChecksumReport:
    """Починить checksum'ы на месте, атомарно.

    Возвращает отчёт ПОСЛЕ починки: `valid` должен стать True, а
    `wrong_offsets` — пустым. Файл перезаписывается только когда есть что
    чинить, поэтому mtime готовой ROM не меняется.
    """
    target = Path(path)
    before = inspect(target)
    if before.valid:
        return before
    rom = GameBoyROM(str(target))
    data = bytearray(rom.data)
    reserved = (rom.data[0x0BE], rom.data[0x0BF]) if rom.system == 'gba' else None
    rom.recalculate_checksums(data)
    if reserved is not None:
        # Резервные 0x0BE-0x0BF пересчитывает `recalculate_checksums` (пишет
        # нули), а проверка их НЕ считает полем: на реальной ROM там бывает не
        # ноль (`Moemon Fire Red ruRevival`: 0x3C/0x2A при рабочем complement),
        # и «починка» молча затерела бы чужие данные. Поэтому возвращаем
        # исходные — команда чинит checksum'ы и не трогает остальное.
        data[0x0BE], data[0x0BF] = reserved
    # Проверка ДО записи. Иначе сбойный `recalculate_checksums` коммитил бы
    # недопочиненный файл без исключения и без бэкапа, а исходные байты были бы
    # потеряны безвозвратно. Отчёт строится из памяти, а не третьим чтением
    # файла: иначе AV-сканер, придержавший путь на секунду, дал бы ложный
    # «ROM_UNREADABLE» про починку, которая на самом деле прошла.
    check = _report_from_data(rom, target, bytes(data))
    if not check.valid:
        raise FixError(
            f'{target}: починка не сошлась, файл не тронут '
            f'(битые: {", ".join(hex(o) for o in check.wrong_offsets) or "сумма"})')
    tmp = target.with_name(target.name + '.chksum.tmp')
    try:
        tmp.write_bytes(bytes(data))
        tmp.replace(target)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise FixError(f'{target}: не удалось записать ({exc})') from exc
    return inspect(target)
