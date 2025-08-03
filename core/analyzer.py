from core.rom import GameBoyROM

class TextAnalyzer:
    """Анализ извлеченного текста для улучшения обработки"""

    @staticmethod
    def detect_terminators(text_data: bytes) -> list:
        """Определение терминаторов текста в бинарных данных"""
        # Поиск повторяющихся байтов после конца видимого текста
        # ...
        return [0x00, 0xFF]  # Пример найденных терминаторов

    @staticmethod
    def detect_text_regions(rom: GameBoyROM) -> list:
        """Автоматическое определение регионов с текстом"""
        # Статистический анализ байтов
        regions = []
        current_region = None

        for i in range(len(rom.data)):
            # Проверяем, похож ли байт на текст
            is_text = 0x20 <= rom.data[i] <= 0x7E or rom.data[i] in [0x00, 0xFF]

            if is_text and not current_region:
                current_region = [i, i]
            elif is_text and current_region:
                current_region[1] = i
            elif not is_text and current_region:
                if current_region[1] - current_region[0] > 10:  # Минимальная длина
                    regions.append(tuple(current_region))
                current_region = None

        return regions

    @staticmethod
    def validate_extraction(rom: GameBoyROM, results: dict) -> dict:
        """Проверка корректности извлечения текста"""
        report = {
            'success_rate': 0.0,
            'possible_errors': [],
            'suggestions': []
        }

        # Анализ статистики извлеченного текста
        total_chars = 0
        unknown_chars = 0

        for seg_name, messages in results.items():
            for msg in messages:
                total_chars += len(msg['text'])
                unknown_chars += msg['text'].count('[')

        if total_chars > 0:
            report['success_rate'] = 1.0 - (unknown_chars / total_chars)

        if report['success_rate'] < 0.7:
            report['suggestions'].append(
                "Низкий процент распознавания текста. Возможно, нужна другая таблица символов."
            )

        return report