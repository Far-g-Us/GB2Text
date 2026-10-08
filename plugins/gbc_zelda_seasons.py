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
Plugin for The Legend of Zelda: Oracle of Seasons (GBC, US).

game_id: GBC_ZELDADINAZ7E (header title "ZELDA DIN AZ7E", platform GBC)

Extraction: full ~2800 null-terminated records across a text pool
(0x73382-0x84DDF), using a mini-dictionary (4 groups, 0-3) with
two-byte refs (0x02-0x05), bracket-style control tokens ([STOP],
[COL], [SPEED], etc.), and literal Unicode for accented Latin and
kanji characters.

Injection: verbatim copy of original bytes when the translation is unchanged
(byte-exact round-trip) and dictionary recompression (greedy longest-match over
the 1024-slot mini-dictionary) for new text records; translations that exceed
their free_after window are skipped (skip_long=True). Extraction-complete
with full round-trip support.

The dictionary segment `oracle_seasons_dict` is extract-only
(`injectable: False`): every one of its 1024 slots is cited by text records,
so writing it would change text that was not translated at all.

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.zelda_oracle_common import OracleTextDecoder

logger = logging.getLogger('gb2text.plugins.oracle_of_seasons')

US_GAME_ID = r'^GBC_ZELDADINAZ7E$'


class OracleOfSeasonsPlugin(GamePlugin):
    """Plugin for The Legend of Zelda: Oracle of Seasons (GBC) - US.

    Full extraction + injection: verbatim byte-copy for unchanged strings,
    greedy dictionary recompression for new translations.
    """

    @property
    def game_id_pattern(self) -> str:
        return US_GAME_ID

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        if len(rom.data) < 0x100000:
            logger.info("Oracle of Seasons: ROM too small (%d bytes), "
                        "returning empty", len(rom.data))
            return []
        decoder = OracleTextDecoder()
        # build_manifest объявлен на bytes, а rom.data — bytearray.
        manifest = decoder.build_manifest(bytes(rom.data))
        if not manifest:
            return []
        # Записи делятся на словарные (index < 0x400) и обычные, и пишутся
        # в этом порядке: словарь первым, потому что обычные записи сжимаются
        # против его ТЕКУЩЕГО содержимого (инжектор передаёт modified_data).
        #
        # Словарные кодируются ТОЛЬКО литералом: если сжать их через словарь,
        # перевод создаёт цикл A->B->A, _decompress его отвергает, и записи
        # выпадают из манифеста вместе с зависимыми.
        #
        # Цена решения: обычная запись хранит свой текст через ссылки на
        # словарь, поэтому перевод словаря неизбежно меняет и все записи, что
        # на него ссылаются. Это свойство формата, а не инструмента.
        dict_entries = [e for e in manifest
                        if isinstance(e.get('index'), int) and e['index'] < 0x400]
        dict_ids = {id(e) for e in dict_entries}
        text_entries = [e for e in manifest if id(e) not in dict_ids]

        def _segment(name: str, entries: list[dict], encoder,
                     limit: int | None = None) -> dict:
            end = entries[-1]['target'] + entries[-1]['free_after']
            if limit is not None:
                # Граница задана явно, а не выведена из последней записи:
                # если в хвосте словаря что-то отбросится, `end` отступит
                # на несколько байт, и следующий сегмент посчитал бы чужие
                # байты своими.
                end = min(end, limit)
            return {
                'name': name,
                'kind': 'pointer_dialogues',
                'start': entries[0]['target'],
                'end': end,
                'decoder': decoder,
                'pointer_encoder': encoder,
                'compression': None,
                'terminator': b'\x00',
                'terminators': [0x00],
                'manifest': entries,
                'max_decode_len': 65536,
                # Окно записи = сама запись, хвост после терминатора —
                # padding: без затирания старый текст продолжает новую
                # запись и в игре видны обрывки исходника.
                'tail_pad': True,
                'pad_byte': 0x00,
            }

        segments: list[dict] = []
        if dict_entries:
            seg = _segment('oracle_seasons_dict', dict_entries,
                           decoder.encode_literal,
                           limit=text_entries[0]['target']
                           if text_entries else None)
            # Словарь extract-only. Общий словаря Oracle цитируется
            # всеми текстовыми записями: значение 0x02..0x05
            # занимает два байта и адресует слот
            # ((b - 2) << 8) | next, то есть слоты 0..1023. Замер на текущем
            # ROM: цитируются все 1024 слота, ссылаются на них 1765 из 1794
            # текстовых записей, плюс 17 вложенных ссылок между
            # самими слотами словаря.
            #
            # Поэтому сокращение любого слота меняет
            # текст всех записей, которые на него ссылаются,
            # и перевод которого слота портит текст
            # всех записей слова. Развёртывать ссылки
            # (copy-on-write) — отдельная задача.
            seg['injectable'] = False
            seg['not_writable_reason'] = 'shared_dictionary'
            segments.append(seg)
        if text_entries:
            # Текстовые записи сжаты: собираются декодером, поэтому
            # собранная строка длиннее исходной, и поместить её в
            # исходное окно невозможно. Перевод этих записей ведётся
            # обычным путём в `core/injector.py::_inject_pointer_dialogues`.
            tseg = _segment('oracle_seasons', text_entries,
                            decoder.encode_compressed)
            segments.append(tseg)
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]
