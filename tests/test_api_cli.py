"""Тесты api.cli через subprocess: выходные коды и JSON на stdout."""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _child_env():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_cli(*args, json_mode=False):
    cmd = [sys.executable, "-m", "api.cli"]
    cmd.extend(args)
    if json_mode:
        cmd.append("--json")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
        env=_child_env(),
    )


def test_cli_no_args_exit_2():
    proc = _run_cli()
    assert proc.returncode == 2


def test_cli_plugins_json(empty_plugin_dir):
    proc = _run_cli("plugins", "--plugin-dir", empty_plugin_dir, json_mode=True)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["data"] == []


def test_cli_detect_json(api_rom_file):
    proc = _run_cli("detect", api_rom_file, "--plugin-dir", "plugins", json_mode=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["data"]["game_id"] == "GB_TESTTITLEAPI"


def test_cli_detect_missing_rom_exit_1():
    proc = _run_cli("detect", "no_such.gb", "--plugin-dir", "plugins", json_mode=True)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("IO_ERROR", "ROM_ERROR")


def test_cli_extract_json(api_rom_file):
    proc = _run_cli("extract", api_rom_file, "--plugin-dir", "plugins", json_mode=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    all_text = " ".join(
        msg["text"] for msgs in data["data"]["segments"].values() for msg in msgs
    )
    assert "HELLO WORLD" in all_text


def test_cli_extract_csv(tmp_path, api_rom_file):
    out_csv = tmp_path / "text.csv"
    proc = _run_cli(
        "extract", api_rom_file, "--plugin-dir", "plugins",
        "--format", "csv", "--output", str(out_csv),
    )
    assert proc.returncode == 0
    content = out_csv.read_text(encoding="utf-8")
    assert "HELLO WORLD" in content


def test_cli_extract_format_conflict(api_rom_file):
    proc = _run_cli(
        "extract", api_rom_file, "--plugin-dir", "plugins",
        "--format", "json", "--json",
    )
    assert proc.returncode == 2


def test_cli_inject_json(api_rom_file, tmp_path):
    translations_path = tmp_path / "translations.json"
    extracted = json.loads(
        subprocess.run(
            [sys.executable, "-m", "api.cli", "extract", api_rom_file,
             "--plugin-dir", "plugins", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_child_env(),
        ).stdout
    )["data"]
    translations = {
        seg: [{"translation": "HI WORLD"} for _ in msgs]
        for seg, msgs in extracted["segments"].items()
    }
    translations_path.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")

    out_rom = tmp_path / "patched.gb"
    proc = _run_cli(
        "inject", api_rom_file,
        "--translations", str(translations_path),
        "--output-rom", str(out_rom),
        "--plugin-dir", "plugins",
        json_mode=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert all(data["data"]["segments"].values())
    assert out_rom.exists()
