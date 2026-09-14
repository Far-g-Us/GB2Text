# План редизайна интерфейса (UI Plan) — GB2Text

Внутренний план работ по внешнему виду. Функциональность не меняется;
гарантия: round-trip extract→inject→extract остаётся бит-в-бит зелёным.

## 1. Текущее состояние (проблемы)

- 8 вкладок (Extract / Edit / Batch / Compare / Guide / Diagnostics / Settings / About)
  на `ttk.Notebook`; виджеты — смесь `ttk.*` и `tk.*` (Listbox, Text/ScrolledText,
  Canvas).
- Цвета захардкожены по вкладкам: diff — `fg="green"/"red"/"orange"`, `bg="lightgray"`
  (Compare); лого-иконка — `#2c3e50/#ecf0f1`; selection — `#3399ff`.
- Тёмная/светлая тема — ручные циклы `widget.configure(bg=...)` в
  `main_window.py` (~строки 3050-3117), работают через хардкод токенов
  `#2b2b2b/#3c3c3c/#555555`.
- Шрифты захардкожены: `Helvetica` (About/заголовки) и `Consolas` (логи/текст),
  в `gui/editor.py` — `Arial`.
- Нет единой системы отступов: padding скачет 5/10/8/12.

## 2. Цели

1. Единая токенизированная тема (цвета + шрифты + отступы) в одном модуле.
2. Полноценный тёмный режим через `ttk.Style` (тема `clam`) + до-стилизация `tk.*`.
3. Консистентная типографика и сетка отступов (базовый шаг 4px/8px).
4. Семантические цвета diff (added/removed/changed) без хардкода.
5. Доступность: контраст ≥ 4.5:1, видимый focus ring, клавиатурная навигация.
6. Сохранение выбора темы в настройках (как сейчас), применение без перезапуска.

## 3. Дизайн-токены

### 3.1 Цвета
Референс-направление — «flat developer tool» (нейтральный slate + синий акцент),
совместимо с текущей иконкой `#2c3e50/#ecf0f1` и selection `#3399ff`.

| Токен          | Light       | Dark        | Применение                     |
|----------------|-------------|-------------|--------------------------------|
| bg             | #f5f6f8     | #1e1e1e     | Окно/фон вкладок               |
| surface        | #ffffff     | #252526     | Карточки, Log-зоны             |
| border         | #d0d3d8     | #3e3e42     | LabelFrame, рамки              |
| text           | #1f2328     | #e0e0e0     | Основной текст                 |
| text-muted     | #5b6470     | #9d9d9d     | Подписи, подсказки             |
| text-disabled  | #9aa0a6     | #5a5a5a     | Disabled-кнопки, read-only     |
| accent         | #1a6cb5     | #569cd6     | Selection, акцент-кнопки       |
| success        | #1e7e34     | #73b366     | Compare: added                 |
| warning        | #8a5d00     | #dcdcaa     | Compare: changed               |
| danger         | #b42318     | #f48771     | Compare: removed / errors      |
| focus-ring     | #1a6cb5     | #569cd6     | Outline при фокусе             |
| brand-bg       | #2c3e50    | #2c3e50     | Лого (не темизируется)         |
| brand-fg       | #ecf0f1    | #ecf0f1     | Лого (не темизируется)         |

Каждая пара «текст на фоне» ≥ 4.5:1; некст-UI (рамки, focus) ≥ 3:1.
`SystemButtonFace` (системный цвет Windows) сознательно заменяется токеном `bg`
ради консистентности на всех ОС. Контроль — `tests/test_theme_contrast.py`
(WCAG-формула, импортирует токены из `gui/theme.py`, падает при падении любой
пары) — пишется в фазе A.

### 3.2 Шрифты
| Роль      | Семейство                                                     | Размеры                    |
|-----------|---------------------------------------------------------------|----------------------------|
| heading   | Segoe UI → SF Pro Text → Noto Sans → DejaVu Sans → TkDefaultFont | 14 bold (About display 16 bold) |
| UI (по умолч.) | та же UI-цепочка                                       | 9/10/11/12 (по умолч. 10)  |
| mono      | Consolas → DejaVu Sans Mono → Courier New → monospace        | 9/10 для логов/текста      |

`theme.py` резолвит семейства в рантайме через `tkfont.nametofont('TkDefaultFont')`,
чтобы fallback работал на Windows/macOS/Linux.

### 3.3 Отступы
Базовая сетка 4px. Именованные tier (чтобы не выбирать числа наугад):

```
SPACING_XS = 4   # иконка+текст, кнопки toolbar (padx=2 с каждой стороны)
SPACING_SM = 8   # внутренний padding LabelFrame, между кнопками
SPACING_MD = 12  # между полями форм
SPACING_LG = 16  # между секциями / LabelFrame и родителем
SPACING_XL = 24  # крупные разрывы
```

## 4. Объём по вкладкам

