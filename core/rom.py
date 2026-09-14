"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Модуль для работы с ROM-файлами Game Boy, Game Boy Color и Game Boy Advance
"""

import logging
import re

from core.mbc import create_mbc

# Валидные расширения файлов
VALID_EXTENSIONS = {'.gb', '.gbc', '.gba'}

# Минимальный размер ROM (меньше - явно невалидный)
MIN_ROM_SIZE = 0x8000  # 32KB

# Максимальный размер ROM (для безопасности)
MAX_ROM_SIZE = 0x4000000  # 64MB


def validate_rom_file(path: str) -> str | None:
    """
    Валидирует ROM файл перед загрузкой.

    Returns:
        None если валиден, строку с ошибкой если нет
    """
    import os

    # Проверка расширения
    ext = os.path.splitext(path)[1].lower()
    if ext not in VALID_EXTENSIONS:
        return f"Неверное расширение файла: {ext}. Ожидалось .gb, .gbc или .gba"

    # Проверка существования
    if not os.path.exists(path):
        return f"Файл не существует: {path}"

    # Проверка размера
    size = os.path.getsize(path)
    if size < MIN_ROM_SIZE:
        return f"Файл слишком маленький: {size} байт. Минимум {MIN_ROM_SIZE} байт"

    if size > MAX_ROM_SIZE:
        return f"Файл слишком большой: {size} байт. Максимум {MAX_ROM_SIZE} байт"

    return None


class GameBoyROM:
    """Загрузка и базовый анализ ROM-файла"""

    def __init__(self, rom_path: str, validate: bool = False):
        logger = logging.getLogger('gb2text.rom')
        logger.info(f"Загрузка ROM из файла: {rom_path}")

        if not isinstance(rom_path, str):
            logger.error(f"rom_path должен быть строкой, а не {type(rom_path)}")
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")

        # Валидация файла перед загрузкой (может быть отключена для тестов)
        if validate:
            validation_error = validate_rom_file(rom_path)
            if validation_error:
                logger.error(f"Валидация ROM не пройдена: {validation_error}")
                raise ValueError(validation_error)

        self.path = rom_path
        self.data = self._load_rom(rom_path)
        self.header = self._parse_header()
        self.system = self._detect_system()
        self.mbc = create_mbc(self.data, self.header['cartridge_type'], self.header['ram_size'])
        logger.info(f"ROM загружен успешно. Размер: {len(self.data)} байт")
        logger.info(f"Определена система: {self.system}")
        logger.debug(f"Заголовок ROM: {self.header}")

    def _load_rom(self, rom_path: str) -> bytearray:
        logger = logging.getLogger('gb2text.rom')
        logger.info(f"Чтение данных из файла: {rom_path}")

        try:
            with open(rom_path, 'rb') as f:
                size = f.seek(0, 2)
                if size > MAX_ROM_SIZE:
                    logger.error(
                        f"Файл слишком большой: {size} байт. Максимум {MAX_ROM_SIZE} байт")
                    raise ValueError(
                        f"Файл слишком большой: {size} байт. Максимум {MAX_ROM_SIZE} байт")
                f.seek(0)
                data = bytearray(f.read())
            logger.info(f"Успешно прочитано {len(data)} байт")
            return data
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Ошибка при чтении ROM файла: {e!s}")
            raise

    def _parse_header(self) -> dict:
        """Парсинг заголовка ROM"""
        if len(self.data) < 0x150:
            raise ValueError("Недопустимый ROM файл: слишком маленький")

        # Определяем систему из расширения файла для выбора формата заголовка
        is_gba = self.path.lower().endswith('.gba')

        if is_gba:
            return self._parse_gba_header()
        else:
            return self._parse_gb_header()

    def _parse_gba_header(self) -> dict:
        """Парсинг заголовка GBA ROM"""
        # GBA заголовок: https://problemkaputt.de/gbatek.htm#gbacartridgeheader
        try:
            title = self.data[0x0A0:0x0AC].decode('ascii', errors='replace').rstrip('\x00')
            game_code = self.data[0x0AC:0x0B0].decode('ascii', errors='replace').rstrip('\x00')
            maker_code = self.data[0x0B0:0x0B2].decode('ascii', errors='replace').rstrip('\x00')

            # GBA ROM size определяется по размеру файла (не из заголовка)
            # Стандартные размеры: 4MB, 8MB, 16MB, 32MB
            rom_size = len(self.data)

            header = {
                'title': title,
                'cgb_flag': 0,
                'new_licensee_code': 0,
                'sgb_flag': 0,
                'cartridge_type': 0,
                'rom_size': rom_size,
                'ram_size': 0,  # GBA RAM size не определяется из заголовка
                'destination_code': 0,
                'old_licensee_code': 0,
                'mask_rom_version': self.data[0x0BC] if len(self.data) > 0x0BC else 0,
                'header_checksum': self.data[0x0BD] if len(self.data) > 0x0BD else 0,
                'global_checksum': 0,
                'game_code': game_code,
                'maker_code': maker_code,
                'system': 'gba'
            }
        except Exception as e:
            raise ValueError(f"Недопустимый GBA ROM файл: ошибка при парсинге заголовка: {e!s}") from e

        return header

    def _parse_gb_header(self) -> dict:
        """Парсинг заголовка GB/GBC ROM"""
        try:
            header = {
                'title': self.data[0x0134:0x0143].decode('ascii', errors='replace').rstrip('\x00'),
                'cgb_flag': self.data[0x0143],
                'new_licensee_code': self.data[0x0144] << 8 | self.data[0x0145],
                'sgb_flag': self.data[0x0146],
                'cartridge_type': self.data[0x0147],
                'rom_size': self.data[0x0148],
                'ram_size': self.data[0x0149],
                'destination_code': self.data[0x014A],
                'old_licensee_code': self.data[0x014B],
                'mask_rom_version': self.data[0x014C],
                'header_checksum': self.data[0x014D],
                'global_checksum': (self.data[0x014E] << 8) | self.data[0x014F],
                'game_code': '',
                'maker_code': '',
                'system': 'gb'  # будет определён позже
            }
        except Exception as e:
            raise ValueError(f"Недопустимый ROM файл: ошибка при парсинге заголовка: {e!s}") from e

        # Исправляем проблему с отсутствующим new_licensee_code
        if header['new_licensee_code'] == 0xFFFF:
            header['new_licensee_code'] = 0

        return header

    def _read_string(self, start: int, length: int) -> str:
        return ''.join(chr(b) for b in self.data[start:start + length]
                       if 0x20 <= b <= 0x7E).strip()

    def _detect_system(self) -> str:
        """Определение системы по сигнатуре ROM"""
        logger = logging.getLogger('gb2text.rom')
        logger.info("Определение типа системы...")

        # Если заголовок уже определил систему (GBA)
        if self.header.get('system') == 'gba':
            logger.info("Определена система: Game Boy Advance (gba)")
            return 'gba'

        # Проверка на Game Boy Advance
        if len(self.data) > 0x100:
            header_start = self.data[:10]
            if b'GBA ' in header_start or b'AGB' in header_start:
                logger.info("Определена система: Game Boy Advance (gba)")
                return 'gba'
            if self.path.lower().endswith('.gba'):
                logger.info("Определена система: Game Boy Advance (gba)")
                return 'gba'

        # Проверка на Game Boy Color
        if self.header['cgb_flag'] == 0x80 or self.header['cgb_flag'] == 0xC0:
            logger.info("Определена система: Game Boy Color (gbc)")
            return 'gbc'

        if self.header['new_licensee_code'] == 0x33:
            logger.info("Определена система: Game Boy Color (gbc)")
            return 'gbc'

        if self.header['header_checksum'] != 0:
            logger.info("Определена система: Game Boy (gb)")
            return 'gb'

        # Проверка по размеру ROM
        rom_size = self.header['rom_size']
        if rom_size <= 8:
            logger.warning("Не удалось точно определить систему, используем Game Boy (gb) по умолчанию")
            return 'gb'
        else:
            return 'gbc'


    def get_game_id(self) -> str:
        """Возвращает идентификатор игры.

        Для GBA: ``GBA_<game_code>``.
        Для GB/GBC: ``GB_`` / ``GBC_`` + sanitized title из заголовка (0x134).
        Если title отсутствует или состоит только из непечатных байтов,
        сохраняется обратная совместимость ``GAME_<cartridge_type>``.
        """
        if self.system == 'gba':
            game_code = self.header.get('game_code', '')
            if game_code:
                return f"GBA_{game_code}"
            return "GBA_UNKNOWN"

        # GB/GBC: sanitized title
        title = self.header.get('title', '')
        safe_title = re.sub(r'[^A-Z0-9]', '', title.upper())
        if safe_title:
            prefix = 'GBC' if self.system == 'gbc' else 'GB'
            return f"{prefix}_{safe_title}"

        # Fallback: cartridge type (обратная совместимость)
        cartridge_type = self.header['cartridge_type']
        return f"GAME_{cartridge_type:02X}"

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def type(self) -> str:
        return self.system

    @property
    def title(self) -> str:
        return self.header.get('title', '')

    @property
    def cgb_flag(self) -> int:
        return self.header.get('cgb_flag', 0)

    @property
    def rom_size(self) -> int:
        return self.header.get('rom_size', 0)

    @property
    def ram_size(self) -> int:
        return self.header.get('ram_size', 0)

    @property
    def region(self) -> int:
        return self.header.get('destination_code', 0)

    def calculate_header_checksum(self, data: bytes | bytearray | None = None) -> int:
        """Глобальный (канонический) header checksum GB/GBC по байтам 0x134-0x14C.

        Dashes include the title: проверяется вся область заголовка, как это
        делает реальное железо (X = X - byte - 1 для каждого байта 0x134..0x14C).
        """
        if data is None:
            data = self.data
        checksum = 0
        for addr in range(0x0134, 0x014D):
            checksum = (checksum - data[addr] - 1) & 0xFF
        return checksum

    def calculate_gba_complement(self, data: bytes | bytearray | None = None) -> int:
        """GBA complement check byte (0x0BD).

        Формула подтверждена эмпирически на 38 коммерческих GBA ROM
        (scripts_roms/checksum_formula_probe.py):
        byte[0x0BD] = (0 - sum(0x0A0..0x0BC) - 0x19) & 0xFF.
        """
        if data is None:
            data = self.data
        return (0 - sum(data[0x0A0:0x0BD]) - 0x19) & 0xFF

    def calculate_global_checksum(self, data: bytes | bytearray | None = None) -> int:
        """Глобальный checksum: сумма всех байт, кроме 0x14E-0x14F.

        Для больших ROM (до 32MB) быстрый ``sum()`` на bytearray
        выполняется на C-уровне и значительно быстрее поэлементного цикла.
        """
        if data is None:
            data = self.data
        return (sum(data) - data[0x14E] - data[0x14F]) & 0xFFFF

    def validate_header(self) -> bool:
        """Проверяет header checksum ROM (GB/GBC: канонический 0x134-0x14C;
        GBA: complement check 0x0BD)."""
        if self.system == 'gba':
            return self.data[0x0BD] == self.calculate_gba_complement(self.data)
        return self.data[0x014D] == self.calculate_header_checksum(self.data)

    def recalculate_checksums(self, data: bytearray) -> None:
        """Пересчитывает и записывает checksum'ы в переданный буфер.

        GB/GBC: header checksum (0x14D) + глобальный (0x14E-0x14F).
        GBA: complement check byte (0x0BD) + reserved 0xBE-0xBF (норма по GBATEK).
        """
        if self.system == 'gba':
            data[0x0BD] = self.calculate_gba_complement(data)
            # 0xBE-0xBF: в коммерческих ROM всегда 0x0000; GBATEK требует
            # sum(0xA0..0xBF) == 0x0000 — complement на 0xBD это обеспечивает.
            data[0x0BE] = 0x00
            data[0x0BF] = 0x00
            return
        data[0x014D] = self.calculate_header_checksum(data)
        global_checksum = self.calculate_global_checksum(data)
        data[0x014E] = (global_checksum >> 8) & 0xFF
        data[0x014F] = global_checksum & 0xFF

    def read(self, address: int) -> int:
        """Чтение из ROM с учетом MBC"""
        if 0x0000 <= address < 0x8000:
            return self.mbc.read_rom(address)
        elif 0xA000 <= address < 0xC000:
            return self.mbc.read_ram(address)
        return 0xFF
