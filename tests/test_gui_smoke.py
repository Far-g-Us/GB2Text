"""
GUI smoke-тесты: реальный Tk, применяют тему, проверяют переживание
смены light/dark без исключений и целостность виджетов.
"""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pytest

from gui import main_window as mw, theme

pytestmark = [pytest.mark.gui, pytest.mark.slow]


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Нет Tk display: {e}")
    root.withdraw()
    return root


@pytest.fixture
def gui(monkeypatch, tmp_path, empty_plugin_dir):
    """Инстанс главного окна с изолированными настройками/ресурсами."""
    for name in ("showwarning", "showinfo", "showerror", "askyesno"):
        monkeypatch.setattr(messagebox, name, lambda *a, **k: None)

    root = _make_root()
    monkeypatch.setattr(
        mw.GBTextExtractorGUI,
        "show_warning_dialog",
        lambda self: None,
    )
    monkeypatch.setattr(
        mw.GBTextExtractorGUI,
        "load_saved_settings",
        lambda self: self._init_default_settings(),
    )
    monkeypatch.setattr(
        mw.GBTextExtractorGUI,
        "_get_resource_path",
        lambda self, relative_path: str(tmp_path / relative_path),
    )

    app = mw.GBTextExtractorGUI(root, plugin_dir=empty_plugin_dir)
    original_theme = theme._current
    original_scheme = theme._current_scheme
    try:
        yield app
    finally:
        theme._current = original_theme
        theme._current_scheme = original_scheme
        theme.unregister_post_apply_hook(app._reapply_compare_colors)
        theme.unregister_post_apply_hook(app._reapply_about_colors)
        theme.unregister_post_apply_hook(app._map_redraw)
        try:
            app.root.destroy()
        except tk.TclError:
            pass


def test_apply_theme_paints_tk_widgets(gui):
    """Смена темы красит tk-виджеты в токены текущей темы."""
    for dark in (False, True):
        gui.theme.set("dark" if dark else "light")
        gui.apply_theme()
        expected = theme.get("surface")
        for widget in (gui.text_output, gui.segments_list,
                       gui.compare_added_list, gui.batch_listbox):
            assert str(widget.cget("bg")).lower() == expected.lower(), f"{widget} bg != {expected} (dark={dark})"


def test_compare_panel_fill_resets_on_empty_result(gui):
    """Залитая панель возвращается к surface при повторном сравнении без различий."""
    gui.compare_added_list.insert(tk.END, "seg_a")
    gui._paint_compare_panel(gui.compare_added_list, "success", "diff-added-bg")
    assert gui.compare_added_list.cget("bg").lower() == theme.get("diff-added-bg").lower()

    gui.compare_added_list.delete(0, tk.END)
    gui._paint_compare_panel(gui.compare_added_list, "success", "diff-added-bg")
    assert gui.compare_added_list.cget("bg").lower() == theme.get("surface").lower()


def test_compare_summarizes_text_entries(gui):
    """Списки сравнения показывают имя сегмента + обрезанный текст."""
    texts1 = {
        "seg_same": "идентичный текст",
        "seg_changed": "старое содержимое",
        "seg_removed": "удалённые строки тут",
    }
    texts2 = {
        "seg_same": "идентичный текст",
        "seg_changed": "новое содержимое после правки",
        "seg_added": "появившийся сегмент",
    }
    gui._find_text_differences(texts1, texts2)

    added = gui.compare_added_list.get(0, tk.END)
    removed = gui.compare_removed_list.get(0, tk.END)
    changed = gui.compare_changed_list.get(0, tk.END)
    assert added == ("seg_added: появившийся сегмент",)
    assert removed == ("seg_removed: удалённые строки тут",)
    assert changed == ("seg_changed: старое содержимое -> новое содержимое после правки",)

    long_text = "A" * 100
    assert gui._summarize_text(long_text).endswith("...")
    assert gui._summarize_text(long_text).startswith("A" * 40)
    assert len(gui._summarize_text("A" * 40)) == 40
    assert len(gui._summarize_text("A" * 41)) == 43
    assert gui._summarize_text("a\n\nb\r\nc") == "a b c"
    assert gui._summarize_text("") == ""

    gui.compare_added_list.delete(0, tk.END)
    gui._find_text_differences({"seg": ""}, {"seg": "", "extra": ""})
    assert gui.compare_added_list.get(0, tk.END) == ("extra",)