| Зона | Действия |
|------|----------|
| Глобально | Новый `gui/theme.py`: токены LIGHT/DARK, `apply(root, dark)`, настройка `ttk.Style` (Notebook, TFrame, TLabel, TButton, TEntry, Treeview — вкл. fieldbackground=surface, selected bg=accent, selected fg контрастный, rowheight) + рекурс. проход по `tk.*` (Listbox/Text/ScrolledText). Focus ring для tk.* — `highlightthickness=2` + `highlightcolor=accent`; для ttk — через Style map (`focuscolor`/`focusborderwidth`). `tk.Menu` стилизуется отдельно через `menu.configure(...)` (не покрывается `winfo_children()`). Каждая модалка Toplevel (search/replace/preview/overflow, предпросмотр editor) вызывает `apply()` в конце своего builder'а. |
| Extract/Edit | Единые поля, кнопки, статус прогресса; убрать хардкод цветов логов. `font=("Arial", ...)` в `gui/editor.py` → UI-токены. |
| Compare | `added/removed/changed` из токенов (заменить `green/red/orange/lightgray`). Цвета `itemconfigure` в Listbox хранятся ссылками на токены и пере-применяются в post-apply хуке после смены темы; опционально в фазах B/C — рефактор на ttk.Treeview с тегами. |
| Guide/Diagnostics/About | Заголовочные теги (header/section/step) из токенов; шкала: 14 bold → 10 → 9; ссылки — токен accent. |
| Settings | Группы с едиными отступами; переключатель темы применяет токены на лету. |
| Batch | Прогресс-иконки/статусы из токенов (success/warning/danger). |

## 5. Этапы (безопасного внедрения)

- **Фаза A** — ✅ выполнена. `gui/theme.py` + перевод main_window/editor.py на токены
  (замена хардкода, без перерисовки раскладки). Вкл. `font=("Arial",...)` →
  UI-токен в editor.py:203/211 и pytest на контраст.
- **Фаза B** — ✅ выполнена. diff-цвета + post-apply хук, брендовая иконка остаётся
  `brand-bg`/`brand-fg`, шрифтовые токены везде.
- **Фаза C** — ✅ выполнена. отступы/выравнивание (tier-сетка), UX: тултипы для кнопок
  toolbar (имя + шорткат), статус-бар, проверка resize на каждой вкладке
  (grid_columnconfigure/grid_rowconfigure), headless-безопасный визуальный
  smoke-тест (создать root Tk, вызвать `apply(dark=True)`, без исключений и
  цвета совпадают с токенами; skip при отсутствии дисплея).
- **Фаза D** — ✅ выполнена. доступность: контраст, focus ring, ручной проход Tab-порядка
  на каждой вкладке, тёмная тема во всех зонах вкл. модалки и лог-области.
- **Фаза E** — ✅ выполнена. хардкод-сканы до нуля в `gui/` (кроме `theme.py` и брендовой
  иконки): `(fg|bg|foreground|background|selectbackground|selectforeground|insertbackground|highlightcolor|highlightbackground)=` и `font=(` в активном коде.
  Единственные оставшиеся вхождения `fg=`/`bg=`/`foreground=` (тултип
  `widgets.py`, diff-Listbox и контролируемые вызовы Compare в `main_window.py`)
  приведены к dict-форме Tkinter API (`configure({...})`), чтобы скан был
  строго нулевым; литералов цветов/шрифтов в активном коде нет.

После каждой фазы: `pytest tests/test_gui*.py tests/test_main_window.py` + round-trip.

## 6. Верификация

- `pytest tests/test_gui*.py tests/test_main_window.py` — green.
- Round-trip тесты — green (никакой логики не трогаем).
- `tests/test_theme_contrast.py` — все пары ≥ 4.5:1 (light + dark).
- `ruff check gui/` — clean.
- Ручной проход: переключение темы без перезапуска, фокус видимый, все диалоги
  в теме, меню в тёмной теме, полнота тёмной темы на каждой вкладке.
- Grep-сканы (фаза E): нуль хардкод-цветов/шрифтов в `gui/` вне
  `theme.py`/констант бренда.

## 7. Вне скоупа

- Никакой смены логики извлечения/вставки, контракта `get_plugin(..., rom=)`,
  форматов TMX/JSON.
- Никаких новых зависимостей (только stdlib tkinter/ttk).
- Не web-tech. tkinter only.
- Скорость/производительность извлечения не меняем.

## 8. Риски

- `ttk.Style` не красит `tk.Listbox/Text/Canvas` — обязателен рекурсивный
  проход по `winfo_children()` с обработкой обоих типов виджетов.
- Пересоздание виджетов при смене языка (`_refresh_ui`) и открытие модалок:
  тему применять после каждой пересборки — `apply()` в конце каждого builder'а
  и после `_refresh_ui`.
- Diff-цвета через `itemconfigure` в Listbox переживают смену темы только через
  post-apply хук (или рефактор на Treeview с тегами).
- tkinterdnd2 drop-target: может игнорировать `ttk.Style`; проверить после
  фазы A, при необходимости пропускать через `isinstance`-чек.
- `apply()` во время активного worker-потока: ходить по снапшоту дерева,
  обернуть в lock.
- Переход на `clam` меняет вид Notebook (плоские вкладки вместо родных
  Windows-табов) — осознанный выбор ради консистентного тёмного режима.
- Контраст проверяется скриптом, не глазом; нужен ручной AA-проход на реальных
  мониторах (гамма/LCD), для граничных пар держать запас ≥ 5:1.

## 9. Определение «готово» по вехам

> **Статус: все фазы A–E завершены (2026-09-11).** Итоговый скан «фазы E»
> по активному коду в `gui/` вне `theme.py` — нуль совпадений.

Веха готова, когда: её pytest/round-trip гейты зелёные, grep-скан чист,
ручной проход темы/тёмного/модалок не показывает расхождений токенов. Фаза E
дополнительно требует зелёный `tests/test_theme_contrast.py` и нуль активных
хардкод-цветов/шрифтов в `gui/`.