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

from tkinter import ttk
import tkinter as tk
from core.i18n import I18N


class TextEditorFrame(ttk.Frame):
    """Редактор текста с возможностью предпросмотра"""

    def __init__(self, parent, segment_data, rom_path, plugin):
        super().__init__(parent)
        self.i18n = I18N(default_lang=self.ui_lang.get())
        self.segment_data = segment_data
        self.rom_path = rom_path
        self.plugin = plugin
        self.original_texts = [item['text'] for item in segment_data]
        self.current_index = 0

        self._setup_ui()
        self._show_current_entry()

    def _setup_ui(self):
        # Создание интерфейса редактора
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Информация о текущей записи
        info_frame = ttk.Frame(self)
        info_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Label(info_frame, text=self.i18n.t("entry")).pack(side="left", padx=5)
        self.entry_label = ttk.Label(info_frame, text="")
        self.entry_label.pack(side="left")

        # Оригинальный текст
        ttk.Label(self, text=self.i18n.t("original.text")).grid(row=1, column=0, sticky="nw", padx=5, pady=2)
        self.original_text = tk.Text(self, height=6, width=50, wrap="word", state="disabled")
        self.original_text.grid(row=1, column=1, sticky="nwe", padx=5, pady=2)

        # Перевод
        ttk.Label(self, text=self.i18n.t("translated.text")).grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.translated_text = tk.Text(self, height=6, width=50, wrap="word")
        self.translated_text.grid(row=2, column=1, sticky="nsew", padx=5, pady=2)

        # Кнопки навигации
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=self.i18n.t("prev.entry"), command=self.prev_entry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=self.i18n.t("next.entry"), command=self.next_entry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=self.i18n.t("save.translation"), command=self.save_changes).pack(side="left", padx=5)

    def _show_current_entry(self):
        if not self.segment_data or self.current_index >= len(self.segment_data):
            return

        entry = self.segment_data[self.current_index]
        self.entry_label.config(text=f"{self.current_index + 1} из {len(self.segment_data)}")

        # Отображение оригинала
        self.original_text.config(state="normal")
        self.original_text.delete(1.0, tk.END)
        self.original_text.insert(tk.END, entry['text'])
        self.original_text.config(state="disabled")

        # Отображение перевода (если есть)
        self.translated_text.delete(1.0, tk.END)
        # Здесь можно загрузить сохраненный перевод

    def prev_entry(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_entry()

    def next_entry(self):
        if self.current_index < len(self.segment_data) - 1:
            self.current_index += 1
            self._show_current_entry()

    def save_changes(self):
        # Сохранение перевода
        translation = self.translated_text.get(1.0, tk.END).strip()
        # Здесь сохраняем перевод в файл или базу данных
        print(f"Сохранен перевод для записи {self.current_index}: {translation[:50]}...")