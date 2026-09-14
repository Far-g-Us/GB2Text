"""Headless e2e-тесты точки входа main.py: агентский режим (subcommands)
и legacy-режим (флаги). Проверяются коды выхода и JSON/CSV на stdout."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_main(*args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "main.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )


def _load_payload(proc):
    output = proc.stdout.strip()
    assert output, f"stdout пустой, stderr={proc.stderr!r}"
    return json.loads(output)


def test_agent_extract_json(api_rom_file):
    proc = _run_main("extract", api_rom_file, "--plugin-dir", "plugins", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = _load_payload(proc)
    assert payload["ok"] is True
    all_text = " ".join(
        msg["text"] for msgs in payload["data"]["segments"].values() for msg in msgs
    )
    assert "HELLO WORLD" in all_text


def test_agent_detect_json(api_rom_file):
    proc = _run_main("detect", api_rom_file, "--plugin-dir", "plugins", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = _load_payload(proc)
    assert payload["ok"] is True
    assert payload["data"]["game_id"] == "GB_TESTTITLEAPI"


def test_agent_inject_json(api_rom_file, tmp_path):
    extract_proc = _run_main("extract", api_rom_file, "--plugin-dir", "plugins", "--json")
    assert extract_proc.returncode == 0, extract_proc.stderr
    extracted = json.loads(extract_proc.stdout)["data"]

    translations = {
        seg: [{"translation": "HI WORLD"} for _ in msgs]
        for seg, msgs in extracted["segments"].items()
    }
    tr_file = tmp_path / "translations.json"
    tr_file.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")

    out_rom = tmp_path / "patched.gb"
    proc = _run_main(
        "inject", api_rom_file,
        "--translations", str(tr_file),
        "--output-rom", str(out_rom),
        "--plugin-dir", "plugins",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    payload = _load_payload(proc)
    assert payload["ok"] is True
    assert all(payload["data"]["segments"].values())
    assert out_rom.exists(), "Выходной ROM не создан"


def test_agent_plugins_json(empty_plugin_dir):
    proc = _run_main("plugins", "--plugin-dir", empty_plugin_dir, "--json")
    assert proc.returncode == 0, proc.stderr
    payload = _load_payload(proc)
    assert payload["ok"] is True
    assert payload["data"] == []


def test_agent_unknown_command_falls_back_to_legacy(api_rom_file):
    """Первый позиционный аргумент вне AGENT_COMMANDS → legacy-режим (rom-файл).
    Файл не существует → код 1, без JSON-обёртки."""
    proc = _run_main("no-such-command", api_rom_file)
    assert proc.returncode == 2
    assert "unrecognized arguments" in proc.stderr.lower()


def test_legacy_extract_json(api_rom_file):
    proc = _run_main(api_rom_file, "--output", "json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert any(
        "HELLO WORLD" in msg["text"]
        for messages in data.values()
        for msg in messages
    )


def test_legacy_extract_csv(api_rom_file, tmp_path):
    out_csv = tmp_path / "legacy.csv"
    proc = _run_main(api_rom_file, "--output", "csv", "--output-file", str(out_csv))
    assert proc.returncode == 0, proc.stderr
    content = out_csv.read_text(encoding="utf-8")
    assert "HELLO WORLD" in content


def test_legacy_roundtrip(api_rom_file, tmp_path):
    """extract -> inject (legacy-флаги) -> re-extract: текст сохраняется."""
    extract_proc = _run_main(api_rom_file, "--output", "json")
    assert extract_proc.returncode == 0, extract_proc.stderr
    original = json.loads(extract_proc.stdout)
    assert original, "Пустое извлечение"

    translations = {
        seg: [{"translation": m["text"]} for m in msgs]
        for seg, msgs in original.items()
    }
    tr_file = tmp_path / "roundtrip_translations.json"
    tr_file.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")

    out_rom = tmp_path / "roundtrip.gb"
    inject_proc = _run_main(
        api_rom_file,
        "--inject",
        "--translations", str(tr_file),
        "--output-rom", str(out_rom),
    )
    assert inject_proc.returncode == 0, inject_proc.stderr
    assert out_rom.exists()

    re_extract = _run_main(str(out_rom), "--output", "json")
    assert re_extract.returncode == 0, re_extract.stderr
    restored = json.loads(re_extract.stdout)
    for seg, msgs in original.items():
        restored_texts = [m["text"] for m in restored.get(seg, [])]
        original_texts = [m["text"] for m in msgs]
        assert restored_texts == original_texts, f"Сегмент {seg}: текст изменился"


def test_legacy_version():
    proc = _run_main("--version")
    assert proc.returncode == 0
    assert "v" in proc.stdout
