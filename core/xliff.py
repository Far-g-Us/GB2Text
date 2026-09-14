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
Модуль для работы с XLIFF (XML Localization Interchange File Format) 1.2.

Формат позволяет передавать извлечённые строки в CAT-инструменты
(Trados, memoQ, OmegaT, Weblate и др.) и получать обратно переводы.

https://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-os.html
"""

import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)

# Namespace XLIFF 1.2
XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"
# Стандартный префикс для XLIFF — ожидается большинством CAT-инструментов
ET.register_namespace('xliff', XLIFF_NS)


class XLIFFHandler:
    """Обработчик XLIFF файлов (экспорт/импорт переводов)"""

    def __init__(self):
        self.version = "1.2"

    def export_xliff(self, results: dict, source_lang: str = "en",
                     target_lang: str = "ru", game_title: str = "Unknown Game") -> str:
        """Экспорт результатов извлечения в XLIFF 1.2.

        Args:
            results: Словарь {segment_name: [{'text': ..., 'offset': ...}, ...]}
            source_lang: Исходный язык (ISO 639-1)
            target_lang: Целевой язык (ISO 639-1)
            game_title: Название игры

        Returns:
            Содержимое XLIFF файла (строка)
        """
        # Создаём корневой элемент с namespace
        xliff = ET.Element(f"{{{XLIFF_NS}}}xliff", version=self.version)

        tu_count = 0

        for segment_name, messages in results.items():
            # Один <file> на сегмент — оригинальный текст как original атрибут
            file_elem = ET.SubElement(
                xliff, f"{{{XLIFF_NS}}}file",
                source_language=source_lang,
                target_language=target_lang,
                datatype="plaintext",
                original=segment_name,
            )
            if game_title:
                file_elem.set("product-name", game_title)

            body = ET.SubElement(file_elem, f"{{{XLIFF_NS}}}body")

            for idx, msg in enumerate(messages):
                original_text = msg.get('text', '').strip()
                if not original_text:
                    continue

                trans_unit = ET.SubElement(body, f"{{{XLIFF_NS}}}trans-unit", id=str(idx))

                # Храним offset в note для возможности обратной вставки
                if 'offset' in msg:
                    note = ET.SubElement(trans_unit, f"{{{XLIFF_NS}}}note")
                    note.text = f"rom-offset: 0x{msg['offset']:04X}"

                source = ET.SubElement(trans_unit, f"{{{XLIFF_NS}}}source")
                source.text = original_text

                # Пустой target помечаем как "непереведён"
                target = ET.SubElement(trans_unit, f"{{{XLIFF_NS}}}target")
                target.set("state", "new")
                target.text = ""

                tu_count += 1

        logger.info(f"Экспортировано {tu_count} единиц перевода в XLIFF")

        # Форматируем как в TMXHandler: ET stringify + minidom pretty print
        rough_string = ET.tostring(xliff, encoding='unicode')
        try:
            reparsed = minidom.parseString(rough_string)
            pretty = reparsed.toprettyxml(indent="  ")
            newline_pos = pretty.index('\n')
            pretty = '<?xml version="1.0" encoding="utf-8"?>' + pretty[newline_pos:]
            return pretty
        except Exception as e:
            logger.warning(f"Не удалось отформатировать XLIFF XML: {e}, возвращаем без форматирования")
            return '<?xml version="1.0" encoding="utf-8"?>\n' + rough_string

    def import_xliff(self, xliff_content: str) -> dict[str, dict[int, str]]:
        """Импорт переводов из XLIFF файла.

        Args:
            xliff_content: Содержимое XLIFF файла

        Returns:
            Словарь {segment_name: {index: translation}} — индекс совпадает
            с порядковым номером trans-unit внутри <file> (атрибут id).
        """
        translations: dict[str, dict[int, str]] = {}

        try:
            root = ET.fromstring(xliff_content)

            # Нормализуем теги: с namespace или без
            if self._local_name(root.tag) != "xliff":
                raise ValueError("Неверный формат XLIFF файла: корневой элемент не 'xliff'")

            imported_count = 0

            for file_elem in self._children(root, "file"):
                segment_name = file_elem.get("original", "unknown")

                body = self._find_child(file_elem, "body")
                if body is None:
                    continue

                for trans_unit in self._children(body, "trans-unit"):
                    id_raw = trans_unit.get("id")
                    if id_raw is None:
                        continue
                    try:
                        index = int(id_raw)
                    except ValueError:
                        continue

                    target = self._find_child(trans_unit, "target")
                    if target is None:
                        continue

                    translation = self._get_element_text(target)
                    if not translation:
                        continue

                    if segment_name not in translations:
                        translations[segment_name] = {}
                    translations[segment_name][index] = translation
                    imported_count += 1

            logger.info(f"Импортировано {imported_count} единиц перевода из XLIFF")

        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XLIFF XML: {e}")
            raise ValueError(f"Неверный формат XLIFF файла: {e}") from e
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Ошибка импорта XLIFF: {e}")
            raise

        return translations

    @staticmethod
    def apply_translations(
        current_results: dict[str, list[dict]],
        translations: dict[str, dict[int, str]],
    ) -> int:
        """Применяет импортированные переводы к current_results (GUI).

        Маппинг по индексу: id trans-unit в export_xliff равен позиции
        сообщения в списке сегмента (до фильтрации пустых), поэтому
        translation применяется к messages[index]. Индексы вне диапазона
        и переводы, совпадающие с уже применёнными, пропускаются.

        Returns: количество реально изменённых переводов.
        """
        applied_count = 0
        for segment_name, by_index in translations.items():
            messages = current_results.get(segment_name)
            if not messages:
                continue
            for index, translation in by_index.items():
                if not (0 <= index < len(messages)):
                    continue
                msg = messages[index]
                if msg.get('translation') == translation:
                    continue
                msg['translation'] = translation
                applied_count += 1
        return applied_count

    def _children(self, element: ET.Element, local_name: str) -> list[ET.Element]:
        """Все дочерние элементы с заданным локальным именем (без учёта namespace)."""
        return [child for child in element if self._local_name(child.tag) == local_name]

    def _find_child(self, element: ET.Element, local_name: str) -> ET.Element | None:
        """Первый дочерний элемент с заданным локальным именем или None."""
        for child in element:
            if self._local_name(child.tag) == local_name:
                return child
        return None

    def _local_name(self, tag: str) -> str:
        """Локальное имя тега без учёта namespace."""
        if isinstance(tag, str) and tag.startswith('{'):
            return tag.split('}', 1)[1]
        return tag

    def _get_element_text(self, element: ET.Element) -> str | None:
        """Извлечение полного текста из элемента, включая вложенные элементы.

        Обрабатывает inline-разметку (g, bx, ex, x) встроенную CAT-инструментом.
        """
        if len(element) == 0:
            text = element.text
            return text.strip() if text else None

        parts = []
        if element.text:
            parts.append(element.text)

        for child in element:
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)

        full_text = ''.join(parts).strip()
        return full_text if full_text else None
