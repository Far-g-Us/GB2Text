# UI Redesign Plan — GB2Text

Internal plan for visual overhaul. Functionality must not change; guarantee:
extract→inject→extract round-trip stays byte-for-byte green.

## 1. Current state (problems)

- 8 tabs (Extract / Edit / Batch / Compare / Guide / Diagnostics / Settings / About)
  on a `ttk.Notebook`; widgets are a mix of `ttk.*` and `tk.*` (Listbox,
  Text/ScrolledText, Canvas).
- Colors hardcoded per tab: diff `fg="green"/"red"/"orange"` and `bg="lightgray"`
  (Compare); logo icon `#2c3e50/#ecf0f1`; selection `#3399ff`.
- Dark/light theme — manual `widget.configure(bg=...)` loops in
  `main_window.py` (roughly lines 3050-3117) driven by hardcoded tokens
  `#2b2b2b/#3c3c3c/#555555`.
- Fonts hardcoded: `Helvetica` (About/headings) and `Consolas` (logs/text),
  plus `Arial` in `gui/editor.py`.
- No consistent spacing: padding varies 5/10/8/12.

## 2. Goals

1. Single tokenized theme (colors + fonts + spacing) in one module.
2. Proper dark mode via `ttk.Style` (theme `clam`) plus extra styling for `tk.*`.
3. Consistent typography and spacing grid (base step 4px/8px).
4. Semantic diff colors (added/removed/changed) — no hardcode.
5. Accessibility: contrast ≥ 4.5:1, visible focus ring, keyboard navigation.
6. Theme choice persisted in settings (as today), applied without restart.

## 3. Design tokens

### 3.1 Colors
Direction — "flat developer tool" (neutral slate + blue accent), compatible
with the current logo `#2c3e50/#ecf0f1` and selection `#3399ff`.

| Token         | Light       | Dark        | Usage                       |
|---------------|-------------|-------------|-----------------------------|
| bg            | #f5f6f8     | #1e1e1e     | Window/tab backgrounds      |
| surface       | #ffffff     | #252526     | Cards, log areas            |
| border        | #d0d3d8     | #3e3e42     | LabelFrame, frames          |
| text          | #1f2328     | #e0e0e0     | Primary text                |
| text-muted    | #5b6470     | #9d9d9d     | Labels, hints               |
| text-disabled | #9aa0a6     | #5a5a5a     | Disabled buttons, read-only |
| accent        | #1a6cb5     | #569cd6     | Selection, accent buttons   |
| success       | #1e7e34     | #73b366     | Compare: added              |
| warning       | #8a5d00     | #dcdcaa     | Compare: changed            |
| danger        | #b42318     | #f48771     | Compare: removed / errors   |
| focus-ring    | #1a6cb5     | #569cd6     | Outline on focus            |
| brand-bg      | #2c3e50    | #2c3e50     | Canvas logo (not themed)    |
| brand-fg      | #ecf0f1    | #ecf0f1     | Canvas logo (not themed)    |

Every "text on background" pair must be ≥ 4.5:1. Non-text UI (borders, focus
rings) ≥ 3:1. Note: `SystemButtonFace` (Windows system color) is deliberately
replaced by the `bg` token for consistent cross-platform rendering.
Enforcement: `tests/test_theme_contrast.py` (WCAG formula, imports tokens from
`gui/theme.py`, fails when any fg/bg pair drops below threshold) — written in
Phase A.

### 3.2 Fonts
| Role            | Family chain                                          | Sizes               |
|-----------------|-------------------------------------------------------|---------------------|
| heading         | Segoe UI → SF Pro Text → Noto Sans → DejaVu Sans → TkDefaultFont | 14 bold (About display 16 bold) |
| UI (default)    | same UI chain                                         | 9/10/11/12 (default 10) |
| mono            | Consolas → DejaVu Sans Mono → Courier New → monospace | 9/10 for logs/text  |

`theme.py` resolves families at runtime via `tkfont.nametofont('TkDefaultFont')`
so OS fallbacks work (Windows/macOS/Linux).

### 3.3 Spacing
Base grid 4px. Named tiers (so no one picks a number ad hoc):

```
SPACING_XS = 4   # icon+label, toolbar buttons (padx=2 per side)
SPACING_SM = 8   # label frame internal padding, between buttons
SPACING_MD = 12  # between form fields
SPACING_LG = 16  # between sections / LabelFrame vs parent
SPACING_XL = 24  # major section breaks
```

## 4. Scope by tab

