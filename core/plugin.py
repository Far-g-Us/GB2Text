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
  - validate_rom(rom) → bool

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
            rom: объект ROM

        Returns:
            True если ROM валиден, False если нет.
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
    """

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
        """Опционально: проверка валидности ROM для этого плагина."""
        return True


class GenericGamePlugin(GamePlugin):
    """Общий плагин для игр без привязки к конкретным коммерческим играм"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GAME_[0-9A-F]{2}$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        return [
            {
                'name': 'main_text',
                'start': 0x4000,
                'end': 0x7FFF,
                'decoder': None,  # Будет определен автоматически
                'compression': None
            }
        ]
