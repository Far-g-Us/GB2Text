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
Модуль для работы с TMX (Translation Memory eXchange) форматом
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Namespace для xml:lang
XML_NS = "http://www.w3.org/XML/1998/namespace"
# Регистрируем namespace чтобы в выводе было xml:lang, а не ns0:lang
ET.register_namespace('xml', XML_NS)


class TMXHandler:
    """Обработчик TMX файлов"""

    def __init__(self):
        self.version = "1.4"

    def export_tmx(self, results: Dict, source_lang: str = "en", target_lang: str = "ru",
                   game_title: str = "Unknown Game") -> str:
        """Экспорт результатов в TMX формат

        Args:
            results: Словарь с результатами извлечения {segment_name: [messages]}
            source_lang: Исходный язык
            target_lang: Целевой язык
            game_title: Название игры

        Returns:
            TMX строка
        """
        # Создаем корневой элемент
        tmx = ET.Element("tmx", version=self.version)

        # Создаем header
        header = ET.SubElement(tmx, "header")
        header.set("creationtool", "GB2Text")
        header.set("creationtoolversion", "1.0")
        header.set("datatype", "plaintext")
        header.set("segtype", "sentence")
        header.set("adminlang", source_lang)
        header.set("srclang", source_lang)
        header.set("o-tmf", "GB2Text")

        # Создаем body
        body = ET.SubElement(tmx, "body")

        # Счётчик добавленных единиц
        tu_count = 0

        # Обрабатываем все сегменты
        for segment_name, messages in results.items():
            for msg in messages:
                original_text = msg.get('text', '').strip()
                translation = msg.get('translation', '').strip()

                # Пропускаем пустые записи
                if not original_text or not translation:
                    continue

                # Создаем translation unit
                tu = ET.SubElement(body, "tu")

                # Добавляем свойства
                prop_game = ET.SubElement(tu, "prop", type="game-title")
                prop_game.text = game_title

                prop_segment = ET.SubElement(tu, "prop", type="segment-name")
                prop_segment.text = segment_name

                if 'offset' in msg:
                    prop_offset = ET.SubElement(tu, "prop", type="rom-offset")
                    prop_offset.text = f"0x{msg['offset']:04X}"

                # Исходный текст — используем полный namespace URI для xml:lang
                tuv_source = ET.SubElement(tu, "tuv")
                tuv_source.set(f"{{{XML_NS}}}lang", source_lang)
                seg_source = ET.SubElement(tuv_source, "seg")
                # ElementTree автоматически экранирует спецсимволы!
                # НЕ вызываем _escape_xml_chars — иначе будет двойное экранирование
                seg_source.text = original_text

                # Перевод
                tuv_target = ET.SubElement(tu, "tuv")
                tuv_target.set(f"{{{XML_NS}}}lang", target_lang)
                seg_target = ET.SubElement(tuv_target, "seg")
                seg_target.text = translation

                tu_count += 1

        logger.info(f"Экспортировано {tu_count} единиц перевода в TMX")

        # Преобразуем в строку с красивым форматированием
        rough_string = ET.tostring(tmx, encoding='unicode', xml_declaration=False)
        try:
            reparsed = minidom.parseString(rough_string)
            pretty = reparsed.toprettyxml(indent="  ", encoding=None)
            # minidom добавляет <?xml version="1.0" ?> — заменяем на правильную декларацию
            if pretty.startswith('<?xml'):
                # Заменяем декларацию на стандартную с encoding
                newline_pos = pretty.index('\n')
                pretty = '<?xml version="1.0" encoding="utf-8"?>' + pretty[newline_pos:]
            return pretty
        except Exception as e:
            logger.warning(f"Не удалось отформатировать XML: {e}, возвращаем без форматирования")
            return '<?xml version="1.0" encoding="utf-8"?>\n' + rough_string

    def import_tmx(self, tmx_content: str) -> Dict[str, Dict[int, str]]:
        """Импорт переводов из TMX файла

        Args:
            tmx_content: Содержимое TMX файла

        Returns:
            Словарь {segment_name: {offset: translation}}
        """
        translations = {}

        try:
            # Парсим XML
            root = ET.fromstring(tmx_content)

            # Проверяем корневой тег
            if root.tag != "tmx":
                raise ValueError("Неверный формат TMX файла: корневой элемент не 'tmx'")

            # Определяем исходный язык из header
            header = root.find("header")
            source_lang = None
            if header is not None:
                source_lang = header.get("srclang")

            body = root.find("body")
            if body is None:
                raise ValueError("TMX файл не содержит элемент 'body'")

            imported_count = 0

            # Обрабатываем translation units
            for tu in body.findall("tu"):
                # Извлекаем метаданные
                segment_name = None
                offset = None

                for prop in tu.findall("prop"):
                    prop_type = prop.get("type")
                    if prop_type == "segment-name":
                        segment_name = prop.text
                    elif prop_type == "rom-offset":
                        try:
                            offset_text = prop.text.strip() if prop.text else ""
                            if offset_text.startswith('0x') or offset_text.startswith('0X'):
                                offset = int(offset_text, 16)
                            else:
                                offset = int(offset_text)
                        except (ValueError, AttributeError):
                            offset = None

                # Извлекаем тексты
                tuv_elements = tu.findall("tuv")
                if len(tuv_elements) < 2:
                    logger.debug(f"Пропускаем TU с менее чем 2 tuv элементами")
                    continue

                source_text = None
                target_text = None

                for tuv in tuv_elements:
                    # Проверяем оба варианта атрибута xml:lang
                    lang = tuv.get(f"{{{XML_NS}}}lang") or tuv.get("xml:lang")

                    seg = tuv.find("seg")
                    if seg is None:
                        continue

                    # ElementTree автоматически деэкранирует XML-сущности,
                    # поэтому seg.text уже содержит чистый текст
                    text = self._get_seg_text(seg)
                    if not text:
                        continue

                    if source_text is None:
                        source_text = text
                    else:
                        target_text = text
                        break  # Берем только первый target

                # Сохраняем перевод
                if segment_name and target_text:
                    if segment_name not in translations:
                        translations[segment_name] = {}

                    # Если offset неизвестен, используем хэш исходного текста
                    key = offset if offset is not None else hash(source_text) if source_text else hash(target_text)
                    translations[segment_name][key] = target_text
                    imported_count += 1

            logger.info(f"Импортировано {imported_count} единиц перевода из TMX")

        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга TMX XML: {e}")
            raise ValueError(f"Неверный формат TMX файла: {e}")
        except ValueError:
            raise  # Пробрасываем ValueError как есть
        except Exception as e:
            logger.error(f"Ошибка импорта TMX: {e}")
            raise

        return translations

    def _get_seg_text(self, seg_element: ET.Element) -> Optional[str]:
        """Извлечение полного текста из элемента <seg>, включая вложенные элементы

        Обрабатывает случаи когда <seg> содержит inline-элементы (bpt, ept, ph и т.д.)

        Args:
            seg_element: XML элемент <seg>

        Returns:
            Текст или None если пустой
        """
        # Простой случай — только текст без дочерних элементов
        if len(seg_element) == 0:
            text = seg_element.text
            return text.strip() if text else None

        # Сложный случай — собираем текст из всех частей
        parts = []
        if seg_element.text:
            parts.append(seg_element.text)

        for child in seg_element:
            # Добавляем текст внутри дочернего элемента
            if child.text:
                parts.append(child.text)
            # Добавляем текст после дочернего элемента (tail)
            if child.tail:
                parts.append(child.tail)

        full_text = ''.join(parts).strip()
        return full_text if full_text else None

    def _escape_xml_chars(self, text: str) -> str:
        """Экранирование специальных XML символов

        ВНИМАНИЕ: Эта функция оставлена для обратной совместимости,
        но НЕ должна использоваться при работе с ElementTree,
        т.к. ElementTree экранирует автоматически.
        Используется только если XML строится вручную (конкатенацией строк).
        """
        from xml.sax.saxutils import escape as sax_escape
        return sax_escape(text, {'"': '&quot;', "'": '&apos;'})

    def get_tmx_info(self, tmx_content: str) -> Dict:
        """Получение информации о TMX файле

        Args:
            tmx_content: Содержимое TMX файла

        Returns:
            Словарь с информацией
        """
        try:
            root = ET.fromstring(tmx_content)

            if root.tag != "tmx":
                return {
                    "version": "Unknown",
                    "creation_tool": "Unknown",
                    "source_lang": "Unknown",
                    "tu_count": 0,
                    "error": "Not a TMX file"
                }

            header = root.find("header")

            info = {
                "version": root.get("version", "1.4"),
                "creation_tool": header.get("creationtool", "Unknown") if header is not None else "Unknown",
                "source_lang": header.get("srclang", "Unknown") if header is not None else "Unknown",
                "tu_count": len(root.findall(".//tu")),
            }

            # Подсчитываем уникальные языки
            languages = set()
            for tuv in root.findall(".//tuv"):
                lang = tuv.get(f"{{{XML_NS}}}lang") or tuv.get("xml:lang")
                if lang:
                    languages.add(lang)
            info["languages"] = sorted(languages)

            return info

        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга TMX: {e}")
            return {
                "version": "Unknown",
                "creation_tool": "Unknown",
                "source_lang": "Unknown",
                "tu_count": 0,
                "error": f"XML parse error: {e}"
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о TMX: {e}")
            return {
                "version": "Unknown",
                "creation_tool": "Unknown",
                "source_lang": "Unknown",
                "tu_count": 0,
                "error": str(e)
            }