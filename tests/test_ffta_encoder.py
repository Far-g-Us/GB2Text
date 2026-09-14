"""Юнит-тесты кодировщика FFTA (plugins/gba_fft_advance.py, Фаза C)

encode() обратен _decode_ffta_text. Проверяется согласованность режимов
(однобайтовый 0x01 / многобайтовый 0x80XX/0x40 XX), спец-токенов и
отвержение неустранимых маркеров. Интеграционный round-trip по всем
сегментам USA ROM — в test_ffta_dialogue.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from plugins.gba_fft_advance import FFTATextDecoder


@pytest.fixture(scope="module")
def decoder() -> FFTATextDecoder:
    return FFTATextDecoder()


def _decode(decoder: FFTATextDecoder, data: bytes) -> str:
    return decoder.decode(data, 0, len(data))


class TestEncodeASCII:
    def test_pure_ascii_uses_single_byte_mode(self, decoder):
        enc = decoder.encode("ABC")
        assert enc[0] == 0x01
        assert _decode(decoder, enc) == "ABC"

    def test_single_byte_offsets_match_decoder(self, decoder):
        # В single-режиме байт X декодируется как 0x8000 | (X - 1)
        enc = decoder.encode("A")  # A = 0x80B0 -> байт 0xB1
        assert enc == b"\x01\xB1"
        assert _decode(decoder, enc) == "A"

    def test_space_is_single_ctrl_byte(self, decoder):
        # Пробел = 0x73 (control) — одиночным байтом в single-режиме
        enc = decoder.encode("A B")
        assert enc == b"\x01\xB1\x73\xB2"
        assert _decode(decoder, enc) == "A B"

    def test_digit_in_single_mode(self, decoder):
        enc = decoder.encode("7")
        assert enc[0] == 0x01
        assert _decode(decoder, enc) == "7"

    def test_karakan_trapped_in_multi_mode(self, decoder):
        # Катакана 0x807F..0x808E: single-байт попал бы в диапазон
        # префиксов 0x80..0x8F — обязан быть multi
        for ch in "ハバマ":
            enc = decoder.encode(ch)
            assert enc[0] == 0x80, f"{ch}: expected multi, got {enc.hex()}"
            assert _decode(decoder, enc) == ch

    def test_0x80ff_code_forced_multi(self, decoder):
        # 0x80FF ('±'): второй байт 0xFF вне 0x8F..0xFE — одиночный байт 0x100 не помещается
        enc = decoder.encode("±")
        assert enc[0] == 0x80
        assert _decode(decoder, enc) == "±"

    def test_literal_braces_in_single_mode(self, decoder):
        # '{' = 0x80F9, '}' = 0x80FA — литеральные скобки (второй байт 0xF9/0xFA
        # в безопасном single-диапазоне), НЕ ссылка на имя
        enc = decoder.encode("{x}")
        assert enc[0] == 0x01
        assert b"\x40\x25" not in enc
        assert _decode(decoder, enc) == "{x}"


class TestEncodeControl:
    def test_named_ctrl_in_single_mode(self, decoder):
        # Именованные токены — одиночными ctrl-байтами в single-режиме
        enc = decoder.encode("[NEWLINE]")
        assert enc == b"\x01\x6E"
        assert _decode(decoder, enc) == "[NEWLINE]"

    def test_newline_in_single_mode_after_ascii(self, decoder):
        enc = decoder.encode("A[NEWLINE]B")
        assert enc == b"\x01\xB1\x6E\xB2"
        assert _decode(decoder, enc) == "A[NEWLINE]B"

    def test_delay_token(self, decoder):
        enc = decoder.encode("[DELAY:12]x")
        assert b"\x40\x74\x0C" in enc
        assert _decode(decoder, enc) == "[DELAY:12]x"

    def test_space_w_token(self, decoder):
        enc = decoder.encode("[SPACE_W:34]x")
        assert b"\x40\x3E\x22" in enc
        assert _decode(decoder, enc) == "[SPACE_W:34]x"

    def test_choice_token_drops_params(self, decoder):
        enc = decoder.encode("[CHOICE]")
        assert enc == b"\x40\x53\x00\x00"

    def test_choice_with_surrounding_text(self, decoder):
        text = "Buy?[CHOICE]No"
        enc = decoder.encode(text)
        assert b"\x40\x53\x00\x00" in enc
        assert _decode(decoder, enc) == text

    def test_raw_plain_hex_marker(self, decoder):
        enc = decoder.encode("[40_07]")
        assert enc == b"\x40\x07"
        assert _decode(decoder, enc) == "[40_07]"

    @pytest.mark.parametrize("marker,expected", [
        ("[40_00]", b"\x40\x00"),
        ("[40_01]", b"\x40\x01"),
        ("[40_40]", b"\x40\x40"),  # ctrl 0x40 форсит multi, но raw-маркер допустим
    ])
    def test_raw_permitted_hex_markers(self, decoder, marker, expected):
        enc = decoder.encode(marker)
        assert enc == expected
        assert _decode(decoder, enc) == marker

    def test_raw_named_fail(self, decoder):
        # '[40_6E]' декодером не производится ([NEWLINE]) — отвергается
        with pytest.raises(ValueError):
            decoder.encode("[40_6E]")

    @pytest.mark.parametrize("marker", [
        "[40_25]",  # имя персонажа
        "[40_3E]",  # ширина пробела
        "[40_53]",  # выбор
        "[40_72]",  # поиск CRN
        "[40_74]",  # задержка
        "[40_73]",  # space
        "[40_61]",  # [WAIT]
    ])
    def test_raw_special_or_named_fail(self, decoder, marker):
        with pytest.raises(ValueError):
            decoder.encode(marker)

    def test_raw_terminator_fail(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("a[00]b")

    def test_raw_mode_prefix_fail(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("a[01]b")

    def test_raw_multi_prefix_fail(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("a[80]b")
        with pytest.raises(ValueError):
            decoder.encode("a[8F]b")

    def test_raw_lone_40_fail(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("[40]")

    def test_delay_overflow_fail(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("[DELAY:256]")


class TestEncodeNames:
    def test_char_name_ref(self, decoder):
        enc = decoder.encode("{Marche}")
        assert enc == b"\x40\x25\x00"
        assert _decode(decoder, enc) == "{Marche}"

    def test_char_name_second_priority(self, decoder):
        enc = decoder.encode("{Ritz}")
        assert enc == b"\x40\x25\x02"
        assert _decode(decoder, enc) == "{Ritz}"

    def test_unknown_char_name_ref(self, decoder):
        enc = decoder.encode("{[3C]}")
        assert enc == b"\x40\x25\x3C"
        assert _decode(decoder, enc) == "{[3C]}"

    def test_crn_name_ref(self, decoder):
        enc = decoder.encode("{Ramza}")
        assert enc == b"\x40\x72\x02"
        assert _decode(decoder, enc) == "{Ramza}"

    def test_unknown_crn_name_ref(self, decoder):
        # CRN-индексы резолвятся в имена (таблица покрывает 0x00-0xFF),
        # поэтому {CRN_XX} — это ручной ввод индекса: байты пишутся,
        # а декодер вернёт имя по индексу
        enc = decoder.encode("{CRN_F0}")
        assert enc == b"\x40\x72\xF0"
        assert _decode(decoder, enc) == "{Quake}"

    def test_char_name_wins_over_crn(self, decoder):
        # Приоритет имён: CHAR_NAMES раньше CRN_NAMES
        enc = decoder.encode("{Cid}")  # Cid есть в CHAR_NAMES (0x06)
        assert enc == b"\x40\x25\x06"

    def test_known_crn_index_ref(self, decoder):
        # {CRN_30} = известный индекс (Chocobo) — байты пишутся, декодер
        # вернёт имя по индексу
        enc = decoder.encode("{CRN_30}")
        assert enc == b"\x40\x72\x30"
        assert _decode(decoder, enc) == "{Chocobo}"

    def test_multi_char_literal_braces(self, decoder):
        # Многосимвольная вставка в фигурных скобках с литеральными скобками
        enc = decoder.encode("{xy}")
        assert b"\x40\x25" not in enc and b"\x40\x72" not in enc
        assert _decode(decoder, enc) == "{xy}"

    def test_force_multi_always_multi(self, decoder):
        # force_multi=True подавляет single-префикс даже для single-текста
        enc = decoder.encode("A", force_multi=True)
        assert enc == b"\x80\xB0"
        assert not enc.startswith(b"\x01")
        assert _decode(decoder, enc) == "A"
        enc2 = decoder.encode("A B", force_multi=True)
        assert enc2 == b"\x80\xB0\x40\x73\x80\xB1"
        assert not enc2.startswith(b"\x01")

    def test_force_multi_dialogue_format(self, decoder):
        # Диалог в оригинале multi (без 0x01) — force_multi сохраняет формат
        enc = decoder.encode("[WAIT]A[NEWLINE]", force_multi=True)
        assert enc == b"\x40\x61\x80\xB0\x40\x6E"
        assert not enc.startswith(b"\x01")
        assert _decode(decoder, enc) == "[WAIT]A[NEWLINE]"

    def test_single_char_space_via_ctrl(self, decoder):
        enc = decoder.encode(" ")
        assert enc == b"\x01\x73"
        assert _decode(decoder, enc) == " "


class TestEncodeErrors:
    def test_unknown_character(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("Й")

    def test_unknown_named_token(self, decoder):
        with pytest.raises(ValueError):
            decoder.encode("[BOGUS]")

    def test_empty_string(self, decoder):
        # Пустой текст -> голый префикс single-режима (без данных)
        assert decoder.encode("") == b"\x01"


class TestEncodeDecodeRoundtrip:
    @pytest.mark.parametrize("text", [
        "Hello, World!",
        "You can't ssell[NEWLINE]itemss that are[NEWLINE]equipped, sson.[WAIT][CLEAR]",
        "Leave me 3,000 gil[NEWLINE]and I'll give you[NEWLINE]a break.[40_77][CLEAR]",
        "[CHOICE]",
        "Line1[NEXT_PAGE][CLEAR]Line2[WAIT][CLEAR]",
        "{Marche} says hi to {Ramza}",
        "ハバマ ABC 123",
        "[DELAY:5][SPACE_W:2]x",
        "{x} ± 7 : ~ '(quote)",
    ])
    def test_roundtrip(self, decoder, text):
        enc = decoder.encode(text)
        assert _decode(decoder, enc) == text