def test_apply_theme_dark_light_no_exceptions(gui):
    """Применение темы туда-обратно не кидает исключений."""
    for value in ("dark", "light", "dark"):
        gui.theme.set(value)
        gui.apply_theme()
    assert theme.is_dark()


def test_compare_item_color_refresh_on_real_theme_switch(gui):
    """itemconfigure-цвет реколорится при РЕАЛЬНОЙ смене темы (hook)."""
    gui.compare_added_list.insert(tk.END, "fake_segment")

    gui.theme.set("dark")
    gui.apply_theme()
    assert gui.compare_added_list.itemcget(0, "fg").lower() == theme.get("success").lower()
    assert gui.compare_added_list.cget("bg").lower() == theme.get("diff-added-bg").lower()
    assert theme.is_dark()

    gui.theme.set("light")
    gui.apply_theme()
    assert gui.compare_added_list.itemcget(0, "fg").lower() == theme.get("success").lower()
    assert gui.compare_added_list.cget("bg").lower() == theme.get("diff-added-bg").lower()
    assert not theme.is_dark()


def test_window_resizes_content(gui):
    """Увеличение окна увеличивает ширину контента (pack-геометрия живёт)."""
    if gui.root.winfo_screenwidth() < 900:
        pytest.skip("Слишком узкий экран для resize-проверки")

    gui.root.deiconify()
    gui.root.geometry("700x500")
    gui.root.update()
    small = gui.tab_control.winfo_width()

    target = min(1200, gui.root.winfo_screenwidth() - 120)
    gui.root.geometry(f"{target}x800")
    gui.root.update()
    large = gui.tab_control.winfo_width()

    assert large > small, f"tab_control не расширился: {small} -> {large} (target={target})"


def test_focus_ring_visible(gui):
    """Видимый focus ring для tk-виджетов и ttk-стилей в обеих темах."""
    for dark in (False, True):
        gui.theme.set("dark" if dark else "light")
        gui.apply_theme()
        assert gui.text_output.cget("highlightthickness") == 2
        assert gui.text_output.cget("highlightcolor") == theme.get("focus-ring")
        assert gui.segments_list.cget("highlightthickness") == 2
        assert gui.segments_list.cget("highlightcolor") == theme.get("focus-ring")
        style = ttk.Style(gui.root)
        assert style.lookup("TButton", "focuscolor") == theme.get("focus-ring")


def test_new_ui_styles_configured(gui):
    """Новые стили UI (accent-кнопка, muted-подписи) активны."""
    style = ttk.Style(gui.root)
    assert style.lookup("Accent.TButton", "background") == theme.get("accent")
    assert style.lookup("Accent.TButton", "foreground") == theme.get("on-accent")
    assert style.lookup("Muted.TLabel", "foreground") == theme.get("text-muted")
    pressed_bg = style.lookup("Accent.TButton", "background", ("pressed",))
    assert pressed_bg and pressed_bg != theme.get("accent")


def test_toolbar_menus_built(gui):
    """Тулбар извлечения: два выпадающих меню с пунктами + кнопка редактора."""
    assert gui.export_menu_btn.winfo_exists()
    assert gui.import_menu_btn.winfo_exists()
    assert isinstance(gui.export_menu, tk.Menu) and gui.export_menu.index("end") is not None
    assert isinstance(gui.import_menu, tk.Menu) and gui.import_menu.index("end") is not None
    labels = {gui.export_menu.entrycget(i, "label") for i in range(5)}
    assert labels == {gui.i18n.t(k) for k in ("export.json", "export.txt", "export.csv", "export.tmx", "export.xliff")}
    import_labels = {gui.import_menu.entrycget(i, "label") for i in range(3)}
    assert import_labels == {gui.i18n.t(k) for k in ("import.csv", "import.tmx", "import.xliff")}
    assert gui.export_menu.entrycget(0, "state") == "disabled"
    assert gui.import_menu.entrycget(0, "state") == "disabled"


def test_tab_traversal_loops(gui):
    """Tab-обход проходит по виджетам и не обрывается раньше времени."""
    gui.root.deiconify()
    gui.root.update()
    seen = []
    current = gui.root
    for _ in range(60):
        nxt = current.tk_focusNext()
        if nxt is None or nxt is gui.root or any(w is nxt for w in seen):
            break
        seen.append(nxt)
        current = nxt
    assert len(seen) >= 8, f"Tab-обход слишком короткий: {len(seen)} виджетов"
    assert all(w.winfo_exists() for w in seen)


