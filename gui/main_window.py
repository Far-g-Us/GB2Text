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
Графический интерфейс для GB Text Extractor с полной функциональностью
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json, re, os, logging, threading, time, sys
from datetime import datetime
from pathlib import Path
from core.rom import GameBoyROM
from core.i18n import I18N
from core.guide import GuideManager
from core.extractor import TextExtractor
from core.injector import TextInjector
from core.plugin_manager import PluginManager, CancellationToken
from core.encoding import get_generic_english_charmap, get_generic_japanese_charmap, get_generic_russian_charmap, auto_detect_charmap
from core.scanner import analyze_text_segment, _detect_language
from typing import Counter


class GBTextExtractorGUI:
    def __init__(self, root, rom_path=None, plugin_dir="plugins", lang="en"):
        if rom_path is not None and not isinstance(rom_path, str):
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")

        # Загружаем сохраненные настройки
        self.load_saved_settings()

        self.i18n = I18N(default_lang=self.ui_lang.get())
        self.root = root
        self.root.title(self.i18n.t("app.title"))
        self.root.geometry("1100x700")
        self._set_app_icon()

        # Инициализация компонентов
        self.rom_path = tk.StringVar(value=rom_path or "")
        self.plugin_dir = plugin_dir
        self.plugin_manager = PluginManager(plugin_dir)
        self.guide_manager = GuideManager()
        self.current_guide = None
        self.current_results = None
        self.current_rom = None
        self.text_injector = None
        self.current_segment = None
        self.current_entries = None
        self.current_entry_index = 0

        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Добавляем переменную для текущего языка интерфейса
        self.ui_lang = tk.StringVar(value=lang)

        self.show_warning_dialog()
        self._setup_ui()
        self._setup_context_menu()

        # Если указан ROM при запуске, сразу загружаем
        if rom_path:
            self.update_game_info()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""

        # Создаем вкладки
        self.tab_control = ttk.Notebook(self.root)

        # Вкладка извлечения текста
        self.extract_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.extract_tab, text=self.i18n.t("tab.extract"))

        # Вкладка редактирования и локализации
        self.edit_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.edit_tab, text=self.i18n.t("tab.edit"))

        # Вкладка руководства
        self.guide_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Вкладка диагностики
        self.diagnostics_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.diagnostics_tab, text=self.i18n.t("diagnostics.tab"))
        self._setup_diagnostics_tab()

        # Вкладка настроек
        self.settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.settings_tab, text=self.i18n.t("tab.settings"))
        self.tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # Вкладка о программе
        self.about_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.about_tab, text=self.i18n.t("tab.about"))

        self.tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # Добавляем статус-бар
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side="bottom", fill="x")

        self.status_label = ttk.Label(self.status_frame, text=self.i18n.t("status.ready"))
        self.status_label.pack(side="left", padx=5, pady=2)

        self.progress = ttk.Progressbar(self.status_frame, orient="horizontal", mode="determinate", length=200)
        self.progress.pack(side="right", padx=5, pady=2)

        # Добавляем кнопку отмены (но не отображаем её изначально)
        self.cancel_button = ttk.Button(
            self.status_frame,
            text=self.i18n.t("cancel"),
            command=self._cancel_extraction
        )

        # Настройка вкладки извлечения
        self._setup_extract_tab()

        # Настройка вкладки редактирования
        self._setup_edit_tab()

        # Настройка вкладки настроек
        self._setup_settings_tab()

        # Настройка вкладки руководства
        self._setup_guide_tab()

        # Настройка вкладки о программе
        self._setup_about_tab()

        # Инициализируем статус
        self.set_status(self.i18n.t("status.ready"))

    def _setup_extract_tab(self):
        """Настройка вкладки извлечения текста"""
        # Верхняя панель: выбор ROM и кнопки
        top_frame = ttk.Frame(self.extract_tab, padding="10")
        top_frame.pack(fill="x", expand=False)

        ttk.Label(top_frame, text=self.i18n.t("rom.file")).pack(side="left", padx=(0, 5))
        ttk.Entry(top_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, 5))
        ttk.Button(top_frame, text=self.i18n.t("browse"), command=self.browse_rom).pack(side="left", padx=(0, 10))
        ttk.Button(top_frame, text=self.i18n.t("extract.text"), command=self.extract_text).pack(side="left")

        # Информационная панель
        info_frame = ttk.LabelFrame(self.extract_tab, text=self.i18n.t("game.info"), padding="10")
        info_frame.pack(fill="x", expand=False, padx=10, pady=(0, 10))

        self.game_info_labels = {}

        info_items = [
            ("game.title", "title"),
            ("system", "system"),
            ("cartridge.type", "cartridge_type"),
            ("rom.size", "rom_size"),
            ("supported.plugin", "supported_plugin")
        ]

        for i18n_key, data_key in info_items:
            row = ttk.Frame(info_frame)
            row.pack(fill="x", expand=True)

            # Создаем метку с названием
            label = ttk.Label(row, text=self.i18n.t(i18n_key) + ":", width=26)
            label.pack(side="left")

            # Создаем метку с данными
            value_label = ttk.Label(row, text="---", wraplength=600)
            value_label.pack(side="left", fill="x", expand=True)

            # Сохраняем метку для последующего обновления
            self.game_info_labels[data_key] = {
                "label": label,
                "value": value_label
            }

        # Основная панель с результатами
        main_frame = ttk.Frame(self.extract_tab, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Левая панель: список сегментов
        left_frame = ttk.LabelFrame(main_frame, text=self.i18n.t("text.segments"), padding="5")
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        # Контейнер для списка сегментов со скроллбаром
        segments_container = ttk.Frame(left_frame)
        segments_container.pack(fill="both", expand=True)

        self.segments_list = tk.Listbox(segments_container, width=25, height=20)
        segments_scrollbar = ttk.Scrollbar(segments_container, orient="vertical", command=self.segments_list.yview)

        self.segments_list.pack(side="left", fill="both", expand=True)
        segments_scrollbar.pack(side="right", fill="y")

        self.segments_list.config(yscrollcommand=segments_scrollbar.set)
        self.segments_list.bind('<<ListboxSelect>>', self.on_segment_select)

        # Правая панель: просмотр текста
        right_frame = ttk.LabelFrame(main_frame, text=self.i18n.t("segment.content"), padding="5")
        right_frame.pack(side="right", fill="both", expand=True)

        # Панель инструментов для просмотра
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill="x", expand=False, pady=(0, 5))

        ttk.Button(toolbar, text=self.i18n.t("export.json"), command=self.export_json).pack(side="left", padx=2)
        ttk.Button(toolbar, text=self.i18n.t("export.txt"), command=self.export_txt).pack(side="left", padx=2)
        ttk.Button(toolbar, text=self.i18n.t("extract.text"), command=self.switch_to_edit_tab).pack(side="left", padx=2)

        self.text_output = scrolledtext.ScrolledText(
            right_frame,
            wrap="word",
            font=("Consolas", 10),
            state="normal"
        )
        self.text_output.pack(fill="both", expand=True)

        # # Текстовая область с прокруткой
        # text_frame = ttk.Frame(right_frame)
        # text_frame.pack(fill="both", expand=True)
        #
        # self.text_output = scrolledtext.ScrolledText(text_frame, wrap="word", font=("Consolas", 10))
        # self.text_output.pack(side="left", fill="both", expand=True)
        #
        # scrollbar = ttk.Scrollbar(text_frame, command=self.text_output.yview)
        # scrollbar.pack(side="right", fill="y")
        #
        # self.text_output.config(yscrollcommand=scrollbar.set)

    def _setup_edit_tab(self):
        """Настройка вкладки редактирования текста"""
        rom_frame = ttk.LabelFrame(self.edit_tab, text=self.i18n.t("rom.file"), padding="10")
        rom_frame.pack(fill="x", expand=False, padx=10, pady=10)

        ttk.Entry(rom_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, 5))
        ttk.Button(rom_frame, text=self.i18n.t("browse"), command=self.browse_rom).pack(side="left", padx=(0, 10))
        ttk.Button(rom_frame, text=self.i18n.t("extract.text"), command=self.load_for_editing).pack(side="left")

        # Панель выбора сегмента
        segment_frame = ttk.LabelFrame(self.edit_tab, text=self.i18n.t("text.segments"), padding="10")
        segment_frame.pack(fill="x", expand=False, padx=10, pady=(0, 10))

        self.segment_var = tk.StringVar()
        self.segment_combo = ttk.Combobox(segment_frame, textvariable=self.segment_var, state="readonly", width=30)
        self.segment_combo.pack(side="left", padx=(0, 10))
        self.segment_combo.bind("<<ComboboxSelected>>", self.on_segment_combo_select)

        ttk.Button(segment_frame, text=self.i18n.t("extract.text"), command=self.load_segment).pack(side="left")

        # Панель для отображения текущей записи
        entry_frame = ttk.Frame(self.edit_tab, padding="5")
        entry_frame.pack(fill="both", expand=True)

        # Панель кнопок
        button_frame = ttk.Frame(entry_frame)
        button_frame.pack(fill="x", pady=(0, 0))

        ttk.Button(button_frame, text=self.i18n.t("save.translation"),
                   command=self.save_translation).pack(side="left", padx=2)
        ttk.Button(button_frame, text=self.i18n.t("inject.translation"),
                   command=self.inject_translation).pack(side="left", padx=2)

        # Добавляем пагинацию
        pagination_frame = ttk.Frame(entry_frame)
        pagination_frame.pack(fill="x", pady=(0, 10))

        self.page_var = tk.IntVar(value=1)
        self.total_pages_var = tk.IntVar(value=1)

        # ttk.Label(pagination_frame, text=self.i18n.t("page")).pack(side="left")
        # ttk.Entry(pagination_frame, textvariable=self.page_var, width=5).pack(side="left")
        # ttk.Label(pagination_frame, text=self.i18n.t("of")).pack(side="left")
        # ttk.Label(pagination_frame, textvariable=self.total_pages_var).pack(side="left")

        # Панель с оригинальным текстом
        original_frame = ttk.LabelFrame(entry_frame, text=self.i18n.t("original.text"))
        original_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.original_text = scrolledtext.ScrolledText(original_frame, wrap="word",
                                                       height=8, state="disabled")
        self.original_text.pack(fill="both", expand=True)

        # Панель с переводом
        translation_frame = ttk.LabelFrame(entry_frame, text=self.i18n.t("translated.text"))
        translation_frame.pack(fill="both", expand=True)

        self.translated_text = scrolledtext.ScrolledText(translation_frame, wrap="word",
                                                         height=8)
        self.translated_text.pack(fill="both", expand=True)

        # Панель навигации
        nav_frame = ttk.Frame(entry_frame)
        nav_frame.pack(fill="x", pady=(5, 0))

        self.prev_btn = ttk.Button(nav_frame, text=self.i18n.t("prev.entry"),
                                   command=self.prev_entry)
        self.prev_btn.pack(side="left")

        self.entry_label = ttk.Label(nav_frame, text="")
        self.entry_label.pack(side="left", padx=0)

        self.next_btn = ttk.Button(nav_frame, text=self.i18n.t("next.entry"),
                                   command=self.next_entry)
        self.next_btn.pack(side="right")

        # Добавляем поддержку горячих клавиш
        self.original_text.bind("<Control-c>", lambda e: self.copy_original_text())
        self.translated_text.bind("<Control-v>", lambda e: self.paste_translation())
        self.translated_text.bind("<Control-V>", lambda e: self.paste_translation())
        self.translated_text.bind("<Control-Left>", self.prev_segment)
        self.translated_text.bind("<Control-Right>", self.next_segment)

    def _setup_settings_tab(self):
        """Настройка вкладки настроек"""
        settings_frame = ttk.LabelFrame(self.settings_tab, text=self.i18n.t("settings.localization"), padding="20")
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Язык интерфейса
        ui_lang_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("ui.language"), padding="10")
        ui_lang_frame.pack(fill="x", expand=False, pady=10)

        ttk.Label(ui_lang_frame, text=self.i18n.t("ui.language")).pack(side="left", padx=(0, 10))

        self.ui_lang = tk.StringVar(value=self.i18n.current_lang)
        lang_combo = ttk.Combobox(ui_lang_frame, textvariable=self.ui_lang, state="readonly", width=15)
        lang_combo['values'] = list(self.i18n.get_available_languages().keys())
        lang_combo.pack(side="left")
        lang_combo.current(list(self.i18n.get_available_languages().keys()).index(self.i18n.current_lang))
        lang_combo.bind("<<ComboboxSelected>>", self.change_ui_language)

        # Язык перевода
        translation_lang_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("target.language"), padding="10")
        translation_lang_frame.pack(fill="x", expand=False, pady=10)

        ttk.Label(translation_lang_frame, text=self.i18n.t("target.language")).pack(side="left", padx=(0, 10))

        self.target_lang = tk.StringVar(value="ru")
        lang_combo = ttk.Combobox(translation_lang_frame, textvariable=self.target_lang, state="readonly", width=15)
        lang_combo['values'] = ('en', 'ru', 'ja')  # 'es', 'fr', 'de'
        lang_combo.pack(side="left")
        lang_combo.current(1)  # Русский по умолчанию

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("encoding.type"), padding="10")
        encoding_frame.pack(fill="x", expand=False, pady=10)

        ttk.Label(encoding_frame, text=self.i18n.t("encoding.type")).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)

        self.encoding_type = tk.StringVar(value="auto")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("auto.detect"), variable=self.encoding_type, value="auto").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("english"), variable=self.encoding_type, value="en").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("japanese"), variable=self.encoding_type, value="ja").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("russian"), variable=self.encoding_type, value="ru").grid(row=3, column=1, sticky="w")

        # Создать конфигурацию
        ttk.Button(settings_frame, text=self.i18n.t("create.config"), command=self.create_user_config).pack(pady=10)

        # Кнопка применения кодировки
        ttk.Button(settings_frame, text=self.i18n.t("apply.encoding"), command=self.apply_encoding).pack(pady=10)

        # Сохранение настроек
        ttk.Button(settings_frame, text=self.i18n.t("save.settings"), command=self.save_settings).pack(pady=10)

    def refresh_guide_tab(self):
        """Обновляет текст вкладки руководства"""
        if hasattr(self, 'load_template_btn'):
            self.load_template_btn.config(text=self.i18n.t("load.template"))
        if hasattr(self, 'save_guide_btn'):
            self.save_guide_btn.config(text=self.i18n.t("save.guide"))
        if hasattr(self, 'apply_guide_btn'):
            self.apply_guide_btn.config(text=self.i18n.t("apply.guide"))

    def create_user_config(self):
        """Создает пользовательскую конфигурацию на основе текущих настроек"""
        if not self.current_rom:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        # Создаем базовую структуру конфигурации
        game_id = self.current_rom.get_game_id()
        config = {
            "name": f"UserConfig_{game_id}",
            "description": f"Auto-generated config for {game_id}",
            "user_created": True,
            "game_id_pattern": f"^{game_id}$",
            "segments": []
        }

        # Попробуем определить сегменты автоматически
        try:
            # Создаем временный плагин для извлечения информации
            from core.extractor import TextExtractor
            extractor = TextExtractor(self.rom_path.get())

            # Попробуем использовать автоопределение
            from plugins.auto_detect import AutoDetectPlugin
            plugin = AutoDetectPlugin()
            segments = plugin.get_text_segments(self.current_rom)

            for seg in segments:
                # Используем extractor для определения таблицы символов
                charmap = None
                if seg['decoder']:
                    # Если декодер уже определен, извлекаем таблицу символов
                    charmap = {}
                    for byte, char in seg['decoder'].charmap.items():
                        charmap[f"0x{byte:02X}"] = char

                config["segments"].append({
                    "name": seg["name"],
                    "start": f"0x{seg['start']:04X}",
                    "end": f"0x{seg['end']:04X}",
                    "charmap": charmap,
                    "compression": seg.get('compression')
                })

            # Сохраняем конфигурацию
            config_dir = Path("plugins/config")
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / f"{game_id.lower()}_config.json"

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("config.created", path=str(config_path))
            )

        except Exception as e:
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("config.error") + f": {str(e)}"
            )

        # Сохраняем конфигурацию
        config_dir = Path("plugins/config")
        config_dir.mkdir(parents=True, exist_ok=True)

        # Используем имя игры из заголовка ROM
        safe_title = re.sub(r'\W+', '', self.current_rom.header['title']).lower()
        config_path = config_dir / f"{safe_title}_{self.current_rom.header['cartridge_type']:02X}.json"

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self.set_status(self.i18n.t("config.created"))
        messagebox.showinfo(
            self.i18n.t("success.title"),
            self.i18n.t("config.created", path=config_path)
        )

    def apply_encoding(self):
        """Применяет выбранную кодировку к текущему сегменту"""
        if not self.current_segment or not self.current_entries:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.segment")
            )
            return

        self.set_status(self.i18n.t("status.processing"), 50)

        encoding_type = self.encoding_type.get()

        # Определяем, какую таблицу символов использовать
        if encoding_type == "auto":
            charmap = auto_detect_charmap(self.current_rom.data, self.current_segment['start'])
        elif encoding_type == "en":
            charmap = get_generic_english_charmap()
        elif encoding_type == "ja":
            charmap = get_generic_japanese_charmap()
        elif encoding_type == "ru":
            charmap = get_generic_russian_charmap()
        else:
            charmap = get_generic_english_charmap()

        # Создаем новый декодер с выбранной таблицей
        from core.decoder import CharMapDecoder
        self.current_segment['decoder'] = CharMapDecoder(charmap)

        # Перезагружаем сегмент с новой кодировкой
        self.load_segment()
        self.set_status(self.i18n.t("encoding.applied"))
        messagebox.showinfo(
            self.i18n.t("success.title"),
            self.i18n.t("encoding.applied")
        )

    def load_guide(self):
        """Загружает руководство для текущей игры"""
        if not self.current_rom:
            return

        game_id = self.current_rom.get_game_id()
        self.current_guide = self.guide_manager.get_guide(game_id)

        if not self.current_guide:
            self.current_guide = self.guide_manager.create_template(game_id)

        self.display_guide()

    def display_guide(self):
        """Отображает текущее руководство"""
        if not self.current_guide:
            return

        self.guide_text.config(state="normal")
        self.guide_text.delete(1.0, tk.END)

        # Заголовок
        self.guide_text.insert(tk.END, f"Руководство для {self.current_guide.get('game_id', 'игры')}\n\n", "header")
        self.guide_text.insert(tk.END, f"{self.current_guide.get('description', '')}\n\n")

        # Шаги
        self.guide_text.insert(tk.END, "Пошаговая инструкция:\n", "section")
        steps = self.current_guide.get('steps', [])
        for i, step in enumerate(steps, 1):
            self.guide_text.insert(tk.END, f"{i}. {step.get('title', '')}\n", "step")
            self.guide_text.insert(tk.END, f"   {step.get('description', '')}\n\n")

        # Советы
        tips = self.current_guide.get('tips', [])
        if tips:
            self.guide_text.insert(tk.END, "Полезные советы:\n", "section")
            for i, tip in enumerate(tips, 1):
                self.guide_text.insert(tk.END, f"• {tip}\n")

        # Настройка стилей
        self.guide_text.tag_config("header", font=("Consolas", 10, "bold"))
        self.guide_text.tag_config("section", font=("Consolas", 10, "underline"))
        self.guide_text.tag_config("step", font=("Consolas", 10, "bold"))

        self.guide_text.config(state="disabled")

    def load_guide_template(self):
        """Загружает шаблон руководства"""
        if not self.current_rom:
            messagebox.showwarning("Предупреждение", "Сначала загрузите ROM-файл")
            return

        game_id = self.current_rom.get_game_id()
        self.current_guide = self.guide_manager.create_template(game_id)
        self.display_guide()

    def save_guide(self):
        """Сохраняет текущее руководство"""
        if not self.current_guide or not self.current_rom:
            return

        if self.guide_manager.save_guide(self.current_rom.get_game_id(), self.current_guide):
            messagebox.showinfo("Успех", "Руководство сохранено")
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить руководство")

    def apply_guide(self):
        """Применяет рекомендации из руководства к извлечению текста"""
        if not self.current_guide or not self.current_rom:
            return

        # Здесь можно добавить логику применения рекомендаций
        messagebox.showinfo("Информация",
                            "Рекомендации из руководства применены.\n"
                            "Теперь вы можете извлечь текст с учетом специфики этой игры.")

    def set_status(self, message: str, progress: int = 0):
        """Устанавливает статус и прогресс"""
        self.status_label.config(text=message)
        self.progress["value"] = progress
        self.root.update_idletasks()

    def start_progress(self, message: str, max_value: int = 100):
        """Начинает индикацию прогресса"""
        self.set_status(message, 0)
        self.progress['maximum'] = max_value
        self.root.update_idletasks()

    def update_progress(self, value: int, message: str = None):
        """Обновляет прогресс"""
        self.progress['value'] = value
        if message:
            self.status_label.config(text=message)
        self.root.update_idletasks()

    def end_progress(self, message: str = None):
        """Завершает индикацию прогресса"""
        if message:
            self.set_status(message)
        else:
            self.set_status(self.i18n.t("status.ready"))
        self.progress['value'] = 0
        self.root.update_idletasks()

    def browse_rom(self):
        """Выбор ROM-файла"""
        path = filedialog.askopenfilename(
            title=self.i18n.t("file.select.rom"),
            filetypes=[
                ("GB/GBC/GBA ROM files", "*.gb *.gbc *.sgb *.gba"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.rom_path.set(path)
            self.set_status(self.i18n.t("rom.loading"))
            self.update_game_info()
            self.set_status(self.i18n.t("rom.loaded"))

    def update_game_info(self):
        """Обновление информации об игре"""
        if not self.rom_path.get():
            return

        try:
            rom = GameBoyROM(self.rom_path.get())
            self.current_rom = rom

            # Определяем систему
            system_name = {
                'gb': 'Game Boy',
                'gbc': 'Game Boy Color',
                'gba': 'Game Boy Advance'
            }.get(rom.system, rom.system.upper())

            # Обновляем информацию
            self.game_info_labels["title"]["value"].config(text=rom.header['title'])
            self.game_info_labels["system"]["value"].config(text=system_name)
            self.game_info_labels["cartridge_type"]["value"].config(text=f"0x{rom.header['cartridge_type']:02X}")
            self.game_info_labels["rom_size"]["value"].config(text=f"{len(rom.data) // 1024} KB")

            # Проверяем поддержку игры
            game_id = rom.get_game_id()
            plugin = self.plugin_manager.get_plugin(game_id, rom.system)
            if plugin:
                self.game_info_labels["supported_plugin"]["value"].config(text=plugin.__class__.__name__)
            else:
                self.game_info_labels["supported_plugin"]["value"].config(text=self.i18n.t("not_found"))

        except Exception as e:
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("rom.load.error", error=str(e))
            )

    def extract_text(self):
        """Извлечение текста из ROM"""
        if not self.rom_path.get():
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        try:
            self.cancel_requested = False
            self.cancellation_token = CancellationToken()
            self.set_status(self.i18n.t("text.extracting"), 0)

            # Добавляем кнопку отмены
            self.cancel_button = ttk.Button(
                self.status_frame,
                text=self.i18n.t("cancel"),
                command=self._cancel_extraction
            )
            self.cancel_button.pack(side="right", padx=5)

            # Запускаем извлечение в отдельном потоке
            def extract_task():
                try:
                    extractor = TextExtractor(
                        self.rom_path.get(),
                        cancellation_token=self.cancellation_token
                    )
                    self.current_results = extractor.extract()
                    return True
                except Exception as e:
                    self.extraction_error = e
                    return False

            # Запускаем задачу извлечения
            extraction_thread = threading.Thread(target=extract_task)
            extraction_thread.daemon = True
            extraction_thread.start()

            # Ожидаем завершения с обновлением прогресса
            start_time = time.time()
            last_update = 0

            while extraction_thread.is_alive():
                elapsed = time.time() - start_time

                # Обновляем прогресс каждые 0.5 секунды
                if elapsed - last_update > 0.5:
                    # Показываем, что процесс идет
                    progress = 5 + (min(90, int(elapsed) * 2))  # Постепенно увеличиваем прогресс
                    self.set_status(
                        f"{self.i18n.t('text.extracting')} ({int(elapsed)}s)",
                        progress
                    )
                    last_update = elapsed

                # Проверяем, не запрошена ли отмена
                if self.cancel_requested:
                    self.cancellation_token.cancel()

                time.sleep(0.1)
                self.root.update()

            # Удаляем кнопку отмены
            if hasattr(self, 'cancel_button') and self.cancel_button.winfo_exists():
                self.cancel_button.destroy()

            # Проверяем, была ли отмена
            if self.cancel_requested:
                self.set_status(self.i18n.t("status.ready"))
                return

            # Проверяем результат
            if hasattr(self, 'extraction_error'):
                raise self.extraction_error

            # Очистка списка сегментов
            self.segments_list.delete(0, tk.END)

            # Заполнение списка сегментов
            for segment_name in self.current_results.keys():
                self.segments_list.insert(tk.END, segment_name)

            # Выбираем первый сегмент
            if self.segments_list.size() > 0:
                self.segments_list.selection_set(0)
                self.on_segment_select(None)

            self.set_status(self.i18n.t("text.extracted"))
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("extraction.success")
            )

        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("extraction.error", error=str(e))
            )
        finally:
            # Удаляем кнопку отмены в любом случае
            if hasattr(self, 'cancel_button') and self.cancel_button.winfo_exists():
                self.cancel_button.destroy()

    def _cancel_extraction(self):
        """Отмена процесса извлечения текста"""
        self.cancel_requested = True
        self.set_status(self.i18n.t("extraction.canceled"))

    def on_segment_select(self, event):
        """Обработка выбора сегмента"""
        # Очищаем текстовую область
        self.text_output.delete(1.0, tk.END)

        if not self.current_results:
            self.text_output.insert(tk.END, "Нет данных для отображения")
            return

        # Получаем выбранный сегмент
        selection = self.segments_list.curselection()
        if not selection:
            return

        segment_index = selection[0]
        segment_name = self.segments_list.get(segment_index)

        # Проверяем, есть ли такой сегмент в результатах
        if segment_name not in self.current_results:
            self.text_output.insert(tk.END, "Сегмент не найден")
            return

        # Отображаем содержимое сегмента в текстовой области
        entries = self.current_results[segment_name]
        for i, entry in enumerate(entries):
            self.text_output.insert(tk.END, f"[{i + 1:04d}] {entry['text']}\n\n")

        # Прокручиваем к началу
        self.text_output.see(1.0)

        self.current_segment = segment_name
        self.current_entries = self.current_results[segment_name]
        self.current_entry_index = 0
        self.set_status(self.i18n.t("text.extracted"))

    def export_json(self):
        """Экспорт результатов в JSON"""
        if not self.current_results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title=self.i18n.t("file.export.json")
        )

        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.current_results, f, indent=2, ensure_ascii=False)
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("export.json.success")
            )

    def export_txt(self):
        """Экспорт результатов в TXT"""
        if not self.current_results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title=self.i18n.t("file.export.txt")
        )

        if path:
            with open(path, 'w', encoding='utf-8') as f:
                for segment_name, messages in self.current_results.items():
                    f.write(f"== {segment_name.upper()} ==\n")
                    for msg in messages:
                        f.write(f"{msg['offset']:04X}: {msg['text']}\n")
                    f.write("\n")
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("export.txt.success")
            )

    def switch_to_edit_tab(self):
        """Переключение на вкладку редактирования"""
        if not self.current_results:
            messagebox.showwarning("Предупреждение", "Сначала извлеките текст")
            return

        # Автоматически переключаемся на вкладку редактирования
        self.tab_control.select(self.edit_tab)

        # Заполняем список сегментов
        self.segment_combo['values'] = list(self.current_results.keys())
        if self.segment_combo['values']:
            self.segment_combo.current(0)

    def load_for_editing(self):
        """Загрузка ROM для редактирования"""
        rom_path = self.rom_path.get()
        if not rom_path:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        try:
            # Проверяем, что файл существует
            if not os.path.exists(rom_path):
                raise FileNotFoundError(f"Файл не найден: {rom_path}")

            # Проверяем размер файла
            file_size = os.path.getsize(rom_path)
            if file_size < 32 * 1024:  # 32 KB
                raise ValueError("ROM файл слишком маленький")

            self.current_rom = GameBoyROM(rom_path)
            self.text_injector = TextInjector(rom_path)

            # Определяем систему
            system_name = {
                'gb': 'Game Boy',
                'gbc': 'Game Boy Color',
                'gba': 'Game Boy Advance'
            }.get(self.current_rom.system, self.current_rom.system.upper())

            # Обновляем информацию
            self.game_info_labels["title"]["value"].config(text=self.current_rom.header['title'])
            self.game_info_labels["system"]["value"].config(text=system_name)
            self.game_info_labels["cartridge_type"]["value"].config(text=f"0x{self.current_rom.header['cartridge_type']:02X}")
            self.game_info_labels["rom_size"]["value"].config(text=f"{len(self.current_rom.data) // 1024} KB")

            # Заполняем список сегментов
            game_id = self.current_rom.get_game_id()
            plugin = self.plugin_manager.get_plugin(game_id, self.current_rom.system)

            if plugin:
                segments = plugin.get_text_segments(self.current_rom)
                self.segment_combo['values'] = [seg['name'] for seg in segments]
                if self.segment_combo['values']:
                    self.segment_combo.current(0)
                    self.load_segment()
            else:
                messagebox.showwarning(
                    self.i18n.t("warning.title"),
                    self.i18n.t("plugin.not.found")
                )

        except Exception as e:
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("rom.load.error", error=str(e))
            )

    def _get_resource_path(self, relative_path):
        """Получает абсолютный путь к ресурсу"""

        try:
            # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            # Обычный запуск Python скрипта
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def load_saved_settings(self):
        """Загружает сохраненные настройки"""
        settings_path = Path(self._get_resource_path("settings/settings.json"))
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.ui_lang = tk.StringVar(value=settings.get("ui_language", "en"))
                self.target_lang = tk.StringVar(value=settings.get("target_language", "ru"))
                self.encoding_type = tk.StringVar(value=settings.get("encoding_type", "auto"))
            except Exception as e:
                print(f"Ошибка загрузки настроек: {str(e)}")
                self._init_default_settings()
        else:
            self._init_default_settings()

    def _init_default_settings(self):
        """Инициализирует настройки по умолчанию"""
        self.ui_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="ru")
        self.encoding_type = tk.StringVar(value="auto")

    def on_segment_combo_select(self, event):
        """Обработка выбора сегмента в комбобоксе"""
        pass

    def load_segment(self):
        """Загрузка выбранного сегмента для редактирования"""
        if not self.current_rom or not self.text_injector:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        segment_name = self.segment_var.get()
        if not segment_name:
            return

        try:
            self.set_status(self.i18n.t("status.loading"), 0)

            # ИСПОЛЬЗУЕМ УЖЕ ИЗВЛЕЧЕННЫЕ РЕЗУЛЬТАТЫ
            if not hasattr(self, 'current_results') or not self.current_results:
                messagebox.showwarning(
                    self.i18n.t("warning.title"),
                    self.i18n.t("extract.text.first")
                )
                return

            # Проверяем, есть ли такой сегмент в результатах
            if segment_name not in self.current_results:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("segment.not.found")
                )
                self.set_status(self.i18n.t("status.error"))
                return

            self.current_segment = segment_name
            self.current_entries = self.current_results[segment_name]
            self.current_entry_index = 0

            self._display_current_entry()
            self.set_status(self.i18n.t("segment.loaded"))

        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("segment.load.error", error=str(e))
            )

    def _display_current_entry(self):
        """Отображение текущей записи для редактирования"""
        logger = logging.getLogger('gb2text.gui')

        if not self.current_entries:
            logger.warning("Попытка отобразить запись, но current_entries пуст")
            return

        try:
            # Определяем текущую страницу и размер страницы
            page_size = 20  # Количество записей на странице
            current_page = self.page_var.get()
            total_pages = (len(self.current_entries) + page_size - 1) // page_size

            # Обновляем информацию о текущей странице
            self.total_pages_var.set(total_pages)
            self.page_var.set(min(current_page, total_pages))

            # Вычисляем индекс записи на текущей странице
            page_index = (current_page - 1) * page_size
            display_entries = self.current_entries[page_index:page_index + page_size]

            # # Обновляем информацию о текущей записи
            # self.entry_label.config(
            #     text=f"{self.i18n.t('entry')}: {page_index + 1}-{min(page_index + len(display_entries), len(self.current_entries))} из {len(self.current_entries)}"
            # )

            # Обновляем информацию о текущей записи
            self.entry_label.config(text=f"{self.i18n.t('entry')}: {self.current_entry_index + 1} из {len(self.current_entries)}")

            # Отображаем оригинал
            self.original_text.config(state="normal")
            self.original_text.delete(1.0, tk.END)

            if display_entries:
                for i, entry in enumerate(display_entries):
                    self.original_text.insert(tk.END, f"[{page_index + i + 1}] {entry['text']}\n\n")

            self.original_text.config(state="disabled")

            # Отображаем перевод
            self.translated_text.config(state="normal")
            self.translated_text.delete(1.0, tk.END)

            if display_entries:
                for i, entry in enumerate(display_entries):
                    translation = entry.get('translation', '')
                    self.translated_text.insert(tk.END, f"[{page_index + i + 1}] {translation}\n\n")

            self.translated_text.config(state="normal")

        except Exception as e:
            logger.error(f"Ошибка при отображении записи: {str(e)}")
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("display.error", error=str(e))
            )

    def prev_entry(self, event=None):
        """Переход к предыдущей записи или сегменту"""
        if self.current_entry_index > 0:
            self.current_entry_index -= 1
            self._display_current_entry()
        else:
            # Переход к последней записи предыдущего сегмента
            segment_names = list(self.current_results.keys())
            current_index = segment_names.index(self.current_segment)

            if current_index > 0:
                prev_segment = segment_names[current_index - 1]
                self.current_segment = prev_segment
                self.current_entries = self.current_results[prev_segment]
                self.current_entry_index = len(self.current_entries) - 1
                self._display_current_entry()
                self._update_segment_selector()

    def next_entry(self, event=None):
        """Переход к следующей записи или сегменту"""
        if self.current_entry_index < len(self.current_entries) - 1:
            self.current_entry_index += 1
            self._display_current_entry()
        else:
            # Переход к первой записи следующего сегмента
            segment_names = list(self.current_results.keys())
            current_index = segment_names.index(self.current_segment)

            if current_index < len(segment_names) - 1:
                next_segment = segment_names[current_index + 1]
                self.current_segment = next_segment
                self.current_entries = self.current_results[next_segment]
                self.current_entry_index = 0
                self._display_current_entry()
                self._update_segment_selector()

    def _update_segment_selector(self):
        """Обновляет выбор в селекторе сегментов"""
        if hasattr(self, 'segment_combo') and self.current_segment in self.segment_combo['values']:
            self.segment_combo.current(self.segment_combo['values'].index(self.current_segment))

    def prev_segment(self, event=None):
        """Переход к предыдущему сегменту"""
        segment_names = list(self.current_results.keys())
        current_index = segment_names.index(self.current_segment)

        if current_index > 0:
            prev_segment = segment_names[current_index - 1]
            self.current_segment = prev_segment
            self.current_entries = self.current_results[prev_segment]
            self.current_entry_index = 0
            self._display_current_entry()
            self._update_segment_selector()

    def next_segment(self, event=None):
        """Переход к следующему сегменту"""
        segment_names = list(self.current_results.keys())
        current_index = segment_names.index(self.current_segment)

        if current_index < len(segment_names) - 1:
            next_segment = segment_names[current_index + 1]
            self.current_segment = next_segment
            self.current_entries = self.current_results[next_segment]
            self.current_entry_index = 0
            self._display_current_entry()
            self._update_segment_selector()

    def copy_original_text(self):
        """Копирование оригинального текста в буфер обмена"""
        if not self.current_entries or self.current_entry_index < 0:
            return

        original_text = self.current_entries[self.current_entry_index]['text']
        self.root.clipboard_clear()
        self.root.clipboard_append(original_text)
        self.root.update()  # Это нужно, чтобы буфер обмена обновился

        self.set_status(self.i18n.t("text.copied"), 100)
        messagebox.showinfo(
            self.i18n.t("success.title"),
            self.i18n.t("original.copied")
        )

    def paste_translation(self):
        """Вставка перевода из буфера обмена"""
        try:
            # Получаем текст из буфера обмена
            clipboard_text = self.root.clipboard_get()

            # Очищаем текущее поле перевода
            self.translated_text.delete(1.0, tk.END)

            # Вставляем текст
            self.translated_text.insert(tk.END, clipboard_text)

            self.set_status(self.i18n.t("translation.pasted"), 100)
        except tk.TclError:
            # Буфер обмена пуст
            messagebox.showinfo(
                self.i18n.t("info.title"),
                self.i18n.t("clipboard.empty")
            )

    def _setup_context_menu(self):
        """Настройка контекстного меню для текстовых полей"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(
            label=self.i18n.t("copy.original"),
            command=self.copy_original_text
        )
        self.context_menu.add_command(
            label=self.i18n.t("paste.translation"),
            command=self.paste_translation
        )

        # Привязываем контекстное меню к текстовым полям
        self.original_text.bind("<Button-3>", self.show_context_menu)
        self.translated_text.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def save_translation(self):
        """Сохранение перевода текущей записи"""
        if not self.current_entries:
            return

        translation = self.translated_text.get(1.0, tk.END).strip()
        if not translation:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.translation")
            )
            return

        self.set_status(self.i18n.t("text.saving"), 50)

        # Здесь сохраняем перевод
        entry = self.current_entries[self.current_entry_index]
        print(f"Сохранен перевод для записи {self.current_entry_index}: {translation[:50]}...")

        # Сохранение в файл или базу данных
        # ...

        self.set_status(self.i18n.t("text.saved"))
        messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("translation.saved"))

    def _setup_about_tab(self):
        """Настройка вкладки 'О программе'"""
        about_frame = ttk.Frame(self.about_tab, padding="20")
        about_frame.pack(fill="both", expand=True)

        # Заголовок
        title_label = ttk.Label(
            about_frame,
            text=f"GB Text Extractor & Translator",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # Версия
        version = self.get_version()
        version_label = ttk.Label(
            about_frame,
            text=self.i18n.t("about.version", version=version),
            font=("Helvetica", 10)
        )
        version_label.pack(anchor="w", pady=(0, 15))

        # Описание
        description = ttk.Label(
            about_frame,
            text=self.i18n.t("about.description"),
            wraplength=700,
            justify="left"
        )
        description.pack(anchor="w", pady=(0, 20))

        # Юридическое предупреждение
        legal_frame = ttk.LabelFrame(about_frame, text=self.i18n.t("about.legal.title"), padding="10")
        legal_frame.pack(fill="x", expand=False, pady=(0, 20))

        legal_text = ttk.Label(
            legal_frame,
            text=self.i18n.t("about.legal.text"),
            wraplength=700,
            justify="left"
        )
        legal_text.pack(anchor="w")

        # Ссылки
        links_frame = ttk.LabelFrame(about_frame, text=self.i18n.t("about.links"), padding="10")
        links_frame.pack(fill="x", expand=False, pady=(0, 20))

        # GitHub ссылка
        github_frame = ttk.Frame(links_frame)
        github_frame.pack(fill="x", expand=False, pady=(0, 5))

        github_label = ttk.Label(
            github_frame,
            text=self.i18n.t("about.github") + ":",
            font=("Helvetica", 9, "bold")
        )
        github_label.pack(side="left", padx=(0, 5))

        github_link = ttk.Label(
            github_frame,
            text="github.com/Far-g-Us/GB2Text",
            foreground="blue",
            cursor="hand2",
            font=("Helvetica", 9)
        )
        github_link.pack(side="left")
        github_link.bind("<Button-1>", lambda e: self.open_url("https://github.com/Far-g-Us/GB2Text"))

        # # Документация ссылка
        # docs_frame = ttk.Frame(links_frame)
        # docs_frame.pack(fill="x", expand=False, pady=(5, 0))
        #
        # docs_label = ttk.Label(
        #     docs_frame,
        #     text=self.i18n.t("about.documentation") + ":",
        #     font=("Helvetica", 9, "bold")
        # )
        # docs_label.pack(side="left", padx=(0, 5))
        #
        # docs_link = ttk.Label(
        #     docs_frame,
        #     text="gb-text-extractor.readthedocs.io",
        #     foreground="blue",
        #     cursor="hand2",
        #     font=("Helvetica", 9)
        # )
        # docs_link.pack(side="left")
        # docs_link.bind("<Button-1>", lambda e: self.open_url("https://gb-text-extractor.readthedocs.io"))


    def _refresh_ui(self):
        """Полностью обновляет интерфейс с новым языком"""
        # Сохраняем текущее состояние
        current_rom = self.rom_path.get()
        current_results = self.current_results
        current_segment = self.current_segment
        current_entry_index = self.current_entry_index

        # Пересоздаем интерфейс
        for widget in self.root.winfo_children():
            widget.destroy()

        # Пересоздаем UI с новым языком
        self._setup_ui()

        # Обновляем вкладку руководства
        self.refresh_guide_tab()

        # Восстанавливаем состояние
        if current_rom:
            self.rom_path.set(current_rom)
            self.update_game_info()

        if current_results:
            self.current_results = current_results
            # Заполняем список сегментов
            self.segments_list.delete(0, tk.END)
            for segment_name in self.current_results.keys():
                self.segments_list.insert(tk.END, segment_name)
            if self.segments_list.size() > 0:
                self.segments_list.selection_set(0)
                self.on_segment_select(None)

        if current_segment and current_entry_index >= 0:
            self.current_segment = current_segment
            self.current_entry_index = current_entry_index
            self._display_current_entry()

        self.set_status(self.i18n.t("status.ready"))

    def change_ui_language(self, event=None):
        """Изменяет язык интерфейса приложения"""
        new_lang = self.ui_lang.get()
        self.i18n.change_language(new_lang)

        # Обновляем все тексты в интерфейсе
        self.root.title(self.i18n.t("app.title"))

        # Обновляем названия вкладок
        self.tab_control.tab(self.extract_tab, text=self.i18n.t("tab.extract"))
        self.tab_control.tab(self.edit_tab, text=self.i18n.t("tab.edit"))
        self.tab_control.tab(self.settings_tab, text=self.i18n.t("tab.settings"))
        self.tab_control.tab(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Обновляем все метки
        self._refresh_ui()
        self._refresh_ui_labels()

        messagebox.showinfo(self.i18n.t("settings.saved"), self.i18n.t("settings.saved"))

    def _refresh_ui_labels(self):
        """Обновляет все текстовые метки в интерфейсе"""
        # Обновляем названия вкладок
        self.tab_control.tab(self.extract_tab, text=self.i18n.t("tab.extract"))
        self.tab_control.tab(self.edit_tab, text=self.i18n.t("tab.edit"))
        self.tab_control.tab(self.settings_tab, text=self.i18n.t("tab.settings"))
        self.tab_control.tab(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Обновляем заголовок информационной панели
        for widget in self.extract_tab.winfo_children():
            if isinstance(widget, ttk.LabelFrame) and widget.cget("text") == self.i18n.t("game.info"):
                widget.config(text=self.i18n.t("game.info"))

        # Обновляем метки в информационной панели
        info_items = [
            ("game.title", "title"),
            ("system", "system"),
            ("cartridge.type", "cartridge_type"),
            ("rom.size", "rom_size"),
            ("supported.plugin", "supported_plugin")
        ]

        for i18n_key, data_key in info_items:
            if data_key in self.game_info_labels:
                self.game_info_labels[data_key]["label"].config(text=self.i18n.t(i18n_key) + ":")

        # Обновляем другие метки
        if hasattr(self, 'load_template_btn'):
            self.load_template_btn.config(text=self.i18n.t("load.template"))
        if hasattr(self, 'save_guide_btn'):
            self.save_guide_btn.config(text=self.i18n.t("save.guide"))
        if hasattr(self, 'apply_guide_btn'):
            self.apply_guide_btn.config(text=self.i18n.t("apply.guide"))

    def _setup_diagnostics_tab(self):
        """Настройка вкладки диагностики"""
        diagnostics_frame = ttk.Frame(self.diagnostics_tab, padding="10")
        diagnostics_frame.pack(fill="both", expand=True)

        # Панель управления
        control_frame = ttk.Frame(diagnostics_frame)
        control_frame.pack(fill="x", expand=False, pady=(0, 10))

        ttk.Button(control_frame, text=self.i18n.t("diagnostics.start"),
                   command=self.run_diagnostics).pack(side="left", padx=5)
        ttk.Button(control_frame, text=self.i18n.t("save.log"),
                   command=self.save_log).pack(side="left", padx=5)

        # Текстовая область для логов
        self.log_text = scrolledtext.ScrolledText(diagnostics_frame, wrap="word", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

        # Автоматическая загрузка текущего лога
        self.load_current_log()

    def load_current_log(self):
        """Загружает текущий лог-файл в текстовую область"""
        try:
            with open('gb2text.log', 'r') as f:
                log_content = f.read()

            self.log_text.config(state="normal")
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, log_content)
            self.log_text.config(state="disabled")

            # Автопрокрутка к концу
            self.log_text.see(tk.END)
        except Exception as e:
            logger = logging.getLogger('gb2text.gui')
            logger.error(f"Не удалось загрузить лог-файл: {str(e)}")

    def run_diagnostics(self):
        """Запуск диагностического процесса"""
        if not self.current_rom:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        logger = logging.getLogger('gb2text.diagnostics')
        logger.info("Запуск диагностического процесса")

        self.set_status(self.i18n.t("diagnostics.running"), 0)

        # Сбор информации о ROM
        diagnostics_info = {
            "rom_path": self.rom_path.get(),
            "rom_size": len(self.current_rom.data),
            "system": self.current_rom.system,
            "header": self.current_rom.header,
            "game_id": self.current_rom.get_game_id()
        }

        # Определение языка ROM
        try:
            # Анализируем первые 2KB ROM для определения языка
            sample_size = min(2048, len(self.current_rom.data))
            freq = Counter()
            for i in range(sample_size):
                freq[self.current_rom.data[i]] += 1

            detected_language = _detect_language(self.current_rom.data, 0, sample_size, freq)

            # Дополнительная статистика по языкам
            ascii_count = sum(freq.get(i, 0) for i in range(0x20, 0x7F))
            japanese_count = sum(freq.get(i, 0) for i in range(0xA0, 0xDF)) + sum(
                freq.get(i, 0) for i in range(0x80, 0x9F))
            cyrillic_count = sum(freq.get(i, 0) for i in range(0xC0, 0xFF))

            total_bytes = sum(freq.values())

            language_stats = {
                "detected_language": detected_language,
                "ascii_density": ascii_count / total_bytes if total_bytes > 0 else 0,
                "japanese_density": japanese_count / total_bytes if total_bytes > 0 else 0,
                "cyrillic_density": cyrillic_count / total_bytes if total_bytes > 0 else 0,
                "sample_size": sample_size,
                "most_common_bytes": freq.most_common(10)
            }

            diagnostics_info["language_analysis"] = language_stats
            logger.info(f"Определен язык ROM: {detected_language}")
            logger.info(f"ASCII плотность: {language_stats['ascii_density']:.2%}")
            logger.info(f"Японская плотность: {language_stats['japanese_density']:.2%}")
            logger.info(f"Кириллическая плотность: {language_stats['cyrillic_density']:.2%}")

        except Exception as e:
            logger.error(f"Ошибка при определении языка: {str(e)}")
            diagnostics_info["language_analysis"] = {"error": str(e)}

        # Анализ текстовых сегментов
        game_id = self.current_rom.get_game_id()
        plugin = self.plugin_manager.get_plugin(game_id, self.current_rom.system)

        if plugin:
            segments = plugin.get_text_segments(self.current_rom)
            diagnostics_info["segments"] = []

            for segment in segments:
                analysis = analyze_text_segment(
                    self.current_rom.data,
                    segment['start'],
                    segment['end']
                )

                # Определяем язык для каждого сегмента отдельно
                segment_freq = Counter()
                segment_data = self.current_rom.data[segment['start']:segment['end']]
                for byte in segment_data:
                    segment_freq[byte] += 1

                segment_language = _detect_language(
                    self.current_rom.data,
                    segment['start'],
                    segment['end'] - segment['start'],
                    segment_freq
                )

                analysis["detected_language"] = segment_language

                diagnostics_info["segments"].append({
                    "name": segment['name'],
                    "start": segment['start'],
                    "end": segment['end'],
                    "analysis": analysis
                })

        # Сохранение диагностики
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        diag_file = f"diagnostics_{timestamp}.json"

        with open(diag_file, 'w', encoding='utf-8') as f:
            json.dump(diagnostics_info, f, indent=2, ensure_ascii=False)

        logger.info(f"Диагностика сохранена в {diag_file}")
        self.set_status(self.i18n.t("diagnostics.completed"), 100)

        messagebox.showinfo(
            self.i18n.t("success.title"),
            f"Диагностика завершена. Результаты сохранены в {diag_file}"
        )

        # Обновляем отображение лога
        self.load_current_log()

    def save_log(self):
        """Сохранение текущего лога"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
            initialfile=f"gb2text_{timestamp}.log"
        )

        if save_path:
            try:
                with open('gb2text.log', 'r') as src, open(save_path, 'w') as dst:
                    dst.write(src.read())
                messagebox.showinfo(
                    self.i18n.t("success.title"),
                    f"Лог успешно сохранен в {save_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    f"Не удалось сохранить лог: {str(e)}"
                )

    def inject_translation(self):
        """Внедрение перевода в ROM"""
        if not self.current_segment or not self.current_entries:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.segment")
            )
            return

        try:
            self.set_status(self.i18n.t("text.injecting"), 0)

            # Получаем переводы
            translations = []
            for i in range(len(self.current_entries)):
                translation = self.translated_text.get(1.0, tk.END).strip()
                translations.append(translation)

            # Внедряем в ROM
            success = self.text_injector.inject_segment(
                self.current_segment['name'],
                translations,
                self.plugin_manager.get_plugin(self.current_rom.get_game_id())
            )

            if success:
                self.set_status(self.i18n.t("status.saving"), 75)

                # Сохраняем измененный ROM
                output_path = filedialog.asksaveasfilename(
                    defaultextension=".gb",
                    filetypes=[
                        ("GB/GBC/GBA ROM files", "*.gb *.gbc *.sgb *.gba"),
                        ("All files", "*.*")
                    ],
                    title=self.i18n.t("file.save.rom")
                )

                if output_path:
                    self.text_injector.save(output_path)
                    self.set_status(self.i18n.t("text.injected"))
                    messagebox.showinfo(
                        self.i18n.t("success.title"),
                        self.i18n.t("inject.success", path=output_path)
                    )
            else:
                self.set_status(self.i18n.t("status.error"))
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("inject.error")
                )


        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("inject.error.detail", error=str(e))
            )

    def save_settings(self):
        """Сохранение настроек локализации"""
        # Сохраняем выбранный язык интерфейса
        settings = {
            "ui_language": self.ui_lang.get(),
            "target_language": self.target_lang.get(),
            "encoding_type": self.encoding_type.get()
        }

        # Сохраняем в файл
        settings_dir = Path("settings")
        settings_dir.mkdir(parents=True, exist_ok=True)
        with open(settings_dir / "settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        # Обновляем текущий язык интерфейса
        self.i18n.change_language(self.ui_lang.get())

        # Обновляем интерфейс
        self._refresh_ui()

        messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("settings.saved"))

    def rate_current_guide(self, rating: int):
        """Оценивает текущее руководство"""
        if not self.current_guide or not self.current_rom:
            return

        if self.guide_manager.rate_guide(self.current_rom.get_game_id(), rating):
            messagebox.showinfo("Успех", f"Руководство оценено на {rating} звезд(ы)")
        else:
            messagebox.showerror("Ошибка", "Не удалось оценить руководство")

    def _setup_guide_tab(self):
        """Настройка вкладки руководства"""
        guide_frame = ttk.Frame(self.guide_tab, padding="10")
        guide_frame.pack(fill="both", expand=True)

        # Панель управления
        control_frame = ttk.Frame(guide_frame)
        control_frame.pack(fill="x", expand=False, pady=(0, 10))

        ttk.Button(control_frame, text=self.i18n.t("load.template"), command=self.load_guide_template).pack(side="left", padx=5)
        ttk.Button(control_frame, text=self.i18n.t("save.guide"), command=self.save_guide).pack(side="left", padx=5)
        ttk.Button(control_frame, text=self.i18n.t("apply.guide"), command=self.apply_guide).pack(side="left", padx=5)

        # Панель оценки
        rating_frame = ttk.Frame(control_frame)
        rating_frame.pack(side="left", padx=(20, 0))
        ttk.Label(rating_frame, text="Оценить:").pack(side="left")

        for i in range(1, 6):
            ttk.Button(rating_frame, text="★", width=2,
                       command=lambda r=i: self.rate_current_guide(r)).pack(side="left")

        # Текстовое представление руководства
        self.guide_text = scrolledtext.ScrolledText(guide_frame, wrap="word", font=("Consolas", 10))
        self.guide_text.pack(fill="both", expand=True)
        self.guide_text.config(state="disabled")

    def show_warning_dialog(self):
        """Показывает юридическое предупреждение при запуске"""
        messagebox.showwarning(
            self.i18n.t("warning.title"),
            self.i18n.t("legal.warning")
        )

    def on_closing(self):
        """Обработка закрытия окна"""
        if messagebox.askyesno(
                self.i18n.t("confirm.title"),
                self.i18n.t("confirm.exit")
        ):
            self.root.destroy()

    def get_version(self):
        """Возвращает версию приложения"""
        try:
            version_path = self._get_resource_path('VERSION')
            print(f"[DEBUG] Ищем VERSION файл по пути: {version_path}")
            print(f"[DEBUG] Файл существует: {os.path.exists(version_path)}")
            if hasattr(sys, '_MEIPASS'):
                print(f"[DEBUG] Запуск из exe, _MEIPASS: {sys._MEIPASS}")
                print(
                    f"[DEBUG] Содержимое _MEIPASS: {os.listdir(sys._MEIPASS) if os.path.exists(sys._MEIPASS) else 'не существует'}")
            else:
                print(f"[DEBUG] Обычный запуск, текущая директория: {os.path.abspath('.')}")
                print(f"[DEBUG] Содержимое текущей директории: {os.listdir('.')}")

            with open(version_path, 'r') as f:
                version = f.read().strip()
                print(f"[DEBUG] Загружена версия: {version}")
                return version
        except Exception as e:
            print(f"[DEBUG] Ошибка загрузки VERSION: {e}")
            return "1.0.0"

    def open_url(self, url):
        """Открывает URL в браузере по умолчанию"""
        import webbrowser
        webbrowser.open(url)

    def _set_app_icon(self):
        """Устанавливает пользовательскую иконку приложения"""
        try:
            # Определяем путь к иконке в зависимости от ОС
            import platform
            system = platform.system()

            resources_dir = Path(self._get_resource_path("resources"))
            if not resources_dir.exists():
                resources_dir.mkdir(exist_ok=True)

            # Пытаемся найти подходящую иконку для текущей ОС
            icon_path = None

            if system == "Windows":
                icon_path = resources_dir / "app_icon.ico"
            elif system == "Darwin":  # macOS
                icon_path = resources_dir / "app_icon.png"
            else:  # Linux и другие
                icon_path = resources_dir / "app_icon.png"

            # Если файл иконки существует, устанавливаем его
            if icon_path and icon_path.exists():
                if system == "Windows":
                    self.root.iconbitmap(str(icon_path))
                else:
                    img = tk.PhotoImage(file=str(icon_path))
                    self.root.iconphoto(True, img)
            else:
                # Если пользовательской иконки нет, создаем стандартную
                self._create_default_icon()

        except Exception as e:
            print(f"Ошибка при установке иконки: {str(e)}")
            self._create_default_icon()

    def _create_default_icon(self):
        """Создает простую стандартную иконку, если пользовательская отсутствует"""
        try:
            # Создаем простое изображение как иконку
            import tkinter as tk

            # Создаем маленькое изображение
            width, height = 16, 16
            icon = tk.PhotoImage(width=width, height=height)

            # Заполняем фон
            icon.put("#2c3e50", to=(0, 0, width, height))

            # Рисуем букву "G" (для Game Boy)
            icon.put("#ecf0f1", to=(3, 3, 6, 12))  # Вертикальная линия
            icon.put("#ecf0f1", to=(3, 3, 12, 6))  # Горизонтальная линия
            icon.put("#ecf0f1", to=(9, 6, 12, 12))  # Правая часть

            # Устанавливаем иконку
            self.root.iconphoto(True, icon)
        except Exception as e:
            print(f"Не удалось создать стандартную иконку: {str(e)}")

def run_gui(rom_path=None, plugin_dir="plugins", lang="en"):
    """Запуск GUI приложения"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='gb2text.log',
        filemode='w'  # 'w' перезаписывает файл при каждом запуске, 'a' дописывает
    )
    logger = logging.getLogger('gb2text')
    logger.info("Запуск GUI версии")

    root = tk.Tk()
    app = GBTextExtractorGUI(root, rom_path, plugin_dir, lang)
    root.mainloop()