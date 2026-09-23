import pytest

from core.i18n import language_code
from core.injector import TextInjector
from core.machine_translation import DeepLTranslator, MachineTranslation
from core.rom_cache import ROMCache
from core.translation_validator import (
    BatchTranslationValidator,
    TranslationValidator,
    ValidationError,
    ValidationLevel,
    ValidationResult,
)


def test_language_code_empty():
    assert language_code("") == "en"


def test_language_code_unknown():
    assert language_code("Klingon") == "klingon"


def test_inject_fit_report_failure(api_rom_file, monkeypatch):
    def _boom(segment, translations):
        raise RuntimeError("fit failed")

    monkeypatch.setattr("core.textbox.fit_report", _boom)
    injector = TextInjector(api_rom_file)
    assert injector.inject_segment("seg", ["hi"], object(), segments=[{"name": "seg"}]) is False
    assert injector.last_fit_report == []


class _RaisingDeepL:
    def get_usage(self):
        return type("Usage", (), {"any_limit_reached": False})()

    def translate_text(self, text, source_lang=None, target_lang=None):
        raise RuntimeError("deepl down")


def test_deepl_translate_error():
    translator = DeepLTranslator("key")
    translator.translator = _RaisingDeepL()
    with pytest.raises(RuntimeError):
        translator.translate("hi", "en", "ru")


class _FakeService:
    def is_available(self):
        return True

    def translate(self, text, source_lang, target_lang):
        return "ok"


class _DeadService:
    def is_available(self):
        return False


def test_fallback_no_current_service():
    manager = MachineTranslation()
    manager.translators = {"google": _FakeService(), "bing": _DeadService()}
    assert manager.translate_with_fallback("hi", "en", "ru") == "ok"


def test_evict_oldest_empty():
    ROMCache()._evict_oldest()


def test_invalidate_missing():
    ROMCache().invalidate("nope")


def test_evict_oldest_falsy_key_kept():
    cache = ROMCache()
    cache._cache = {"": (object(), "h", 1.0)}
    cache._evict_oldest()
    assert list(cache._cache) == [""]


def test_length_warning_zone():
    report = TranslationValidator(max_length=100)._validate_length("x" * 95)
    assert report.is_valid is True
    assert len(report.warnings) == 1


def test_pointers_match_logged():
    report = TranslationValidator()._validate_pointers("see [1A2B] now")
    assert report.is_valid is True


def test_glyphs_early_valid():
    report = TranslationValidator()._validate_glyphs("abc")
    assert report.is_valid is True
    assert report.errors == []


def test_summary_with_error_levels():
    bad = ValidationResult(
        is_valid=False,
        errors=[ValidationError(ValidationLevel.CRITICAL, "boom")],
        warnings=[],
        max_length=100,
        original_length=3,
        translated_length=3,
    )
    good = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        max_length=100,
        original_length=3,
        translated_length=3,
    )
    summary = BatchTranslationValidator().get_summary({"a": bad, "b": good})
    assert "1" in summary.split("Невалидных")[1]
    assert "critical" in summary
    assert "Ошибки по уровням" not in BatchTranslationValidator().get_summary({"b": good})
