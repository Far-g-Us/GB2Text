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

from core.rom import GameBoyROM
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger('gb2text.analyzer')


class TextAnalyzer:
    """Анализ извлеченного текста для улучшения обработки"""

    @staticmethod
    def detect_terminators(text_data: bytes, start: int = 0, length: int = 1000) -> List[int]:
        """
        Определение терминаторов текста в бинарных данных
        Возвращает список байтов, которые, вероятно, являются терминаторами текста
        """

        logger.info(f"Определение терминаторов текста (начало: 0x{start:X}, длина: {length})")

        # Анализ частоты использования байтов
        freq = {}
        for i in range(start, min(start + length, len(text_data))):
            byte = text_data[i]
            freq[byte] = freq.get(byte, 0) + 1

        # Сортируем по частоте
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        # Предполагаем, что самые частые байты - это пробелы или терминаторы
        common_bytes = [byte for byte, count in sorted_freq[:5]]

        # Проверяем, какие из них могут быть терминаторами
        terminators = []
        for byte in common_bytes:
            # Проверяем, часто ли этот байт встречается в конце "сообщений"
            is_terminator = True
            message_count = 0
            terminator_count = 0

            i = start
            while i < min(start + length, len(text_data)) - 1:
                # Начало потенциального сообщения
                if text_data[i] not in common_bytes:
                    message_count += 1
                    # Ищем конец сообщения
                    j = i + 1
                    while j < min(start + length, len(text_data)) - 1:
                        if text_data[j] == byte:
                            terminator_count += 1
                            break
                        j += 1
                    i = j
                i += 1

            # Если терминатор встречается в конце большинства сообщений
            if message_count > 0 and terminator_count / message_count > 0.7:
                terminators.append(byte)

        logger.info(f"Найдены терминаторы: {[f'0x{t:02X}' for t in terminators]}")
        return terminators

    @staticmethod
    def detect_text_regions(rom: GameBoyROM, min_length: int = 100) -> List[Tuple[int, int]]:
        """
        Автоматическое определение регионов с текстом

        Возвращает список кортежей (начало, конец) регионов, содержащих текст
        """
        logger.info("Определение регионов с текстом")
        regions = []
        current_region = None
        in_text = False

        # Пропускаем первые 0x150 байт (заголовок ROM)
        start_idx = 0x150

        for i in range(start_idx, len(rom.data)):
            # Проверяем, похож ли байт на текст
            # ASCII символы, пробелы и распространенные терминаторы
            is_text = (0x20 <= rom.data[i] <= 0x7E or
                       rom.data[i] in [0x00, 0x0A, 0x0D, 0xFF])

            if is_text:
                if not in_text:
                    # Начало нового региона
                    current_region = [i, i]
                    in_text = True
                else:
                    # Продолжаем текущий регион
                    current_region[1] = i
            else:
                if in_text:
                    # Проверяем, достаточно ли длинный регион
                    if current_region[1] - current_region[0] >= min_length:
                        regions.append(tuple(current_region))
                    current_region = None
                    in_text = False

        # Проверяем последний регион
        if in_text and current_region[1] - current_region[0] >= min_length:
            regions.append(tuple(current_region))

        logger.info(f"Найдено {len(regions)} регионов с текстом")
        return regions

    @staticmethod
    def validate_extraction(rom: GameBoyROM, results: Dict[str, List[Dict]]) -> Dict:
        """
        Проверка корректности извлечения текста

        Возвращает отчет о достоверности результатов
        """
        logger.info("Проверка корректности извлечения текста")

        total_messages = 0
        valid_messages = 0
        possible_errors = []

        for segment_name, messages in results.items():
            total_messages += len(messages)

            for msg in messages:
                text = msg['text']
                offset = msg['offset']

                # Проверяем, содержит ли текст "читаемые" символы
                readable_chars = sum(1 for c in text if 0x20 <= ord(c) <= 0x7E)
                readability = readable_chars / len(text) if text else 0

                # Проверяем на наличие нечитаемых последовательностей
                has_invalid_sequence = False
                for i in range(len(text) - 3):
                    if text[i:i + 4] == "[CD][":
                        has_invalid_sequence = True
                        break

                if readability > 0.7 and not has_invalid_sequence:
                    valid_messages += 1
                else:
                    possible_errors.append({
                        'segment': segment_name,
                        'offset': offset,
                        'issue': 'low_readability' if readability <= 0.7 else 'invalid_sequence',
                        'readability': readability
                    })

        success_rate = valid_messages / total_messages if total_messages > 0 else 0

        report = {
            'success_rate': success_rate,
            'total_messages': total_messages,
            'valid_messages': valid_messages,
            'possible_errors': possible_errors
        }

        logger.info(f"Проверка завершена. Уровень достоверности: {success_rate:.2%}")
        return report