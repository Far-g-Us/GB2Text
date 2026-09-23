"""Playtest PyBoy-first: валидация, fake-прогоны, stub, compare (без эмулятора)."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PIL import Image

from core.playtest import (
    MGBABackend,
    PlaytestBackend,
    PyBoyBackend,
    _default_factory,
    build_mgba_driver,
    collect_mgba_shots,
    compare_reports,
    hash_shot,
    is_dark,
    validate_script,
)


def _any(value: object) -> Any:
    return value


def _step(**kw: object) -> dict:
    base: dict = {"buttons": [], "frames": 10}
    base.update(kw)
    return base


class FakeCore:
    def __init__(self, mode="vary", fail_at=0):
        self.mode = mode
        self.fail_at = fail_at
        self.calls: list = []
        self.frame = 0
        self.closed = False

    def press(self, name):
        self.calls.append(("press", name))

    def release(self, name):
        self.calls.append(("release", name))

    def tick(self, n):
        self.calls.append(("tick", n))
        self.frame += n
        if self.fail_at and self.frame >= self.fail_at:
            raise RuntimeError("boom")

    def shot(self):
        if self.mode == "still":
            color = (100, 100, 100)
        elif self.mode == "dark":
            color = (0, 0, 0)
        else:
            color = (100 + self.frame % 100, 30, 30)
        return Image.new("RGB", (160, 144), color)

    def close(self):
        self.closed = True


def _backend(mode="vary", **kw):
    box = {}
    core = FakeCore(mode, **kw)

    def factory(path):
        box["path"] = path
        return core

    return PyBoyBackend("game.gb", core_factory=factory), core, box


class TestValidate:
    def test_ok(self):
        script = validate_script([{"buttons": ["a", "START"], "frames": 5, "mark": "menu-1"}, {"buttons": [], "frames": 3}])
        assert script == [{"buttons": ["A", "START"], "frames": 5, "mark": "menu-1"}, {"buttons": [], "frames": 3, "mark": None}]

    def test_not_list(self):
        cases: tuple[Any, ...] = (None, "x", {}, 5)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_script(_any(bad))

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_script([])

    def test_too_many_steps(self):
        with pytest.raises(ValueError):
            validate_script([_step() for _ in range(257)])

    def test_bad_step(self):
        with pytest.raises(ValueError):
            validate_script(["x"])
        with pytest.raises(ValueError):
            validate_script([{"buttons": []}])
        with pytest.raises(ValueError):
            validate_script([{"frames": 5}])

    def test_bad_buttons(self):
        for bad in ("A", 5, None, ["X"], [None], [True]):
            with pytest.raises(ValueError):
                validate_script([_step(buttons=_any(bad))])

    def test_bad_frames(self):
        for bad in (True, "5", None, 0, -1, 601):
            with pytest.raises(ValueError):
                validate_script([_step(frames=_any(bad))])

    def test_bad_mark(self):
        for bad in ("", "a/b", "a b", "..", 5, True):
            with pytest.raises(ValueError):
                validate_script([_step(mark=_any(bad))])

    def test_dup_mark(self):
        with pytest.raises(ValueError):
            validate_script([_step(mark="m"), _step(mark="m")])

    def test_total_cap(self):
        with pytest.raises(ValueError):
            validate_script([_step(frames=600) for _ in range(31)])


class TestHash:
    def test_stable(self):
        img = Image.new("RGB", (160, 144), (1, 2, 3))
        assert hash_shot(img) == hash_shot(img.copy())

    def test_size_norm(self):
        assert hash_shot(Image.new("RGB", (10, 10), (9, 9, 9))) == hash_shot(Image.new("RGB", (160, 144), (9, 9, 9)))

    def test_dark(self):
        assert is_dark(Image.new("RGB", (160, 144), (0, 0, 0))) is True
        assert is_dark(Image.new("RGB", (160, 144), (255, 255, 255))) is False


class TestRun:
    def test_marks_and_shots(self, tmp_path):
        backend, core, box = _backend()
        report = backend.run([{"buttons": ["A"], "frames": 5, "mark": "m1"}, {"buttons": [], "frames": 2}], out_dir=str(tmp_path))
        assert box["path"] == "game.gb"
        assert report["total"] == 7
        assert len(report["hashes"]) == 7
        assert report["marks"]["m1"]["frame"] == 5
        assert report["marks"]["m1"]["shot"].endswith("0000_m1_5.png")
        assert os.path.isfile(report["marks"]["m1"]["shot"])
        assert ("press", "A") in core.calls
        assert ("release", "A") in core.calls
        assert core.closed is True
        assert report["stuck"] is False
        assert report["dark"] == []

    def test_no_out_dir(self):
        backend, _, _ = _backend()
        report = backend.run([_step(mark="m")])
        assert report["marks"]["m"]["shot"] is None

    def test_bad_out_dir(self):
        backend, _, _ = _backend()
        for bad in ("", 5, None.__class__):
            with pytest.raises(ValueError):
                backend.run([_step()], out_dir=_any(bad))

    def test_stuck(self):
        backend, _, _ = _backend("still")
        report = backend.run([{"buttons": ["START"], "frames": 130}])
        assert report["stuck"] is True

    def test_not_stuck_moving(self):
        backend, _, _ = _backend("vary")
        report = backend.run([{"buttons": ["START"], "frames": 130}])
        assert report["stuck"] is False

    def test_not_stuck_idle(self):
        backend, _, _ = _backend("still")
        report = backend.run([{"buttons": [], "frames": 130}])
        assert report["stuck"] is False

    def test_dark_frames(self):
        backend, _, _ = _backend("dark")
        report = backend.run([_step(frames=3)])
        assert report["dark"] == [1, 2, 3]

    def test_close_on_error(self):
        backend, _core, _ = _backend("vary", fail_at=3)
        with pytest.raises(RuntimeError):
            backend.run([_step(frames=10)])

    def test_bad_rom(self):
        for bad in ("", None, 5):
            with pytest.raises(ValueError):
                PyBoyBackend(_any(bad))

    def test_close_recorded_on_error(self):
        backend, core, _ = _backend("vary", fail_at=3)
        try:
            backend.run([_step(frames=10)])
        except RuntimeError:
            pass
        assert core.closed is True


class TestFactory:
    def test_default(self, monkeypatch):
        seen = {}

        class FakePyBoy:
            def __init__(self, rom, window=None):
                seen["rom"] = rom
                seen["window"] = window
                self.screen = SimpleNamespace(image=Image.new("RGB", (160, 144), (1, 1, 1)))

            def set_emulation_speed(self, speed):
                seen["speed"] = speed

            def button_press(self, name):
                seen.setdefault("press", []).append(name)

            def button_release(self, name):
                seen.setdefault("release", []).append(name)

            def tick(self, n, render):
                seen.setdefault("tick", []).append((n, render))

            def stop(self, save):
                seen["save"] = save

        monkeypatch.setitem(sys.modules, "pyboy", SimpleNamespace(PyBoy=FakePyBoy))
        ns = _default_factory("x.gb")
        ns.press("A")
        ns.tick(1)
        ns.release("A")
        shot = ns.shot()
        assert shot.size == (160, 144)
        ns.close()
        assert seen["rom"] == "x.gb"
        assert seen["window"] == "null"
        assert seen["speed"] == 0
        assert seen["press"] == ["a"]
        assert seen["release"] == ["a"]
        assert seen["tick"] == [(1, True)]
        assert seen["save"] is False


class TestDriver:
    def test_content(self, tmp_path):
        lua = build_mgba_driver(
            [{"buttons": ["start"], "frames": 5, "mark": "m1"}, {"buttons": [], "frames": 3, "mark": "m2"}],
            str(tmp_path),
        )
        assert "0.10.x" in lua
        assert "mgba.io/docs" in lua
        assert f"[[{tmp_path}]]" in lua
        assert '[5] = "0000_m1_5"' in lua
        assert '[8] = "0001_m2_8"' in lua
        assert "emu:addKey(C.GBA_KEY.START)" in lua
        assert "emu:clearKey(C.GBA_KEY.START)" in lua
        assert 'callbacks:add("frame"' in lua
        assert "emu:screenshot" in lua
        assert 'console:log("gb2text driver loaded")' in lua

    def test_lower_buttons(self, tmp_path):
        lua = build_mgba_driver([{"buttons": ["a"], "frames": 2}], str(tmp_path))
        assert "C.GBA_KEY.A" in lua

    def test_path_passthrough(self, tmp_path):
        out = str(tmp_path / "dir with spaces" / "юникод")
        lua = build_mgba_driver([_step()], out)
        assert f"[[{out}]]" in lua

    def test_bad_script(self, tmp_path):
        with pytest.raises(ValueError):
            build_mgba_driver(["x"], str(tmp_path))

    def test_bad_out_dir(self):
        for bad in ("", None, 5):
            with pytest.raises(ValueError):
                build_mgba_driver([_step()], _any(bad))

    def test_bracket_escape(self, tmp_path):
        with pytest.raises(ValueError):
            build_mgba_driver([_step()], str(tmp_path) + "]]")

    def test_shot_before_events(self, tmp_path):
        lua = build_mgba_driver(
            [{"buttons": ["A"], "frames": 5, "mark": "m1"}, {"buttons": ["B"], "frames": 3}],
            str(tmp_path),
        )
        assert "assumed" in lua
        body = lua[lua.index('callbacks:add("frame"') :]
        assert body.index("local m = marks") < body.index("local ev = events")
        at5 = lua[lua.index("[5] = function") :]
        assert at5.index("emu:clearKey(C.GBA_KEY.A)") < at5.index("emu:addKey(C.GBA_KEY.B)")


class TestCollect:
    def _png(self, path, color=(5, 5, 5)):
        Image.new("RGB", (240, 160), color).save(str(path))

    def test_ok(self, tmp_path):
        steps = [{"buttons": ["A"], "frames": 5, "mark": "m1"}, {"buttons": [], "frames": 3}]
        self._png(tmp_path / "0000_m1_5.png")
        report = collect_mgba_shots(str(tmp_path), steps)
        assert report["marks"]["m1"]["frame"] == 5
        assert report["marks"]["m1"]["shot"].endswith("0000_m1_5.png")
        assert len(report["hashes"]) == 1
        assert report["stuck"] is False
        assert report["total"] == 8
        assert report["source"] == "mgba-manual"
        assert report["dark"] == [5]

    def test_bright(self, tmp_path):
        steps = [{"buttons": [], "frames": 2, "mark": "m"}]
        self._png(tmp_path / "0000_m_2.png", color=(200, 200, 200))
        report = collect_mgba_shots(str(tmp_path), steps)
        assert report["dark"] == []

    def test_missing(self, tmp_path):
        with pytest.raises(RuntimeError):
            collect_mgba_shots(str(tmp_path), [_step(mark="m")])

    def test_broken(self, tmp_path):
        (tmp_path / "0000_m_10.png").write_bytes(b"not a png")
        with pytest.raises(RuntimeError):
            collect_mgba_shots(str(tmp_path), [_step(frames=10, mark="m")])

    def test_bad_args(self, tmp_path):
        with pytest.raises(ValueError):
            collect_mgba_shots("", [_step()])
        with pytest.raises(ValueError):
            collect_mgba_shots(str(tmp_path), ["x"])


class TestStub:
    def test_bad_rom(self):
        with pytest.raises(ValueError):
            MGBABackend("")

    def test_run_refused(self):
        backend = MGBABackend("game.gba")
        with pytest.raises(RuntimeError):
            backend.run([_step()])
        with pytest.raises(ValueError):
            backend.run(["x"])

    def test_protocol(self):
        assert isinstance(PyBoyBackend("a.gb"), PlaytestBackend)
        assert isinstance(MGBABackend("a.gba"), PlaytestBackend)


class TestCompare:
    def _reports(self):
        base = {"marks": {"m1": {"frame": 5, "hash": "aa", "shot": None}, "m2": {"frame": 9, "hash": "bb", "shot": None}}}
        cur = {"marks": {"m1": {"frame": 5, "hash": "aa", "shot": None}, "m2": {"frame": 9, "hash": "cc", "shot": None}, "m3": {"frame": 1, "hash": "dd", "shot": None}}}
        return base, cur

    def test_diff(self):
        base, cur = self._reports()
        assert compare_reports(base, cur) == {"m1": "same", "m2": "diff", "m3": "extra"}

    def test_missing(self):
        base, _ = self._reports()
        assert compare_reports(base, {"marks": {}}) == {"m1": "missing", "m2": "missing"}

    def test_bad_mode(self):
        base, cur = self._reports()
        with pytest.raises(ValueError):
            compare_reports(base, cur, mode="translated")

    def test_bad_shapes(self):
        base, cur = self._reports()
        cases: tuple[Any, ...] = (None, [], "x")
        for bad in cases:
            with pytest.raises(ValueError):
                compare_reports(_any(bad), cur)
            with pytest.raises(ValueError):
                compare_reports(base, _any(bad))
        with pytest.raises(ValueError):
            compare_reports({"marks": None}, cur)
        with pytest.raises(ValueError):
            compare_reports(base, {"marks": []})
        with pytest.raises(ValueError):
            compare_reports({"marks": {"m1": "x"}}, cur)
        with pytest.raises(ValueError):
            compare_reports(base, {"marks": {"m1": "x", "m2": {"hash": "bb"}}})


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
