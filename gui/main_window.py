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
import json, re, os
from datetime import time
from pathlib import Path
from core.rom import GameBoyROM
from core.i18n import I18N
from core.guide import GuideManager
from core.extractor import TextExtractor
from core.injector import TextInjector
from core.plugin_manager import PluginManager
from core.encoding import get_generic_english_charmap, get_generic_japanese_charmap, get_generic_russian_charmap, auto_detect_charmap

class GBTextExtractorGUI:
    def __init__(self, root, rom_path=None, plugin_dir="plugins", lang="en"):
        # Загружаем сохраненные настройки
        self.load_saved_settings()

        self.i18n = I18N(default_lang=self.ui_lang.get())
        self.root = root
        self.root.title(self.i18n.t("app.title"))
        self.root.geometry("1100x700")

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
        #self.apply_encoding = None

        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Добавляем переменную для текущего языка интерфейса
        self.ui_lang = tk.StringVar(value=lang)

        self.show_warning_dialog()
        self._setup_ui()

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

        # Вкладка настроек
        self.settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.settings_tab, text=self.i18n.t("tab.settings"))
        self.tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # Вкладка руководства
        self.guide_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.guide_tab, text=self.i18n.t("guide.tab"))

        # Вкладка о программе
        self.about_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.about_tab, text=self.i18n.t("tab.about"))

        self.tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # Добавляем статус-бар
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text=self.i18n.t("status.ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(self.status_bar, mode='determinate', maximum=100)
        self.progress_bar.pack(side=tk.RIGHT, padx=5)

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
            label = ttk.Label(row, text=self.i18n.t(i18n_key) + ":", width=20)
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
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left_frame, text=self.i18n.t("text.segments")).pack(anchor="w")
        self.segments_list = tk.Listbox(left_frame, width=25, height=20)
        self.segments_list.pack(fill="y", expand=True)
        self.segments_list.bind('<<ListboxSelect>>', self.on_segment_select)

        # Правая панель: просмотр текста
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(right_frame, text=self.i18n.t("segment.content")).pack(anchor="w")

        # Панель инструментов для просмотра
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill="x", expand=False)

        ttk.Button(toolbar, text=self.i18n.t("export.json"), command=self.export_json).pack(side="left", padx=2)
        ttk.Button(toolbar, text=self.i18n.t("export.txt"), command=self.export_txt).pack(side="left", padx=2)
        ttk.Button(toolbar, text=self.i18n.t("extract.text"), command=self.switch_to_edit_tab).pack(side="left", padx=2)

        # Текстовая область с прокруткой
        text_frame = ttk.Frame(right_frame)
        text_frame.pack(fill="both", expand=True)

        self.text_output = scrolledtext.ScrolledText(text_frame, wrap="word", font=("Consolas", 10))
        self.text_output.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_output.yview)
        scrollbar.pack(side="right", fill="y")

        self.text_output.config(yscrollcommand=scrollbar.set)

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

        # Панель редактирования
        edit_frame = ttk.Frame(self.edit_tab, padding="10")
        edit_frame.pack(fill="both", expand=True)

        # Левая панель: оригинал
        left_frame = ttk.LabelFrame(edit_frame, text=self.i18n.t("original.text"), padding="5")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.original_text = scrolledtext.ScrolledText(left_frame, wrap="word", font=("Consolas", 10), state="disabled")
        self.original_text.pack(fill="both", expand=True)

        # Правая панель: перевод
        right_frame = ttk.LabelFrame(edit_frame, text=self.i18n.t("translated.text"), padding="5")
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.translated_text = scrolledtext.ScrolledText(right_frame, wrap="word", font=("Consolas", 10))
        self.translated_text.pack(fill="both", expand=True)

        # Панель навигации и сохранения
        nav_frame = ttk.Frame(self.edit_tab, padding="10")
        nav_frame.pack(fill="x", expand=False)

        self.entry_info = ttk.Label(nav_frame, text=self.i18n.t("entry", current=0, total=0))
        self.entry_info.pack(side="left", padx=(0, 20))

        ttk.Button(nav_frame, text=self.i18n.t("prev.entry"), command=self.prev_entry).pack(side="left", padx=5)
        ttk.Button(nav_frame, text=self.i18n.t("next.entry"), command=self.next_entry).pack(side="left", padx=5)
        ttk.Button(nav_frame, text=self.i18n.t("save.translation"), command=self.save_translation).pack(side="left", padx=20)
        ttk.Button(nav_frame, text=self.i18n.t("inject.translation"), command=self.inject_translation).pack(side="left", padx=5)

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

        # Текстовое представление руководства
        self.guide_text = scrolledtext.ScrolledText(guide_frame, wrap="word", font=("Consolas", 10))
        self.guide_text.pack(fill="both", expand=True)
        self.guide_text.config(state="disabled")

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
                config["segments"].append({
                    "name": seg["name"],
                    "start": f"0x{seg['start']:04X}",
                    "end": f"0x{seg['end']:04X}",
                    # Таблица символов будет определена при использовании
                })
        except:
            # Если автоопределение не сработало, создаем шаблон
            config["segments"].append({
                "name": "main_text",
                "start": "0x4000",
                "end": "0x7FFF"
            })

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

    def set_status(self, status: str, progress: int = 0):
        """Устанавливает статус в статус-баре"""
        self.status_label.config(text=status)
        self.progress_bar['value'] = progress
        self.root.update_idletasks()

    def start_progress(self, message: str, max_value: int = 100):
        """Начинает индикацию прогресса"""
        self.set_status(message, 0)
        self.progress_bar['maximum'] = max_value
        self.root.update_idletasks()

    def update_progress(self, value: int, message: str = None):
        """Обновляет прогресс"""
        self.progress_bar['value'] = value
        if message:
            self.status_label.config(text=message)
        self.root.update_idletasks()

    def end_progress(self, message: str = None):
        """Завершает индикацию прогресса"""
        if message:
            self.set_status(message)
        else:
            self.set_status(self.i18n.t("status.ready"))
        self.progress_bar['value'] = 0
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

            # Обновляем информацию
            self.game_info_labels["title"]["value"].config(text=rom.header['title'])
            self.game_info_labels["system"]["value"].config(text=rom.system.upper())
            self.game_info_labels["cartridge_type"]["value"].config(text=f"0x{rom.header['cartridge_type']:02X}")
            self.game_info_labels["rom_size"]["value"].config(text=f"{len(rom.data) // 1024} KB")

            # Проверяем поддержку игры
            game_id = rom.get_game_id()
            plugin = self.plugin_manager.get_plugin(game_id)
            if plugin:
                self.game_info_labels["supported_plugin"]["value"].config(text=plugin.__class__.__name__)
            else:
                self.game_info_labels["supported_plugin"]["value"].config(text=self.i18n.t("not_found"))

        except Exception as e:
            messagebox.showerror(self.i18n.t("error.title"),
                                 self.i18n.t("rom.load.error", error=str(e)))

    def extract_text(self):
        """Извлечение текста из ROM"""
        if not self.rom_path.get():
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("select.rom"))
            return

        try:
            self.set_status(self.i18n.t("text.extracting"), 0)

            extractor = TextExtractor(self.rom_path.get())
            self.current_results = extractor.extract()

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
            messagebox.showinfo(self.i18n.t("success.title"), self.i18n.t("extraction.success"))

        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("extraction.error", error=str(e))
            )

    def on_segment_select(self, event):
        """Обработка выбора сегмента"""
        if not self.current_results:
            return

        selection = self.segments_list.curselection()
        if not selection:
            return

        segment_name = self.segments_list.get(selection[0])
        segment_data = self.current_results[segment_name]

        # Очистка текстовой области
        self.text_output.delete(1.0, tk.END)

        # Заполнение текстовой области
        for item in segment_data:
            self.text_output.insert(tk.END, f"Offset: 0x{item['offset']:04X}\n")
            self.text_output.insert(tk.END, f"{item['text']}\n\n")

    def export_json(self):
        """Экспорт результатов в JSON"""
        if not self.current_results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Сохранить как JSON"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", "Результаты успешно сохранены в JSON")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

    def export_txt(self):
        """Экспорт результатов в TXT"""
        if not self.current_results:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Сохранить как TXT"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    for seg_name, messages in self.current_results.items():
                        f.write(f"== {seg_name.upper()} ==\n")
                        for msg in messages:
                            f.write(f"Offset: 0x{msg['offset']:04X}\n")
                            f.write(f"{msg['text']}\n\n")
                messagebox.showinfo("Успех", "Результаты успешно сохранены в TXT")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

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
        if not self.rom_path.get():
            messagebox.showwarning("Предупреждение", "Сначала выберите ROM-файл")
            return

        try:
            self.current_rom = GameBoyROM(self.rom_path.get())
            self.text_injector = TextInjector(self.rom_path.get())

            # Обновляем информацию
            self.game_info["Название:"].config(text=self.current_rom.header['title'])
            self.game_info["Система:"].config(text=self.current_rom.system.upper())
            self.game_info["Тип картриджа:"].config(text=f"0x{self.current_rom.header['cartridge_type']:02X}")
            self.game_info["Размер ROM:"].config(text=f"{len(self.current_rom.data)//1024} KB")

            # Заполняем список сегментов
            plugin = self.plugin_manager.get_plugin(self.current_rom.get_game_id())
            if plugin:
                self.segment_combo['values'] = [seg['name'] for seg in plugin.get_text_segments(self.current_rom)]
                if self.segment_combo['values']:
                    self.segment_combo.current(0)
            else:
                messagebox.showwarning("Предупреждение", "Не найден подходящий плагин для этой игры")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить ROM:\n{str(e)}")

    def load_saved_settings(self):
        """Загружает сохраненные настройки"""
        settings_path = Path("settings/settings.json")
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.ui_lang = tk.StringVar(value=settings.get("ui_language", "en"))
                self.target_lang = tk.StringVar(value=settings.get("target_language", "ru"))
                self.encoding_type = tk.StringVar(value=settings.get("encoding_type", "auto"))
            except Exception as e:
                print(f"Ошибка загрузки настроек: {str(e)}")
                self.ui_lang = tk.StringVar(value="en")
                self.target_lang = tk.StringVar(value="ru")
                self.encoding_type = tk.StringVar(value="auto")
        else:
            self.ui_lang = tk.StringVar(value="en")
            self.target_lang = tk.StringVar(value="ru")
            self.encoding_type = tk.StringVar(value="auto")

    def on_segment_combo_select(self, event):
        """Обработка выбора сегмента в комбобоксе"""
        pass

    def load_segment(self):
        """Загрузка выбранного сегмента для редактирования"""
        if not self.current_rom or not self.text_injector:
            messagebox.showwarning(self.i18n.t("warning.title"), self.i18n.t("select.rom"))
            return

        segment_name = self.segment_var.get()
        if not segment_name:
            return

        try:
            self.set_status(self.i18n.t("status.loading"), 0)

            # Получаем плагин для текущей игры
            plugin = self.plugin_manager.get_plugin(self.current_rom.get_game_id())
            if not plugin:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("plugin.not.found")
                )
                self.set_status(self.i18n.t("status.error"))
                return

            # Получаем сегмент
            segments = plugin.get_text_segments(self.current_rom)
            segment = next((s for s in segments if s['name'] == segment_name), None)
            if not segment:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("extraction.error", error="Segment not found")
                )
                self.set_status(self.i18n.t("status.error"))
                return

            self.current_segment = segment

            # Извлекаем текст из сегмента
            extractor = TextExtractor(self.rom_path.get())
            results = extractor.extract()

            if segment_name not in results:
                messagebox.showerror(
                    self.i18n.t("error.title"),
                    self.i18n.t("extraction.error", error="Failed to extract text from this segment")
                )
                self.set_status(self.i18n.t("status.error"))
                return

            self.current_entries = results[segment_name]
            self.current_entry_index = 0
            self._display_current_entry()

            self.set_status(self.i18n.t("text.extracted"))


        except Exception as e:
            self.set_status(self.i18n.t("status.error"))
            messagebox.showerror(
                self.i18n.t("error.title"),
                self.i18n.t("extraction.error", error=str(e))
            )

    def _display_current_entry(self):
        """Отображение текущей записи для редактирования"""
        if not self.current_entries:
            return

        # Обновляем информацию о текущей записи
        self.entry_info.config(text=f"{self.i18n.t('entry')}: {self.current_entry_index + 1} из {len(self.current_entries)}")

        # Отображаем оригинал
        self.original_text.config(state="normal")
        self.original_text.delete(1.0, tk.END)
        self.original_text.insert(tk.END, self.current_entries[self.current_entry_index]['text'])
        self.original_text.config(state="disabled")

        # Отображаем перевод (если есть)
        self.translated_text.delete(1.0, tk.END)
        # Здесь можно загрузить сохраненный перевод

    def prev_entry(self):
        """Переход к предыдущей записи"""
        if not self.current_entries:
            return

        if self.current_entry_index > 0:
            self.current_entry_index -= 1
            self._display_current_entry()

    def next_entry(self):
        """Переход к следующей записи"""
        if not self.current_entries:
            return

        if self.current_entry_index < len(self.current_entries) - 1:
            self.current_entry_index += 1
            self._display_current_entry()

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
        self._refresh_labels()

        messagebox.showinfo(self.i18n.t("settings.saved"), self.i18n.t("settings.saved"))

    def _refresh_labels(self):
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

        self.load_template_btn = ttk.Button(control_frame, text=self.i18n.t("load.template"), command=self.load_guide_template)
        self.load_template_btn.pack(side="left", padx=5)

        self.save_guide_btn = ttk.Button(control_frame, text=self.i18n.t("save.guide"), command=self.save_guide)
        self.save_guide_btn.pack(side="left", padx=5)

        self.apply_guide_btn = ttk.Button(control_frame, text=self.i18n.t("apply.guide"), command=self.apply_guide)
        self.apply_guide_btn.pack(side="left", padx=5)

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
            with open('VERSION', 'r') as f:
                return f.read().strip()
        except:
            return "1.0.0"

    def open_url(self, url):
        """Открывает URL в браузере по умолчанию"""
        import webbrowser
        webbrowser.open(url)


def run_gui(rom_path=None, plugin_dir="plugins", lang="en"):
    """Запуск GUI приложения"""
    root = tk.Tk()
    app = GBTextExtractorGUI(root, rom_path, plugin_dir, lang)
    root.mainloop()