def test_segment_filter_filters_and_counts(gui):
    """Фильтр по имени сегмента: подстрока без регистра + счётчик X / Y."""
    gui.current_results = {
        "charset": [],
        "dialog_main": [],
        "menu_items": [],
        "story_intro": [],
    }
    gui._refresh_segments_list(gui.current_results.keys())
    assert gui.segments_list.size() == 4
    assert gui.segment_count_var.get() == "4 / 4"

    gui.segment_filter_var.set("MAIN")
    gui.root.update()
    visible = [gui.segments_list.get(i) for i in range(gui.segments_list.size())]
    assert visible == ["dialog_main"]
    assert gui.segment_count_var.get() == "1 / 4"

    gui.segment_filter_var.set("zzz-несуществующий")
    gui.root.update()
    assert gui.segments_list.size() == 0
    assert gui.segment_count_var.get() == "0 / 4"

    gui.segment_filter_var.set("")
    gui.root.update()
    assert gui.segments_list.size() == 4


def test_preview_render_normalizes_tokens():
    """_preview_render убирает номера записей и оборачивает токены."""
    assert mw.GBTextExtractorGUI._preview_render("[1] HELLO [END]") == "HELLO <end>"
    assert mw.GBTextExtractorGUI._preview_render("[12] [LINE] A") == "<line> A"


def test_preview_updates_on_display_and_keyrelease(gui):
    """Превью обновляется при показе записи и при вводе в translated_text."""
    gui.current_results = {
        "seg_a": [
            {"text": "HELLO WORLD", "translation": "ПРИВЕТ [END]"},
        ],
    }
    gui.current_segment = "seg_a"
    gui.current_entries = gui.current_results["seg_a"]
    gui.current_entry_index = 0
    gui._display_current_entry()

    assert gui.preview_text is not None
    assert gui.preview_frame.cget("text") == gui.i18n.t("preview.encoding.title")
    body = gui.preview_text.get("1.0", "end-1c")
    assert "ПРИВЕТ <end>" in body
    assert "1" in gui.preview_length_var.get()

    gui.translated_text.delete("1.0", tk.END)
    gui.translated_text.insert("1.0", "НОВЫЙ ТЕКСТ [END]")
    gui._update_preview()
    body = gui.preview_text.get("1.0", "end-1c")
    assert body == "НОВЫЙ ТЕКСТ <end>"


def _settings_children(gui):
    config_canvas = next(
        (w for w in gui.settings_tab.winfo_children() if w.winfo_class() == "Canvas"),
        None,
    )
    assert config_canvas is not None, "Settings-вкладка не содержит канвас прокрутки"
    inner = next(
        (w for w in config_canvas.winfo_children() if w.winfo_class() == "TLabelframe"),
        None,
    )
    if inner is None:
        wrapper = next(
            (w for w in config_canvas.winfo_children() if w.winfo_class() == "TFrame"),
            None,
        )
        if wrapper is not None:
            inner = next(
                (w for w in wrapper.winfo_children() if w.winfo_class() == "TLabelframe"),
                None,
            )
    assert inner is not None, "Канвас не содержит внутренний фрейм настроек"
    return config_canvas, inner


def test_settings_scroll_mousewheel_bound_locally(gui):
    """Колесо мыши привязано локально к канвасу и его потомкам (не bind_all)."""
    config_canvas, inner = _settings_children(gui)
    assert config_canvas.bind("<MouseWheel>"), "Канвас без bind колеса мыши"
    assert inner.bind("<MouseWheel>"), "Внутренний фрейм без bind колеса мыши"
    for child in inner.winfo_children():
        if child.winfo_class() == "TLabelframe":
            assert child.bind("<MouseWheel>"), f"{child} без колеса мыши"


def test_settings_scroll_survives_refresh_ui(gui):
    """После _refresh_ui привязки колеса пересоздаются без TclError."""
    gui._refresh_ui()
    config_canvas, inner = _settings_children(gui)
    assert config_canvas.bind("<MouseWheel>")
    assert inner.bind("<MouseWheel>")


class _FakeROM:
    def __init__(self, size):
        self.data = bytes(size)
        self.system = "gba"
        self.header = {"title": "", "cartridge_type": 0, "rom_size": 0}


