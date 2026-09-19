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
Базовые классы для плагинов

Контракт плагина (GamePlugin):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Обязательные методы (ABC):
  - game_id_pattern: str — regex паттерн для идентификации игры
  - get_text_segments(rom) → list[dict] — возвращает список текстовых сегментов

Опциональные методы (Protocol):
  - get_compression_handler(segment_name) → CompressionHandler | None
  - get_terminators(segment_name) → list[int]
  - get_pointer_size(rom) → int
  - validate_rom(rom) → bool — сигнатурный гейт выбора плагина.
    Вызывается PluginManager.get_plugin() ТОЛЬКО когда туда передан rom.
    Дефолт (не переопределён) = True для любого ROM: плагин считается
    «без гейта» (level 0). Плагин с переопределённым validate_rom считается
    «с гейтом» (level 1) и выигрывает выбор у плагина без гейта при том же
    game_id_pattern — это механизм поддержки ROM-хаков и вариантов игры с
    тем же game_code (заголовок/размер меняются, game_code — нет).
    КОНТРАКТ для хак-плагинов: validate_rom ОБЯЗАН возвращать False на ROM,
    не подходящем под сигнатуру плагина, иначе он перебьёт ванильный плагин.
    Исключения из validate_rom рассматриваются как «ROM не подходит».

Структура dict, возвращаемого get_text_segments():
  - name: str           — уникальное имя сегмента
  - start: int          — начальный адрес в ROM
  - end: int            — конечный адрес в ROM
  - decoder: CharMapDecoder | None — декодер (или None для автоопределения)
  - compression: str | CompressionHandler | None — тип сжатия

Пример реализации:
  class MyGamePlugin(GamePlugin):
      @property
      def game_id_pattern(self) -> str:
          return r'^GAME_ID$'

      def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
          return [{
              'name': 'dialogue',
              'start': 0x4000,
              'end': 0x7FFF,
              'decoder': None,
              'compression': None,
          }]
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from core.rom import GameBoyROM


@runtime_checkable
class PluginProtocol(Protocol):
    """
    Протокол для опциональных методов плагина.

    Плагин МОЖЕТ реализовать любой из этих методов.
    Если метод не реализован — ядро использует дефолтное поведение.
    """

    def get_compression_handler(self, segment_name: str) -> object | None:
        """
        Вернуть обработчик сжатия для указанного сегмента.

        Args:
            segment_name: имя сегмента из get_text_segments()

        Returns:
            Объект с методом decompress(data, start) → (bytes, int)
            или None если сегмент не сжат.
        """
        ...

    def get_terminators(self, segment_name: str) -> list[int]:
        """
        Вернуть список байт-терминаторов для указанного сегмента.

        Args:
            segment_name: имя сегмента

        Returns:
            Список байт, которые являются терминаторами сообщений.
            Дефолт: [0x00, 0xFF, 0xFE, 0x0D, 0x0A]
        """
        ...

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        """
        Вернуть размер указателя в байтах (2 для GB/GBC, 4 для GBA).

        Args:
            rom: объект ROM

        Returns:
            Размер указателя: 2 или 4
        """
        ...

    def validate_rom(self, rom: GameBoyROM) -> bool:
        """
        Проверить что ROM файл подходит для этого плагина.

        Args:
            rom: загруженный ROM файл

        Returns:
            True если ROM валиден, False если нет.
        """
        ...

    def get_font_meta(self) -> dict | None:
        """
        Метаданные шрифта игры для inject_glyphs (core/font_tiles).

        Returns:
            None (шрифт неизвестен/не поддерживается) или dict:
            {'offset': int (база тайлов в ROM),
             'bpp': 1 | 2 (по умолчанию 2),
             'count': int (число глифов, по умолчанию до конца блока),
             'stride': int (байт на тайл: 16 при 2bpp, 8 при 1bpp)}.
            Отсутствующие ключи заменяются дефолтами; неизвестный bpp
            трактуется как 2.
        """
        ...


class GamePlugin(ABC):
    """
    Базовый класс для плагинов поддержки игр.

    Обязательные методы:
      - game_id_pattern (property) — regex паттерн для идентификации игры
      - get_text_segments(rom) — список текстовых сегментов

    Опциональные методы (см. PluginProtocol):
      - get_compression_handler(segment_name)
      - get_terminators(segment_name)
      - get_pointer_size(rom)
      - validate_rom(rom)
      - get_font_meta()

    Атрибуты:
      - is_stub (bool) — True если плагин только детектирует игру,
        но структура текста ещё не реализована (get_text_segments может
        вернуть пустой список). Используется тестами и GUI для честного
        статуса вместо мусорных сегментов. Контракт: читать is_stub
        ПОСЛЕ вызова get_text_segments(rom) — плагины, общие для рабочей
        и stub-версии игры, выставляют флаг внутри метода по game_code.
    """

    _is_stub: bool = False

    @property
    def is_stub(self) -> bool:
        return self._is_stub

    @property
    @abstractmethod
    def game_id_pattern(self) -> str:
        """Regex паттерн для идентификации игры (например r'^POKEMON_RB$')."""
        pass

    @abstractmethod
    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """
        Вернуть список текстовых сегментов ROM.

        Args:
            rom: загруженный ROM

        Returns:
            Список dict с ключами: name, start, end, decoder, compression
        """
        pass

    def get_compression_handler(self, segment_name: str) -> object | None:
        """Опционально: обработчик сжатия для сегмента."""
        return None

    def get_terminators(self, segment_name: str) -> list[int]:
        """Опционально: байт-терминаторы для сегмента."""
        return [0x00, 0xFF, 0xFE, 0x0D, 0x0A]

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        """Опционально: размер указателя (2=GB, 4=GBA)."""
        return 2

    def validate_rom(self, rom: GameBoyROM) -> bool:
        """Сигнатурный гейт: подходит ли этот ROM плагину.

        Дефолт True. Переопределение маркирует плагин как «с гейтом»
        (level 1): он принимает только ROM, подходящий под его сигнатуру,
        и выигрывает выбор у плагина без гейта при том же game_id_pattern.
        Для ROM-хаков validate_rom ОБЯЗАН вернуть False на ROM, не
        подходящий под сигнатуру, иначе хак-плагин перебьёт ванильный.
        Исключение внутри validate_rom трактуется как False."""
        return True

    def get_font_meta(self) -> dict | None:
        """Опционально: метаданные шрифта игры (см. PluginProtocol)."""
        return None


class GenericGamePlugin(GamePlugin):
    """Общий плагин для игр без привязки к конкретным коммерческим играм"""

    @property
    def game_id_pattern(self) -> str:
        return r"^GAME_[0-9A-F]{2}$"

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        return [
            {
                "name": "main_text",
                "start": 0x4000,
                "end": 0x7FFF,
                "decoder": None,  # Будет определен автоматически
                "compression": None,
            }
        ]
