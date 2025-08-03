"""
Графический интерфейс для GB Text Extractor
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from core.rom import GameBoyROM
from core.extractor import TextExtractor
from core.plugin_manager import PluginManager


class GBTextExtractorGUI:
    def __init__(self, root, rom_path=None, plugin_dir="plugins"):
        self.root = root
        self.root.title("GB Text Extractor")
        self.root.geometry("900x600")

        # Инициализация компонентов
        self.rom_path = tk.StringVar(value=rom_path or "")
        self.plugin_dir = plugin_dir
        self.plugin_manager = PluginManager(plugin_dir)
        self.current_results = None

        self._setup_ui()

        # Если указан ROM при запуске, сразу загружаем
        if rom_path:
            self.update_game_info()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Верхняя панель: выбор ROM и кнопки
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x", expand=False)

        ttk.Label(top_frame, text="ROM файл:").pack(side="left", padx=(0, 5))
        ttk.Entry(top_frame, textvariable=self.rom_path, width=50).pack(side="left", padx=(0, 5))
        ttk.Button(top_frame, text="Обзор", command=self.browse_rom).pack(side="left", padx=(0, 10))
        ttk.Button(top_frame, text="Извлечь текст", command=self.extract_text).pack(side="left")

        # Информационная панель
        info_frame = ttk.LabelFrame(self.root, text="Информация об игре", padding="10")
        info_frame.pack(fill="x", expand=False, padx=10, pady=(0, 10))

        self.game_info = {}
        for i, label in enumerate(["Название:", "Тип картриджа:", "Размер ROM:", "Поддерживаемый плагин:"]):
            row = ttk.Frame(info_frame)
            row.pack(fill="x", expand=True)
            ttk.Label(row, text=label, width=20).pack(side="left")
            self.game_info[label] = ttk.Label(row, text="---", wraplength=600)
            self.game_info[label].pack(side="left", fill="x", expand=True)

        # Основная панель с результатами
        main_frame = ttk.Frame(self.root, padding="10")
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

        # Текстовая область с прокруткой
        text_frame = ttk.Frame(right_frame)
        text_frame.pack(fill="both", expand=True)

        self.text_output = tk.Text(text_frame, wrap="word")
        self.text_output.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_output.yview)
        scrollbar.pack(side="right", fill="y")

        self.text_output.config(yscrollcommand=scrollbar.set)

    def browse_rom(self):
        """Выбор ROM-файла"""
        path = filedialog.askopenfilename(
            title="Выберите Game Boy ROM файл",
            filetypes=[("GB/GBC ROM files", "*.gb *.gbc *.sgb"), ("All files", "*.*")]
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
            # Обновляем информацию
            self.game_info["Название:"].config(text=rom.header['title'])
            self.game_info["Тип картриджа:"].config(text=f"0x{rom.header['cartridge_type']:02X}")
            self.game_info["Размер ROM:"].config(text=f"{len(rom.data) // 1024} KB")

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
                            f.write(f"0x{msg['offset']:04X}: {msg['text']}\n\n")
                messagebox.showinfo("Успех", "Результаты успешно сохранены в TXT")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{str(e)}")


def run_gui(rom_path=None, plugin_dir="plugins"):
    """Запуск GUI приложения"""
    root = tk.Tk()
    app = GBTextExtractorGUI(root, rom_path, plugin_dir)
    root.mainloop()