def test_map_tab_present(gui):
    """Вкладка карты ROM присутствует и имеет канвас."""
    assert hasattr(gui, "map_canvas")
    assert hasattr(gui, "map_status_var")
    tabs = gui.tab_control.tabs()
    assert str(gui.map_tab) in tabs
    assert gui.tab_control.tab(str(gui.map_tab), "text") == gui.i18n.t("map.tab")


def test_map_empty_when_no_rom(gui):
    """Без ROM канвас показывает заглушку."""
    gui.current_rom = None
    gui._draw_map()
    texts = [gui.map_canvas.itemcget(it, "text") for it in gui.map_canvas.find_all()]
    assert gui.i18n.t("map.no.rom") in texts


def test_map_draws_segments(gui):
    """Карта рисует блоки и подсвечивает сегменты."""
    gui.current_rom = _FakeROM(0x20000)
    gui.current_segments_meta = [
        {"name": "seg_a", "start": 0x100, "end": 0x200},
        {"name": "seg_b", "start": 0x10000, "end": 0x11000},
    ]
    gui._draw_map()
    assert len(gui.map_canvas.find_all()) > 4


def test_map_click_updates_status(gui):
    """Клик по блоку с сегментом показывает детали."""
    gui.current_rom = _FakeROM(0x10000)
    gui.current_segments_meta = [{"name": "seg_a", "start": 0x1000, "end": 0x1100}]
    gui._draw_map()
    import types
    gui._on_map_click(types.SimpleNamespace(y=10))
    assert "seg_a" in gui.map_status_var.get()


def test_map_redraw_survives_refresh_ui(gui):
    """Перерисовка карты после _refresh_ui не кидает исключений."""
    gui.current_rom = _FakeROM(0x10000)
    gui.current_segments_meta = [{"name": "seg_a", "start": 0x0, "end": 0x800}]
    gui._refresh_ui()
    gui._map_redraw()
    assert len(gui.map_canvas.find_all()) > 4


def test_map_click_below_last_block_clamps(gui):
    """Клик ниже последнего блока не даёт инвалидный диапазон."""
    gui.current_rom = _FakeROM(0x10000)
    gui.current_segments_meta = []
    gui._draw_map()
    import types
    gui._on_map_click(types.SimpleNamespace(y=5000))
    assert gui.map_status_var.get() == "0x08000-0x0FFFF"


def test_charmap_editor_opens(gui):
    """Диалог редактора TBL открывается и заполняет дерево."""
    gui.current_rom = None
    dialog = mw._CharmapEditorDialog(gui.root, gui, grab=False)
    try:
        assert len(dialog.tree.get_children()) > 0
        assert "0x41" in dialog.tree.get_children()
    finally:
        dialog.win.destroy()


def test_charmap_editor_duplicate_rejected(gui):
    """Добавление существующего кода отклоняется."""
    dialog = mw._CharmapEditorDialog(gui.root, gui, grab=False)
    try:
        assert not dialog._apply_add(0x41, "Z")
    finally:
        dialog.win.destroy()


def test_charmap_editor_add_edit_remove(gui):
    """Добавление, правка и удаление записей в диалоге."""
    dialog = mw._CharmapEditorDialog(gui.root, gui, grab=False)
    try:
        assert dialog._apply_add(0xAB, "Х")
        assert "0xAB" in dialog.tree.get_children()
        assert dialog._apply_edit(0xAB, "Щ")
        values = dialog.tree.item("0xAB", "values")
        assert "Щ" in values[1]
        dialog.tree.selection_set("0xAB")
        dialog._remove_selected()
        assert 0xAB not in dialog._charmap
    finally:
        dialog.win.destroy()


def test_charmap_editor_zero_code_and_control(gui):
    """Код 0x00 и multi-char control-токены допустимы."""
    dialog = mw._CharmapEditorDialog(gui.root, gui, grab=False)
    try:
        assert dialog._apply_add(0x00, "[END]")
        assert dialog._charmap[0x00] == "[END]"
        assert dialog._apply_edit(0x00, "[CR]")
        assert dialog._charmap[0x00] == "[CR]"
    finally:
        dialog.win.destroy()


def test_main_window_still_saves_settings(gui, monkeypatch, tmp_path):
    """Главное окно по-прежнему сохраняет настройки."""
    monkeypatch.chdir(tmp_path)
    gui.save_settings(silent=True)
    assert (Path("settings") / "settings.json").exists()


