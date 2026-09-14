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

import logging
import os
import shutil
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from core.i18n import I18N
from gui import theme, widgets

logger = logging.getLogger(__name__)


class TextEditorFrame(ttk.Frame):
    """Редактор текста с возможностью предпросмотра"""

    def __init__(self, parent, segment_data, rom_path, plugin, lang='en'):
        super().__init__(parent)
        self.i18n = I18N(default_lang=lang)
        self.segment_data = segment_data
        self.rom_path = rom_path
        self.plugin = plugin
        self.original_texts = [item['text'] for item in segment_data]
        self.current_index = 0

        # История изменений для undo/redo
        self.history = []  # Список всех изменений
        self.history_index = -1  # Текущая позиция в истории
        self.max_history = 50  # Максимум записей в истории

        # Бэкап
        self.backup_path = None
        self._create_backup()

        self._setup_ui()
        self._show_current_entry()

    def _setup_ui(self):
        # Создание интерфейса редактора
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Информация о текущей записи
        info_frame = ttk.Frame(self)
        info_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=theme.SPACING["SM"])

        ttk.Label(info_frame, text=self.i18n.t("entry")).pack(side="left", padx=theme.SPACING["SM"])
        self.entry_label = ttk.Label(info_frame, text="")
        self.entry_label.pack(side="left")

        # Кнопка создания бекапа
        backup_btn = ttk.Button(info_frame, text=self.i18n.t("editor.create.backup"), command=self._create_backup)
        backup_btn.pack(side="right", padx=theme.SPACING["SM"])

        # Оригинальный текст
        ttk.Label(self, text=self.i18n.t("original.text")).grid(row=1, column=0, sticky="nw", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])
        self.original_text = tk.Text(self, height=6, width=50, wrap="word", state="disabled")
        self.original_text.grid(row=1, column=1, sticky="nwe", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])

        # Перевод
        ttk.Label(self, text=self.i18n.t("translated.text")).grid(row=2, column=0, sticky="nw", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])
        self.translated_text = tk.Text(self, height=6, width=50, wrap="word")
        self.translated_text.grid(row=2, column=1, sticky="nsew", padx=theme.SPACING["SM"], pady=theme.SPACING["XS"])

        # Привязка событий для undo/redo
        self.translated_text.bind('<Control-z>', lambda e: self.undo())
        self.translated_text.bind('<Control-y>', lambda e: self.redo())
        self.translated_text.bind('<<Modified>>', self._on_text_change)

        # Кнопки навигации
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=theme.SPACING["MD"])

        undo_btn = ttk.Button(btn_frame, text=self.i18n.t("undo"), command=self.undo)
        undo_btn.pack(side="left", padx=theme.SPACING["SM"])
        redo_btn = ttk.Button(btn_frame, text=self.i18n.t("redo"), command=self.redo)
        redo_btn.pack(side="left", padx=theme.SPACING["SM"])
        prev_btn = ttk.Button(btn_frame, text=self.i18n.t("prev.entry"), command=self.prev_entry)
        prev_btn.pack(side="left", padx=theme.SPACING["SM"])
        next_btn = ttk.Button(btn_frame, text=self.i18n.t("next.entry"), command=self.next_entry)
        next_btn.pack(side="left", padx=theme.SPACING["SM"])
        save_btn = ttk.Button(btn_frame, text=self.i18n.t("save.translation"), command=self.save_changes)
        save_btn.pack(side="left", padx=theme.SPACING["SM"])

    def _create_backup(self):
        """Создание бэкапа ROM файла (только если ещё нет бэкапа для этого ROM)"""
        if not self.rom_path or not os.path.exists(self.rom_path):
            return

        # Создаем папку для бэкапов если её нет
        backup_dir = os.path.join(os.path.dirname(self.rom_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Проверяем, есть ли уже бэкап для этого ROM
        rom_name = os.path.basename(self.rom_path)
        existing_backups = [f for f in os.listdir(backup_dir) if f.endswith(rom_name)]
        if existing_backups:
            self.backup_path = os.path.join(backup_dir, sorted(existing_backups)[-1])
            logger.info(f"Бэкап уже существует: {self.backup_path}")
            return

        # Генерируем имя файла с timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{timestamp}_{rom_name}"
        self.backup_path = os.path.join(backup_dir, backup_filename)

        # Копируем файл
        shutil.copy2(self.rom_path, self.backup_path)
        logger.info(f"Бэкап создан: {self.backup_path}")

    def _on_text_change(self, event=None):
        """Обработка изменения текста для истории"""
        if self.translated_text.edit_modified():
            current_text = self.translated_text.get(1.0, tk.END).strip()
            self._add_to_history(current_text)
            self.translated_text.edit_modified(False)

    def _add_to_history(self, text):
        """Добавление изменения в историю"""
        # Удаляем все записи после текущей позиции
        self.history = self.history[:self.history_index + 1]

        # Добавляем новое изменение
        self.history.append({
            'index': self.current_index,
            'text': text
        })

        # Ограничиваем размер истории
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        self.history_index = len(self.history) - 1

    def undo(self):
        """Отмена последнего изменения"""
        if self.history_index > 0:
            self.history_index -= 1
            entry = self.history[self.history_index]
            self.current_index = entry['index']
            self._show_current_entry()
            self.translated_text.delete(1.0, tk.END)
            self.translated_text.insert(tk.END, entry['text'])

    def redo(self):
        """Возврат отменённого изменения"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            entry = self.history[self.history_index]
            self.current_index = entry['index']
            self._show_current_entry()
            self.translated_text.delete(1.0, tk.END)
            self.translated_text.insert(tk.END, entry['text'])

    def _show_current_entry(self):
        if not self.segment_data or self.current_index >= len(self.segment_data):
            return

        entry = self.segment_data[self.current_index]
        self.entry_label.config(text=f"{self.current_index + 1} {self.i18n.t('of')} {len(self.segment_data)}")

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
        # Получаем текущий перевод
        translation = self.translated_text.get(1.0, tk.END).strip()
        original = self.segment_data[self.current_index]['text']

        # Создаем диалог предпросмотра
        preview_window = tk.Toplevel(self)
        preview_window.title(self.i18n.t("preview.title"))
        preview_window.geometry("600x400")
        widgets.apply_window_icon(preview_window)

        # Оригинал
        ttk.Label(preview_window, text=self.i18n.t("preview.original"), font=theme.ui_font(10, "bold")).pack(pady=theme.SPACING["SM"])
        original_text = tk.Text(preview_window, height=4, width=70, state="disabled")
        original_text.pack(pady=theme.SPACING["SM"])
        original_text.config(state="normal")
        original_text.insert(tk.END, original)
        original_text.config(state="disabled")

        # Новый перевод
        ttk.Label(preview_window, text=self.i18n.t("preview.new.translation"), font=theme.ui_font(10, "bold")).pack(pady=theme.SPACING["SM"])
        new_text = tk.Text(preview_window, height=4, width=70, state="disabled")
        new_text.pack(pady=theme.SPACING["SM"])
        new_text.config(state="normal")
        new_text.insert(tk.END, translation)
        new_text.config(state="disabled")

        # Кнопки
        btn_frame = ttk.Frame(preview_window)
        btn_frame.pack(pady=theme.SPACING["XL"])

        def confirm_save():
            # Фактическое сохранение перевода
            self.segment_data[self.current_index]['translation'] = translation
            logger.info(f"Сохранен перевод для записи {self.current_index}: {translation[:50]}...")
            preview_window.destroy()

        confirm_btn = ttk.Button(btn_frame, text=self.i18n.t("preview.confirm"), command=confirm_save)
        confirm_btn.pack(side="left", padx=theme.SPACING["MD"])
        cancel_btn = ttk.Button(btn_frame, text=self.i18n.t("preview.cancel"), command=preview_window.destroy)
        cancel_btn.pack(side="left", padx=theme.SPACING["MD"])

        theme.apply(preview_window, theme.is_dark())
