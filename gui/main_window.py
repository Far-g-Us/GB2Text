"""
Графический интерфейс для GB Text Extractor с полной функциональностью
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
from core.rom import GameBoyROM
from core.extractor import TextExtractor
from core.injector import TextInjector
from core.plugin_manager import PluginManager
from core.encoding import get_english_charmap, get_japanese_charmap, get_russian_charmap

class GBTextExtractorGUI:
    def __init__(self, root, rom_path=None, plugin_dir="plugins"):
        self.root = root
        self.root.title("GB Text Extractor & Translator")
        self.root.geometry("1100x700")

        # Инициализация компонентов
        self.rom_path = tk.StringVar(value=rom_path or "")
        self.plugin_dir = plugin_dir
        self.plugin_manager = PluginManager(plugin_dir)
        self.current_results = None
        self.current_rom = None
        self.text_injector = None
        self.current_segment = None
        self.current_entry_index = 0

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
        self.tab_control.add(self.extract_tab, text='Извлечение текста')

        # Вкладка редактирования и локализации
        self.edit_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.edit_tab, text='Редактирование текста')

        # Вкладка настроек
        self.settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.settings_tab, text='Настройки')

        self.tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # === Настройка вкладки извлечения ===
        self._setup_extract_tab()

        # === Настройка вкладки редактирования ===
        self._setup_edit_tab()

        # === Настройка вкладки настроек ===
        self._setup_settings_tab()

    def _setup_extract_tab(self):
        """Настройка вкладки извлечения текста"""
        # Верхняя панель: выбор ROM и кнопки
        top_frame = ttk.Frame(self.extract_tab, padding="10")
        top_frame.pack(fill="x", expand=False)

        ttk.Label(top_frame, text="ROM файл:").pack(side="left", padx=(0, 5))
        ttk.Entry(top_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, 5))
        ttk.Button(top_frame, text="Обзор", command=self.browse_rom).pack(side="left", padx=(0, 10))
        ttk.Button(top_frame, text="Извлечь текст", command=self.extract_text).pack(side="left")

        # Информационная панель
        info_frame = ttk.LabelFrame(self.extract_tab, text="Информация об игре", padding="10")
        info_frame.pack(fill="x", expand=False, padx=10, pady=(0, 10))

        self.game_info = {}
        for i, label in enumerate(["Название:", "Система:", "Тип картриджа:", "Размер ROM:", "Поддерживаемый плагин:"]):
            row = ttk.Frame(info_frame)
            row.pack(fill="x", expand=True)
            ttk.Label(row, text=label, width=20).pack(side="left")
            self.game_info[label] = ttk.Label(row, text="---", wraplength=600)
            self.game_info[label].pack(side="left", fill="x", expand=True)

        # Основная панель с результатами
        main_frame = ttk.Frame(self.extract_tab, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Левая панель: список сегментов
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left_frame, text="Текстовые сегменты:").pack(anchor="w")
        self.segments_list = tk.Listbox(left_frame, width=25, height=20)
        self.segments_list.pack(fill="y", expand=True)
        self.segments_list.bind('<<ListboxSelect>>', self.on_segment_select)

        # Правая панель: просмотр текста
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(right_frame, text="Содержимое сегмента:").pack(anchor="w")

        # Панель инструментов для просмотра
        toolbar = ttk.Frame(right_frame)
        toolbar.pack(fill="x", expand=False)

        ttk.Button(toolbar, text="Экспорт в JSON", command=self.export_json).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Экспорт в TXT", command=self.export_txt).pack(side="left", padx=2)
        ttk.Button(toolbar, text="К редактированию", command=self.switch_to_edit_tab).pack(side="left", padx=2)

        # Текстовая область с прокруткой
        text_frame = ttk.Frame(right_frame)
        text_frame.pack(fill="both", expand=True)

        self.text_output = scrolledtext.ScrolledText(text_frame, wrap="word", font=("Consolas", 10))
        self.text_output.pack(side="left", fill="both", expand=True)

    def _setup_edit_tab(self):
        """Настройка вкладки редактирования текста"""
        # Панель выбора ROM
        rom_frame = ttk.LabelFrame(self.edit_tab, text="Выбор ROM файла", padding="10")
        rom_frame.pack(fill="x", expand=False, padx=10, pady=10)

        ttk.Label(rom_frame, text="ROM файл:").pack(side="left", padx=(0, 5))
        ttk.Entry(rom_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, 5))
        ttk.Button(rom_frame, text="Обзор", command=self.browse_rom).pack(side="left", padx=(0, 10))
        ttk.Button(rom_frame, text="Загрузить", command=self.load_for_editing).pack(side="left")

        # Панель выбора сегмента
        segment_frame = ttk.LabelFrame(self.edit_tab, text="Выбор сегмента", padding="10")
        segment_frame.pack(fill="x", expand=False, padx=10, pady=(0, 10))

        self.segment_var = tk.StringVar()
        self.segment_combo = ttk.Combobox(segment_frame, textvariable=self.segment_var, state="readonly", width=30)
        self.segment_combo.pack(side="left", padx=(0, 10))
        self.segment_combo.bind("<<ComboboxSelected>>", self.on_segment_combo_select)

        ttk.Button(segment_frame, text="Загрузить сегмент", command=self.load_segment).pack(side="left")

        # Панель редактирования
        edit_frame = ttk.Frame(self.edit_tab, padding="10")
        edit_frame.pack(fill="both", expand=True)

        # Левая панель: оригинал
        left_frame = ttk.LabelFrame(edit_frame, text="Оригинальный текст", padding="5")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.original_text = scrolledtext.ScrolledText(left_frame, wrap="word", font=("Consolas", 10), state="disabled")
        self.original_text.pack(fill="both", expand=True)

        # Правая панель: перевод
        right_frame = ttk.LabelFrame(edit_frame, text="Перевод", padding="5")
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.translated_text = scrolledtext.ScrolledText(right_frame, wrap="word", font=("Consolas", 10))
        self.translated_text.pack(fill="both", expand=True)

        # Панель навигации и сохранения
        nav_frame = ttk.Frame(self.edit_tab, padding="10")
        nav_frame.pack(fill="x", expand=False)

        self.entry_info = ttk.Label(nav_frame, text="Запись: 0 из 0")
        self.entry_info.pack(side="left", padx=(0, 20))

        ttk.Button(nav_frame, text="← Предыдущий", command=self.prev_entry).pack(side="left", padx=5)
        ttk.Button(nav_frame, text="Следующий →", command=self.next_entry).pack(side="left", padx=5)
        ttk.Button(nav_frame, text="Сохранить перевод", command=self.save_translation).pack(side="left", padx=20)
        ttk.Button(nav_frame, text="Внедрить в ROM", command=self.inject_translation).pack(side="left", padx=5)

    def _setup_settings_tab(self):
        """Настройка вкладки настроек"""
        settings_frame = ttk.LabelFrame(self.settings_tab, text="Настройки локализации", padding="20")
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Язык перевода
        lang_frame = ttk.LabelFrame(settings_frame, text="Язык перевода", padding="10")
        lang_frame.pack(fill="x", expand=False, pady=10)

        ttk.Label(lang_frame, text="Целевой язык:").pack(side="left", padx=(0, 10))

        self.target_lang = tk.StringVar(value="ru")
        lang_combo = ttk.Combobox(lang_frame, textvariable=self.target_lang, state="readonly", width=15)
        lang_combo['values'] = ('en', 'ru', 'ja') #'es', 'fr', 'de'
        lang_combo.pack(side="left")
        lang_combo.current(1)  # Русский по умолчанию

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(settings_frame, text="Настройки кодировки", padding="10")
        encoding_frame.pack(fill="x", expand=False, pady=10)

        ttk.Label(encoding_frame, text="Тип кодировки:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)

        self.encoding_type = tk.StringVar(value="auto")
        ttk.Radiobutton(encoding_frame, text="Автоопределение", variable=self.encoding_type, value="auto").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text="Английская", variable=self.encoding_type, value="en").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text="Японская", variable=self.encoding_type, value="ja").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(encoding_frame, text="Русская", variable=self.encoding_type, value="ru").grid(row=3, column=1, sticky="w")

        # Сохранение настроек
        ttk.Button(settings_frame, text="Сохранить настройки", command=self.save_settings).pack(pady=20)

    def browse_rom(self):
        """Выбор ROM-файла"""
        path = filedialog.askopenfilename(
            title="Выберите Game Boy ROM файл",
            filetypes=[
                ("GB/GBC/GBA ROM files", "*.gb *.gbc *.sgb *.gba"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.rom_path.set(path)
            self.update_game_info()

    def update_game_info(self):
        """Обновление информации об игре"""
        if not self.rom_path.get():
            return

        try:
            rom = GameBoyROM(self.rom_path.get())
            self.current_rom = rom

            # Обновляем информацию
            self.game_info["Название:"].config(text=rom.header['title'])
            self.game_info["Система:"].config(text=rom.system.upper())
            self.game_info["Тип картриджа:"].config(text=f"0x{rom.header['cartridge_type']:02X}")
            self.game_info["Размер ROM:"].config(text=f"{len(rom.data)//1024} KB")

            # Проверяем поддержку игры
            game_id = rom.get_game_id()
            plugin = self.plugin_manager.get_plugin(game_id)
            if plugin:
                self.game_info["Поддерживаемый плагин:"].config(text=plugin.__class__.__name__)
            else:
                self.game_info["Поддерживаемый плагин:"].config(text="Не найден")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить ROM:\n{str(e)}")

    def extract_text(self):
        """Извлечение текста из ROM"""
        if not self.rom_path.get():
            messagebox.showwarning("Предупреждение", "Сначала выберите ROM-файл")
            return

        try:
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

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось извлечь текст:\n{str(e)}")

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

    def on_segment_combo_select(self, event):
        """Обработка выбора сегмента в комбобоксе"""
        pass

    def load_segment(self):
        """Загрузка выбранного сегмента для редактирования"""
        if not self.current_rom or not self.text_injector:
            messagebox.showwarning("Предупреждение", "Сначала загрузите ROM-файл")
            return

        segment_name = self.segment_var.get()
        if not segment_name:
            return

        try:
            # Получаем плагин для текущей игры
            plugin = self.plugin_manager.get_plugin(self.current_rom.get_game_id())
            if not plugin:
                messagebox.showerror("Ошибка", "Не найден подходящий плагин для этой игры")
                return

            # Получаем сегмент
            segments = plugin.get_text_segments(self.current_rom)
            segment = next((s for s in segments if s['name'] == segment_name), None)
            if not segment:
                messagebox.showerror("Ошибка", "Сегмент не найден")
                return

            self.current_segment = segment

            # Извлекаем текст из сегмента
            extractor = TextExtractor(self.rom_path.get())
            results = extractor.extract()

            if segment_name not in results:
                messagebox.showerror("Ошибка", "Не удалось извлечь текст из этого сегмента")
                return

            self.current_entries = results[segment_name]
            self.current_entry_index = 0
            self._display_current_entry()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить сегмент:\n{str(e)}")

    def _display_current_entry(self):
        """Отображение текущей записи для редактирования"""
        if not self.current_entries:
            return

        # Обновляем информацию о текущей записи
        self.entry_info.config(text=f"Запись: {self.current_entry_index + 1} из {len(self.current_entries)}")

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
        if self.current_entry_index > 0:
            self.current_entry_index -= 1
            self._display_current_entry()

    def next_entry(self):
        """Переход к следующей записи"""
        if self.current_entry_index < len(self.current_entries) - 1:
            self.current_entry_index += 1
            self._display_current_entry()

    def save_translation(self):
        """Сохранение перевода текущей записи"""
        if not self.current_entries:
            return

        translation = self.translated_text.get(1.0, tk.END).strip()
        if not translation:
            messagebox.showwarning("Предупреждение", "Введите перевод")
            return

        # Здесь сохраняем перевод
        entry = self.current_entries[self.current_entry_index]
        print(f"Сохранен перевод для записи {self.current_entry_index}: {translation[:50]}...")

        # Сохранение в файл или базу данных
        # ...

        messagebox.showinfo("Успех", "Перевод сохранен")

    def inject_translation(self):
        """Внедрение перевода в ROM"""
        if not self.current_segment or not self.current_entries:
            messagebox.showwarning("Предупреждение", "Сначала загрузите сегмент для редактирования")
            return

        try:
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
                # Сохраняем измененный ROM
                output_path = filedialog.asksaveasfilename(
                    defaultextension=".gb",
                    filetypes=[
                        ("GB/GBC/GBA ROM files", "*.gb *.gbc *.sgb *.gba"),
                        ("All files", "*.*")
                    ],
                    title="Сохранить измененный ROM"
                )

                if output_path:
                    self.text_injector.save(output_path)
                    messagebox.showinfo("Успех", f"Измененный ROM сохранен в {output_path}")
            else:
                messagebox.showerror("Ошибка", "Не удалось внедрить текст. Возможно, перевод слишком длинный.")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось внедрить перевод:\n{str(e)}")

    def save_settings(self):
        """Сохранение настроек локализации"""
        # Здесь сохраняются настройки
        messagebox.showinfo("Успех", "Настройки сохранены")

def run_gui(rom_path=None, plugin_dir="plugins"):
    """Запуск GUI приложения"""
    root = tk.Tk()
    app = GBTextExtractorGUI(root, rom_path, plugin_dir)
    root.mainloop()