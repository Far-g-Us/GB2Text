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
Константы и настройки для GB2Text
"""

# === ROM Header Constants ===
ROM_HEADER_SIZE = 0x150  # Стандартный размер заголовка ROM
TITLE_OFFSET = 0x0134
TITLE_LENGTH = 15
CGB_FLAG_OFFSET = 0x0143
NEW_LICENSEE_CODE_OFFSET = 0x0144
SGB_FLAG_OFFSET = 0x0146
CARTRIDGE_TYPE_OFFSET = 0x0147
ROM_SIZE_OFFSET = 0x0148
RAM_SIZE_OFFSET = 0x0149
DESTINATION_CODE_OFFSET = 0x014A
OLD_LICENSEE_CODE_OFFSET = 0x014B
MASK_ROM_VERSION_OFFSET = 0x014C
HEADER_CHECKSUM_OFFSET = 0x014D
GLOBAL_CHECKSUM_OFFSET = 0x014E

# === Memory Regions ===
BANK_0_START = 0x4000
BANK_0_END = 0x7FFF
VRAM_START = 0xA000
VRAM_END = 0xC000
RAM_START = 0xC000
WORK_RAM_START = 0xC000
EXTERNAL_RAM_START = 0xA000

# === GBA Constants ===
GBA_ROM_BASE_ADDRESS = 0x08000000
GBA_MIN_ADDRESS = 0x4000
GBA_HEADER_SIGNATURE = b'Nintendo Game Boy'

# === Text Detection ===
MIN_SEGMENT_LENGTH = 200  # Минимальная длина текстового сегмента
MIN_READABILITY = 0.65  # Минимальная читаемость для auto_detect
MIN_POINTER_LENGTH = 4  # Минимальная длина указателя
READABLE_BLOCK_SIZE = 32  # Размер блока для анализа читаемости

# === Terminators ===
TEXT_TERMINATORS = {0x00, 0xFF, 0xFE, 0x0D, 0x0A}
COMMON_TERMINATORS = [0x00, 0xFF, 0xFE]

# === ASCII Ranges ===
ASCII_PRINTABLE_START = 0x20
ASCII_PRINTABLE_END = 0x7E

# === Japanese Character Ranges ===
KATAKANA_RANGE = (0xA0, 0xDF)
HIRAGANA_RANGE = (0x80, 0x9F)

# === Russian Character Ranges (CP866) ===
CYRILLIC_UPPER = (0xA0, 0xBF)
CYRILLIC_LOWER = (0xC0, 0xFF)

# === System Types ===
SYSTEM_GB = 'gb'
SYSTEM_GBC = 'gbc'
SYSTEM_GBA = 'gba'

# === Pointer Sizes ===
POINTER_SIZES = {
    SYSTEM_GB: 2,
    SYSTEM_GBC: 2,
    SYSTEM_GBA: 4,
}

# === Compression Types ===
COMPRESSION_NONE = 'none'
COMPRESSION_GBA_LZ77 = 'gba_lz77'
COMPRESSION_LZ77 = 'lz77'
COMPRESSION_LZSS = 'lzss'
COMPRESSION_RLE = 'rle'
COMPRESSION_AUTO = 'auto'

# === Plugin Settings ===
MAX_CONFIGS = 20  # Максимальное количество конфигурационных плагинов

# === Quality Thresholds ===
MIN_READABILITY_LOW = 0.5  # Низкое качество декодирования
MIN_READABILITY_MEDIUM = 0.7  # Среднее качество
QUALITY_GOOD = 0.7  # Хорошее качество

# === Scanner Settings ===
POINTER_GROUP_MAX_DISTANCE = 50
ANALYSIS_BLOCK_SIZE = 0x1000  # 4KB для группировки анализа

# === GUI Settings ===
DEFAULT_WINDOW_WIDTH = 1100
DEFAULT_WINDOW_HEIGHT = 700
