"""CLI-команда `fixsum`: проверка и починка checksum'ов ROM.

Контракт отличается от остальных команд CLI: код 1 здесь означает «checksum
сломан», а не «ошибка выполнения» — это сигнал для CI. Ошибки (нечитаемый ROM)
по-прежнему идут через `_fail` с кодом 1 и JSON-контрактом ошибки.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from api.cli import _cmd_fixsum, build_parser, main

# `resolve_rom` отвергает файл меньше MIN_ROM_SIZE (32768) и с неверным
# расширением — именно эта проверка защищает `--fix` от записи в `.sav`/`.txt`.
# Фикстуры обязаны быть настоящего размера и с валидным расширением.
ROM_SIZE = 0x8000


def _gb(size: int = ROM_SIZE) -> bytearray:
    blob = bytearray(size)
    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - blob[addr] - 1) & 0xFF
    blob[0x014D] = checksum
    total = sum(blob) & 0xFFFF
    blob[0x014E] = (total >> 8) & 0xFF
    blob[0x014F] = total & 0xFF
    return blob


def _gba(size: int = ROM_SIZE) -> bytearray:
    blob = bytearray(size)
    blob[0x0BD] = (0 - sum(blob[0x0A0:0x0BD]) - 0x19) & 0xFF
    return blob


def _args(rom, mode: str) -> argparse.Namespace:
    return build_parser().parse_args(["fixsum", rom, mode])


def test_check_valid_rom_returns_zero(tmp_path, capsys) -> None:
    rom = tmp_path / 'ok.gb'
    rom.write_bytes(bytes(_gb()))
    assert main(["fixsum", str(rom), "--check"]) == 0
    assert "ok" in capsys.readouterr().out


def test_check_broken_rom_returns_broken_code(tmp_path, capsys) -> None:
    """Код 3 = «сломан», а не 1 («упало»): это то, на что смотрит CI."""
    from api.cli import C_BROKEN_CHECKSUM

    rom = tmp_path / 'bad.gb'
    blob = _gb()
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert main(["fixsum", str(rom), "--check"]) == C_BROKEN_CHECKSUM
    out = capsys.readouterr().out
    assert "СЛОМАНО" in out
    assert "header_0x14D" in out


def test_fix_repairs_and_reports_true(tmp_path, capsys) -> None:
    rom = tmp_path / 'fix.gba'
    blob = _gba()
    blob[0x0BD] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert main(["fixsum", str(rom), "--fix"]) == 0
    out = capsys.readouterr().out
    assert "починено" in out
    assert rom.read_bytes()[0x0BD] == _gba()[0x0BD]


def test_fix_on_clean_rom_says_nothing_to_do(tmp_path, capsys) -> None:
    """`repair()` возвращает отчёт ПОСЛЕ, поэтому «чинить нечего» печаталось
    бы и на только что починенном файле — состояние ДО снимается отдельно."""
    rom = tmp_path / 'clean.gba'
    rom.write_bytes(bytes(_gba()))
    assert main(["fixsum", str(rom), "--fix"]) == 0
    assert "чинить нечего" in capsys.readouterr().out


def test_json_output_shape(tmp_path, capsys) -> None:
    import json

    rom = tmp_path / 'j.gb'
    rom.write_bytes(bytes(_gb()))
    assert main(["fixsum", str(rom), "--check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    data = payload["data"]
    assert data["system"] == "gb"
    assert data["valid"] is True
    assert data["repaired"] is False
    assert data["wrong_offsets"] == []


def test_json_fix_sets_repaired_flag(tmp_path, capsys) -> None:
    import json

    rom = tmp_path / 'jf.gba'
    blob = _gba()
    blob[0x0BD] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert main(["fixsum", str(rom), "--fix", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["data"]["repaired"] is True


def test_missing_rom_is_a_contract_error(tmp_path, capsys) -> None:
    assert main(["fixsum", str(tmp_path / "нет.gb"), "--check"]) == 1
    assert capsys.readouterr().err


def test_save_file_is_refused_and_untouched(tmp_path, capsys) -> None:
    """`.sav` не переписывается: без `resolve_rom` байт 0x14D затирал бы сейв.

    Защита ценная сама по себе, но особенно для `--fix`: команда РАЗРУШАЮЩАЯ,
    и агент с glob-ом по каталогу наверняка подставит ей не только ROM.
    """
    sav = tmp_path / "game.sav"
    payload = bytes(range(256)) * 4
    sav.write_bytes(payload)
    assert main(["fixsum", str(sav), "--fix"]) == 1
    assert "Ошибка" in capsys.readouterr().err
    assert sav.read_bytes() == payload


def test_non_rom_file_is_refused_and_untouched(tmp_path, capsys) -> None:
    notes = tmp_path / "notes.txt"
    payload = b"hello" * 1000
    notes.write_bytes(payload)
    assert main(["fixsum", str(notes), "--fix"]) == 1
    assert notes.read_bytes() == payload


def test_broken_checksum_uses_distinct_exit_code(tmp_path, capsys) -> None:
    """Код 3 ≠ 1: CI обязан отличить «ROM сломан» от «ошибка/нет доступа»."""
    from api.cli import C_BROKEN_CHECKSUM

    rom = tmp_path / "code.gb"
    blob = _gb()
    blob[0x014D] ^= 0xFF
    rom.write_bytes(bytes(blob))
    assert main(["fixsum", str(rom), "--check"]) == C_BROKEN_CHECKSUM
    assert C_BROKEN_CHECKSUM != 1


def test_mode_is_required() -> None:
    """Без --check/--fix команда не знает, что делать, и обязана сказать об
    этом через argparse (код 2), а не молча ничего не сделать."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["fixsum", "rom.gb"])
    assert excinfo.value.code == 2


def test_check_and_fix_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["fixsum", "rom.gb", "--check", "--fix"])
    assert excinfo.value.code == 2


def test_cmd_is_registered_in_help() -> None:
    text = build_parser().format_help()
    assert "fixsum" in text


def test_cmd_fixsum_direct_call(tmp_path) -> None:
    """Прямой вызов команды без main(): контракт возврата — тот же."""
    rom = tmp_path / 'direct.gb'
    rom.write_bytes(bytes(_gb()))
    assert _cmd_fixsum(_args(str(rom), "--check")) == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
