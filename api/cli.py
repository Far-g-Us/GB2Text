"""CLI-интерфейс GB2Text для агентов: python -m api.cli <command> [--json].

Команды: plugins, detect, extract, inject, serve.
Коды выхода: 0 — ok, 1 — runtime/validation (contract-ошибка на stdout при --json),
2 — ошибка парсинга argparse. JSON-ответы только на stdout, utf-8.
"""

import argparse
import csv
import json
import logging
import sys

from api import _core
from api._core import SDKError, get_version

logger = logging.getLogger("gb2text.api.cli")


def _reconfigure_stdout():
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _emit(data, as_json: bool):
    if as_json:
        sys.stdout.write(json.dumps({"ok": True, "data": data}, ensure_ascii=False) + "\n")
    else:
        return data


def _fail(exc: SDKError, as_json: bool) -> int:
    if as_json:
        sys.stdout.write(
            json.dumps(
                {"ok": False, "error": {"code": exc.code, "message": exc.message}},
                ensure_ascii=False,
            )
            + "\n"
        )
    else:
        print(f"Ошибка ({exc.code}): {exc.message}", file=sys.stderr)
    return 1


def _print_plugins(data, as_json: bool):
    if as_json:
        _emit(data, True)
        return
    for p in data:
        kind = "config" if p["kind"] == "config" else "python"
        sig = " [hack]" if p["signature"] else ""
        print(f"{p['name']}: {p['game_id_pattern']} ({kind}){sig}")


def _print_extract_text(result, lang: str):
    for seg_name, messages in result["segments"].items():
        print(f"\n== {seg_name.upper()} ==")
        for msg in messages:
            print(f"0x{msg['offset']:04X}: {msg['text']}")


def _print_extract_csv(result, out_path=None):
    writer_holder = None if out_path is None else open(out_path, "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(sys.stdout if writer_holder is None else writer_holder)
        writer.writerow(["segment", "offset", "text"])
        for seg_name, messages in result["segments"].items():
            for msg in messages:
                writer.writerow([seg_name, msg["offset"], msg["text"]])
    finally:
        if writer_holder is not None:
            writer_holder.close()


def _cmd_plugins(args):
    data = _core.list_plugins(args.plugin_dir)
    _print_plugins(data, args.json)
    return 0


def _cmd_detect(args):
    data = _core.detect(args.rom, plugin_dir=args.plugin_dir)
    if args.json:
        _emit(data, True)
    else:
        print(f"game_id: {data['game_id']}")
        print(f"system:  {data['system']}")
        print(f"title:   {data['title']}")
        print(f"size:    {data['size']} bytes")
        print(f"plugin:  {data['plugin']}")
    return 0


def _cmd_extract(args):
    result = _core.extract(
        args.rom,
        plugin_dir=args.plugin_dir,
        max_segments=args.max_segments,
        language=args.lang,
    )
    if args.json:
        _emit(result, True)
        return 0
    if args.format == "json":
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif args.format == "csv":
        _print_extract_csv(result, args.output)
    else:
        _print_extract_text(result, args.lang)
    return 0


def _cmd_inject(args):
    translations = _core.load_json_file(args.translations)
    result = _core.inject(
        args.rom,
        translations,
        output_path=args.output_rom,
        plugin_dir=args.plugin_dir,
    )
    if args.json:
        _emit(result, True)
    else:
        print(f"Сохранено: {result['output_path']}")
        print(f"Checksum:  0x{result['checksum']:04X}")
        for seg_name, ok in result["segments"].items():
            status = "ok" if ok else "FAIL"
            print(f"  {seg_name}: {status}")
    return 0


def _cmd_serve(args):
    from api import serve

    serve(
        args.host,
        args.port,
        plugin_dir=args.plugin_dir,
        max_workers=args.max_workers,
        api_token=args.api_token,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="api.cli",
        description="GB2Text agent CLI. Версия " + get_version(),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plugins = sub.add_parser("plugins", help="Список плагинов")
    p_plugins.add_argument("--plugin-dir", default="plugins")
    p_plugins.add_argument("--json", action="store_true")
    p_plugins.set_defaults(func=_cmd_plugins)

    p_detect = sub.add_parser("detect", help="Определить игру/плагин для ROM")
    p_detect.add_argument("rom")
    p_detect.add_argument("--plugin-dir", default="plugins")
    p_detect.add_argument("--json", action="store_true")
    p_detect.set_defaults(func=_cmd_detect)

    p_extract = sub.add_parser("extract", help="Извлечь текст")
    p_extract.add_argument("rom")
    p_extract.add_argument("-o", "--output", help="Файл для csv (для text/json — stdout)")
    p_extract.add_argument("--format", default="text", choices=["text", "json", "csv"])
    p_extract.add_argument("--plugin-dir", default="plugins")
    p_extract.add_argument("--max-segments", type=int)
    p_extract.add_argument("--lang", default="en", choices=["en", "ru", "ja", "zh"])
    p_extract.add_argument("--json", action="store_true")
    p_extract.set_defaults(func=_cmd_extract)

    p_inject = sub.add_parser("inject", help="Внедрить переводы (формат main.py)")
    p_inject.add_argument("rom")
    p_inject.add_argument("--translations", required=True)
    p_inject.add_argument("--output-rom", help="Выходной ROM (по умолчанию *_translated рядом)")
    p_inject.add_argument("--plugin-dir", default="plugins")
    p_inject.add_argument("--json", action="store_true")
    p_inject.set_defaults(func=_cmd_inject)

    p_serve = sub.add_parser("serve", help="HTTP/JSON-сервис")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--plugin-dir", default="plugins")
    p_serve.add_argument("--max-workers", type=int, default=4)
    p_serve.add_argument(
        "--api-token",
        default=None,
        help="Bearer-токен для авторизации (приоритет у env GB2TEXT_API_TOKEN). "
             "Обязателен для non-loopback хоста.",
    )
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "json", False):
        _reconfigure_stdout()
    if getattr(args, "command", None) == "extract" and getattr(args, "json", False) and getattr(args, "format", None) == "json":
        parser.error("--json и --format json взаимоисключающие (первый оборачивает, второй — формат данных)")
    try:
        status = args.func(args)
        return status if isinstance(status, int) else 1
    except SDKError as exc:
        return _fail(exc, getattr(args, "json", False))
    except Exception as exc:
        logger.exception("Необработанная ошибка CLI")
        if getattr(args, "json", False):
            sys.stdout.write(
                json.dumps(
                    {"ok": False, "error": {"code": "INTERNAL", "message": "Внутренняя ошибка"}},
                    ensure_ascii=False,
                )
                + "\n"
            )
        else:
            print(f"Ошибка (INTERNAL): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