def _probe_load_settings(monkeypatch, tmp_path, base_dir):
    """Вызов load_saved_settings на минимальном объекте с изолированным Tk."""
    root = _make_root()
    try:
        app = mw.GBTextExtractorGUI.__new__(mw.GBTextExtractorGUI)
        app._get_resource_path = lambda rel: str(base_dir / rel)
        app.load_saved_settings()
        return app.target_lang, app.spell_lang
    finally:
        root.destroy()


def test_load_settings_reads_cwd_over_legacy(monkeypatch, tmp_path):
    """load_saved_settings читает cwd-файл; legacy (_MEIPASS) не перебивает его."""
    monkeypatch.chdir(tmp_path)
    new_dir = Path("settings")
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "settings.json").write_text(
        '{"target_language": "ru", "spell_lang": "en"}', encoding="utf-8")

    legacy = tmp_path / "legacy"
    (legacy / "settings").mkdir(parents=True, exist_ok=True)
    (legacy / "settings" / "settings.json").write_text(
        '{"target_language": "ja", "spell_lang": "ja"}', encoding="utf-8")

    target_lang, spell_lang = _probe_load_settings(monkeypatch, tmp_path, legacy)
    assert target_lang.get() == "ru"
    assert spell_lang.get() == "en"


def test_load_settings_migrates_legacy_when_cwd_missing(monkeypatch, tmp_path):
    """Без cwd-файла load_saved_settings восстанавливается из legacy-пути."""
    monkeypatch.chdir(tmp_path)

    legacy = tmp_path / "legacy"
    (legacy / "settings").mkdir(parents=True, exist_ok=True)
    (legacy / "settings" / "settings.json").write_text(
        '{"target_language": "ja", "spell_lang": "ja"}', encoding="utf-8")

    target_lang, spell_lang = _probe_load_settings(monkeypatch, tmp_path, legacy)
    assert target_lang.get() == "ja"
    assert spell_lang.get() == "ja"


def _probe_load_ui_lang(monkeypatch, tmp_path, base_dir):
    """Возвращает ui_lang после load_saved_settings с изолированным Tk."""
    root = _make_root()
    try:
        app = mw.GBTextExtractorGUI.__new__(mw.GBTextExtractorGUI)
        app._get_resource_path = lambda rel: str(base_dir / rel)
        app.load_saved_settings()
        return app.ui_lang.get()
    finally:
        root.destroy()


def test_load_settings_normalizes_language_name_to_code(monkeypatch, tmp_path):
    """Название или код языка в settings.json сводится к коду (en/ru/ja/zh)."""
    monkeypatch.chdir(tmp_path)
    new_dir = Path("settings")
    new_dir.mkdir(parents=True, exist_ok=True)
    legacy = tmp_path / "legacy"
    (legacy / "settings").mkdir(parents=True, exist_ok=True)

    cases = ["ru", "Русский", "en", "English", "ja", "日本語", "zh", "中文"]
    expected = ["ru", "ru", "en", "en", "ja", "ja", "zh", "zh"]
    for raw, want in zip(cases, expected, strict=True):
        (new_dir / "settings.json").write_text(
            f'{{"ui_language": "{raw}"}}', encoding="utf-8")
        assert _probe_load_ui_lang(monkeypatch, tmp_path, legacy) == want


def test_save_settings_writes_language_code(monkeypatch, tmp_path):
    """save_settings пишет в файл код языка, а не его название."""
    monkeypatch.chdir(tmp_path)
    root = _make_root()
    try:
        app = mw.GBTextExtractorGUI.__new__(mw.GBTextExtractorGUI)
        app.ui_lang = tk.StringVar(value="Русский")
        app.target_lang = tk.StringVar(value="ru")
        app.encoding_type = tk.StringVar(value="auto")
        app.verbose_unknown_var = tk.BooleanVar(value=False)
        app.theme = tk.StringVar(value="light")
        app.mt_service = tk.StringVar(value="google")
        app.deepl_key = tk.StringVar(value="")
        app.bing_key = tk.StringVar(value="")
        app.bing_region = tk.StringVar(value="global")
        app.spell_enabled = tk.BooleanVar(value=True)
        app.spell_lang = tk.StringVar(value="auto")
        app.i18n = type("FakeI18N", (), {"change_language": lambda s, lang: None})()
        app._apply_mt_settings = lambda: None
        app._refresh_ui = lambda: None
        app.save_settings(silent=True)
        data = Path("settings/settings.json").read_text(encoding="utf-8")
        assert '"ui_language": "ru"' in data
    finally:
        root.destroy()
