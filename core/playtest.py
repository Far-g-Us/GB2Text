"""Headless playtest: scripted emulator runs with screenshots (PyBoy-first).

GB/GBC через PyBoy (in-process, без сети); GBA — stub до второго инкремента.
ROM только читается (stop(save=False), сайд-файлов нет). Эвристики stuck/dark —
preview-маркеры Layer 5, не гейты: still-экран при wait без кнопок — норма,
мигающий курсор даёт ложноотрицательный stuck. Golden compare — только
same-language round-trip (переведённый текст легитимно отличается).
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Protocol, runtime_checkable

BUTTONS = ("A", "B", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT")
_PYBOY_MAP = {b: b.lower() for b in BUTTONS}
MAX_STEPS = 256
MAX_WAIT = 600
MAX_TOTAL_FRAMES = 18000
STUCK_WINDOW = 120
SHOT_SIZE = (160, 144)
_MARK_RE = re.compile(r"[A-Za-z0-9_-]+")
_MGBA_VERSION_PIN = "0.10.x"
_MGBA_DOCS = "https://mgba.io/docs/scripting.html"


def validate_script(script: list) -> list[dict]:
    """Нормализует input-скрипт: [{buttons:[UP..], frames:int, mark:str|None}].

    Кнопки регистронезависимо (хранятся верхним), пустой buttons — чистое
    ожидание. mark — для скриншота, уникален. Лимиты: шагов ≤256, wait
    1..600, суммарно ≤18000 кадров.
    """
    if not isinstance(script, (list, tuple)) or not script:
        raise ValueError("script must be a non-empty list")
    if len(script) > MAX_STEPS:
        raise ValueError(f"script has {len(script)} steps, max {MAX_STEPS}")
    total = 0
    seen: set[str] = set()
    out: list[dict] = []
    for pos, step in enumerate(script):
        if not isinstance(step, dict):
            raise ValueError(f"step {pos} must be a dict")
        try:
            buttons = step["buttons"]
            frames = step["frames"]
        except KeyError as exc:
            raise ValueError(f"step {pos} needs {exc}") from exc
        mark = step.get("mark")
        if isinstance(buttons, str) or not isinstance(buttons, (list, tuple)):
            raise ValueError(f"step {pos} buttons must be a list")
        norm_buttons: list[str] = []
        for b in buttons:
            if not isinstance(b, str) or b.upper() not in BUTTONS:
                raise ValueError(f"step {pos} bad button: {b!r}")
            norm_buttons.append(b.upper())
        if isinstance(frames, bool) or not isinstance(frames, int):
            raise ValueError(f"step {pos} frames must be int: {frames!r}")
        if frames < 1 or frames > MAX_WAIT:
            raise ValueError(f"step {pos} frames {frames} out of 1-{MAX_WAIT}")
        if mark is not None:
            if not isinstance(mark, str) or _MARK_RE.fullmatch(mark) is None:
                raise ValueError(f"step {pos} bad mark: {mark!r}")
            if mark in seen:
                raise ValueError(f"duplicate mark: {mark!r}")
            seen.add(mark)
        total += frames
        if total > MAX_TOTAL_FRAMES:
            raise ValueError(f"script exceeds {MAX_TOTAL_FRAMES} total frames")
        out.append({"buttons": norm_buttons, "frames": frames, "mark": mark})
    return out


def hash_shot(image) -> str:
    """sha256 RGB фиксированного размера (стабилен между PIL/PyBoy).

    Размер общий для GB/GBA: пригоден только для внутриплатформенного сравнения.
    """
    return hashlib.sha256(image.convert("RGB").resize(SHOT_SIZE).tobytes()).hexdigest()


def is_dark(image) -> bool:
    """Preview-маркер тёмного кадра (max яркости ≤8)."""
    return bool(max(image.convert("L").resize(SHOT_SIZE).getdata()) <= 8)


@runtime_checkable
class PlaytestBackend(Protocol):
    """Общий протокол бэкендов: run(script, out_dir) -> report."""

    def run(self, script: list, out_dir: str | None = None) -> dict: ...  # pragma: no cover


def _default_factory(rom_path: str):
    """Реальное PyBoy-ядро: hold кнопок весь шаг, рендер каждого кадра."""
    from pyboy import PyBoy

    emu = PyBoy(rom_path, window="null")
    emu.set_emulation_speed(0)

    def tick(n: int) -> None:
        emu.tick(n, True)

    def press(name: str) -> None:
        emu.button_press(_PYBOY_MAP[name])

    def release(name: str) -> None:
        emu.button_release(_PYBOY_MAP[name])

    def shot():
        return emu.screen.image.copy()

    def close() -> None:
        emu.stop(False)

    from types import SimpleNamespace

    return SimpleNamespace(tick=tick, press=press, release=release, shot=shot, close=close)


class PyBoyBackend:
    """GB/GBC headless-прогон. core_factory — для тестов (fake без эмулятора)."""

    def __init__(self, rom_path: str, core_factory=None):
        if not isinstance(rom_path, str) or not rom_path:
            raise ValueError(f"bad rom_path: {rom_path!r}")
        self._rom = rom_path
        self._factory = core_factory or _default_factory

    def run(self, script: list, out_dir: str | None = None) -> dict:
        steps = validate_script(script)
        if out_dir is not None:
            if not isinstance(out_dir, str) or not out_dir:
                raise ValueError(f"bad out_dir: {out_dir!r}")
            os.makedirs(out_dir, exist_ok=True)
        core = self._factory(self._rom)
        hashes: list[str] = []
        pressed: list[bool] = []
        dark: list[int] = []
        marks: dict[str, dict] = {}
        frame = 0
        try:
            for num, step in enumerate(steps):
                pushed = list(step["buttons"])
                for b in pushed:
                    core.press(b)
                for _ in range(step["frames"]):
                    core.tick(1)
                    frame += 1
                    img = core.shot()
                    digest = hash_shot(img)
                    hashes.append(digest)
                    pressed.append(bool(pushed))
                    if is_dark(img):
                        dark.append(frame)
                for b in pushed:
                    core.release(b)
                if step["mark"] is not None:
                    shot_path = None
                    if out_dir is not None:
                        shot_path = os.path.join(out_dir, f"{num:04d}_{step['mark']}_{frame}.png")
                        img.save(shot_path)
                    marks[step["mark"]] = {"frame": frame, "hash": digest, "shot": shot_path}
        finally:
            core.close()
        stuck = (
            len(hashes) >= STUCK_WINDOW
            and len(set(hashes[-STUCK_WINDOW:])) == 1
            and any(pressed[-STUCK_WINDOW:])
        )
        return {"marks": marks, "hashes": hashes, "stuck": stuck, "dark": dark, "total": frame, "source": "pyboy"}


class MGBABackend:
    """GBA: v1 — только Lua-драйвер + сборщик (ручной запуск в mGBA-Qt).

    run() остаётся честным отказом до пилота на реальном mGBA.
    Пайплайн v1: build_mgba_driver(steps, out_dir) -> .lua, запуск вручную
    (mGBA-Qt Tools > Scripting), затем collect_mgba_shots(out_dir, steps).
    """

    def __init__(self, rom_path: str):
        if not isinstance(rom_path, str) or not rom_path:
            raise ValueError(f"bad rom_path: {rom_path!r}")
        self._rom = rom_path

    def run(self, script: list, out_dir: str | None = None) -> dict:
        validate_script(script)
        raise RuntimeError("mGBA automated run not implemented; use build_mgba_driver + manual run + collect_mgba_shots")


def build_mgba_driver(steps: list, out_dir: str) -> str:
    """Lua-драйвер mGBA для ручного прогона (Qt Tools > Scripting).

    API: mgba.io/docs, пин _MGBA_VERSION_PIN. ВСЕ вызовы assumed
    (пилот-гейт): callbacks/add-frame, emu addKey/clearKey/screenshot,
    console:log, тайминг колбэка "frame".
    Тайминг-контракт (как в run()): скриншот марк-кадра — при удержании
    кнопок шага (до их снятия), снятие/установка — после скриншота.
    """

    def _emit_key(table: str, name: str) -> str:
        return f"emu:{table}(C.GBA_KEY.{name})"

    norm = validate_script(steps)
    if not isinstance(out_dir, str) or not out_dir:
        raise ValueError(f"bad out_dir: {out_dir!r}")
    if "]]" in out_dir:
        raise ValueError("out_dir must not contain ']]' (Lua literal)")
    head = [
        "-- GB2Text mGBA playtest driver (manual run: mGBA-Qt Tools > Scripting).",
        f"-- Pinned API: mGBA {_MGBA_VERSION_PIN}, {_MGBA_DOCS} (all calls assumed, pilot-gated).",
        f"local OUT = [[{out_dir}]]",
        "local frame = 0",
        "local marks = {",
    ]
    events: dict[int, list[str]] = {}
    frame = 0
    for num, step in enumerate(norm):
        for b in step["buttons"]:
            events.setdefault(frame, []).append(_emit_key("addKey", b))
        frame += step["frames"]
        for b in step["buttons"]:
            events.setdefault(frame, []).append(_emit_key("clearKey", b))
        if step["mark"] is not None:
            head.append(f'  [{frame}] = "{num:04d}_{step["mark"]}_{frame}",')
    head.append("}")
    head.append("local events = {")
    for at in sorted(events):
        head.append(f"  [{at}] = function()")
        head.extend(f"    {call}" for call in events[at])
        head.append("  end,")
    head.extend(
        [
            "}",
        "local boot = events[0]",
        "if boot ~= nil then boot() end",
        'callbacks:add("frame", function()',
        "  frame = frame + 1",
        "  local m = marks[frame]",
        '  if m ~= nil then emu:screenshot(OUT .. "/" .. m .. ".png") end',
        "  local ev = events[frame]",
        "  if ev ~= nil then ev() end",
        "end)",
        'console:log("gb2text driver loaded")',
        ]
    )
    return "\n".join(head) + "\n"


def collect_mgba_shots(out_dir: str, steps: list) -> dict:
    """Отчёт из PNG ручного mGBA-прогона (driver выше + collect).

    hashes — только по маркам (покадровых нет): stuck всегда False,
    preview-маркер dark — по маркам. Форма отчёта та же, source=mgba-manual.
    """
    norm = validate_script(steps)
    if not isinstance(out_dir, str) or not out_dir:
        raise ValueError(f"bad out_dir: {out_dir!r}")
    from PIL import Image

    marks: dict[str, dict] = {}
    hashes: list[str] = []
    dark: list[int] = []
    frame = 0
    for num, step in enumerate(norm):
        frame += step["frames"]
        if step["mark"] is None:
            continue
        name = f"{num:04d}_{step['mark']}_{frame}.png"
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path):
            raise RuntimeError(f"missing playtest shot: {name}")
        try:
            with Image.open(path) as img:
                img.load()
                digest = hash_shot(img)
                shaded = is_dark(img)
        except OSError as exc:
            raise RuntimeError(f"bad playtest shot {name}: {exc}") from exc
        marks[step["mark"]] = {"frame": frame, "hash": digest, "shot": path}
        hashes.append(digest)
        if shaded:
            dark.append(frame)
    return {"marks": marks, "hashes": hashes, "stuck": False, "dark": dark, "total": frame, "source": "mgba-manual"}


def compare_reports(baseline: dict, current: dict, *, mode: str = "roundtrip") -> dict[str, str]:
    """Структурный diff марок по хешам. Только mode='roundtrip' (same-language).

    Переведённый ROM легитимно отличается — сравнение с ним вне roundtrip
    запрещено явной ошибкой (Layer 5: структура, не попиксельность).
    Кросс-платформа не рекомендуется (разные рендеры дадут diff).
    """
    if mode != "roundtrip":
        raise ValueError("compare_reports is only valid for same-language roundtrip")
    if not isinstance(baseline, dict) or not isinstance(current, dict):
        raise ValueError("reports must be dicts")
    base_marks = baseline.get("marks")
    cur_marks = current.get("marks")
    if not isinstance(base_marks, dict) or not isinstance(cur_marks, dict):
        raise ValueError("reports need 'marks' dicts")
    out: dict[str, str] = {}
    for name, entry in base_marks.items():
        if not isinstance(entry, dict):
            raise ValueError(f"bad baseline mark: {name!r}")
        peer = cur_marks.get(name)
        if peer is None:
            out[name] = "missing"
        elif not isinstance(peer, dict):
            raise ValueError(f"bad current mark: {name!r}")
        elif peer.get("hash") == entry.get("hash"):
            out[name] = "same"
        else:
            out[name] = "diff"
    for name in cur_marks:
        if name not in base_marks:
            out[name] = "extra"
    return out