| Area      | Actions |
|-----------|---------|
| Global    | New `gui/theme.py`: LIGHT/DARK tokens, `apply(root, dark)`, `ttk.Style` setup (Notebook, TFrame, TLabel, TButton, TEntry, Treeview — incl. Treeview fieldbackground=surface, selected bg=accent, selected fg contrasting, rowheight) + recursive walk over `tk.*` (Listbox/Text/ScrolledText). tk.* focus ring via `highlightthickness=2` + `highlightcolor=accent`; ttk focus via Style map (`focuscolor`/`focusborderwidth`). `tk.Menu` is styled separately via `menu.configure(...)` (not covered by `winfo_children()`). Every modal Toplevel (search/replace/preview/overflow, editor preview) calls `apply()` at the end of its builder. |
| Extract/Edit | Unified inputs, buttons, progress status; remove log-color hardcode. Replace `font=("Arial", ...)` in `gui/editor.py` with UI tokens. |
| Compare      | `added/removed/changed` from tokens (drop `green/red/orange/lightgray`). Listbox `itemconfigure` colors are stored as token references and re-applied in a post-apply hook after each theme switch; optional refactor to ttk.Treeview with tags in Phases B/C. |
| Guide/Diagnostics/About | Header tags (header/section/step) from tokens; type scale: 14 bold → 10 → 9; default link color from `link`-style token (accent). |
| Settings     | Groups with uniform spacing; theme switch applies tokens live. |
| Batch        | Progress icons/statuses from tokens (success/warning/danger). |

## 5. Phases (safe rollout)

- **Phase A** — ✅ completed. `gui/theme.py` + migrate main_window/editor.py to tokens
  (hardcode→token only, no layout redraw). Includes `font=("Arial",...)` →
  UI token in editor.py:203/211, and the contrast pytest.
- **Phase B** — ✅ completed. diff colors + post-apply hook, brand icon kept as `brand-bg`/`brand-fg`, font tokens everywhere.
- **Phase C** — ✅ completed. spacing/alignment (tier grid), UX: toolbar tooltips (name +
  shortcut), status bar, resize mechanics check per tab
  (grid_columnconfigure/grid_rowconfigure), headless-safe visual smoke test
  (build root Tk, run `apply(dark=True)`, assert no exceptions and colors match
  tokens; skip when no display).
- **Phase D** — ✅ completed. accessibility: contrast, focus ring, keyboard/Tab order manual
  pass on every tab, dark theme on all tabs incl. modals and log areas.
- **Phase E** — ✅ completed. hardcode sweep to zero in `gui/` (except `theme.py` and the
  brand icon): `(fg|bg|foreground|background|selectbackground|selectforeground|insertbackground|highlightcolor|highlightbackground)=` and `font=(` in active code.
  The few remaining `fg=`/`bg=`/`foreground=` occurrences (tooltip in
  `widgets.py`, diff-Listboxes and Compare call sites in `main_window.py`) were
  converted to the dict form of the Tkinter API (`configure({...})`) so the
  sweep is strictly zero; no color/font literals remain in active code.

After each phase: `pytest tests/test_gui*.py tests/test_main_window.py` + round-trip.

## 6. Verification

- `pytest tests/test_gui*.py tests/test_main_window.py` — green.
- Round-trip tests — green (no logic touched).
- `tests/test_theme_contrast.py` — all pairs ≥ 4.5:1 (light + dark).
- `ruff check gui/` — clean.
- Manual pass: theme toggle live without restart, visible focus, all dialogs
  themed, menus themed in dark, dark mode complete on every tab.
- Grep sweeps (Phase E) show zero hardcoded colors/fonts in `gui/` outside
  `theme.py`/brand constants.

## 7. Out of scope

- No changes to extraction/insertion logic, `get_plugin(..., rom=)` contract,
  TMX/JSON formats.
- No new dependencies (stdlib tkinter/ttk only).
- No web tech. tkinter only.
- Extraction speed/performance untouched.

## 8. Risks

- `ttk.Style` does not paint `tk.Listbox/Text/Canvas` — recursive walk over
  `winfo_children()` is mandatory, handling both widget kinds.
- Widget recreation on language switch (`_refresh_ui`) and modal creation:
  theme must be applied after every rebuild — call `apply()` at the end of each
  builder and after `_refresh_ui`.
- Listbox `itemconfigure` diff colors survive theme switch only via the
  post-apply hook (or Treeview-with-tags refactor).
- tkinterdnd2 drop-target widgets may ignore `ttk.Style`; verify after Phase A,
  skip via an `isinstance` check if needed.
- `apply()` during an active worker thread: guard against a mutating widget tree
  (walk a snapshot, wrap in a lock).
- Switching to `clam` visibly changes Notebook look (flat tabs instead of native
  Windows tabs) — deliberate for consistent cross-platform dark mode.
- Contrast is only audited by script, not by eye; do a manual AA pass on real
  monitors (gamma/LCD variance), keep ≥ 5:1 for borderline pairs where possible.

## 9. Definition of done (per milestone)

> **Status: all phases A–E completed (2026-09-11).** Final Phase E sweep over
> active code in `gui/` outside `theme.py` — zero matches.

Milestone done when: its pytest/round-trip gates are green, its grep sweep is
clean, and the manual theme/dark/modal pass shows no token mismatches. Phase E
additionally requires `tests/test_theme_contrast.py` green and zero
hardcoded-color/hardcoded-font active occurrences in `gui/`.