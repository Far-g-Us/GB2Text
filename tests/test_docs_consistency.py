"""Unit tests for scripts/check_docs_consistency.py (pure functions)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_docs_consistency import (
    _check_legal_semantics,
    _file_slugs,
    _is_external,
    _resolve_anchor,
    _resolve_local,
    check_legal,
    check_links,
    check_routers,
    github_slug,
    main,
    split_link_target,
)

# --- github-slugger эталоны (сверены с живым GitHub-рендером + github-slugger) ---


def test_slug_english_emoji_headings() -> None:
    assert github_slug("⚠️ Legal Disclaimer") == "\ufe0f-legal-disclaimer"
    assert github_slug("🚀 Features") == "-features"
    assert github_slug("🧩 Community Plugins & Custom Fonts") == ("-community-plugins--custom-fonts")


def test_slug_russian_emoji_headings() -> None:
    assert github_slug("⚠️ Правовая оговорка") == "\ufe0f-правовая-оговорка"
    assert github_slug("🚀 Особенности") == "-особенности"
    assert github_slug("🧩 Плагины сообщества и пользовательские шрифты") == (
        "-плагины-сообщества-и-пользовательские-шрифты"
    )


def test_slug_plain() -> None:
    assert github_slug("Quick Start") == "quick-start"
    assert github_slug("README") == "readme"
    assert github_slug("A & B") == "a--b"


def test_slug_type_guard() -> None:
    assert github_slug(None) == ""
    assert github_slug(123) == ""
    assert github_slug(["x"]) == ""


def test_slug_no_nfc_side_effects() -> None:
    assert github_slug("Café") == "café"


def test_split_link_target() -> None:
    assert split_link_target("a/b.md#sec") == ("a/b.md", "sec")
    assert split_link_target("a/b.md") == ("a/b.md", None)
    assert split_link_target("#sec") == ("", "sec")


def test_is_external() -> None:
    assert _is_external("https://example.com/x")
    assert _is_external("mailto:a@b.c")
    assert not _is_external("docs/en/README.md")
    assert not _is_external("../README.md#sec")


def test_resolve_anchor_duplicates(tmp_path: Path) -> None:
    f = tmp_path / "dup.md"
    f.write_text(
        "# Features\n## Usage\n## Features\n",
        encoding="utf-8",
    )
    assert _resolve_anchor("features", f)
    assert _resolve_anchor("features-1", f)
    assert not _resolve_anchor("features-2", f)
    assert not _resolve_anchor("nope", f)


def test_check_routers_missing_link(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Router\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/index.md").write_text("# Index\n", encoding="utf-8")
    for lang in ("en", "ru"):
        d = tmp_path / "docs" / lang
        d.mkdir(parents=True)
        (d / "README.md").write_text(f"# {lang}\n", encoding="utf-8")
    problems = check_routers(tmp_path)
    assert any("не ссылается на download.md" in p or "does not reference" in p for p in problems)


def test_check_routers_ok(tmp_path: Path) -> None:
    for rel, body in [
        ("README.md", "[Download](docs/en/download.md)"),
        ("docs/index.md", "[Download](en/download.md)"),
        ("docs/en/README.md", "[Download](download.md)"),
        ("docs/ru/README.md", "[Download](download.md)"),
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    assert check_routers(tmp_path) == []


def test_check_legal_missing(tmp_path: Path) -> None:
    for rel in (
        "docs/en/README.md",
        "docs/ru/README.md",
        "docs/en/download.md",
        "docs/ru/download.md",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# empty\n", encoding="utf-8")
    problems = check_legal(tmp_path)
    assert any("legal" in p or "non-affiliation" in p for p in problems)


def test_check_legal_ok(tmp_path: Path) -> None:
    en = (
        "## Legal Disclaimer\n\n"
        "ROM files that you legally own.\n"
        "This project does NOT contain or distribute any commercial ROM files.\n"
    )
    ru = (
        "## Правовая оговорка\n\n"
        "ROM-файлами на законных основаниях.\n"
        "Этот проект не содержит и не распространяет какие-либо коммерческие файлы ROM.\n"
    )
    en_dl = en + "not affiliated with or endorsed by Nintendo.\n"
    ru_dl = ru + "не аффилирован с Nintendo и не одобрен ею.\n"
    for rel, body in [
        ("docs/en/README.md", en),
        ("docs/ru/README.md", ru),
        ("docs/en/download.md", en_dl),
        ("docs/ru/download.md", ru_dl),
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    assert check_legal(tmp_path) == []


def test_legal_semantics_blockquote_wrap() -> None:
    body = "> какие-либо коммерческие\n> файлы ROM.\n"
    assert _check_legal_semantics(body, "ru") == ["missing legal statement: own"]


def test_own_word_boundary() -> None:
    assert _check_legal_semantics("Download the tool from releases.", "en") == [
        "missing legal statement: own",
        "missing legal statement: no-commercial",
        "missing legal statement: no-commercial-short",
    ]
    assert _check_legal_semantics("ROM files that you legally own.", "en") == [
        "missing legal statement: no-commercial",
        "missing legal statement: no-commercial-short",
    ]


def test_anchor_only_validated(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("# Real\n\n[ok](#real)\n[bad](#missing)\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "current file" in problems[0]


def test_image_single_report(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("![alt](missing.png)\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "broken image" in problems[0]


def test_percent_encoded_hash(tmp_path: Path) -> None:
    (tmp_path / "file#name.md").write_text("# R\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("[x](file%23name.md)\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []
    ok, why = _resolve_local(tmp_path, tmp_path, "other%23name.md")
    assert not ok
    assert "missing target" in why


def test_anchor_suffix_zero_rejected(tmp_path: Path) -> None:
    f = tmp_path / "s.md"
    f.write_text("# Features\n## Features\n", encoding="utf-8")
    assert not _resolve_anchor("features-0", f)
    assert not _resolve_anchor("features-01", f)
    assert _resolve_anchor("features-1", f)


def test_cross_lang_pair_allowed(tmp_path: Path) -> None:
    _, why = _resolve_local(tmp_path, tmp_path, "en/ru/x.md")
    assert why == "missing target: en/ru/x.md"


def test_double_dir_still_banned(tmp_path: Path) -> None:
    ok, why = _resolve_local(tmp_path, tmp_path, "docs/en/en/x.md")
    assert not ok
    assert "double directory" in why


def test_dir_anchor_validated(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "README.md").write_text("# Sec\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("[ok](sub/#sec)\n[bad](sub/#nope)\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "#nope" in problems[0]


def test_drive_letter_not_external() -> None:
    assert not _is_external("C:/a/b.md")
    assert not _is_external("C:\\a\\b.md")
    assert _is_external("https://x.y/z")


def test_fenced_headings_ignored(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("```\n# fake\n```\n\n[x](#fake)\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1


def test_closing_hashes_stripped(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("## Foo ##\n\n[x](#foo)\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []


def test_ref_usage_undefined(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("[a][lbl]\n\n[lbl]: real.md\n", encoding="utf-8")
    (tmp_path / "real.md").write_text("# R\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []
    f.write_text("[a][nope]\n\n[lbl]: real.md\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "undefined reference" in problems[0]


def test_ref_image_undefined(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("![a][nope]\n\n[lbl]: real.md\n", encoding="utf-8")
    (tmp_path / "real.md").write_text("# R\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "undefined image reference" in problems[0]
    f.write_text("![a][lbl]\n\n[lbl]: real.md\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []


def test_slug_maintain_case() -> None:
    assert github_slug("ABC Def", maintain_case=True) == "ABC-Def"
    assert github_slug("ABC Def") == "abc-def"


def test_file_slugs_unreadable(tmp_path: Path) -> None:
    assert _file_slugs(tmp_path) == {}


def test_file_slugs_empty_slug_skipped(tmp_path: Path) -> None:
    f = tmp_path / "s.md"
    f.write_text("# !!!\n", encoding="utf-8")
    assert _file_slugs(f) == {}


def test_resolve_anchor_empty() -> None:
    assert _resolve_anchor("", None) is True


def test_resolve_external_ok(tmp_path: Path) -> None:
    ok, why = _resolve_local(tmp_path, tmp_path, "https://example.com/x")
    assert ok and why == ""


def test_resolve_traversal_blocked(tmp_path: Path) -> None:
    ok, why = _resolve_local(tmp_path, tmp_path, "../../outside.md")
    assert not ok
    assert "repository root" in why


def test_dir_anchor_second_index(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "index.md").write_text("# Sec\n", encoding="utf-8")
    ok, _ = _resolve_local(tmp_path, tmp_path, "sub/#sec")
    assert ok
    ok, why = _resolve_local(tmp_path, tmp_path, "sub/#nope")
    assert not ok and "#nope" in why


def test_dir_anchor_no_index(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    ok, why = _resolve_local(tmp_path, tmp_path, "sub/#sec")
    assert not ok and "no index" in why


def test_file_anchor_missing(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# Real\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("[x](other.md#nope)\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "anchor not found" in problems[0]


def test_check_links_exclusions(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("[x](missing.md)\n", encoding="utf-8")
    assert check_links(tmp_path, [f], exclusions=["a.md"]) == []
    assert len(check_links(tmp_path, [f])) == 1


def test_check_links_unreadable(tmp_path: Path) -> None:
    problems = check_links(tmp_path, [tmp_path])
    assert len(problems) == 1
    assert "unreadable" in problems[0]


def test_html_links_ok_and_broken(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# R\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text('<a href="other.md">x</a>\n<img src="other.md">\n', encoding="utf-8")
    assert check_links(tmp_path, [f]) == []
    f.write_text('<a href="missing.md">x</a>\n<img src="gone.png">\n', encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 2
    assert any("<a href>" in p for p in problems)
    assert any("<img src>" in p for p in problems)


def test_ref_def_broken_target(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("[a]: missing.md\n", encoding="utf-8")
    problems = check_links(tmp_path, [f])
    assert len(problems) == 1
    assert "broken reference" in problems[0]


def test_check_routers_missing_files(tmp_path: Path) -> None:
    problems = check_routers(tmp_path)
    assert len(problems) == 4
    assert all("MISSING" in p for p in problems)


def test_check_routers_unreadable(tmp_path: Path) -> None:
    (tmp_path / "README.md").mkdir()
    problems = check_routers(tmp_path)
    assert any("unreadable" in p for p in problems)


def test_check_legal_missing_files(tmp_path: Path) -> None:
    problems = check_legal(tmp_path)
    assert len(problems) == 4
    assert all("MISSING" in p for p in problems)


def test_check_legal_unreadable(tmp_path: Path) -> None:
    p = tmp_path / "docs" / "en" / "README.md"
    p.parent.mkdir(parents=True)
    p.mkdir()
    problems = check_legal(tmp_path)
    assert any("unreadable" in p for p in problems)


def test_main_all_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "README.md").write_text("[D](docs/en/download.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "index.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "index.md").write_text("[D](en/download.md)\n", encoding="utf-8")
    en_dl = (
        "ROM files that you legally own.\n"
        "This project does NOT contain or distribute any commercial ROM files.\n"
        "property of their respective owners.\n"
        "not affiliated with or endorsed by Nintendo.\n"
    )
    ru_dl = (
        "ROM-файлами на законных основаниях.\n"
        "Этот проект не содержит и не распространяет какие-либо коммерческие файлы ROM.\n"
        "собственностью их соответствующих владельцев.\n"
        "не аффилирован с Nintendo и не одобрен ею.\n"
    )
    for rel, body in [
        ("docs/en/README.md", "[D](download.md)\n" + en_dl),
        ("docs/ru/README.md", "[D](download.md)\n" + ru_dl),
        ("docs/en/download.md", "# Download\n\n" + en_dl),
        ("docs/ru/download.md", "# Download\n\n" + ru_dl),
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["--all"]) == 0
    assert main(["--all", "--quiet"]) == 0


def test_dir_no_anchor_ok(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    ok, _ = _resolve_local(tmp_path, tmp_path, "sub")
    assert ok


def test_file_link_no_anchor_ok(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# R\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("[x](other.md)\n![i](other.md)\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []


def test_file_link_valid_anchor(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# Real\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("[ok](other.md#real)\n", encoding="utf-8")
    assert check_links(tmp_path, [f]) == []


def test_main_links_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.md").write_text("[x](missing.md)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["--mode", "links"]) == 1
    assert main(["--mode", "links", "--quiet"]) == 1


def test_main_routers_legal_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--mode", "routers"]) == 1
    assert main(["--mode", "legal"]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
