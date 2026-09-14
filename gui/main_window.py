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

import json
import logging
import os
import platform
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Опциональный импорт для drag & drop
try:
    import tkinterdnd2
    TKINTERDND2_AVAILABLE = True
except ImportError:
    tkinterdnd2 = None
    TKINTERDND2_AVAILABLE = False

# Инициализация логгера
logger = logging.getLogger('gb2text.gui')

from core import secret_store
from core.constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH
from core.encoding import (
    get_generic_chinese_charmap,
    get_generic_english_charmap,
    get_generic_japanese_charmap,
    get_generic_russian_charmap,
    get_generic_shiftjis_charmap,
)
from core.extractor import TextExtractor
from core.guide import GuideManager
from core.i18n import I18N, language_code
from core.injector import TextInjector
from core.machine_translation import MachineTranslation
from core.plugin_manager import CancellationToken, PluginManager
from core.rom import GameBoyROM
from core.scanner import analyze_text_segment, detect_multiple_languages
from core.tmx import TMXHandler
from core.xliff import XLIFFHandler
from gui import theme, widgets


class GBTextExtractorGUI:
    def __init__(self, root, rom_path=None, plugin_dir="plugins", lang="en", *,
                 show_warning=True):
        if rom_path is not None and not isinstance(rom_path, str):
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")

        self.root = root

        # Загружаем сохраненные настройки
        self.load_saved_settings()

        self.i18n = I18N(default_lang=self.ui_lang.get())
        self.machine_translation = MachineTranslation()
        self.tmx_handler = TMXHandler()
        self.xliff_handler = XLIFFHandler()
        self._apply_mt_settings()
        self._mt_thread: threading.Thread | None = None
        self._mt_error: Exception | None = None
        self._mt_result: str | None = None
        self._mt_entry_index: int | None = None
        self._mt_segment: str | None = None
        self._captured_mt_entry: dict | None = None
        self._mt_start_time: float = 0.0
        self._mt_in_progress: bool = False
        self._mt_cloud_confirmed: bool = False
        self.root.title(self.i18n.t("app.title"))
        self.root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")

        # Инициализация компонентов
        self.rom_path = tk.StringVar(value=rom_path or "")
        self.plugin_dir = plugin_dir
        self.plugin_manager = PluginManager(plugin_dir)
        self.guide_manager = GuideManager()
        self.current_guide = None
        self.current_results = None
        self.current_rom = None
        self._loaded_rom_path = None  # Кэш пути загруженного ROM
        self.text_injector = None
        self.current_segment = None
        self.current_entries: list[dict[str, str]] | None = None
        self.current_entry_index = 0
        self.current_segments_meta = []

        # Фильтр списка сегментов
        self._all_segments = []
        self.segment_filter_var = tk.StringVar()
        self.segment_count_var = tk.StringVar()

        # Реалтайм-превью перевода
        self.preview_text = None
        self.preview_frame = None
        self.preview_length_var = tk.StringVar()

        # Состояние проверки орфографии (переменные Настроек создаются в
        # load_saved_settings; здесь — только отложенный таймер и сервис)
        self._spell_after_id = None
        self._spell_svc = None

        # Поиск и замена
        self.search_results = []
        self.search_index = 0
        self.search_term = ""
        self.replace_term = ""
        self.search_dialog = None
        self.replace_dialog = None

        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Иконку ставим ДО показа предупреждения: пока висит модальный
        # messagebox, главное окно в taskbar должно уже иметь наш лого.
        self._set_app_icon()

        if show_warning:
            self.show_warning_dialog()
        self._setup_ui()
        self._setup_search()
        self._setup_drag_drop()
        try:
            theme.register_post_apply_hook(self._reapply_compare_colors)
            theme.register_post_apply_hook(self._reapply_about_colors)
            theme.register_post_apply_hook(self._map_redraw)
        except Exception:
            for hook in (self._reapply_compare_colors, self._reapply_about_colors, self._map_redraw):
                theme.unregister_post_apply_hook(hook)
            raise

        # Если указан ROM при запуске, сразу загружаем
        if rom_path:
            self.update_game_info()

        # Применяем тему и иконку синхронно — до первого показа окна.
        # Раньше тема применялась через after(100): окно успевало
        # отрисоваться в дефолтной ttk-теме, и после перекраски весь
        # текст «сползал»; иконка при этом могла сбрасываться.
        self.apply_theme()
        self._set_app_icon()

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

        # Вкладка пакетной обработки
        self.batch_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.batch_tab, text=self.i18n.t("batch.tab"))
        self._setup_batch_tab()

        # Вкладка сравнения ROM
        self.compare_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.compare_tab, text=self.i18n.t("compare.tab"))

        # Вкладка руководства
        self.guide_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Вкладка диагностики
        self.diagnostics_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.diagnostics_tab, text=self.i18n.t("diagnostics.tab"))
        self._setup_diagnostics_tab()

        # Вкладка карты ROM
        self.map_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.map_tab, text=self.i18n.t("map.tab"))
        self._setup_map_tab()

        # Вкладка настроек
        self.settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.settings_tab, text=self.i18n.t("tab.settings"))

        # Вкладка о программе
        self.about_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.about_tab, text=self.i18n.t("tab.about"))

        self.tab_control.pack(expand=1, fill="both", padx=theme.SPACING["MD"], pady=(theme.SPACING["XS"], theme.SPACING["MD"]))

        # Добавляем статус-бар
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side="bottom", fill="x")
        ttk.Separator(self.root, orient="horizontal").pack(
            side="bottom", fill="x", pady=(theme.SPACING["SM"], 0))

        self.status_label = ttk.Label(self.status_frame, text=self.i18n.t("status.ready"))
        self.status_label.pack(side="left", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])

        self.progress = ttk.Progressbar(self.status_frame, orient="horizontal", mode="determinate", length=200)
        self.progress.pack(side="right", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])

        # Кнопка отмены создаётся при начале извлечения
        self.cancel_button = None

        # Настройка вкладки извлечения
        self._setup_extract_tab()

        # Настройка вкладки редактирования
        self._setup_edit_tab()

        # Настройка вкладки сравнения ROM
        self._setup_compare_tab()

        # Настройка вкладки настроек
        self._setup_settings_tab()

        # Настройка вкладки руководства
        self._setup_guide_tab()

        # Настройка вкладки о программе
        self._setup_about_tab()

        # Контекстное меню пересоздаётся вместе с UI (переживает смену языка)
        self._setup_context_menu()

        # Инициализируем статус
        self.set_status(self.i18n.t("status.ready"))

    def _setup_extract_tab(self):
        """Настройка вкладки извлечения текста"""
        # Верхняя панель: выбор ROM и кнопки
        top_frame = ttk.Frame(self.extract_tab, padding=(theme.SPACING["MD"], theme.SPACING["SM"], theme.SPACING["MD"], theme.SPACING["MD"]))
        top_frame.pack(fill="x", expand=False)

        ttk.Label(top_frame, text=self.i18n.t("rom.file")).pack(side="left", padx=(0, theme.SPACING["SM"]))
        ttk.Entry(top_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, theme.SPACING["SM"]))
        ttk.Button(top_frame, text=self.i18n.t("browse"), command=self.browse_rom).pack(side="left", padx=(0, theme.SPACING["MD"]))
        ttk.Button(top_frame, text=self.i18n.t("extract.text"), command=self.extract_text,
                   style="Accent.TButton").pack(side="left")

        # Информационная панель
        info_frame = ttk.LabelFrame(self.extract_tab, text=self.i18n.t("game.info"), padding=theme.SPACING["MD"])
        info_frame.pack(fill="x", expand=False, padx=theme.SPACING["MD"], pady=(0, theme.SPACING["MD"]))

        self.game_info_labels = {}

        info_items = [
            ("game.title", "title"),
            ("system", "system"),
            ("cartridge.type", "cartridge_type"),
            ("mbc.type", "mbc_type"),
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
            value_label = ttk.Label(row, text="---", wraplength=600, style="Muted.TLabel")
            value_label.pack(side="left", fill="x", expand=True)

            # Сохраняем метку для последующего обновления
            self.game_info_labels[data_key] = {
                "label": label,
                "value": value_label
            }

        # Основная панель с результатами
        main_frame = ttk.Frame(self.extract_tab, padding=theme.SPACING["MD"])
        main_frame.pack(fill="both", expand=True)

        # Левая панель: список сегментов
        left_frame = ttk.LabelFrame(main_frame, text=self.i18n.t("text.segments"), padding=theme.SPACING["SM"])
        left_frame.pack(side="left", fill="y", padx=(0, theme.SPACING["MD"]))

        # Контейнер для списка сегментов со скроллбаром
        segments_container = ttk.Frame(left_frame)
        segments_container.pack(fill="both", expand=True)

        # Фильтр/поиск по имени сегмента
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["XS"]))
        self.segment_filter_var.trace_add("write", self._filter_segments)
        self.segment_filter_entry = ttk.Entry(
            filter_frame, textvariable=self.segment_filter_var, width=25
        )
        self.segment_filter_entry.pack(fill="x")
        ttk.Label(filter_frame, textvariable=self.segment_count_var, anchor="w").pack(
            fill="x", expand=False, pady=(theme.SPACING["XS"], 0)
        )

        self.segments_list = tk.Listbox(segments_container, width=25, height=20)
        segments_scrollbar = ttk.Scrollbar(segments_container, orient="vertical", command=self.segments_list.yview)

        self.segments_list.pack(side="left", fill="both", expand=True)
        segments_scrollbar.pack(side="right", fill="y")

        self.segments_list.config(yscrollcommand=segments_scrollbar.set)
        self.segments_list.bind('<<ListboxSelect>>', self.on_segment_select)

        # Правая панель: просмотр текста
        right_frame = ttk.LabelFrame(main_frame, text=self.i18n.t("segment.content"), padding=theme.SPACING["SM"])
        right_frame.pack(side="right", fill="both", expand=True)

        # Панель инструментов для просмотра
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill="x", expand=False, pady=(0, theme.SPACING["SM"]))

        self.export_menu_btn = ttk.Menubutton(toolbar, text=self.i18n.t("toolbar.export"))
        self.export_menu = tk.Menu(self.export_menu_btn, tearoff=0)
        for label_key, command in (
            ("export.json", self.export_json),
            ("export.txt", self.export_txt),
            ("export.csv", self.export_csv),
            ("export.tmx", self.export_tmx),
            ("export.xliff", self.export_xliff),
        ):
            self.export_menu.add_command(label=self.i18n.t(label_key), command=command)
        self.export_menu_btn.config(menu=self.export_menu)
        theme.style_menu(self.export_menu)
        self.export_menu_btn.pack(side="left", padx=(theme.SPACING["XS"], 0))

        self.import_menu_btn = ttk.Menubutton(toolbar, text=self.i18n.t("toolbar.import"))
        self.import_menu = tk.Menu(self.import_menu_btn, tearoff=0)
        for label_key, command in (
            ("import.csv", self.import_csv),
            ("import.tmx", self.import_tmx),
            ("import.xliff", self.import_xliff),
        ):
            self.import_menu.add_command(label=self.i18n.t(label_key), command=command)
        self.import_menu_btn.config(menu=self.import_menu)
        theme.style_menu(self.import_menu)
        self.import_menu_btn.pack(side="left", padx=(theme.SPACING["XS"], 0))

        ttk.Button(toolbar, text=self.i18n.t("open.in.editor"),
                   command=self.switch_to_edit_tab).pack(side="left", padx=(theme.SPACING["XS"], 0))

        self._update_toolbar_menu_state()

        self.text_output = scrolledtext.ScrolledText(
            right_frame,
            wrap="word",
            font=theme.mono_font(10),
            state="normal"
        )
        self.text_output.pack(fill="both", expand=True)

    def _update_toolbar_menu_state(self):
        """Отключает пункты Экспорт/Импорт, пока нет извлечённых данных."""
        state = "normal" if self.current_results else "disabled"
        for menu in (getattr(self, "export_menu", None), getattr(self, "import_menu", None)):
            if menu is None:
                continue
            end = menu.index("end")
            if end is None:
                continue
            for i in range(end + 1):
                menu.entryconfigure(i, state=state)

    def _setup_edit_tab(self):
        """Настройка вкладки редактирования текста"""
        rom_frame = ttk.LabelFrame(self.edit_tab, text=self.i18n.t("rom.file"), padding=theme.SPACING["MD"])
        rom_frame.pack(fill="x", expand=False, padx=theme.SPACING["MD"], pady=theme.SPACING["MD"])

        ttk.Entry(rom_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, theme.SPACING["SM"]))
        ttk.Button(rom_frame, text=self.i18n.t("browse"), command=self.browse_rom).pack(side="left", padx=(0, theme.SPACING["MD"]))
        ttk.Button(rom_frame, text=self.i18n.t("load.for.editing"), command=self.load_for_editing).pack(side="left")

        # Панель выбора сегмента
        segment_frame = ttk.LabelFrame(self.edit_tab, text=self.i18n.t("text.segments"), padding=theme.SPACING["MD"])
        segment_frame.pack(fill="x", expand=False, padx=theme.SPACING["MD"], pady=(0, theme.SPACING["MD"]))

        self.segment_var = tk.StringVar()
        self.segment_combo = ttk.Combobox(segment_frame, textvariable=self.segment_var, state="readonly", width=30)
        self.segment_combo.pack(side="left", padx=(0, theme.SPACING["MD"]))
        self.segment_combo.bind("<<ComboboxSelected>>", self.on_segment_combo_select)

        ttk.Button(segment_frame, text=self.i18n.t("load.segment"), command=self.load_segment).pack(side="left")

        # Панель для отображения текущей записи
        entry_frame = ttk.Frame(self.edit_tab, padding=(theme.SPACING["MD"], 0, theme.SPACING["MD"], theme.SPACING["SM"]))
        entry_frame.pack(fill="both", expand=True)

        # Панель кнопок
        button_frame = ttk.Frame(entry_frame)
        button_frame.pack(fill="x", pady=(0, theme.SPACING["SM"]))

        ttk.Button(button_frame, text=self.i18n.t("save.translation"),
                   command=self.save_translation).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(button_frame, text=self.i18n.t("inject.translation"),
                   command=self.inject_translation).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(button_frame, text=self.i18n.t("machine.translate"),
                   command=self.machine_translate_current).pack(side="left", padx=theme.SPACING["XS"])

        self.page_var = tk.IntVar(value=1)
        self.total_pages_var = tk.IntVar(value=1)

        # Панель с оригинальным текстом
        original_frame = ttk.LabelFrame(entry_frame, text=self.i18n.t("original.text"))
        original_frame.pack(fill="both", expand=True, pady=(0, theme.SPACING["SM"]))

        self.original_text = scrolledtext.ScrolledText(original_frame, wrap="word",
                                                       height=6, state="disabled")
        self.original_text.pack(
            fill="both", expand=True,
            padx=theme.SPACING["SM"], pady=(theme.SPACING["SM"], 0),
        )

        # Панель с переводом
        translation_frame = ttk.LabelFrame(entry_frame, text=self.i18n.t("translated.text"))
        translation_frame.pack(fill="both", expand=True, pady=(0, theme.SPACING["SM"]))

        self.translated_text = scrolledtext.ScrolledText(translation_frame, wrap="word",
                                                         height=6)
        self.translated_text.pack(
            fill="both", expand=True,
            padx=theme.SPACING["SM"], pady=(theme.SPACING["SM"], 0),
        )

        # Виджет, в котором пользователь работал последним: find/replace из
        # диалога поиска применяется к нему, а не к text_output (fallback).
        # Фокус на текстовом виджете обновляет указатель, так что смена
        # вкладок не оставляет устаревший целевой виджет.
        self._last_edit_widget = self.translated_text
        for w in (self.translated_text, self.original_text, self.text_output):
            w.bind("<FocusIn>", lambda e, w=w: setattr(self, "_last_edit_widget", w))

        # Панель предпросмотра кодирования (реалтайм)
        preview_frame = ttk.LabelFrame(entry_frame, text=self.i18n.t("preview.encoding.title"))
        preview_frame.pack(fill="both", expand=True, pady=(0, theme.SPACING["SM"]))
        self.preview_frame = preview_frame

        self.preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap="word",
            height=6,
            state="disabled",
            font=theme.mono_font(10),
        )
        self.preview_text.pack(
            fill="both", expand=True,
            padx=theme.SPACING["SM"], pady=(theme.SPACING["SM"], 0),
        )
        ttk.Label(preview_frame, textvariable=self.preview_length_var, anchor="w").pack(
            fill="x", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"]
        )
        self.translated_text.bind("<KeyRelease>", self._update_preview)
        self.translated_text.bind("<KeyRelease>", self._schedule_spellcheck, add="+")

        # Проверка орфографии
        spell_check_frame = ttk.Frame(entry_frame)
        spell_check_frame.pack(fill="x")

        ttk.Checkbutton(
            spell_check_frame,
            text=self.i18n.t("spell.check"),
            variable=self.spell_enabled,
            command=self._update_spellcheck,
        ).pack(side="left")
        spell_lang_combo = ttk.Combobox(
            spell_check_frame,
            textvariable=self.spell_lang,
            state="readonly",
            width=8,
            values=("auto", "ru", "en"),
        )
        spell_lang_combo.pack(side="left", padx=(theme.SPACING["XS"], 0))
        spell_lang_combo.bind("<<ComboboxSelected>>", lambda e: self._update_spellcheck())
        self.translated_text.tag_configure("spell", foreground="red", underline=True)

        # Панель навигации
        nav_frame = ttk.Frame(entry_frame)
        nav_frame.pack(fill="x", pady=(theme.SPACING["SM"], 0))

        self.prev_btn = ttk.Button(nav_frame, text=self.i18n.t("prev.entry"),
                                   command=self.prev_entry)
        self.prev_btn.pack(side="left")

        self.entry_label = ttk.Label(nav_frame, text="")
        self.entry_label.pack(side="left", padx=0)

        self.next_btn = ttk.Button(nav_frame, text=self.i18n.t("next.entry"),
                                   command=self.next_entry)
        self.next_btn.pack(side="right")

        # Включаем undo для текстовых виджетов
        self.original_text.config(undo=True)
        self.translated_text.config(undo=True)

        # Добавляем поддержку горячих клавиш
        self.original_text.bind("<Control-c>", lambda e: self.copy_original_text())
        self.translated_text.bind("<Control-v>", lambda e: self.paste_translation())
        self.translated_text.bind("<Control-V>", lambda e: self.paste_translation())
        self.translated_text.bind("<Control-Left>", self.prev_segment)
        self.translated_text.bind("<Control-Right>", self.next_segment)

    def _setup_batch_tab(self):
        """Настройка вкладки пакетной обработки"""
        # Верхняя панель с кнопками
        top_frame = ttk.Frame(self.batch_tab, padding=theme.SPACING["MD"])
        top_frame.pack(fill="x", expand=False)

        ttk.Button(
            top_frame,
            text=self.i18n.t("batch.add.files"),
            command=self._batch_add_files
        ).pack(side="left", padx=theme.SPACING["SM"])

        ttk.Button(
            top_frame,
            text=self.i18n.t("batch.clear.list"),
            command=self._batch_clear_list
        ).pack(side="left", padx=theme.SPACING["SM"])

        # Список файлов
        list_frame = ttk.LabelFrame(
            self.batch_tab,
            text=self.i18n.t("batch.rom.list"),
            padding=theme.SPACING["MD"]
        )
        list_frame.pack(fill="both", expand=True, padx=theme.SPACING["MD"], pady=theme.SPACING["MD"])

        self.batch_listbox = tk.Listbox(list_frame, width=60, height=15)
        self.batch_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.batch_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.batch_listbox.config(yscrollcommand=scrollbar.set)

        # Нижняя панель с кнопками обработки
        bottom_frame = ttk.Frame(self.batch_tab, padding=theme.SPACING["MD"])
        bottom_frame.pack(fill="x", expand=False)

        # Инициализация переменных ДО использования
        self.batch_files = []
        self.batch_count_var = tk.StringVar(value=self.i18n.t("batch.rom.count").format(count=0))

        ttk.Label(
            bottom_frame,
            textvariable=self.batch_count_var
        ).pack(side="left", padx=theme.SPACING["SM"])

        ttk.Button(
            bottom_frame,
            text=self.i18n.t("batch.start"),
            command=self._batch_start
        ).pack(side="left", padx=theme.SPACING["SM"])

        ttk.Button(
            bottom_frame,
            text=self.i18n.t("batch.export.all"),
            command=self._batch_export_all
        ).pack(side="left", padx=theme.SPACING["SM"])

    def _setup_compare_tab(self):
        """Настройка вкладки сравнения ROM"""
        # Выбор ROM файлов
        rom_frame = ttk.LabelFrame(
            self.compare_tab,
            text=self.i18n.t("compare.select.roms"),
            padding=theme.SPACING["MD"]
        )
        rom_frame.pack(fill="x", padx=theme.SPACING["MD"], pady=(theme.SPACING["MD"], 0))

        # ROM 1
        rom1_frame = ttk.Frame(rom_frame)
        rom1_frame.pack(fill="x", pady=theme.SPACING["SM"])
        ttk.Label(rom1_frame, text=self.i18n.t("compare.rom1")).pack(side="left", padx=theme.SPACING["SM"])
        self.compare_rom1_path = tk.StringVar()
        ttk.Entry(rom1_frame, textvariable=self.compare_rom1_path, width=50).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(
            rom1_frame,
            text=self.i18n.t("button.browse"),
            command=lambda: self._browse_compare_rom(1)
        ).pack(side="left", padx=theme.SPACING["SM"])

        # ROM 2
        rom2_frame = ttk.Frame(rom_frame)
        rom2_frame.pack(fill="x", pady=theme.SPACING["SM"])
        ttk.Label(rom2_frame, text=self.i18n.t("compare.rom2")).pack(side="left", padx=theme.SPACING["SM"])
        self.compare_rom2_path = tk.StringVar()
        ttk.Entry(rom2_frame, textvariable=self.compare_rom2_path, width=50).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(
            rom2_frame,
            text=self.i18n.t("button.browse"),
            command=lambda: self._browse_compare_rom(2)
        ).pack(side="left", padx=theme.SPACING["SM"])

        # Кнопка сравнения
        btn_frame = ttk.Frame(self.compare_tab)
        btn_frame.pack(fill="x")
        ttk.Button(
            btn_frame,
            text=self.i18n.t("compare.start"),
            command=self._compare_roms
        ).pack(pady=(theme.SPACING["SM"], 0))

        # Результаты сравнения
        result_frame = ttk.LabelFrame(
            self.compare_tab,
            text=self.i18n.t("compare.results"),
            padding=theme.SPACING["MD"]
        )
        result_frame.pack(
            fill="both", expand=True,
            padx=theme.SPACING["MD"], pady=(0, theme.SPACING["MD"]),
        )

        # Текстовые области для результатов
        text_frame = ttk.Frame(result_frame)
        text_frame.pack(fill="both", expand=True)

        # Добавленные тексты
        added_frame = ttk.LabelFrame(text_frame, text=self.i18n.t("compare.added"), padding=theme.SPACING["SM"])
        added_frame.pack(side="left", fill="both", expand=True, padx=theme.SPACING["XS"])
        self.compare_added_list = tk.Listbox(added_frame, width=30, height=15)
        self.compare_added_list.pack(side="left", fill="both", expand=True)
        added_scroll = ttk.Scrollbar(added_frame, command=self.compare_added_list.yview)
        added_scroll.pack(side="right", fill="y")
        self.compare_added_list.config(yscrollcommand=added_scroll.set)

        # Удалённые тексты
        removed_frame = ttk.LabelFrame(text_frame, text=self.i18n.t("compare.removed"), padding=theme.SPACING["SM"])
        removed_frame.pack(side="left", fill="both", expand=True, padx=theme.SPACING["XS"])
        self.compare_removed_list = tk.Listbox(removed_frame, width=30, height=15)
        self.compare_removed_list.pack(side="left", fill="both", expand=True)
        removed_scroll = ttk.Scrollbar(removed_frame, command=self.compare_removed_list.yview)
        removed_scroll.pack(side="right", fill="y")
        self.compare_removed_list.config(yscrollcommand=removed_scroll.set)

        # Изменённые тексты
        changed_frame = ttk.LabelFrame(text_frame, text=self.i18n.t("compare.changed"), padding=theme.SPACING["SM"])
        changed_frame.pack(side="left", fill="both", expand=True, padx=theme.SPACING["XS"])
        self.compare_changed_list = tk.Listbox(changed_frame, width=30, height=15)
        self.compare_changed_list.pack(side="left", fill="both", expand=True)
        changed_scroll = ttk.Scrollbar(changed_frame, command=self.compare_changed_list.yview)
        changed_scroll.pack(side="right", fill="y")
        self.compare_changed_list.config(yscrollcommand=changed_scroll.set)

    def _browse_compare_rom(self, rom_num):
        """Выбор ROM файла для сравнения"""
        path = filedialog.askopenfilename(
            filetypes=[
                ("ROM files", "*.gb *.gbc *.gba *.sgb"),
                ("All files", "*.*")
            ],
            title=self.i18n.t("compare.select.rom")
        )
        if path:
            if rom_num == 1:
                self.compare_rom1_path.set(path)
            else:
                self.compare_rom2_path.set(path)

    def _compare_roms(self):
        """Сравнение двух ROM файлов"""
        rom1_path = self.compare_rom1_path.get()
        rom2_path = self.compare_rom2_path.get()

        if not rom1_path or not rom2_path:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("compare.select.both")
            )
            return

        if not os.path.exists(rom1_path) or not os.path.exists(rom2_path):
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("compare.file.not.found")
            )
            return

        # Очищаем списки
        self.compare_added_list.delete(0, tk.END)
        self.compare_removed_list.delete(0, tk.END)
        self.compare_changed_list.delete(0, tk.END)

        try:
            # Загружаем ROM файлы
            rom1 = GameBoyROM(rom1_path)
            rom2 = GameBoyROM(rom2_path)

            # Получаем плагины
            game_id1 = rom1.get_game_id()
            game_id2 = rom2.get_game_id()

            plugin1 = self.plugin_manager.get_plugin(game_id1, rom1.system, rom=rom1)
            plugin2 = self.plugin_manager.get_plugin(game_id2, rom2.system, rom=rom2)

            if not plugin1 or not plugin2:
                messagebox.showwarning(
                    self.i18n.t("warning.title"),
                    self.i18n.t("compare.no.plugin")
                )
                return

            # Извлекаем тексты
            segments1 = plugin1.get_text_segments(rom1)
            segments2 = plugin2.get_text_segments(rom2)

            # Сравниваем
            texts1 = self._extract_texts_from_segments(rom1, segments1)
            texts2 = self._extract_texts_from_segments(rom2, segments2)

            # Находим различия
            self._find_text_differences(texts1, texts2)

            self.set_status(self.i18n.t("compare.complete"))

        except Exception as e:
            logger.error(f"Ошибка сравнения ROM: {e}")
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("compare.error").format(error=str(e))
            )

    def _extract_texts_from_segments(self, rom, segments):
        """Извлечение текстов из сегментов ROM"""
        texts = {}
        for seg in segments:
            start = seg.get('start', 0)
            end = seg.get('end', len(rom.data))
            data = rom.data[start:end]

            # Пробуем декодировать
            try:
                decoder = seg.get('decoder')
                if decoder is None:
                    from core.decoder import CharMapDecoder
                    from core.scanner import auto_detect_charmap
                    charmap = auto_detect_charmap(rom.data, start, prefer_lang=seg.get('lang'))
                    decoder = CharMapDecoder(charmap)
                text = decoder.decode(data, 0, len(data))
                texts[seg.get('name', f'Segment_{start}')] = text
            except Exception as e:
                logger.debug(f"Не удалось декодировать сегмент {seg.get('name', 'unknown')}: {e}")
        return texts

    @staticmethod
    def _summarize_text(text: str, limit: int = 40) -> str:
        """Однострочное краткое представление текста сегмента."""
        one_line = " ".join(text.split())
        if len(one_line) > limit:
            return one_line[:limit] + "..."
        return one_line

    def _find_text_differences(self, texts1, texts2):
        """Нахождение различий между текстами"""
        keys1 = set(texts1.keys())
        keys2 = set(texts2.keys())

        # Добавленные сегменты
        added = keys2 - keys1
        added_bg = theme.get("diff-added-bg")
        for key in sorted(added):
            summary = self._summarize_text(texts2[key])
            label = f"{key}: {summary}" if summary else key
            self.compare_added_list.insert(tk.END, label)
            self.compare_added_list.itemconfigure(
                tk.END,
                {"fg": theme.get("success"), "bg": added_bg},
            )

        # Удалённые сегменты
        removed = keys1 - keys2
        removed_bg = theme.get("diff-removed-bg")
        for key in sorted(removed):
            summary = self._summarize_text(texts1[key])
            label = f"{key}: {summary}" if summary else key
            self.compare_removed_list.insert(tk.END, label)
            self.compare_removed_list.itemconfigure(
                tk.END,
                {"fg": theme.get("danger"), "bg": removed_bg},
            )

        # Изменённые сегменты
        common = keys1 & keys2
        changed_bg = theme.get("diff-changed-bg")
        for key in sorted(common):
            if texts1[key] != texts2[key]:
                old_summary = self._summarize_text(texts1[key])
                new_summary = self._summarize_text(texts2[key])
                label = f"{key}: {old_summary} -> {new_summary}" if (old_summary or new_summary) else key
                self.compare_changed_list.insert(tk.END, label)
                self.compare_changed_list.itemconfigure(
                    tk.END,
                    {"fg": theme.get("warning"), "bg": changed_bg},
                )

        # Заливаем фон панелей (пустая панель возвращается к surface)
        for listbox, fg_token, bg_token in (
            (self.compare_added_list, "success", "diff-added-bg"),
            (self.compare_removed_list, "danger", "diff-removed-bg"),
            (self.compare_changed_list, "warning", "diff-changed-bg"),
        ):
            self._paint_compare_panel(listbox, fg_token, bg_token)

        # Статистика
        added_count = len(added)
        removed_count = len(removed)
        changed_count = sum(1 for k in common if texts1[k] != texts2[k])

        self.set_status(
            self.i18n.t("compare.stats").format(
                added=added_count,
                removed=removed_count,
                changed=changed_count
            )
        )

    def _paint_compare_panel(self, listbox, fg_token, bg_token):
        """Красит строки и фон панели сравнения текущими токенами темы.

        Пустая панель (size()==0) возвращается к surface — после повторного
        сравнения без различий залитая ранее панель не остаётся «кричащей».
        """
        if listbox is None:
            return
        try:
            fg = theme.get(fg_token)
            bg = theme.get(bg_token) if listbox.size() else theme.get("surface")
            listbox.configure(bg=bg)
            for i in range(listbox.size()):
                listbox.itemconfigure(i, {"fg": fg, "bg": bg})
        except tk.TclError:
            pass

    def _reapply_compare_colors(self):
        """Post-apply hook: переприменяет diff-цвета элементов Listbox.

        itemconfigure-цвета не привязаны к ttk.Style/tk-опциям и после
        смены темы остаются со старыми значениями — перекрашиваем их
        текущими токенами (вызывается при реальной смене темы).
        """
        lists = (
            (getattr(self, "compare_added_list", None), "success", "diff-added-bg"),
            (getattr(self, "compare_removed_list", None), "danger", "diff-removed-bg"),
            (getattr(self, "compare_changed_list", None), "warning", "diff-changed-bg"),
        )
        for listbox, token, bg_token in lists:
            self._paint_compare_panel(listbox, token, bg_token)

    def _reapply_about_colors(self):
        """Post-apply hook: перекрашивает GitHub-ссылку на вкладке About.

        Widget-level foreground перекрывает стиль TLabel и не обновляется
        сам по себе при смене темы — без этого хука ссылка остаётся со
        старым accent (в dark контраст падает до ~2.8:1).
        """
        link = getattr(self, "github_link", None)
        if link is None:
            return
        try:
            link.configure({"foreground": theme.get("accent")})
        except tk.TclError:
            pass

    def _batch_add_files(self):
        """Добавить файлы для пакетной обработки"""
        files = filedialog.askopenfilenames(
            filetypes=[
                ("ROM files", "*.gb *.gbc *.gba *.sgb"),
                ("All files", "*.*")
            ],
            title=self.i18n.t("batch.select.files")
        )

        if files:
            self.batch_files.extend(files)
            self._batch_update_list()

    def _batch_clear_list(self):
        """Очистить список файлов"""
        self.batch_files = []
        self._batch_update_list()

    def _batch_update_list(self):
        """Обновить список файлов в listbox"""
        self.batch_listbox.delete(0, tk.END)
        for f in self.batch_files:
            self.batch_listbox.insert(tk.END, os.path.basename(f))
        self.batch_count_var.set(self.i18n.t("batch.rom.count").format(count=len(self.batch_files)))

    def _batch_start(self):
        """Запустить пакетную обработку"""
        if getattr(self, '_batch_running', False):
            self.set_status(self.i18n.t("batch.in.progress"))
            return
        if getattr(self, '_extraction_in_progress', False):
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("extraction.in.progress")
            )
            return

        if not self.batch_files:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("batch.no.files")
            )
            return

        # Запускаем обработку в отдельном потоке
        self._batch_running = True
        thread = threading.Thread(target=self._batch_process_files, daemon=True)
        thread.start()

    def _batch_process_files(self):
        """Обработать все файлы"""
        try:
            self._do_batch_process_files()
        except Exception:
            logger.error("Batch processing failed", exc_info=True)
            try:
                self.root.after(0, lambda: self.end_progress(""))
            except tk.TclError:
                pass
            try:
                self.root.after(0, lambda: messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("batch.error")
                ))
            except tk.TclError:
                pass
        finally:
            try:
                self.root.after(0, lambda: setattr(self, "_batch_running", False))
            except tk.TclError:
                pass

    def _do_batch_process_files(self):
        from core.extractor import TextExtractor

        files = list(self.batch_files)
        self.root.after(0, lambda: self.start_progress(
            self.i18n.t("batch.processing"), len(files)))
        results = {}

        for i, rom_path in enumerate(files):
            file_name = os.path.basename(rom_path)
            self.root.after(0, lambda v=i, n=file_name: self.update_progress(
                v, self.i18n.t("batch.processing").format(file=n)))

            try:
                extractor = TextExtractor(rom_path)
                result = extractor.extract()
                results[rom_path] = result
            except Exception as e:
                logger.error(f"Error processing {rom_path}: {e}")

        self.batch_results = results
        count = len(results)
        self.root.after(0, lambda: self.end_progress(self.i18n.t("batch.complete")))
        self.root.after(0, lambda c=count: messagebox.showinfo(
            self.i18n.t("success.title"),
            self.i18n.t("batch.complete.success").format(count=c)
        ))

    def _batch_export_all(self):
        """Экспортировать все результаты"""
        if not hasattr(self, 'batch_results') or not self.batch_results:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("batch.no.results")
            )
            return

        export_dir = filedialog.askdirectory(
            title=self.i18n.t("export.directory")
        )

        if export_dir:
            for rom_path, result in self.batch_results.items():
                game_name = os.path.splitext(os.path.basename(rom_path))[0]
                export_path = os.path.join(export_dir, f"{game_name}.json")

                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("batch.export.success")
            )

    def _setup_settings_tab(self):
        """Настройка вкладки настроек"""
        canvas = tk.Canvas(self.settings_tab, borderwidth=0, highlightthickness=0)
        canvas.configure({"bg": theme.get("surface")})
        scrollbar = ttk.Scrollbar(self.settings_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        settings_wrapper = ttk.Frame(canvas)
        settings_window = canvas.create_window((0, 0), window=settings_wrapper, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(settings_window, width=e.width))

        settings_frame = ttk.LabelFrame(settings_wrapper, text=self.i18n.t("settings.localization"), padding=theme.SPACING["MD"])
        settings_frame.pack(fill="both", expand=True, padx=theme.SPACING["MD"], pady=theme.SPACING["SM"])

        def _on_settings_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        def _on_settings_button_4(_event):
            canvas.yview_scroll(-1, "units")

        def _on_settings_button_5(_event):
            canvas.yview_scroll(1, "units")

        def _bind_settings_wheel(widget):
            widget.bind("<MouseWheel>", _on_settings_mousewheel)
            widget.bind("<Button-4>", _on_settings_button_4)
            widget.bind("<Button-5>", _on_settings_button_5)
            for child in widget.winfo_children():
                _bind_settings_wheel(child)

        def _on_settings_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            _bind_settings_wheel(settings_frame)

        # Колесо вешаем локально на канвас и всех потомков settings_frame
        # (перебиндинг при каждом <Configure>: новые LabelFrame-дети получают
        # скролл сразу после создания). Привязки живут вместе с виджетами и
        # умирают при их пересоздании, не трогая скролл в других вкладках.
        settings_frame.bind("<Configure>", _on_settings_configure)
        _bind_settings_wheel(canvas)

        # Язык интерфейса
        ui_lang_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("ui.language"), padding=theme.SPACING["MD"])
        ui_lang_frame.pack(fill="x", expand=False, pady=theme.SPACING["MD"])

        ttk.Label(ui_lang_frame, text=self.i18n.t("ui.language")).pack(side="left", padx=(0, theme.SPACING["MD"]))

        self.ui_lang = tk.StringVar(value=self.i18n.get_available_languages().get(self.i18n.current_lang, "English"))
        lang_combo = ttk.Combobox(ui_lang_frame, textvariable=self.ui_lang, state="readonly", width=15)
        lang_combo['values'] = list(self.i18n.get_available_languages().values())
        lang_combo.pack(side="left")
        # Устанавливаем текущее значение по названию
        current_name = self.i18n.get_available_languages().get(self.i18n.current_lang, "English")
        lang_combo.current(list(self.i18n.get_available_languages().values()).index(current_name))
        lang_combo.bind("<<ComboboxSelected>>", self.change_ui_language)

        # Язык перевода
        translation_lang_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("target.language"), padding=theme.SPACING["MD"])
        translation_lang_frame.pack(fill="x", expand=False, pady=theme.SPACING["MD"])

        ttk.Label(translation_lang_frame, text=self.i18n.t("target.language")).pack(side="left", padx=(0, theme.SPACING["MD"]))

        self.target_lang = tk.StringVar(value="ru")
        lang_combo = ttk.Combobox(translation_lang_frame, textvariable=self.target_lang, state="readonly", width=15)
        lang_combo['values'] = ('en', 'ru', 'ja', 'es', 'fr', 'de', 'zh')
        lang_combo.pack(side="left")
        lang_combo.current(1)  # Русский по умолчанию

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("encoding.type"), padding=theme.SPACING["MD"])
        encoding_frame.pack(fill="x", expand=False, pady=theme.SPACING["MD"])

        ttk.Label(encoding_frame, text=self.i18n.t("encoding.type")).grid(row=0, column=0, sticky="w", padx=(0, theme.SPACING["MD"]), pady=theme.SPACING["SM"])

        self.encoding_type = tk.StringVar(value="auto")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("auto.detect"), variable=self.encoding_type, value="auto").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("english"), variable=self.encoding_type, value="en").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("japanese"), variable=self.encoding_type, value="ja").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("russian"), variable=self.encoding_type, value="ru").grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text=self.i18n.t("chinese"), variable=self.encoding_type, value="zh").grid(row=4, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text="Shift-JIS (GBA)", variable=self.encoding_type, value="shiftjis").grid(row=5, column=1, sticky="w")
        self._sync_verbose_unknown_flag()
        ttk.Checkbutton(
            encoding_frame,
            text=self.i18n.t("verbose.unknown"),
            variable=self.verbose_unknown_var,
            command=self._on_toggle_verbose_unknown,
        ).grid(row=6, column=1, sticky="w", pady=(theme.SPACING["XS"], 0))

        ttk.Button(
            encoding_frame,
            text=self.i18n.t("tbl.editor.open"),
            command=self._open_charmap_editor,
        ).grid(row=7, column=1, sticky="w", pady=(theme.SPACING["SM"], 0))

        # Тема оформления
        theme_frame = ttk.LabelFrame(settings_frame, text=self.i18n.t("settings.theme"), padding=theme.SPACING["MD"])
        theme_frame.pack(fill="x", expand=False, pady=theme.SPACING["MD"])

        if not hasattr(self, 'theme'):
            self.theme = tk.StringVar(value="light")
        ttk.Radiobutton(theme_frame, text="Light", variable=self.theme, value="light", command=self.apply_theme).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Radiobutton(theme_frame, text="Dark", variable=self.theme, value="dark", command=self.apply_theme).pack(side="left", padx=theme.SPACING["SM"])

        # Machine Translation
        mt_frame = ttk.LabelFrame(settings_frame, text="Machine Translation", padding=theme.SPACING["MD"])
        mt_frame.pack(fill="x", expand=False, pady=theme.SPACING["MD"])

        # Service selection
        ttk.Label(mt_frame, text="Service:").grid(row=0, column=0, sticky="w", padx=(0, theme.SPACING["MD"]), pady=theme.SPACING["XS"])
        service_combo = ttk.Combobox(mt_frame, textvariable=self.mt_service, state="readonly", width=15)
        service_combo['values'] = ('google', 'deepl', 'bing')
        service_combo.grid(row=0, column=1, sticky="w", pady=theme.SPACING["XS"])
        service_combo.current(0)

        # DeepL API Key
        ttk.Label(mt_frame, text="DeepL API Key:").grid(row=1, column=0, sticky="w", padx=(0, theme.SPACING["MD"]), pady=theme.SPACING["XS"])
        ttk.Entry(mt_frame, textvariable=self.deepl_key, width=30, show="*").grid(row=1, column=1, sticky="w", pady=theme.SPACING["XS"])

        # Bing API Key
        ttk.Label(mt_frame, text="Bing API Key:").grid(row=2, column=0, sticky="w", padx=(0, theme.SPACING["MD"]), pady=theme.SPACING["XS"])
        ttk.Entry(mt_frame, textvariable=self.bing_key, width=30, show="*").grid(row=2, column=1, sticky="w", pady=theme.SPACING["XS"])

        # Bing Region
        ttk.Label(mt_frame, text="Bing Region:").grid(row=3, column=0, sticky="w", padx=(0, theme.SPACING["MD"]), pady=theme.SPACING["XS"])
        ttk.Entry(mt_frame, textvariable=self.bing_region, width=15).grid(row=3, column=1, sticky="w", pady=theme.SPACING["XS"])

        # Создать конфигурацию
        ttk.Button(settings_frame, text=self.i18n.t("create.config"), command=self.create_user_config).pack(pady=theme.SPACING["XS"])

        # Кнопка применения кодировки
        ttk.Button(settings_frame, text=self.i18n.t("apply.encoding"), command=self.apply_encoding).pack(pady=theme.SPACING["XS"])

        # Сохранение настроек
        save_btn = ttk.Button(settings_frame, text=self.i18n.t("save.settings"), command=self.save_settings)
        save_btn.pack(pady=theme.SPACING["XS"])

        # Колесо привязываем сразу ко всем уже созданным потомкам
        # (event <Configure> может долго не приходить в невидимых окнах)
        _bind_settings_wheel(settings_frame)

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
            TextExtractor(self.rom_path.get())

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
                self.i18n.t("config.created", path=os.path.basename(config_path))
            )
            # Конфиг успешно создан, завершаем
            self.set_status(self.i18n.t("config.created"))
            return

        except Exception as e:
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("config.error") + f": {e!s}"
            )

    def apply_encoding(self):
        """Применяет выбранную кодировку к текущему сегменту"""
        if not self.current_segment or not self.current_entries:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.segment")
            )
            return

        if not self._guard_unsaved_changes():
            self.set_status(self.i18n.t("status.ready"))
            return

        self.set_status(self.i18n.t("status.processing"), 50)

        encoding_type = self.encoding_type.get()

        segment_meta = self._get_segment_meta(self.current_segment)
        if not segment_meta:
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("segment.not.found")
            )
            self.set_status(self.i18n.t("status.error"))
            return

        charmap = self._build_charmap(encoding_type, segment_meta)

        ok = self._recode_current_segment(segment_meta, charmap)
        if ok:
            self.set_status(self.i18n.t("encoding.applied"))
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("encoding.applied")
            )
        else:
            self.set_status(self.i18n.t("status.error"))

    def _get_segment_meta(self, segment_name):
        """Возвращает словарь сегмента по имени"""
        for seg in self.current_segments_meta:
            if seg.get('name') == segment_name:
                return seg
        if self.current_rom:
            try:
                plugin = self.plugin_manager.get_plugin(
                    self.current_rom.get_game_id(), self.current_rom.system, rom=self.current_rom)
            except Exception:
                plugin = None
            if plugin:
                for seg in plugin.get_text_segments(self.current_rom):
                    if seg.get('name') == segment_name:
                        return seg
        return None

    def _recode_current_segment(self, segment_meta, charmap):
        """
        Перекодирует текущий сегмент новой таблицей символов.

        Переводы, введённые пользователем, сохраняются: для каждого нового
        сообщения копируется перевод из старого сообщения с таким же текстом.
        Guard на несохранённые правки выполняют вызывающие методы.
        """
        try:
            from core.decoder import CharMapDecoder
            from core.extractor import TextExtractor

            decoder = CharMapDecoder(
                charmap,
                verbose_unknown=self.verbose_unknown_var.get()
            )

            extractor = TextExtractor(self.rom_path.get(), rom=self.current_rom)
            new_entries = extractor.recode_segment(segment_meta, decoder)

            # Переносим старые переводы: сначала по offset (стабилен при смене
            # кодировки), затем по исходному тексту (если offset съехал).
            old_by_offset = {
                entry.get('offset'): entry.get('translation')
                for entry in self.current_entries or []
                if entry.get('translation')
            }
            old_by_text = {
                entry.get('text'): entry.get('translation')
                for entry in self.current_entries or []
                if entry.get('translation')
            }
            for entry in new_entries:
                translation = old_by_offset.get(entry.get('offset'))
                if not translation:
                    translation = old_by_text.get(entry.get('text'))
                if translation:
                    entry['translation'] = translation

            self.current_results[self.current_segment] = new_entries
            prev_index = self.current_entry_index
            self.current_entries = new_entries
            self.current_entry_index = min(prev_index, max(0, len(new_entries) - 1))
            if hasattr(self, '_display_current_entry'):
                self._display_current_entry()
            return True
        except Exception as e:
            logger.error(f"Ошибка перекодирования сегмента: {e}", exc_info=True)
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("extraction.error", error=str(e))
            )
            return False

    def _sync_verbose_unknown_flag(self):
        """Синхронизирует флаг показа неизвестных байтов с декодерами"""
        try:
            from core import decoder as decoder_module
            decoder_module.DEFAULT_VERBOSE_UNKNOWN = self.verbose_unknown_var.get()
        except Exception as e:
            logger.error(f"Не удалось синхронизировать флаг verbose unknown: {e}")

    def _build_charmap(self, encoding_type, segment_meta):
        """Строит таблицу символов для выбранной кодировки"""
        if encoding_type == "auto":
            if segment_meta.get('decoder'):
                return segment_meta['decoder'].charmap
            from core.scanner import auto_detect_charmap
            if self.current_rom is None:
                raise ValueError("ROM not loaded")
            return auto_detect_charmap(
                self.current_rom.data,
                segment_meta.get('start', 0),
                prefer_lang=segment_meta.get('lang'))
        try:
            from core.charset import load_charset
            charmap = load_charset(encoding_type)
            if not charmap:
                raise ValueError("Empty charset file")
            return charmap
        except (FileNotFoundError, ValueError, ImportError):
            if encoding_type == "ja":
                return get_generic_japanese_charmap()
            elif encoding_type == "ru":
                return get_generic_russian_charmap()
            elif encoding_type == "zh":
                return get_generic_chinese_charmap()
            elif encoding_type == "shiftjis":
                return get_generic_shiftjis_charmap()
            else:
                return get_generic_english_charmap()

    def _on_toggle_verbose_unknown(self):
        """Обработчик переключателя неизвестных байтов"""
        if not self._guard_unsaved_changes():
            # «Отмена» — откатываем чекбокс, чтобы состояние соответствовало
            # фактически применяемому значению (деколог/настройки не тронуты).
            self.verbose_unknown_var.set(not self.verbose_unknown_var.get())
            self.set_status(self.i18n.t("status.ready"))
            return
        self._sync_verbose_unknown_flag()
        self.save_settings(silent=True)
        if self.current_segment and self.current_entries:
            segment_meta = self._get_segment_meta(self.current_segment)
            if segment_meta:
                charmap = self._build_charmap(self.encoding_type.get(), segment_meta)
                if self._recode_current_segment(segment_meta, charmap):
                    self.set_status(self.i18n.t("encoding.applied"))
                else:
                    self.set_status(self.i18n.t("status.error"))
            else:
                self.set_status(self.i18n.t("segment.not.found"))

    def _editor_charmap(self):
        """Возвращает копию таблицы символов для редактора TBL"""
        segment_meta = {}
        if self.current_segment:
            meta = self._get_segment_meta(self.current_segment)
            if meta:
                segment_meta = meta
        try:
            return dict(self._build_charmap(self.encoding_type.get(), segment_meta))
        except Exception:
            fallback = {
                "ja": get_generic_japanese_charmap(),
                "ru": get_generic_russian_charmap(),
                "zh": get_generic_chinese_charmap(),
                "shiftjis": get_generic_shiftjis_charmap(),
            }
            return fallback.get(self.encoding_type.get(), get_generic_english_charmap())

    def _open_charmap_editor(self):
        """Открывает диалог редактора таблицы символов"""
        dialog = _CharmapEditorDialog(self.root, self)
        dialog.run()

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
        self.guide_text.insert(tk.END, f"{self.i18n.t('guide.for.game').format(game_id=self.current_guide.get('game_id', ''))}\n\n", "header")
        self.guide_text.insert(tk.END, f"{self.current_guide.get('description', '')}\n\n")

        # Шаги
        self.guide_text.insert(tk.END, f"{self.i18n.t('guide.step.by.step')}\n", "section")
        steps = self.current_guide.get('steps', [])
        for i, step in enumerate(steps, 1):
            self.guide_text.insert(tk.END, f"{i}. {step.get('title', '')}\n", "step")
            self.guide_text.insert(tk.END, f"   {step.get('description', '')}\n\n")

        # Советы
        tips = self.current_guide.get('tips', [])
        if tips:
            self.guide_text.insert(tk.END, f"{self.i18n.t('guide.tips')}\n", "section")
            for _i, tip in enumerate(tips, 1):
                self.guide_text.insert(tk.END, f"• {tip}\n")

        # Настройка стилей
        self.guide_text.tag_config("header", font=theme.mono_font(10, "bold"))
        self.guide_text.tag_config("section", font=theme.mono_font(10, "underline"))
        self.guide_text.tag_config("step", font=theme.mono_font(10, "bold"))

        self.guide_text.config(state="disabled")

    def load_guide_template(self):
        """Загружает шаблон руководства"""
        if not self.current_rom:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("guide.load.rom.first"))
            return

        game_id = self.current_rom.get_game_id()
        self.current_guide = self.guide_manager.create_template(game_id)
        self.display_guide()

    def save_guide(self):
        """Сохраняет текущее руководство"""
        if not self.current_guide or not self.current_rom:
            return

        if self.guide_manager.save_guide(self.current_rom.get_game_id(), self.current_guide):
            messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("guide.saved"))
        else:
            messagebox.showerror(self.i18n.t("error.title"), self.i18n.t("guide.save.error"))

    def apply_guide(self):
        """Применяет рекомендации из руководства к извлечению текста"""
        if not self.current_guide or not self.current_rom:
            return

        # Здесь можно добавить логику применения рекомендаций
        messagebox.showinfo(self.i18n.t("info.title"),
                            self.i18n.t("guide.applied"))

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

    def update_progress(self, value: int, message: str | None = None):
        """Обновляет прогресс"""
        self.progress['value'] = value
        if message:
            self.status_label.config(text=message)
        self.root.update_idletasks()

    def end_progress(self, message: str | None = None):
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

        # Проверяем кэш - если ROM уже загружен, не перезагружаем
        if self._loaded_rom_path == self.rom_path.get() and self.current_rom:
            # ROM уже загружен, просто обновляем отображение
            rom = self.current_rom
        else:
            try:
                rom = GameBoyROM(self.rom_path.get())
                self.current_rom = rom
                self._loaded_rom_path = self.rom_path.get()
            except Exception as e:
                logger.error(f"Ошибка загрузки ROM: {e}")
                self.set_status(f"ROM error: {e}")
                return

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
        self.game_info_labels["mbc_type"]["value"].config(text=self._get_mbc_name(rom.header['cartridge_type']))
        self.game_info_labels["rom_size"]["value"].config(text=f"{len(rom.data) // 1024} KB")

        # Проверяем поддержку игры
        game_id = rom.get_game_id()
        plugin = self.plugin_manager.get_plugin(game_id, rom.system, rom=rom)
        if plugin:
            self.game_info_labels["supported_plugin"]["value"].config(text=plugin.__class__.__name__)
        else:
            self.game_info_labels["supported_plugin"]["value"].config(text=self.i18n.t("not_found"))

        self._update_title()

    def _update_title(self):
        """Обновляет заголовок окна с именем текущего ROM."""
        title = self.i18n.t("app.title")
        rom_path = self.rom_path.get()
        if rom_path:
            title = f"{title} — {os.path.basename(rom_path)}"
        self.root.title(title)

    def extract_text(self):
        """Извлечение текста из ROM"""
        if not self.rom_path.get():
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        if getattr(self, '_extraction_in_progress', False):
            self.set_status(self.i18n.t("extraction.in.progress"))
            return

        if getattr(self, '_batch_running', False):
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("batch.in.progress")
            )
            return

        if not self._guard_unsaved_changes():
            return

        try:
            self._extraction_in_progress = True
            self.cancel_requested = False
            self.cancellation_token = CancellationToken()
            self.extraction_error = None
            self.set_status(self.i18n.t("text.extracting"), 0)

            # Добавляем кнопку отмены
            self.cancel_button = ttk.Button(
                self.status_frame,
                text=self.i18n.t("cancel"),
                command=self._cancel_extraction
            )
            self.cancel_button.pack(side="right", padx=theme.SPACING["SM"])

            # Запускаем извлечение в отдельном потоке
            def extract_task():
                try:
                    extractor = TextExtractor(
                        self.rom_path.get(),
                        plugin_manager=self.plugin_manager,
                        cancellation_token=self.cancellation_token
                    )
                    result = extractor.extract()
                    # Не затираем предыдущие результаты, если пользователь уже отменил
                    if self.cancellation_token.is_cancellation_requested():
                        return False
                    self.current_results = result
                    return True
                except Exception as e:
                    self.extraction_error = e
                    return False

            # Запускаем задачу извлечения
            extraction_thread = threading.Thread(target=extract_task)
            extraction_thread.daemon = True
            extraction_thread.start()

            # Ожидаем завершения через root.after() polling (не блокируя main loop)
            self._extraction_start_time = time.time()
            self._extraction_thread = extraction_thread
            self._poll_extraction()

        except Exception as e:
            self._extraction_in_progress = False
            self._extraction_thread = None
            btn = getattr(self, "cancel_button", None)
            if btn is not None:
                try:
                    btn.destroy()
                except tk.TclError:
                    pass
                self.cancel_button = None
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("extraction.error", error=str(e))
            )

    def _cancel_extraction(self):
        """Отмена процесса извлечения текста"""
        self.cancel_requested = True
        self.cancellation_token.cancel()
        self.set_status(self.i18n.t("extraction.canceled"))

    def _poll_extraction(self):
        """Poll extraction thread completion via root.after() — non-blocking."""
        if self._extraction_thread.is_alive():
            elapsed = time.time() - self._extraction_start_time
            progress = 5 + min(90, int(elapsed) * 2)
            self.set_status(
                f"{self.i18n.t('text.extracting')} ({int(elapsed)}s)",
                progress
            )
            self.root.after(500, self._poll_extraction)
        else:
            # Thread finished — clean up and process result
            self._extraction_in_progress = False
            self._extraction_thread = None
            if getattr(self, 'cancel_button', None) is not None and self.cancel_button.winfo_exists():
                self.cancel_button.destroy()

            if self.cancel_requested:
                self.set_status(self.i18n.t("status.ready"))
                return

            if self.extraction_error is not None:
                self.set_status(self.i18n.t("status.error"))
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("extraction.error", error=str(self.extraction_error))
                )
                return

            self._refresh_segments_list(self.current_results.keys())
            self._update_toolbar_menu_state()

            if self.segments_list.size() > 0:
                self.segments_list.selection_set(0)
                self.on_segment_select(None)

            self.set_status(self.i18n.t("text.extracted"))
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("extraction.success")
            )

    def _refresh_segments_list(self, segment_names):
        """Обновляет полный список сегментов и переприменяет фильтр."""
        self._all_segments = list(segment_names)
        self._filter_segments()

    def _filter_segments(self, *args):
        """Применяет текущий фильтр (подстрока, без учёта регистра) к списку."""
        query = self.segment_filter_var.get().strip().lower()
        self.segments_list.delete(0, tk.END)
        shown = 0
        for name in self._all_segments:
            if query in name.lower():
                self.segments_list.insert(tk.END, name)
                shown += 1
        self.segment_count_var.set(f"{shown} / {len(self._all_segments)}")
        if shown > 0:
            self.segments_list.selection_clear(0, tk.END)

    def on_segment_select(self, event):
        """Обработка выбора сегмента"""
        # Пользовательский выбор переключает редактируемую страницу —
        # защищаем несохранённый перевод. Программные вызовы (event=None)
        # приходят уже после собственных guard-проверок (extract/_refresh_ui).
        if event is not None and not self._guard_unsaved_changes():
            return

        # Очищаем текстовую область
        self.text_output.delete(1.0, tk.END)

        if not self.current_results:
            self.text_output.insert(tk.END, self.i18n.t("no.data.to.display"))
            return

        # Получаем выбранный сегмент
        selection = self.segments_list.curselection()
        if not selection:
            return

        segment_index = selection[0]
        segment_name = self.segments_list.get(segment_index)

        # Проверяем, есть ли такой сегмент в результатах
        if segment_name not in self.current_results:
            self.text_output.insert(tk.END, self.i18n.t("segment.not.found"))
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
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                messagebox.showinfo(
                    self.i18n.t("success.title"),
                    self.i18n.t("export.json.success")
                )
            except (OSError, TypeError, ValueError) as exc:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    f"{self.i18n.t('export.error')}: {exc}"
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
            try:
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
            except OSError as exc:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    f"{self.i18n.t('export.error')}: {exc}"
                )

    def export_csv(self):
        """Экспорт результатов в CSV"""
        if not self.current_results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=self.i18n.t("file.export.csv")
        )

        if path:
            try:
                import csv
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['segment', 'offset', 'original_text', 'translation'])

                    for segment_name, messages in self.current_results.items():
                        for msg in messages:
                            translation = msg.get('translation', '')
                            writer.writerow([
                                segment_name,
                                f"0x{msg['offset']:04X}",
                                msg.get('text', ''),
                                translation
                            ])

                messagebox.showinfo(
                    self.i18n.t("success.title"),
                    self.i18n.t("export.csv.success")
                )
            except Exception as e:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    f"{self.i18n.t('export.error')}: {e}"
                )

    def import_csv(self):
        """Импорт переводов из CSV"""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=self.i18n.t("file.import.csv")
        )

        if not path:
            return

        try:
            import csv
            translations = {}

            with open(path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    segment = row.get('segment', '')
                    offset_str = row.get('offset', '')
                    translation = row.get('translation', '')

                    if segment and offset_str and translation:
                        # Конвертируем offset из hex
                        try:
                            offset = int(offset_str.replace('0x', '').replace('0X', ''), 16)
                        except ValueError:
                            logger.warning(f"Пропускаю строку CSV с невалидным offset: '{offset_str}'")
                            continue

                        if segment not in translations:
                            translations[segment] = {}
                        translations[segment][offset] = translation

            # Применяем переводы
            if not self._guard_unsaved_changes():
                return
            if self.current_results:
                for segment_name, messages in self.current_results.items():
                    if segment_name in translations:
                        for msg in messages:
                            offset = msg.get('offset')
                            if offset in translations[segment_name]:
                                msg['translation'] = translations[segment_name][offset]

            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("import.csv.success")
            )

            # Обновляем отображение
            self._display_current_entry()

        except Exception as e:
            messagebox.showerror(
                self.i18n.t("error.title"),
                f"{self.i18n.t('import.error')}: {e}"
            )

    def export_tmx(self):
        """Экспорт результатов в TMX"""
        if not self.current_results:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("batch.no.results"))
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".tmx",
            filetypes=[("TMX files", "*.tmx"), ("All files", "*.*")],
            title=self.i18n.t("file.export.tmx")
        )

        if path:
            try:
                # Получаем название игры
                game_title = "Unknown Game"
                if self.current_rom:
                    game_title = self.current_rom.get_title() or "Unknown Game"

                # Экспортируем в TMX
                source_lang = self.encoding_type.get()
                if source_lang == "auto":
                    source_lang = "en"  # По умолчанию английский
                target_lang = self.target_lang.get()

                tmx_content = self.tmx_handler.export_tmx(
                    self.current_results,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    game_title=game_title
                )

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(tmx_content)

                messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("export.tmx.success").format(path=os.path.basename(path)))

            except Exception as e:
                messagebox.showerror(self.i18n.t("error.title"), self.i18n.t("export.tmx.error").format(error=e))

    def export_xliff(self):
        """Экспорт результатов в XLIFF (для CAT-инструментов)"""
        if not self.current_results:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("batch.no.results"))
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xliff",
            filetypes=[("XLIFF files", "*.xliff"), ("XML files", "*.xlf"), ("All files", "*.*")],
            title=self.i18n.t("file.export.xliff")
        )

        if path:
            try:
                # Получаем название игры
                game_title = "Unknown Game"
                if self.current_rom:
                    game_title = self.current_rom.get_title() or "Unknown Game"

                # Экспортируем в XLIFF
                source_lang = self.encoding_type.get()
                if source_lang == "auto":
                    source_lang = "en"  # По умолчанию английский
                target_lang = self.target_lang.get()

                xliff_content = self.xliff_handler.export_xliff(
                    self.current_results,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    game_title=game_title
                )

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(xliff_content)

                messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("export.xliff.success").format(path=os.path.basename(path)))

            except Exception as e:
                messagebox.showerror(self.i18n.t("error.title"), self.i18n.t("export.xliff.error").format(error=e))

    def import_tmx(self):
        """Импорт переводов из TMX"""
        path = filedialog.askopenfilename(
            filetypes=[("TMX files", "*.tmx"), ("All files", "*.*")],
            title=self.i18n.t("file.import.tmx")
        )

        if not path:
            return

        try:
            with open(path, encoding='utf-8') as f:
                tmx_content = f.read()

            # Импортируем переводы
            translations = self.tmx_handler.import_tmx(tmx_content)

            # Применяем переводы
            if not self._guard_unsaved_changes():
                return
            if self.current_results:
                applied_count = 0
                for segment_name, messages in self.current_results.items():
                    if segment_name in translations:
                        for msg in messages:
                            offset = msg.get('offset')
                            source = msg.get('text', '')
                            entry = translations[segment_name]
                            # Сначала сопоставление по ROM-offset, затем по исходному тексту
                            if offset is not None and offset in entry:
                                msg['translation'] = entry[offset]
                                applied_count += 1
                            elif source and source in entry:
                                msg['translation'] = entry[source]
                                applied_count += 1

                messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("import.tmx.success").format(count=applied_count))

                # Обновляем отображение
                self._display_current_entry()

        except Exception as e:
            messagebox.showerror(self.i18n.t("error.title"), self.i18n.t("import.tmx.error").format(error=e))

    def import_xliff(self):
        """Импорт переводов из XLIFF (CAT-инструменты: Trados, memoQ)."""
        if not self.current_results:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("batch.no.results"))
            return

        path = filedialog.askopenfilename(
            filetypes=[("XLIFF files", "*.xliff"), ("XML files", "*.xlf"), ("All files", "*.*")],
            title=self.i18n.t("file.import.xliff")
        )

        if not path:
            return

        try:
            with open(path, encoding='utf-8') as f:
                xliff_content = f.read()

            # Импортируем переводы: {segment_name: {int_index: translation}}
            translations = self.xliff_handler.import_xliff(xliff_content)
            if not self._guard_unsaved_changes():
                return
            applied_count = XLIFFHandler.apply_translations(self.current_results, translations)

            if applied_count:
                messagebox.showinfo(self.i18n.t("success.title"),
                                    self.i18n.t("import.xliff.success").format(count=applied_count))
                self._display_current_entry()
            else:
                messagebox.showinfo(self.i18n.t("info.title"),
                                    self.i18n.t("import.xliff.success").format(count=0))

        except Exception as e:
            messagebox.showerror(self.i18n.t("error.title"), self.i18n.t("import.xliff.error").format(error=e))

    def switch_to_edit_tab(self):
        """Переключение на вкладку редактирования"""
        if not self.current_results:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("extract.text.first"))
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

        if not self._guard_unsaved_changes():
            return

        # Проверяем кэш - если ROM уже загружен и путь тот же, не перезагружаем
        if self._loaded_rom_path == rom_path and self.current_rom:
            logger.info("Используем кэшированный ROM")
        else:
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
                self._loaded_rom_path = rom_path

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
                self.game_info_labels["mbc_type"]["value"].config(text=self._get_mbc_name(self.current_rom.header['cartridge_type']))
                self.game_info_labels["rom_size"]["value"].config(text=f"{len(self.current_rom.data) // 1024} KB")

                # Заполняем список сегментов
                game_id = self.current_rom.get_game_id()
                plugin = self.plugin_manager.get_plugin(game_id, self.current_rom.system, rom=self.current_rom)

                if plugin:
                    segments = plugin.get_text_segments(self.current_rom)
                    self.current_segments_meta = segments
                    self._map_redraw()
                    self.segment_combo['values'] = [seg['name'] for seg in segments]
                    if self.segment_combo['values']:
                        self.segment_combo.current(0)
                        self.load_segment(ask=False)
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

    def _get_mbc_name(self, cartridge_type):
        """Возвращает название MBC по типу картриджа"""
        mbc_types = {
            0x00: "ROM Only",
            0x01: "MBC1",
            0x02: "MBC1+RAM",
            0x03: "MBC1+RAM+Battery",
            0x05: "MBC2",
            0x06: "MBC2+Battery",
            0x08: "ROM+RAM",
            0x09: "ROM+RAM+Battery",
            0x0B: "MMM01",
            0x0C: "MMM01+RAM",
            0x0D: "MMM01+RAM+Battery",
            0x0F: "MBC3+Timer+Battery",
            0x10: "MBC3+Timer+RAM+Battery",
            0x11: "MBC3",
            0x12: "MBC3+RAM",
            0x13: "MBC3+RAM+Battery",
            0x19: "MBC5",
            0x1A: "MBC5+RAM",
            0x1B: "MBC5+RAM+Battery",
            0x1C: "MBC5+Rumble",
            0x1D: "MBC5+Rumble+RAM",
            0x1E: "MBC5+Rumble+RAM+Battery",
            0x1F: "MBC6",
            0x20: "MBC7",
            0x22: "MBC5+SRAM+Battery",  # Также известен как MBC5 для GBA
        }
        return mbc_types.get(cartridge_type, f"Unknown (0x{cartridge_type:02X})")

    def load_saved_settings(self):
        """Загружает сохраненные настройки.

        Настройки хранятся рядом с исполняемым файлом (cwd) — save_settings
        пишет в Path("settings"). Раньше load читал через _get_resource_path,
        который в PyInstaller указывает на _MEIPASS (временная папка, не
        переживает перезапуск), из-за чего сохранённые настройки не
        восстанавливались. Миграция: если нового файла нет, пробуем старый
        cwd-путь вблизи _MEIPASS.
        """
        settings_path = Path("settings") / "settings.json"
        legacy_path = Path(self._get_resource_path("settings/settings.json"))
        candidate = settings_path if settings_path.exists() else legacy_path
        if candidate.exists():
            try:
                with open(candidate, encoding="utf-8") as f:
                    settings = json.load(f)
                self.ui_lang = tk.StringVar(value=language_code(settings.get("ui_language", "en")))
                self.target_lang = tk.StringVar(value=settings.get("target_language", "ru"))
                self.encoding_type = tk.StringVar(value=settings.get("encoding_type", "auto"))
                self.verbose_unknown_var = tk.BooleanVar(value=settings.get("verbose_unknown", False))
                self.theme = tk.StringVar(value=settings.get("theme", "light"))
                self.mt_service = tk.StringVar(value=settings.get("mt_service", "google"))
                self.deepl_key = tk.StringVar(value=secret_store.load_secret("deepl_key") or "")
                self.bing_key = tk.StringVar(value=secret_store.load_secret("bing_key") or "")
                self.bing_region = tk.StringVar(value=settings.get("bing_region", "global"))
                self.spell_enabled = tk.BooleanVar(value=settings.get("spell_enabled", True))
                self.spell_lang = tk.StringVar(value=settings.get("spell_lang", "auto"))
                self._migrate_legacy_secrets(settings)

                # Если ключи мигрировали из legacy-файла (_MEIPASS в PyInstaller),
                # затираем его: он мог содержать открытые ключи.
                if candidate != settings_path and candidate.exists():
                    try:
                        candidate.write_text("{}", encoding="utf-8")
                    except OSError:
                        logger.warning(
                            "Не удалось затереть legacy settings.json: %s", candidate
                        )
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {e!s}")
                self._init_default_settings()
        else:
            self._init_default_settings()

    def _migrate_legacy_secrets(self, settings: dict):
        """Переносит открытые API-ключи из settings.json в защищённое хранилище.

        Если в хранилище уже есть ключ — файловое значение не перезаписывает
        его. При успешном переносе поля GUI обновляются сразу. Если хранилище
        недоступно — ключ всё равно вычищается из файла
        (лучше переввести, чем хранить открытым текстом).
        """
        legacy = {
            name: settings.get(name)
            for name in ("deepl_key", "bing_key")
            if settings.get(name)
        }
        if not legacy:
            return

        for name, value in legacy.items():
            if secret_store.load_secret(name):
                settings.pop(name, None)
                continue
            if isinstance(value, str) and value:
                ok = secret_store.store_secret(name, value)
                var = getattr(self, name, None)
                if ok and var is not None:
                    var.set(value)
            else:
                ok = False
            if not ok:
                logger.warning(
                    "Не удалось перенести '%s' в защищённое хранилище", name
                )
            settings.pop(name, None)
        self._write_settings_file(settings)

    def _init_default_settings(self):
        """Инициализирует настройки по умолчанию"""
        self.ui_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="ru")
        self.encoding_type = tk.StringVar(value="auto")
        self.verbose_unknown_var = tk.BooleanVar(value=False)
        self.theme = tk.StringVar(value="light")
        self.mt_service = tk.StringVar(value="google")
        self.deepl_key = tk.StringVar(value="")
        self.bing_key = tk.StringVar(value="")
        self.bing_region = tk.StringVar(value="global")
        self.spell_enabled = tk.BooleanVar(value=True)
        self.spell_lang = tk.StringVar(value="auto")

    def on_segment_combo_select(self, event):
        """Обработка выбора сегмента в комбобоксе"""
        self.load_segment()

    def load_segment(self, *, ask=True):
        """Загрузка выбранного сегмента для редактирования"""
        if not self.current_rom or not self.text_injector:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("select.rom")
            )
            return

        if ask and not self._guard_unsaved_changes():
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

    @staticmethod
    def _preview_render(text: str) -> str:
        """Готовит текст перевода к предпросмотру: убирает номера записей
        и заменяет контрольные токены вида [END]/[LINE] на <end>/<line>."""
        text = re.sub(r'^\[\d+\]\s*', '', text, flags=re.M)
        return re.sub(r'\[([A-Za-z0-9_]+)\]', lambda m: f"<{m.group(1).lower()}>", text)

    def _update_preview(self, *_):
        """Обновляет предпросмотр кодирования и счётчик длин."""
        if self.preview_text is None:
            return
        raw = self.translated_text.get("1.0", "end-1c")
        text = self._preview_render(raw)
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.config(state="disabled")

        tr_len = len(re.sub(r'^\[\d+\]\s*', '', raw, flags=re.M).replace("\n", ""))
        orig_raw = self.original_text.get("1.0", "end-1c")
        orig_len = len(re.sub(r'^\[\d+\]\s*', '', orig_raw, flags=re.M).replace("\n", ""))
        self.preview_length_var.set(
            f"{self.i18n.t('preview.chars')}: {tr_len} | "
            f"{self.i18n.t('preview.orig')}: {orig_len}"
        )

    def _schedule_spellcheck(self, *_):
        """Откладывает проверку орфографии на ~500мс (debounce на ввод)."""
        if not getattr(self, "spell_enabled", None) or not self.spell_enabled.get():
            return
        if hasattr(self, "_spell_after_id") and self._spell_after_id:
            try:
                self.root.after_cancel(self._spell_after_id)
            except Exception:
                pass
        self._spell_after_id = self.root.after(500, self._update_spellcheck)

    def _update_spellcheck(self, *_):
        """Подсвечивает опечатки (red underline) в поле перевода."""
        if hasattr(self, "_spell_after_id") and self._spell_after_id:
            try:
                self.root.after_cancel(self._spell_after_id)
                self._spell_after_id = None
            except Exception:
                self._spell_after_id = None

        if not getattr(self, "spell_enabled", None) or not self.spell_enabled.get():
            self._clear_spell_tags()
            return

        if not getattr(self, "translated_text", None):
            return

        try:
            from core.spell_checker import check_text

            raw = self.translated_text.get("1.0", "end-1c")
            self._clear_spell_tags()
            if not raw.strip():
                return
            errors = check_text(raw, lang=self.spell_lang.get())
            for start, end, _word, _suggestions in errors:
                self.translated_text.tag_add(
                    "spell",
                    f"1.0 + {start} chars",
                    f"1.0 + {end} chars",
                )
        except Exception as e:  # если зависимость недоступна — без подсветки
            logger = logging.getLogger('gb2text.gui')
            logger.warning(f"Spell check unavailable: {e}")

    def _clear_spell_tags(self):
        if getattr(self, "translated_text", None):
            self.translated_text.tag_remove("spell", "1.0", tk.END)

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
            self._update_preview()
            self._update_spellcheck()

        except Exception as e:
            logger.error(f"Ошибка при отображении записи: {e!s}")
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("display.error", error=str(e))
            )

    def prev_entry(self, event=None):
        """Переход к предыдущей записи или сегменту"""
        if not self.current_results or not self.current_entries:
            return
        if self.current_entry_index is None:
            return
        if self.current_entry_index > 0:
            if not self._guard_unsaved_changes():
                return
            self.current_entry_index -= 1
            self._display_current_entry()
        else:
            # Переход к последней записи предыдущего сегмента
            segment_names = list(self.current_results.keys())
            try:
                current_index = segment_names.index(self.current_segment)
            except (ValueError, AttributeError):
                return

            if current_index > 0:
                if not self._guard_unsaved_changes():
                    return
                prev_segment = segment_names[current_index - 1]
                self.current_segment = prev_segment
                self.current_entries = self.current_results[prev_segment]
                self.current_entry_index = len(self.current_entries) - 1
                self._display_current_entry()
                self._update_segment_selector()

    def next_entry(self, event=None):
        """Переход к следующей записи или сегменту"""
        if not self.current_results or not self.current_entries:
            return
        if self.current_entry_index is None:
            return
        if self.current_entry_index < len(self.current_entries) - 1:
            if not self._guard_unsaved_changes():
                return
            self.current_entry_index += 1
            self._display_current_entry()
        else:
            # Переход к первой записи следующего сегмента
            segment_names = list(self.current_results.keys())
            try:
                current_index = segment_names.index(self.current_segment)
            except (ValueError, AttributeError):
                return

            if current_index < len(segment_names) - 1:
                if not self._guard_unsaved_changes():
                    return
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
        if not self.current_results:
            return
        segment_names = list(self.current_results.keys())
        try:
            current_index = segment_names.index(self.current_segment)
        except (ValueError, AttributeError):
            return

        if current_index > 0:
            if not self._guard_unsaved_changes():
                return
            prev_segment = segment_names[current_index - 1]
            self.current_segment = prev_segment
            self.current_entries = self.current_results[prev_segment]
            self.current_entry_index = 0
            self._display_current_entry()
            self._update_segment_selector()

    def next_segment(self, event=None):
        """Переход к следующему сегменту"""
        if not self.current_results:
            return
        segment_names = list(self.current_results.keys())
        try:
            current_index = segment_names.index(self.current_segment)
        except (ValueError, AttributeError):
            return

        if current_index < len(segment_names) - 1:
            if not self._guard_unsaved_changes():
                return
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
        self.root.update()

        self.set_status(self.i18n.t("text.copied"), 100)

    def paste_translation(self):
        """Вставка перевода из буфера обмена в блок текущей записи"""
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            # Буфер обмена пуст
            messagebox.showinfo(
                self.i18n.t("info.title"),
                self.i18n.t("clipboard.empty")
            )
            return

        if not clipboard_text.strip():
            # Пустая вставка не должна выглядеть как «очистка перевода»:
            # пустой блок в _collect трактуется как «не редактировался»
            # (fallback на сохранённый перевод), поэтому блок не трогаем.
            messagebox.showinfo(
                self.i18n.t("info.title"),
                self.i18n.t("clipboard.empty")
            )
            return

        idx = self.current_entry_index
        if idx is None or not self.current_entries or idx >= len(self.current_entries):
            return

        bounds = self._find_entry_block_bounds(idx)
        if bounds is None:
            return
        block_start, end_rel = bounds
        # Заменяем только содержимое текущего блока, остальные записи страницы
        # не трогаем (старая версия чистила весь виджет и ломала маркеры [N]).
        self.translated_text.delete(f"1.0+{block_start}c", f"1.0+{block_start + end_rel}c")
        self.translated_text.insert(f"1.0+{block_start}c", clipboard_text)
        self._update_preview()
        self._update_spellcheck()
        self.set_status(self.i18n.t("translation.pasted"), 100)

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

    def _setup_search(self):
        """Настройка горячих клавиш для поиска и замены"""
        # Горячие клавиши для поиска
        self.root.bind('<Control-f>', lambda e: self.show_search_dialog())
        self.root.bind('<Control-F>', lambda e: self.show_search_dialog())
        self.root.bind('<F3>', lambda e: self.find_next())
        self.root.bind('<Shift-F3>', lambda e: self.find_prev())
        self.root.bind('<Control-h>', lambda e: self.show_replace_dialog())
        self.root.bind('<Control-H>', lambda e: self.show_replace_dialog())

        # Undo/Redo
        self.root.bind('<Control-z>', lambda e: self._undo())
        self.root.bind('<Control-Z>', lambda e: self._undo())
        self.root.bind('<Control-y>', lambda e: self._redo())
        self.root.bind('<Control-Y>', lambda e: self._redo())

    def _undo(self):
        """Отмена последнего действия"""
        widget = self.root.focus_get()
        if hasattr(widget, 'edit_undo'):
            try:
                widget.edit_undo()
            except tk.TclError:
                pass  # Нельзя отменить

    def _redo(self):
        """Повтор отменённого действия"""
        widget = self.root.focus_get()
        if hasattr(widget, 'edit_redo'):
            try:
                widget.edit_redo()
            except tk.TclError:
                pass  # Нельзя повторить

    def _setup_drag_drop(self):
        """Настройка поддержки drag & drop"""
        if TKINTERDND2_AVAILABLE:
            try:
                self.root.drop_target_register("DND_Files")
                self.root.dnd_bind('<<Drop>>', self._on_file_drop)
                logger.info("Drag & drop enabled")
            except Exception as e:
                logger.warning(f"Failed to enable drag & drop: {e}")
        else:
            logger.info("tkinterdnd2 not available, drag & drop disabled")

    def _on_file_drop(self, event):
        """Обработка перетаскивания файла"""
        # Получаем путь к файлу из события
        files = self.root.tk.splitlist(event.data)
        if files:
            file_path = files[0]
            # Проверяем расширение
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.gb', '.gbc', '.gba', '.sgb']:
                self.rom_path.set(file_path)
                self.update_game_info()
                self.set_status(self.i18n.t("status.rom.loaded"))
            else:
                messagebox.showwarning(
                    self.i18n.t("warning.title"),
                    self.i18n.t("invalid.rom.file")
                )

    def show_search_dialog(self):
        """Показывает диалог поиска"""
        if self.search_dialog and self.search_dialog.winfo_exists():
            self.search_dialog.lift()
            return

        self.search_dialog = tk.Toplevel(self.root)
        self.search_dialog.title(self.i18n.t("search.title"))
        self.search_dialog.geometry("350x120")
        self.search_dialog.transient(self.root)
        self.search_dialog.resizable(False, False)
        widgets.apply_window_icon(self.search_dialog)

        # Поле поиска
        search_frame = ttk.Frame(self.search_dialog, padding=theme.SPACING["MD"])
        search_frame.pack(fill="both", expand=True)

        ttk.Label(search_frame, text=self.i18n.t("search.find")).grid(row=0, column=0, sticky="w", pady=theme.SPACING["SM"])
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.grid(row=0, column=1, pady=theme.SPACING["SM"], padx=theme.SPACING["SM"])

        # Кнопки
        btn_frame = ttk.Frame(search_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=theme.SPACING["MD"])

        ttk.Button(btn_frame, text=self.i18n.t("search.next"), command=self.find_next).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(btn_frame, text=self.i18n.t("search.previous"), command=self.find_prev).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(btn_frame, text=self.i18n.t("search.close"), command=self.search_dialog.destroy).pack(side="left", padx=theme.SPACING["XS"])

        theme.apply(self.search_dialog, theme.is_dark())
        self.search_entry.focus()

    def show_replace_dialog(self):
        """Показывает диалог замены"""
        if self.replace_dialog and self.replace_dialog.winfo_exists():
            self.replace_dialog.lift()
            return

        self.replace_dialog = tk.Toplevel(self.root)
        self.replace_dialog.title(self.i18n.t("search.replace"))
        self.replace_dialog.geometry("400x150")
        self.replace_dialog.transient(self.root)
        self.replace_dialog.resizable(False, False)
        widgets.apply_window_icon(self.replace_dialog)

        # Поля ввода
        input_frame = ttk.Frame(self.replace_dialog, padding=theme.SPACING["MD"])
        input_frame.pack(fill="both", expand=True)

        ttk.Label(input_frame, text=self.i18n.t("search.find")).grid(row=0, column=0, sticky="w", pady=theme.SPACING["SM"])
        self.replace_search_entry = ttk.Entry(input_frame, width=30)
        self.replace_search_entry.grid(row=0, column=1, pady=theme.SPACING["SM"], padx=theme.SPACING["SM"])

        ttk.Label(input_frame, text=self.i18n.t("search.replace_with")).grid(row=1, column=0, sticky="w", pady=theme.SPACING["SM"])
        self.replace_entry = ttk.Entry(input_frame, width=30)
        self.replace_entry.grid(row=1, column=1, pady=theme.SPACING["SM"], padx=theme.SPACING["SM"])

        # Кнопки
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=theme.SPACING["MD"])

        ttk.Button(btn_frame, text=self.i18n.t("search.next"), command=self.find_next).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(btn_frame, text=self.i18n.t("search.replace"), command=self.replace_current).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(btn_frame, text=self.i18n.t("search.replace_all"), command=self.replace_all).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(btn_frame, text=self.i18n.t("search.close"), command=self.replace_dialog.destroy).pack(side="left", padx=theme.SPACING["XS"])

        theme.apply(self.replace_dialog, theme.is_dark())
        self.replace_search_entry.focus()

    def find_next(self, event=None):
        """Поиск следующего вхождения"""
        # Получаем текст из активного виджета
        text_widget = self._get_active_text_widget()
        if not text_widget:
            return

        if not text_widget.get("1.0", "end").strip():
            messagebox.showinfo(self.i18n.t("search.title"), self.i18n.t("search.no_results"))
            return

        search_term = self._get_search_term()
        if not search_term:
            self.show_search_dialog()
            return

        content = text_widget.get("1.0", "end-1c")

        # Конвертируем tkinter text index в character offset
        insert_index = text_widget.index("insert")
        start_offset = len(content[:int(insert_index.split('.')[0]) - 1]) + int(insert_index.split('.')[1])

        # Ищем от текущей позиции
        pos = content.find(search_term, start_offset)
        if pos == -1:
            # Ищем с начала
            pos = content.find(search_term)
            if pos == -1:
                messagebox.showinfo(self.i18n.t("search.title"), self.i18n.t("search.no_results"))
                return

        # Переходим к найденному
        line = content[:pos].count('\n') + 1
        col = pos - content[:pos].rfind('\n') - 1
        text_widget.mark_set("insert", f"{line}.{col}")
        text_widget.see(f"{line}.{col}")
        text_widget.tag_remove("sel", "1.0", "end")
        text_widget.tag_add("sel", f"{line}.{col}", f"{line}.{col + len(search_term)}")

    def find_prev(self, event=None):
        """Поиск предыдущего вхождения"""
        text_widget = self._get_active_text_widget()
        if not text_widget:
            return

        search_term = self._get_search_term()
        if not search_term:
            self.show_search_dialog()
            return

        content = text_widget.get("1.0", "end-1c")

        # Конвертируем tkinter text index в character offset
        insert_index = text_widget.index("insert")
        start_offset = len(content[:int(insert_index.split('.')[0]) - 1]) + int(insert_index.split('.')[1])

        # Ищем назад от текущей позиции
        before_cursor = content[:start_offset]
        pos = before_cursor.rfind(search_term)

        if pos == -1:
            # Ищем с конца
            pos = content.rfind(search_term)
            if pos == -1:
                messagebox.showinfo(self.i18n.t("search.title"), self.i18n.t("search.no_results"))
                return

        # Переходим к найденному
        line = content[:pos].count('\n') + 1
        col = pos - content[:pos].rfind('\n') - 1
        text_widget.mark_set("insert", f"{line}.{col}")
        text_widget.see(f"{line}.{col}")
        text_widget.tag_remove("sel", "1.0", "end")
        text_widget.tag_add("sel", f"{line}.{col}", f"{line}.{col + len(search_term)}")

    def _get_active_text_widget(self):
        """Получает активный текстовый виджет для поиска/замены.

        Если фокус находится в диалоге поиска или на виджете,
        который не является одним из трёх текстовых полей,
        возвращает последний редактируемый виджет (или translated_text).
        """
        focus_widget = self.root.focus_get()
        if focus_widget in (self.translated_text, self.original_text,
                            getattr(self, 'text_output', None)):
            self._last_edit_widget = focus_widget
            return focus_widget
        return getattr(self, '_last_edit_widget', None) or self.translated_text

    def _get_search_term(self):
        """Получает строку поиска из активного диалога"""
        if self.replace_dialog and self.replace_dialog.winfo_exists():
            return self.replace_search_entry.get()
        if self.search_dialog and self.search_dialog.winfo_exists():
            return self.search_entry.get()
        return ""

    def replace_current(self):
        """Заменяет текущее выделение"""
        text_widget = self._get_active_text_widget()
        if not text_widget:
            return

        search_term = self.replace_search_entry.get() if hasattr(self, 'replace_search_entry') else ""
        replace_term = self.replace_entry.get() if hasattr(self, 'replace_entry') else ""

        if not search_term:
            return

        # Проверяем, есть ли выделение
        try:
            selected = text_widget.get("sel.first", "sel.last")
            if selected == search_term:
                text_widget.delete("sel.first", "sel.last")
                text_widget.insert("insert", replace_term)
        except tk.TclError:
            pass

        # Переходим к следующему
        self.find_next()

    def replace_all(self):
        """Заменяет все вхождения"""
        text_widget = self._get_active_text_widget()
        if not text_widget:
            return

        search_term = self.replace_search_entry.get() if hasattr(self, 'replace_search_entry') else ""
        replace_term = self.replace_entry.get() if hasattr(self, 'replace_entry') else ""

        if not search_term:
            return

        content = text_widget.get("1.0", "end-1c")
        new_content = content.replace(search_term, replace_term)

        try:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", new_content)
        except tk.TclError:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("search.replaced.failed")
            )
            return

        count = content.count(search_term)
        messagebox.showinfo(
            self.i18n.t("search.replace"),
            self.i18n.t("search.replaced").format(count=count)
        )

        # Программные delete/insert не генерируют <KeyRelease> —
        # синхронизируем предпросмотр кодирования и спеллчек вручную
        try:
            self._update_preview()
            self._update_spellcheck()
        except Exception:
            pass

    def save_translation(self):
        """Сохранение перевода текущей записи"""
        if not self.current_entries:
            return

        translation = self._current_entry_from_widget()
        if not translation:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.translation")
            )
            return

        # Показываем предпросмотр перед сохранением
        if self._show_preview_dialog(translation):
            self.set_status(self.i18n.t("text.saving"), 50)

            # Здесь сохраняем перевод
            entry = self.current_entries[self.current_entry_index]
            # Во время модального диалога MT мог завершиться — перечитываем актуальное значение
            translation = self._current_entry_from_widget()
            # Сохраняем перевод в текущую запись (используется при инжекте)
            entry['translation'] = translation
            logger.info(f"Сохранен перевод для записи {self.current_entry_index}: {translation[:50]}...")

            self.set_status(self.i18n.t("text.saved"))
            messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("translation.saved"))

    def _is_entry_dirty(self) -> bool:
        """True, если перевод страницы в виджете отличается от сохранённого."""
        if not self.current_entries:
            return False
        try:
            widget_translations = self._collect_translations_from_widget()
            saved = [e.get('translation', e['text']) for e in self.current_entries]
        except Exception:
            # Не удалось распарсить блоки или битые записи — консервативно
            # считаем «изменено».
            return True
        return bool(widget_translations != saved)

    def _save_current_page_silent(self) -> bool:
        """Тихо сохраняет переводы ВСЕХ записей текущей страницы.

        Returns:
            bool: True — сохранено; False — не удалось собрать переводы.
        """
        if not self.current_entries:
            return True
        try:
            translations = self._collect_translations_from_widget()
        except Exception as exc:
            logger.error(f"Не удалось собрать переводы страницы: {exc!s}")
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("translation.saved.failed")
            )
            return False
        for i, entry in enumerate(self.current_entries):
            entry['translation'] = translations[i]
        self.set_status(self.i18n.t("text.saved"))
        return True

    def _guard_unsaved_changes(self) -> bool:
        """Защищает навигацию/выгрузку от потери несохранённого перевода.

        Returns:
            True — можно продолжать (изменений нет либо пользователь
            разрешил продолжить); False — операция отменяется пользователем.
        """
        if not self._is_entry_dirty():
            return True
        choice = messagebox.askyesnocancel(
            self.i18n.t("warning.title"),
            self.i18n.t("confirm.unsaved"),
        )
        if choice is None:
            return False
        if choice and not self._save_current_page_silent():
            return False
        return True

    def machine_translate_current(self):
        """Выполняет машинный перевод текущего текста (в фоновом потоке)."""
        if not self.current_entries:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("warning.no.text"))
            return

        entry = self.current_entries[self.current_entry_index]
        original_text = entry.get('text', '').strip()

        if not original_text:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("warning.no.original"))
            return

        if self._mt_in_progress:
            self.set_status(self.i18n.t("translation.in.progress"))
            return

        if getattr(self, '_inject_in_progress', False):
            self.set_status(self.i18n.t("translation.in.progress"))
            return

        if not self._mt_cloud_confirmed:
            if not messagebox.askyesno(
                self.i18n.t("confirm.title"),
                self.i18n.t("confirm.machine.translate")
            ):
                return
            self._mt_cloud_confirmed = True

        # Определяем языки
        source_lang = self.encoding_type.get()
        if source_lang == 'auto':
            if self.current_rom and hasattr(self, 'current_plugin') and self.current_plugin:
                source_lang = getattr(self.current_plugin, 'source_language', 'en')
            elif any(ord(c) > 0x3040 and ord(c) < 0x30FF for c in original_text):
                source_lang = 'ja'
            elif any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in original_text):
                source_lang = 'zh'
            elif any(0x0400 <= ord(c) <= 0x04FF for c in original_text):
                source_lang = 'ru'
            else:
                source_lang = 'en'

        target_lang = self.target_lang.get()

        self._mt_in_progress = True
        self._mt_error = None
        self._mt_result = None
        self._mt_entry_index = self.current_entry_index
        self._mt_segment = self.current_segment
        self._captured_mt_entry = entry
        self._mt_start_time = time.time()
        self.set_status(self.i18n.t("status.translating"), 0)

        def translate_task():
            try:
                translated = self.machine_translation.translate(original_text, source_lang, target_lang)
                self._mt_result = translated
            except Exception as exc:
                self._mt_error = exc

        self._mt_thread = threading.Thread(target=translate_task, daemon=True)
        self._mt_thread.start()
        self._poll_machine_translate()

    def _poll_machine_translate(self):
        """Poll machine-translate thread completion via root.after() — non-blocking."""
        thread = getattr(self, '_mt_thread', None)
        if thread is None:
            return
        if thread.is_alive():
            elapsed = time.time() - getattr(self, '_mt_start_time', time.time())
            self.set_status(
                f"{self.i18n.t('status.translating')} ({int(elapsed)}s)",
                5 + min(70, int(elapsed) * 2)
            )
            self.root.after(500, self._poll_machine_translate)
            return

        self._mt_in_progress = False
        self._mt_thread = None
        error = getattr(self, '_mt_error', None)
        result = getattr(self, '_mt_result', None)
        entry_index = self._mt_entry_index
        segment = self._mt_segment
        captured = self._captured_mt_entry
        self._mt_error = None
        self._mt_result = None
        self._mt_entry_index = None
        self._mt_segment = None
        self._captured_mt_entry = None

        if error is not None:
            self.set_status(self.i18n.t("translation.failed"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("translation.error").format(error=error)
            )
            return

        if result is None:
            self.set_status(self.i18n.t("translation.failed"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("translation.error").format(error="empty result")
            )
            return

        if captured is not None:
            captured['translation'] = result

        if (
            captured is not None
            and self.current_entries is not None
            and entry_index is not None
            and entry_index < len(self.current_entries)
            and self.current_entry_index == entry_index
            and self.current_segment == segment
            and captured is self.current_entries[entry_index]
        ):
            self._replace_current_entry_in_widget()
        if entry_index is not None:
            self.set_status(
                self.i18n.t("translation.completed.entry").format(entry=entry_index + 1)
            )
        else:
            self.set_status(self.i18n.t("translation.completed"))

    def _find_entry_block_bounds(self, idx):
        """Возвращает (block_start, end_rel) границы блока записи idx в translated_text.

        block_start — позиция текста перевода сразу после маркера ``[N] ``,
        end_rel — длина блока перевода (до следующего маркера ``[N] `` или конца).
        Использует ту же логику строгой последовательности маркеров, что и
        ``_collect_translations_from_widget``: границей блока считается только
        маркер следующего номера ``[idx+2]``, вложенный ``[N]`` внутри перевода
        не разрезает блок.
        """
        if idx is None or idx < 0:
            return None
        bounds = self._scan_entry_blocks(count=idx + 1)
        if idx >= len(bounds):
            return None
        return bounds[idx]

    def _find_marker_at_line_start(self, content, marker, from_pos=0):
        """Находит первое вхождение marker, стоящее в начале строки,
        начиная с позиции from_pos.
        """
        pos = content.find(marker, from_pos)
        while pos >= 0:
            if pos == 0 or content[pos - 1] == "\n":
                return pos
            pos = content.find(marker, pos + 1)
        return None

    def _scan_entry_blocks(self, content=None, count=None):
        """Сканирует блоки ``[N] `` в translated_text и возвращает список границ.

        Возвращаемое значение — список из count элементов (по умолчанию
        len(current_entries)): ``(block_start, end_rel)`` либо ``None``, если
        маркер не найден. Каждый следующий маркер ищется после конца
        предыдущего блока; границей блока считается только маркер следующего
        номера ``[idx+2]``, отделённый двойным переводом строки (формат
        виджета: блоки разделяются ``\n\n``). Используется единая логика для
        ``_find_entry_block_bounds`` и ``_collect_translations_from_widget``.
        """
        if count is None:
            if not self.current_entries:
                return []
            count = len(self.current_entries)
        if content is None:
            content = self.translated_text.get("1.0", tk.END)
        bounds: list[tuple[int, int] | None] = []
        search_from = 0
        block_stop_re = re.compile(r"\n\n\[(\d+)\] ")
        for idx in range(count):
            marker = f"[{idx + 1}] "
            start = self._find_marker_at_line_start(content, marker, search_from)
            if start is None:
                bounds.append(None)
                continue
            block_start = start + len(marker)
            rest = content[block_start:]
            end_rel = len(rest.rstrip("\n"))
            for m in block_stop_re.finditer(rest):
                if int(m.group(1)) == idx + 2:
                    end_rel = m.start()
                    break
            bounds.append((block_start, end_rel))
            search_from = block_start + end_rel
        return bounds

    def _replace_current_entry_in_widget(self):
        """Точечно заменяет блок текущей записи в translated_text, сохраняя остальные записи страницы."""
        idx = self.current_entry_index
        entries = self.current_entries
        if entries is None or idx is None or idx >= len(entries):
            return
        bounds = self._find_entry_block_bounds(idx)
        if bounds is None:
            return
        block_start, end_rel = bounds
        translation = entries[idx].get('translation', '')
        self.translated_text.delete(f"1.0+{block_start}c", f"1.0+{block_start + end_rel}c")
        self.translated_text.insert(f"1.0+{block_start}c", translation)
        self._update_preview()
        self._update_spellcheck()

    def _current_entry_from_widget(self):
        """Извлекает перевод текущей записи из её блока [N] в translated_text."""
        idx = self.current_entry_index
        if idx is None:
            return ""
        bounds = self._find_entry_block_bounds(idx)
        if bounds is None:
            return ""
        block_start, end_rel = bounds
        return self.translated_text.get("1.0", tk.END)[block_start:block_start + end_rel].rstrip("\n")

    def _collect_translations_from_widget(self):
        """Собирает переводы всех записей из блоков [N] в translated_text.

        Пустой блок означает «перевод не редактировался» — берётся
        сохранённый либо оригинал. Границы блоков вычисляет общий
        ``_scan_entry_blocks`` (та же логика строгой последовательности
        маркеров, что и в ``_find_entry_block_bounds``).
        """
        content = self.translated_text.get("1.0", tk.END)
        entries = self.current_entries or []
        bounds = self._scan_entry_blocks(content, count=len(entries))
        translations = []
        for idx, entry in enumerate(entries):
            bound = bounds[idx] if idx < len(bounds) else None
            if bound is None:
                translations.append(entry.get('translation', entry['text']))
                continue
            block_start, end_rel = bound
            block_text = content[block_start:block_start + end_rel].rstrip("\n")
            translations.append(block_text if block_text else entry.get('translation', entry['text']))
        return translations

    def _show_preview_dialog(self, translation):
        """Показывает диалог предпросмотра изменений"""
        if not self.current_entries:
            return True

        entry = self.current_entries[self.current_entry_index]
        original = entry.get('text', '')

        preview_dialog = tk.Toplevel(self.root)
        preview_dialog.title(self.i18n.t("preview.title"))
        preview_dialog.geometry("600x400")
        preview_dialog.transient(self.root)
        widgets.apply_window_icon(preview_dialog)

        # Сравнение текстов
        content_frame = ttk.Frame(preview_dialog, padding=theme.SPACING["MD"])
        content_frame.pack(fill="both", expand=True)

        # Оригинал
        orig_frame = ttk.LabelFrame(content_frame, text=self.i18n.t("original.text"), padding=theme.SPACING["SM"])
        orig_frame.pack(fill="both", expand=True, pady=theme.SPACING["SM"])
        orig_text = scrolledtext.ScrolledText(orig_frame, height=6, state="disabled")
        orig_text.pack(fill="both", expand=True)
        orig_text.config(state="normal")
        orig_text.insert("1.0", original)
        orig_text.config(state="disabled")

        # Перевод
        trans_frame = ttk.LabelFrame(content_frame, text=self.i18n.t("translated.text"), padding=theme.SPACING["SM"])
        trans_frame.pack(fill="both", expand=True, pady=theme.SPACING["SM"])
        trans_text = scrolledtext.ScrolledText(trans_frame, height=6, state="disabled")
        trans_text.pack(fill="both", expand=True)
        trans_text.config(state="normal")
        trans_text.insert("1.0", translation)
        trans_text.config(state="disabled")

        # Кнопки
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(fill="x", pady=theme.SPACING["MD"])

        result = {"confirmed": False}

        def confirm():
            result["confirmed"] = True
            preview_dialog.destroy()

        def cancel():
            preview_dialog.destroy()

        ttk.Button(btn_frame, text=self.i18n.t("preview.confirm"), command=confirm).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(btn_frame, text=self.i18n.t("preview.cancel"), command=cancel).pack(side="left", padx=theme.SPACING["SM"])

        theme.apply(preview_dialog, theme.is_dark())
        preview_dialog.grab_set()
        preview_dialog.wait_window()

        return result["confirmed"]

    def _setup_about_tab(self):
        """Настройка вкладки 'О программе'"""
        about_frame = ttk.Frame(self.about_tab, padding=theme.SPACING["XL"])
        about_frame.pack(fill="both", expand=True)

        # Заголовок
        title_label = ttk.Label(
            about_frame,
            text="GB Text Extractor & Translator",
            font=theme.ui_font(16, "bold")
        )
        title_label.pack(anchor="w", pady=(0, theme.SPACING["MD"]))

        # Версия
        version = self.get_version()
        version_label = ttk.Label(
            about_frame,
            text=self.i18n.t("about.version", version=version),
            font=theme.ui_font(10)
        )
        version_label.pack(anchor="w", pady=(0, theme.SPACING["LG"]))

        # Описание
        description = ttk.Label(
            about_frame,
            text=self.i18n.t("about.description"),
            wraplength=700,
            justify="left"
        )
        description.pack(anchor="w", pady=(0, theme.SPACING["XL"]))

        # Юридическое предупреждение
        legal_frame = ttk.LabelFrame(about_frame, text=self.i18n.t("about.legal.title"), padding=theme.SPACING["MD"])
        legal_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["XL"]))

        legal_text = ttk.Label(
            legal_frame,
            text=self.i18n.t("about.legal.text"),
            wraplength=700,
            justify="left"
        )
        legal_text.pack(anchor="w")

        # Ссылки
        links_frame = ttk.LabelFrame(about_frame, text=self.i18n.t("about.links"), padding=theme.SPACING["MD"])
        links_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["XL"]))

        # GitHub ссылка
        github_frame = ttk.Frame(links_frame)
        github_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["SM"]))

        github_label = ttk.Label(
            github_frame,
            text=self.i18n.t("about.github") + ":",
            font=theme.ui_font(9, "bold")
        )
        github_label.pack(side="left", padx=(0, theme.SPACING["SM"]))

        self.github_link = ttk.Label(
            github_frame,
            text="github.com/Far-g-Us/GB2Text",
            cursor="hand2",
            font=theme.ui_font(9)
        )
        self.github_link.configure({"foreground": theme.get("accent")})
        self.github_link.pack(side="left")
        self.github_link.bind("<Button-1>", lambda e: self.open_url("https://github.com/Far-g-Us/GB2Text"))

        # # Документация ссылка
        # docs_frame = ttk.Frame(links_frame)
        # docs_frame.pack(fill="x", expand=False, pady=(theme.SPACING["SM"], 0))
        #
        # docs_label = ttk.Label(
        #     docs_frame,
        #     text=self.i18n.t("about.documentation") + ":",
        #     font=("Helvetica", 9, "bold")
        # )
        # docs_label.pack(side="left", padx=(0, theme.SPACING["SM"]))
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
        """Полностью обновляет интерфейс с новым языком.

        Вызывается только из change_ui_language() и save_settings(), которые
        уже провели _guard_unsaved_changes() до смены языка — здесь guard
        не нужен (иначе был бы двойной диалог при Discard).
        """
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
        try:
            if current_rom:
                self.rom_path.set(current_rom)
                self.update_game_info()

            if current_results:
                self.current_results = current_results
                self._refresh_segments_list(self.current_results.keys())
                self._update_toolbar_menu_state()
                if self.segments_list.size() > 0:
                    self.segments_list.selection_set(0)
                    self.on_segment_select(None)

            if current_segment and current_entry_index >= 0:
                self.current_segment = current_segment
                self.current_entry_index = current_entry_index
                self._display_current_entry()
        except Exception as e:
            logger.warning(f"Failed to restore UI state: {e}")

        self.set_status(self.i18n.t("status.ready"))
        self.apply_theme()

    def change_ui_language(self, event=None):
        """Изменяет язык интерфейса приложения"""
        chosen_lang = language_code(self.ui_lang.get())
        if not self._guard_unsaved_changes():
            # «Отмена» — откатываем комбобокс к фактически применяемому языку.
            self.ui_lang.set(self.i18n.current_lang or "en")
            return
        self.i18n.change_language(chosen_lang)

        # Обновляем все тексты в интерфейсе
        self.root.title(self.i18n.t("app.title"))

        # Обновляем названия вкладок
        self.tab_control.tab(self.extract_tab, text=self.i18n.t("tab.extract"))
        self.tab_control.tab(self.edit_tab, text=self.i18n.t("tab.edit"))
        self.tab_control.tab(self.settings_tab, text=self.i18n.t("tab.settings"))
        self.tab_control.tab(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Обновляем все метки
        self._refresh_ui()

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
        diagnostics_frame = ttk.Frame(self.diagnostics_tab, padding=theme.SPACING["MD"])
        diagnostics_frame.pack(fill="both", expand=True)

        # Панель управления
        control_frame = ttk.Frame(diagnostics_frame)
        control_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["MD"]))

        ttk.Button(control_frame, text=self.i18n.t("diagnostics.start"),
                   command=self.run_diagnostics).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(control_frame, text=self.i18n.t("save.log"),
                   command=self.save_log).pack(side="left", padx=theme.SPACING["SM"])

        # Текстовая область для логов
        self.log_text = scrolledtext.ScrolledText(diagnostics_frame, wrap="word", font=theme.mono_font(10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

        # Автоматическая загрузка текущего лога
        self.load_current_log()

    def _setup_map_tab(self):
        """Настройка вкладки карты ROM"""
        map_frame = ttk.Frame(self.map_tab, padding=theme.SPACING["MD"])
        map_frame.pack(fill="both", expand=True)

        # Статусная панель с деталями выбранного сегмента
        self.map_status_var = tk.StringVar(value=self.i18n.t("map.no.rom"))
        ttk.Label(map_frame, textvariable=self.map_status_var, font=theme.mono_font(10)).pack(
            fill="x", pady=(0, theme.SPACING["SM"]))

        # Полотно с блоками ROM
        map_body = ttk.Frame(map_frame)
        map_body.pack(fill="both", expand=True)

        self.map_canvas = tk.Canvas(map_body, height=360, highlightthickness=1,
                                    highlightbackground=theme.get("border"))
        map_scrollbar = ttk.Scrollbar(map_body, orient="vertical", command=self.map_canvas.yview)
        self.map_canvas.configure(yscrollcommand=map_scrollbar.set)
        self.map_canvas.pack(side="left", fill="both", expand=True)
        map_scrollbar.pack(side="right", fill="y")

        def _on_map_wheel(event):
            self.map_canvas.yview_scroll(int(-event.delta / 120), "units")

        def _on_map_button_4(_event):
            self.map_canvas.yview_scroll(-1, "units")

        def _on_map_button_5(_event):
            self.map_canvas.yview_scroll(1, "units")

        self.map_canvas.bind("<MouseWheel>", _on_map_wheel)
        self.map_canvas.bind("<Button-4>", _on_map_button_4)
        self.map_canvas.bind("<Button-5>", _on_map_button_5)
        self.map_canvas.bind("<Button-1>", self._on_map_click)

        # Инлайн-легенда
        legend_frame = ttk.Frame(map_frame)
        legend_frame.pack(fill="x", pady=(theme.SPACING["SM"], 0))
        self._legend_swatch = tk.Canvas(legend_frame, width=14, height=14, highlightthickness=0)
        self._legend_swatch.pack(side="left", padx=(0, theme.SPACING["XS"]))
        ttk.Label(legend_frame, text=self.i18n.t("map.legend.free")).pack(side="left", padx=(0, theme.SPACING["MD"]))
        self._legend_swatch_seg = tk.Canvas(legend_frame, width=14, height=14, highlightthickness=0)
        self._legend_swatch_seg.pack(side="left", padx=(0, theme.SPACING["XS"]))
        ttk.Label(legend_frame, text=self.i18n.t("map.legend.segments")).pack(side="left")

        self.tab_control.bind("<<NotebookTabChanged>>", self._on_map_tab_changed)
        self._draw_map()

    def _on_map_tab_changed(self, event):
        """Перерисовка карты при переключении на вкладку"""
        try:
            if self.tab_control.select() == str(self.map_tab):
                self._draw_map()
        except tk.TclError:
            pass

    def _map_redraw(self):
        """Перерисовка карты после смены темы или обновления данных"""
        try:
            self._draw_map()
        except (tk.TclError, RuntimeError):
            pass

    def _draw_map(self):
        """Отрисовка блоков ROM на карте"""
        if not hasattr(self, "map_canvas"):
            return
        canvas = self.map_canvas
        canvas.delete("all")
        bg = theme.get("bg")
        free_color = theme.get("surface")
        seg_color = theme.get("accent")
        border = theme.get("border")
        text_color = theme.get("text-muted")

        if self.current_rom is None:
            canvas.config(bg=bg, highlightbackground=border)
            canvas.create_text(canvas.winfo_width() // 2 or 200, 160,
                               text=self.i18n.t("map.no.rom"), fill=text_color)
            return

        size = len(self.current_rom.data)
        block_size = 0x8000
        blocks = max(1, (size + block_size - 1) // block_size)

        width = max(canvas.winfo_width(), 200)
        margin = 4
        gutter = 64
        usable = width - gutter - margin
        x0, x1 = gutter, gutter + usable
        row_h = 12

        # Рисуем блоки по одному столбцу; высота канваса минимально 10px на блок
        canvas.config(height=max(120, blocks * row_h + 8))
        canvas.config(bg=bg, highlightbackground=border)

        # Раскраска легенды
        for swatch in (self._legend_swatch, self._legend_swatch_seg):
            swatch.delete("all")
        self._legend_swatch.create_rectangle(0, 0, 14, 14, fill=free_color, outline=border)
        self._legend_swatch_seg.create_rectangle(0, 0, 14, 14, fill=seg_color, outline=border)

        for i in range(blocks):
            y = 6 + i * row_h
            start = i * block_size
            end = min(size, start + block_size)
            color = free_color
            for seg in self.current_segments_meta:
                seg_end = seg.get("end", seg.get("start", 0))
                if seg.get("start", 0) < end and seg_end > start:
                    color = seg_color
                    break
            canvas.create_rectangle(x0, y, x1, y + row_h - 2, fill=color,
                                    outline=border, width=0)

        # Разметка позиций: слева шкала адресов (гуттер), блоки за ним
        for i in range(blocks):
            y = 6 + i * row_h
            canvas.create_text(margin, y + (row_h - 2) / 2, anchor="w",
                               text=f"0x{i * block_size:05X}", fill=text_color,
                               font=theme.mono_font(8))

        # Маркер размера
        total_kb = size // 1024
        canvas.create_text(width - margin, 4, anchor="ne",
                           text=f"{total_kb} KB", fill=text_color,
                           font=theme.mono_font(9))

        if not self.current_segments_meta:
            canvas.create_text(margin, 6 + blocks * row_h + 8, anchor="w",
                               text=self.i18n.t("map.no.segments"), fill=text_color,
                               font=theme.mono_font(9))

        # Скролл-регион под весь контент карты
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_map_click(self, event):
        """Обработка клика по блоку: показывает сегменты внутри"""
        if self.current_rom is None or not hasattr(self, "map_canvas"):
            return
        block_size = 0x8000
        row_h = 12
        blocks = max(1, (len(self.current_rom.data) + block_size - 1) // block_size)
        i = min(max(0, (event.y - 6) // row_h), blocks - 1)
        start = i * block_size
        end = min(len(self.current_rom.data), start + block_size)

        inside = [seg for seg in self.current_segments_meta
                  if seg.get("start", 0) < end and seg.get("end", seg.get("start", 0)) > start]
        if inside:
            parts = []
            for seg in inside:
                seg_start = seg.get("start", 0)
                seg_end = seg.get("end", seg.get("start", 0))
                parts.append(f"{seg.get('name', '?')}: 0x{seg_start:05X}-0x{seg_end:05X} "
                             f"({seg_end - seg_start + 1} B)")
            self.map_status_var.set(" | ".join(parts))
        else:
            self.map_status_var.set(f"0x{start:05X}-0x{end - 1:05X}")

    def load_current_log(self):
        """Загружает текущий лог-файл в текстовую область"""
        try:
            if getattr(sys, "frozen", False):
                log_path = str(Path(sys.executable).parent / "gb2text.log")
            else:
                log_path = self._get_resource_path('gb2text.log')
            with open(log_path) as f:
                log_content = f.read()

            self.log_text.config(state="normal")
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, log_content)
            self.log_text.config(state="disabled")

            # Автопрокрутка к концу
            self.log_text.see(tk.END)
        except Exception as e:
            logger = logging.getLogger('gb2text.gui')
            logger.error(f"Не удалось загрузить лог-файл: {e!s}")

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

            detected_languages = detect_multiple_languages(self.current_rom.data, 0, sample_size)

            # Дополнительная статистика по языкам
            ascii_count = sum(freq.get(i, 0) for i in range(0x20, 0x7F))
            japanese_count = sum(freq.get(i, 0) for i in range(0xA0, 0xDF)) + sum(
                freq.get(i, 0) for i in range(0x80, 0x9F))
            cyrillic_count = sum(freq.get(i, 0) for i in range(0xA0, 0xBF)) + sum(
                freq.get(i, 0) for i in range(0xC0, 0xFF))

            total_bytes = sum(freq.values())

            language_stats = {
                "detected_languages": detected_languages,
                "ascii_density": ascii_count / total_bytes if total_bytes > 0 else 0,
                "japanese_density": japanese_count / total_bytes if total_bytes > 0 else 0,
                "cyrillic_density": cyrillic_count / total_bytes if total_bytes > 0 else 0,
                "sample_size": sample_size,
                "most_common_bytes": freq.most_common(10)
            }

            diagnostics_info["language_analysis"] = language_stats
            logger.info(f"Обнаруженные языки ROM: {detected_languages}")
            logger.info(f"ASCII плотность: {language_stats['ascii_density']:.2%}")
            logger.info(f"Японская плотность: {language_stats['japanese_density']:.2%}")
            logger.info(f"Кириллическая плотность: {language_stats['cyrillic_density']:.2%}")

        except Exception as e:
            logger.error(f"Ошибка при определении языка: {e!s}")
            diagnostics_info["language_analysis"] = {"error": str(e)}

        # Анализ текстовых сегментов
        game_id = self.current_rom.get_game_id()
        plugin = self.plugin_manager.get_plugin(game_id, self.current_rom.system, rom=self.current_rom)

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
                segment_data = self.current_rom.data[segment['start']:segment['end']]
                segment_langs = detect_multiple_languages(
                    self.current_rom.data,
                    segment['start'],
                    len(segment_data)
                )

                analysis["detected_language"] = segment_langs
                analysis["lang"] = segment.get("lang", segment_langs[0] if segment_langs else "english")

                diagnostics_info["segments"].append({
                    "name": segment['name'],
                    "start": segment['start'],
                    "end": segment['end'],
                    "lang": segment.get("lang", segment_langs[0] if segment_langs else "english"),
                    "analysis": analysis
                })

        # Сохранение диагностики
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        diag_file = f"diagnostics_{timestamp}.json"

        try:
            with open(diag_file, 'w', encoding='utf-8') as f:
                json.dump(diagnostics_info, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error(f"Не удалось сохранить диагностику: {exc}")
            messagebox.showerror(
                self.i18n.t("error.title"),
                f"{self.i18n.t('export.error')}: {exc}"
            )
            return

        logger.info(f"Диагностика сохранена в {diag_file}")
        self.set_status(self.i18n.t("diagnostics.completed"), 100)

        messagebox.showinfo(
            self.i18n.t("success.title"),
            f"{self.i18n.t('diagnostics.saved').format(path=os.path.basename(diag_file))}"
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
                if getattr(sys, "frozen", False):
                    log_path = str(Path(sys.executable).parent / "gb2text.log")
                else:
                    log_path = self._get_resource_path('gb2text.log')
                with open(log_path) as src, open(save_path, 'w') as dst:
                    dst.write(src.read())
                messagebox.showinfo(
                    self.i18n.t("success.title"),
                    self.i18n.t("log.saved").format(path=os.path.basename(save_path))
                )
            except Exception as e:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("log.save.error").format(error=e)
                )

    def inject_translation(self):
        """Внедрение перевода в ROM (в фоновом потоке, без фриза UI)."""
        if not self.current_segment or not self.current_entries:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("warning.no.segment")
            )
            return

        if getattr(self, '_inject_in_progress', False):
            self.set_status(self.i18n.t("injection.in.progress"))
            return

        if self._mt_in_progress:
            self.set_status(self.i18n.t("translation.in.progress"))
            return

        if not messagebox.askyesno(self.i18n.t("confirm.title"), self.i18n.t("confirm.inject")):
            return

        self._inject_in_progress = True
        plugin = self.plugin_manager.get_plugin(
            self.current_rom.get_game_id(), self.current_rom.system, rom=self.current_rom
        )
        self.set_status(self.i18n.t("text.injecting"), 0)

        # Получаем переводы из виджета (блоки [N] в translated_text); те записи,
        # которые не редактировались — берут сохранённый перевод либо оригинал
        if self.current_entries and self.translated_text.get("1.0", "end-1c"):
            translations = self._collect_translations_from_widget()
        else:
            translations = [e.get('translation', e['text']) for e in self.current_entries]

        self._inject_error = None
        self._inject_success = False
        self._inject_start_time = time.time()

        def inject_task():
            try:
                self._inject_success = self.text_injector.inject_segment(
                    self.current_segment,  # имя сегмента строкой
                    translations,
                    plugin,
                )
            except Exception as exc:
                self._inject_error = exc

        self._inject_thread = threading.Thread(target=inject_task, daemon=True)
        self._inject_thread.start()
        self._poll_injection()

    def _poll_injection(self):
        """Poll injection thread completion via root.after() — non-blocking."""
        thread = getattr(self, '_inject_thread', None)
        if thread is None:
            return
        if thread.is_alive():
            elapsed = time.time() - getattr(self, '_inject_start_time', time.time())
            progress = 5 + min(70, int(elapsed) * 2)
            self.set_status(
                f"{self.i18n.t('text.injecting')} ({int(elapsed)}s)",
                progress
            )
            self.root.after(500, self._poll_injection)
            return

        # Thread finished — grab results and clean state atomically
        self._inject_in_progress = False
        self._inject_thread = None
        error = getattr(self, '_inject_error', None)
        success = getattr(self, '_inject_success', False)
        self._inject_error = None
        self._inject_success = False

        if error is not None:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("inject.error.detail", error=str(error))
            )
            return

        if not success:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("inject.error")
            )
            return

        try:
            self.set_status(self.i18n.t("status.saving"), 75)

            # Собираем потерянные символы до диалога сохранения — сброс
            # списков происходит и при отмене, иначе следующий инжект
            # показал бы объединённый отчёт двух прогонов
            try:
                unmapped = self.text_injector.collect_unmapped_chars()
            except Exception as exc:
                logger.warning(f"Не удалось подсчитать потерянные символы: {exc}")
                unmapped = []
            if unmapped:
                messagebox.showwarning(
                    self.i18n.t("warning.title"),
                    self.i18n.t("inject.unmapped").format(chars="".join(unmapped))
                )

            # Сохраняем измененный ROM
            output_path = filedialog.asksaveasfilename(
                defaultextension=".gb",
                filetypes=[
                    ("GB/GBC/GBA ROM files", "*.gb *.gbc *.sgb *.gba"),
                    ("All files", "*.*")
                ],
                title=self.i18n.t("file.save.rom")
            )

            if not output_path:
                self.set_status(self.i18n.t("status.ready"))
                return

            self.text_injector.save(output_path)
            self.set_status(self.i18n.t("text.injected"))
            messagebox.showinfo(
                self.i18n.t("success.title"),
                self.i18n.t("inject.success", path=os.path.basename(output_path))
            )
            try:
                self._show_overflow_report()
            except Exception as exc:
                logger.warning(f"Не удалось показать отчёт о переполнении: {exc}")
        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("inject.error.detail", error=str(e))
            )

    def _on_overflow_close(self, win):
        """Закрытие диалога отчёта: снимает guard и уничтожает окно."""
        if getattr(self, '_overflow_dialog', None) is win:
            self._overflow_dialog = None
        win.destroy()

    def _show_overflow_report(self):
        """Показывает полный отчёт о строках, не поместившихся в ROM."""
        report = getattr(self.text_injector, 'last_overflow_report', []) or []
        if not report:
            return
        dialog = getattr(self, '_overflow_dialog', None)
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    self._on_overflow_close(dialog)
            except tk.TclError:
                self._overflow_dialog = None
        lines = self._overflow_report_lines(report)

        win = tk.Toplevel(self.root)
        self._overflow_dialog = win
        win.title(self.i18n.t("inject.overflow.title"))
        win.geometry("760x480")
        win.transient(self.root)
        widgets.apply_window_icon(win)
        try:
            win.grab_set()
        except tk.TclError:
            pass
        win.focus_set()
        win.protocol('WM_DELETE_WINDOW', lambda: self._on_overflow_close(win))
        win.bind('<Escape>', lambda e: self._on_overflow_close(win))

        header = ttk.Label(
            win,
            text=self.i18n.t("inject.overflow.summary", count=len(report)),
            wraplength=720,
            justify="left",
        )
        header.pack(fill="x", padx=theme.SPACING["MD"], pady=(theme.SPACING["MD"], theme.SPACING["SM"]))

        text = scrolledtext.ScrolledText(win, wrap="word", font=theme.mono_font(9))
        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=theme.SPACING["MD"], pady=(0, theme.SPACING["SM"]))
        text.focus_set()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=theme.SPACING["MD"], pady=(0, theme.SPACING["MD"]))
        copy_btn = ttk.Button(
            btns,
            text=self.i18n.t("inject.overflow.copy"),
            command=lambda: self._copy_overflow_report(text, copy_btn),
        )
        copy_btn._orig_text = self.i18n.t("inject.overflow.copy")
        copy_btn.pack(side="right", padx=(theme.SPACING["SM"], 0))
        ttk.Button(
            btns,
            text=self.i18n.t("inject.overflow.close"),
            command=lambda: self._on_overflow_close(win),
        ).pack(side="right")

        theme.apply(win, theme.is_dark())

    def _copy_overflow_report(self, text_widget, button):
        """Копирует полный отчёт о переполнении в буфер обмена с фидбеком."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text_widget.get("1.0", "end-1c"))
        logger.info("Отчёт о переполнении скопирован в буфер обмена")
        after_id = getattr(button, '_after_id', None)
        if after_id is not None:
            try:
                button.after_cancel(after_id)
            except Exception:
                pass
        original = getattr(button, '_orig_text', button.cget("text"))
        button.config(text="✓ " + self.i18n.t("inject.overflow.copied"))
        button._after_id = button.after(
            1500,
            lambda b=button, o=original: b.config(text=o) if b.winfo_exists() else None,
        )

    def _overflow_report_lines(self, report):
        """Формирует строки полного отчёта (без усечения текстов)."""
        lines = []
        for item in report:
            text = item.get('text', '')
            lines.append(self.i18n.t(
                "inject.overflow.line",
                target=item.get('target', 0),
                need=item.get('length', 0),
                free=item.get('free_after', 0),
                text=text,
            ))
        return lines

    def _write_settings_file(self, settings: dict) -> bool:
        """Атомарно записывает settings.json рядом с исполняемым файлом."""
        settings_dir = Path("settings")
        try:
            settings_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=settings_dir)
            os.close(fd)
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, settings_dir / "settings.json")
                return True
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.error(f"Не удалось сохранить настройки: {exc}")
            return False

    def save_settings(self, silent: bool = False):
        """Сохранение настроек локализации.
        silent=True — только запись в файл, без пересоздания UI и messagebox."""
        if not silent and not self._guard_unsaved_changes():
            return

        # Сохраняем выбранный язык интерфейса (код языка, а не название)
        ui_lang_code = language_code(self.ui_lang.get())
        settings = {
            "ui_language": ui_lang_code,
            "target_language": self.target_lang.get(),
            "encoding_type": self.encoding_type.get(),
            "verbose_unknown": self.verbose_unknown_var.get(),
            "theme": self.theme.get(),
            "mt_service": self.mt_service.get(),
            "bing_region": self.bing_region.get(),
            "spell_enabled": self.spell_enabled.get(),
            "spell_lang": self.spell_lang.get()
        }

        # API-ключи машинного перевода — только в защищённом хранилище,
        # в settings.json их нет и не будет.
        secret_ok = True
        deepl_value = self.deepl_key.get()
        if deepl_value:
            secret_ok = secret_store.store_secret("deepl_key", deepl_value) and secret_ok
        else:
            secret_store.delete_secret("deepl_key")
        bing_value = self.bing_key.get()
        if bing_value:
            secret_ok = secret_store.store_secret("bing_key", bing_value) and secret_ok
        else:
            secret_store.delete_secret("bing_key")

        file_ok = self._write_settings_file(settings)

        if not file_ok and not silent:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                f"{self.i18n.t('export.error')}",
            )
        if not secret_ok and not silent:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t("mt.secret.save_failed"),
            )

        if silent:
            # Тихий режим (например toggle verbose_unknown): язык меняем
            # без диалогов и без перестройки UI.
            self.i18n.change_language(ui_lang_code)
            return

        # Обновляем текущий язык интерфейса
        self.i18n.change_language(ui_lang_code)

        # Обновляем интерфейс
        self._refresh_ui()

        # Применяем настройки машинного перевода
        self._apply_mt_settings()

        messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("settings.saved"))

    def _apply_mt_settings(self):
        """Применяет настройки машинного перевода"""
        self.machine_translation = MachineTranslation()

        # Добавляем Google (всегда доступен)
        self.machine_translation.add_google_translator()

        # Добавляем DeepL если есть ключ
        deepl_key = self.deepl_key.get()
        if deepl_key:
            self.machine_translation.add_deepl_translator(deepl_key)

        # Добавляем Bing если есть ключ
        bing_key = self.bing_key.get()
        if bing_key:
            region = self.bing_region.get() or 'global'
            self.machine_translation.add_bing_translator(bing_key, region)

        # Устанавливаем текущий сервис
        service = self.mt_service.get()
        try:
            self.machine_translation.set_service(service)
        except ValueError:
            # Если сервис недоступен, используем первый доступный
            available = self.machine_translation.get_available_services()
            if available:
                self.machine_translation.set_service(available[0])
                self.mt_service.set(available[0])

    def apply_theme(self):
        """Применяет выбранную тему оформления"""
        theme.apply(self.root, self.theme.get() == "dark")

    def _setup_guide_tab(self):
        """Настройка вкладки руководства"""
        guide_frame = ttk.Frame(self.guide_tab, padding=theme.SPACING["MD"])
        guide_frame.pack(fill="both", expand=True)

        # Панель управления
        control_frame = ttk.Frame(guide_frame)
        control_frame.pack(fill="x", expand=False, pady=(0, theme.SPACING["MD"]))

        ttk.Button(control_frame, text=self.i18n.t("load.template"), command=self.load_guide_template).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(control_frame, text=self.i18n.t("save.guide"), command=self.save_guide).pack(side="left", padx=theme.SPACING["SM"])
        ttk.Button(control_frame, text=self.i18n.t("apply.guide"), command=self.apply_guide).pack(side="left", padx=theme.SPACING["SM"])

        # Текстовое представление руководства
        self.guide_text = scrolledtext.ScrolledText(guide_frame, wrap="word", font=theme.mono_font(10))
        self.guide_text.pack(fill="both", expand=True)
        self.guide_text.config(state="disabled")

    def show_warning_dialog(self):
        """Показывает юридическое предупреждение при запуске"""
        win = tk.Toplevel(self.root)
        win.title(self.i18n.t("warning.title"))
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        widgets.apply_window_icon(win)

        body = ttk.Frame(win, padding=(24, 24, 24, 16))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        icon_panel = ttk.Frame(body)
        icon_panel.grid(column=0, row=0, sticky="nsew", padx=(0, 12))
        icon_label = ttk.Label(icon_panel, text="\u26a0\ufe0f", font=("Segoe UI Emoji", 18))
        icon_label.pack(expand=True)

        msg = ttk.Label(body, text=self.i18n.t("legal.warning"), wraplength=480, justify="left")
        msg.grid(column=1, row=0, sticky="nsew")

        ttk.Button(body, text="OK", command=win.destroy).grid(
            column=0, row=1, columnspan=2, pady=(16, 0)
        )

        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"+{x}+{y}")
        win.wait_window()

    def on_closing(self):
        """Обработка закрытия окна"""
        was_dirty = self._is_entry_dirty()
        if not self._guard_unsaved_changes():
            return
        if was_dirty or messagebox.askyesno(
                self.i18n.t("confirm.title"),
                self.i18n.t("confirm.exit")
        ):
            theme.unregister_post_apply_hook(self._reapply_compare_colors)
            theme.unregister_post_apply_hook(self._reapply_about_colors)
            theme.unregister_post_apply_hook(self._map_redraw)
            self.root.destroy()

    def get_version(self):
        """Возвращает версию приложения"""
        try:
            version_path = self._get_resource_path('VERSION')
            with open(version_path) as f:
                version = f.read().strip()
                return version
        except OSError:
            return "1.0.0"

    def open_url(self, url):
        """Открывает URL в браузере по умолчанию"""
        import webbrowser
        webbrowser.open(url)

    def _set_app_icon(self):
        """Устанавливает пользовательскую иконку приложения"""
        try:
            # Сохраняем ссылки на изображения: tk.PhotoImage без живой ссылки
            # может быть собран сборщиком мусора, и иконка "иногда" пропадает
            # из titlebar после отрисовки окна.
            self._app_icon_images: list = []
            icon_set = False

            resources_dir = Path(self._get_resource_path("resources"))
            if not resources_dir.exists():
                # Нет каталога ресурсов — не создаём его на диске, используем
                # встроенную иконку по умолчанию.
                self._create_default_icon()
                return

            if platform.system() == "Windows":
                ico_path = resources_dir / "app_icon.ico"
                png_path = resources_dir / "app_icon.png"
                # Иконка titlebar в Windows берётся из .ico (iconbitmap,
                # перезаписывает PNG-вариант). PNG через iconphoto ставим
                # для дочерних окон как fallback, пока присутствует .ico.
                if png_path.exists():
                    img = tk.PhotoImage(file=str(png_path))
                    self._app_icon_images.append(img)
                    self.root.iconphoto(True, img)
                    icon_set = True
                if ico_path.exists():
                    try:
                        self.root.iconbitmap(str(ico_path))
                        icon_set = True
                    except tk.TclError:
                        pass
            else:
                icon_path = resources_dir / "app_icon.png"
                if icon_path.exists():
                    img = tk.PhotoImage(file=str(icon_path))
                    self._app_icon_images.append(img)
                    self.root.iconphoto(True, img)
                    icon_set = True

            if not icon_set:
                # Если пользовательской иконки нет, создаем стандартную
                self._create_default_icon()

        except Exception as e:
            logger.error(f"Ошибка при установке иконки: {e!s}")
            self._create_default_icon()

    def _create_default_icon(self):
        """Создает простую стандартную иконку, если пользовательская отсутствует"""
        try:
            # Создаем простое изображение как иконку
            # Сохраняем ссылку, иначе PhotoImage будет собран GC
            if not hasattr(self, '_default_icon_image'):
                width, height = 16, 16
                icon = tk.PhotoImage(width=width, height=height)

                # Заполняем фон
                icon.put(theme.BRAND["bg"], to=(0, 0, width, height))

                # Рисуем букву "G" (для Game Boy)
                icon.put(theme.BRAND["fg"], to=(3, 3, 6, 12))  # Вертикальная линия
                icon.put(theme.BRAND["fg"], to=(3, 3, 12, 6))  # Горизонтальная линия
                icon.put(theme.BRAND["fg"], to=(9, 6, 12, 12))  # Правая часть

                self._default_icon_image = icon

            self.root.iconphoto(True, self._default_icon_image)
        except Exception as e:
            logger.error(f"Не удалось создать стандартную иконку: {e!s}")

class _CharmapEditorDialog:
    """Модальный диалог просмотра и правки таблицы символов.

    Ром не модифицируется — изменения живут в диалоге и могут быть
    экспортированы в JSON.
    """

    def __init__(self, parent, owner, grab=True):
        self.owner = owner
        self.win = tk.Toplevel(parent)
        self.win.title(owner.i18n.t("tbl.editor.title"))
        self.win.geometry("600x440")
        if grab:
            self.win.grab_set()

        frame = ttk.Frame(self.win, padding=theme.SPACING["MD"])
        frame.pack(fill="both", expand=True)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, theme.SPACING["SM"]))
        ttk.Button(toolbar, text=owner.i18n.t("tbl.editor.add"),
                   command=self._show_add_dialog).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(toolbar, text=owner.i18n.t("tbl.editor.edit"),
                   command=self._show_edit_dialog).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(toolbar, text=owner.i18n.t("tbl.editor.remove"),
                   command=self._remove_selected).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(toolbar, text=owner.i18n.t("tbl.editor.export"),
                   command=self._export_to_json).pack(side="left", padx=theme.SPACING["XS"])

        self.total_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.total_var).pack(anchor="w", pady=(0, theme.SPACING["SM"]))

        columns = ("code", "char", "desc")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("code", text=owner.i18n.t("tbl.editor.code"))
        self.tree.heading("char", text=owner.i18n.t("tbl.editor.char"))
        self.tree.heading("desc", text=owner.i18n.t("tbl.editor.desc"))
        self.tree.column("code", width=80, anchor="center")
        self.tree.column("char", width=180, anchor="center")
        self.tree.column("desc", width=260)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._show_edit_dialog())

        self._charmap = dict(owner._editor_charmap())
        self._reload()

    def _reload(self):
        self.tree.delete(*self.tree.get_children())
        for code in sorted(self._charmap):
            char = self._charmap[code]
            self.tree.insert("", "end", iid=f"0x{code:02X}",
                             values=(f"0x{code:02X}", repr(char), self._describe(char)))
        self.total_var.set(self.owner.i18n.t("tbl.editor.total", count=len(self._charmap)))

    def _describe(self, char):
        if not char or char[0] == "[":
            return self.owner.i18n.t("tbl.editor.desc.control")
        if char in (" ", "\t", "\n", "\r"):
            return self.owner.i18n.t("tbl.editor.desc.whitespace")
        return ""

    def run(self):
        self.win.wait_window(self.win)

    def _apply_add(self, code, char):
        if not (0 <= code <= 0xFF) or len(char) < 1:
            self.owner.set_status(self.owner.i18n.t("tbl.editor.invalid"))
            return False
        if code in self._charmap:
            self.owner.set_status(
                self.owner.i18n.t("tbl.editor.duplicate", code=f"0x{code:02X}"))
            return False
        self._charmap[code] = char
        self._reload()
        return True

    def _apply_edit(self, code, char):
        if code not in self._charmap or len(char) < 1:
            self.owner.set_status(self.owner.i18n.t("tbl.editor.invalid"))
            return False
        self._charmap[code] = char
        self._reload()
        return True

    def _show_add_dialog(self):
        self._prompt(save_action=self._apply_add)

    def _show_edit_dialog(self):
        selection = self.tree.selection()
        if not selection:
            return
        self._prompt(save_action=self._apply_edit, default_code=int(selection[0], 16))

    def _prompt(self, save_action, default_code=None):
        prompt = tk.Toplevel(self.win)
        prompt.title(self.owner.i18n.t("tbl.editor.title"))
        prompt.transient(self.win)
        prompt.grab_set()

        frame = ttk.Frame(prompt, padding=theme.SPACING["MD"])
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.owner.i18n.t("tbl.editor.enter.code")).pack(anchor="w")
        code_entry = ttk.Entry(frame)
        code_entry.pack(fill="x", pady=(0, theme.SPACING["SM"]))
        if default_code is not None:
            code_entry.insert(0, f"0x{default_code:02X}")
        ttk.Label(frame, text=self.owner.i18n.t("tbl.editor.enter.char")).pack(anchor="w")
        char_entry = ttk.Entry(frame)
        char_entry.pack(fill="x", pady=(0, theme.SPACING["SM"]))
        if default_code is not None:
            char_entry.insert(0, self._charmap.get(default_code, ""))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=theme.SPACING["SM"])

        def _submit():
            try:
                code = int(code_entry.get().strip(), 16)
            except ValueError:
                code = -1
            if save_action(code, char_entry.get()):
                prompt.destroy()

        ttk.Button(buttons, text=self.owner.i18n.t("tbl.editor.edit") if default_code is not None
                   else self.owner.i18n.t("tbl.editor.add"), command=_submit).pack(side="left", padx=theme.SPACING["XS"])
        ttk.Button(buttons, text=self.owner.i18n.t("preview.cancel"), command=prompt.destroy).pack(side="left", padx=theme.SPACING["XS"])

    def _remove_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        self._charmap.pop(int(selection[0], 16), None)
        self._reload()

    def _export_to_json(self):
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        entries = [{"code": f"0x{code:02X}", "char": self._charmap[code]}
                   for code in sorted(self._charmap)]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.owner.set_status(self.owner.i18n.t("tbl.editor.invalid"))
            messagebox.showerror(self.owner.i18n.t("error.title"), str(e))
            return
        self.owner.set_status(self.owner.i18n.t("tbl.editor.exported", path=path))

def run_gui(rom_path=None, plugin_dir="plugins", lang="en"):
    """Запуск GUI приложения"""
    if getattr(sys, "frozen", False):
        log_dir = Path(sys.executable).parent
    else:
        log_dir = Path(__file__).resolve().parent.parent
    log_path = str(log_dir / "gb2text.log")
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=log_path,
            filemode='w'
        )
    except OSError:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    logger = logging.getLogger('gb2text')
    logger.info("Запуск GUI версии")

    root = tkinterdnd2.TkinterDnD.Tk() if TKINTERDND2_AVAILABLE else tk.Tk()
    GBTextExtractorGUI(root, rom_path, plugin_dir, lang)
    root.mainloop()
