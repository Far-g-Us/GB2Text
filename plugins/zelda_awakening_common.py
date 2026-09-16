"""
GB Text Extraction Framework

COPYRIGHT WARNING:
This software tool is intended ONLY for the analysis of ROM files
lawfully owned by the user. Any use of this tool to
illegally copy, distribute, or modify copyrighted
material is strictly prohibited.

This project does NOT contain or distribute any ROM files or
copyrighted material. All ROM files must be
lawfully acquired by the user independently.

This tool is developed exclusively for research purposes,
education, and reverse engineering within the limits permitted by law.
"""

"""
Общий декодер текста The Legend of Zelda: Link's Awakening (GB) и
Link's Awakening DX (GBC).

Схема кодирования (одинакова для обеих версий, проверена на реальных ROM):
  - Обычный текст — прямой ASCII (0x20-0x7E), апостроф — байт 0x5E ('^').
  - 0xFF — терминатор записи (→ '[END]').
  - 0xFE — разделитель реплик внутри записи (→ '[NEXT]').
  - 0xF0-0xF3 — стрелки UP/DOWN/LEFT/RIGHT.
  - Прочие байты >= 0x80 — глифы/иконки → '[IC_XX]' (безопасный токен:
    НЕ форма '[XX]', поэтому _split_messages не разрывает запись).
  - Байты < 0x20 — контрольные коды → '[CTL_XX]'.

Инжектор должен резать записи ТОЛЬКО по 0xFF (terminators=[0xFF]):
паритет с экстрактором сохраняется, так как '[NEXT]' и '[IC_XX]' не
разрывают сообщения в _split_messages.

NOTE: This module contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

logger = logging.getLogger('gb2text.plugins.zelda_awakening_common')

ZELDA_TERMINATORS: list[int] = [0xFF]
ZELDA_PAD_BYTE = 0xFF

ZELDA_ARROWS: dict[int, str] = {
    0xF0: '[UP]',
    0xF1: '[DOWN]',
    0xF2: '[LEFT]',
    0xF3: '[RIGHT]',
}

_NAMED_TOKENS: dict[str, int] = {v: k for k, v in ZELDA_ARROWS.items()}


class ZeldaTextDecoder:
    """Decoder for Zelda LA / LA DX text.

    Decode: full byte range; 0xFF → '[END]' for _split_messages.
    Encode: reverses decode, skipping '[END]' (terminator is implicit).
    """

    def __init__(self):
        self.logger = logger

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = start + length
        for i in range(start, min(end, len(data))):
            byte = data[i]
            if byte == 0xFF:
                result.append('[END]')
            elif byte == 0xFE:
                result.append('[NEXT]')
            elif byte in ZELDA_ARROWS:
                result.append(ZELDA_ARROWS[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append("'" if byte == 0x5E else chr(byte))
            elif byte >= 0x80:
                result.append(f'[IC_{byte:02X}]')
            else:
                result.append(f'[CTL_{byte:02X}]')
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out: list[int] = []
        i = 0
        n = len(text)
        while i < n:
            if text.startswith('[END]', i):
                self.logger.warning(
                    "[END] token in translation is dropped: terminator 0xFF "
                    "is written by the injector, not part of the message text")
                i += 5
                continue
            if text.startswith('[NEXT]', i):
                out.append(0xFE)
                i += 6
                continue
            if text[i] == '[':
                parsed = self._match_bracketed_byte(text, i)
                if parsed is not None:
                    out.append(parsed)
                    i += 7
                    continue
                token = next((t for t in sorted(_NAMED_TOKENS, key=len,
                                                reverse=True)
                              if text.startswith(t, i)), None)
                if token is not None:
                    out.append(_NAMED_TOKENS[token])
                    i += len(token)
                    continue
            ch = text[i]
            code = ord(ch)
            if code == 0x27 or code == 0x5E:  # ' и ^ → байт-апостроф 0x5E
                if code == 0x5E:
                    self.logger.warning(
                        "Caret '^' mapped to apostrophe byte 0x5E "
                        "(LA charmap has no caret)")
                out.append(0x5E)
            elif 0x20 <= code <= 0x7E:
                out.append(code)
            else:
                self.logger.warning(
                    f"Symbol {ch!r} not supported in Zelda charmap, skipped")
            i += 1
        return bytes(out)

    @staticmethod
    def _match_bracketed_byte(text: str, i: int) -> int | None:
        """Разбирает '[IC_XX]' / '[CTL_XX]' → байт (XX — 2 hex-цифры)."""
        token = text[i + 1:i + 4] if i + 4 <= len(text) else ''
        if token not in ('IC_', 'CTL_'):
            return None
        hex_part = text[i + 4:i + 6]
        if len(hex_part) != 2 or not all(
                c in '0123456789ABCDEFabcdef' for c in hex_part):
            return None
        if i + 6 >= len(text) or text[i + 6] != ']':
            return None
        return int(hex_part, 16)
