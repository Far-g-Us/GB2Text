# Supported Games

Games with text extraction support.

## Status Legend
- ✅ Full — Читаемый текст на реальном ROM
- ⚠️ Partial — Часть текста извлекается, часть garbled
- 🔧 Stub — Плагин есть, не работает (charmap/pointer table неизвестны)
- ❌ Broken — Плагин есть, но результат garbled

## GBA Games — Working / Partial

| Game | Game ID | Plugin | Status | Notes |
|------|---------|--------|--------|-------|
| Mario & Luigi: Superstar Saga | A88E | gba_mario_luigi_ss | ✅ Full | ASCII, все сегменты читаемы |
| Final Fantasy Tactics Advance | AFXE | gba_fft_advance | ✅ Full | Multi-byte 0x8X XX, LZSS, 4 таблицы, CRN |
| Legend of Zelda: The Minish Cap | BZME | gba_zelda_tmc | ✅ Full | Tile-based ASCII, 2 hardcoded блока (intro + NPC dialogue) |
| Wario Land 4 | AWAE | gba_wario_land_4 | ✅ Full | 1585 записей, DataCrystal TBL |
| Astro Boy: Omega Factor | BTAE | gba_astro_boy | ✅ Full | Caesar cipher -1 |
| Final Fantasy V Advance | BZ5E | gba_ff5_advance | ✅ Full | Pointer table @ 0x36DD64, 8495 entries |
| Final Fantasy IV Advance | BZ4E | gba_ff4_advance | ✅ Full | Complete TBL: 0x00-0x7F single-byte + 0xC2XX-0xD6XX multi-byte kanji |
| Sonic Advance | ASOE | gba_sonic_advance | ✅ Full | ASCII, credits + zone names |
| Kingdom Hearts: Chain of Memories | B8CE | gba_kingdom_hearts_com | ✅ Full | ASCII + control codes |
| Phoenix Wright: Ace Attorney | ASBJ | gba_phoenix_wright | ✅ Full | Fan-translated ROM, ASCII |
| Mega Man Battle Network | AREP | gba_megaman_battle_network | ✅ Full | ASCII subset, control codes |
| Metroid Fusion | AMTE | gba_metroid_fusion | ⚠️ Partial | Только credits (4 hardcoded блока), диалоги не найдены |
| FF1&2: Dawn of Souls | BZSE | gba_ff12_dawn_of_souls | 🔧 Stub | TBL provided, pointer table location unknown |

## GBA Games — Broken / Stub

| Game | Game ID | Plugin | Status | Problem |
|------|---------|--------|--------|---------|
| Pokemon Emerald | BPEE | gba_pokemon | ⚠️ Partial | LZ77 decompression + charmap working. Item names readable (PROTEIN, REVIVE, STARDUST etc). Pointer table extraction not yet implemented |
| Pokemon Ruby | AXRE | gba_pokemon | ⚠️ Partial | Same as Emerald |
| Pokemon Sapphire | AXVE | gba_pokemon | ⚠️ Partial | Same as Emerald |
| Castlevania: Aria of Sorrow | A2CE | gba_castlevania | ✅ Full | 6543 strings (EN/FR/DE). Pointer-based extraction, ASCII + control codes |
| FF VI Advance | BZ6E | gba_ff6_advance | 🔧 Stub | 0 сегментов, нет pointer table |
| Fire Emblem (Europe) | AE7Y | gba_fire_emblem | 🔧 Stub | Huffman tree не реализован (USA адреса известны, EU — нет) |
| Fire Emblem: Sacred Stones | BE8P | gba_fire_emblem | 🔧 Stub | Huffman tree не реализован |
| Castlevania: Circle of the Moon | AAME | gba_castlevania_ctm | 🔧 Stub | 0 сегментов, charmap неизвестен |
| Castlevania: Harmony of Dissonance | ACHP | gba_castlevania_hod | 🔧 Stub | 0 сегментов, charmap неизвестен |
| Mega Man Battle Network | AREP | gba_megaman_battle_network | 🔧 Stub | 0 сегментов |

## GBA Games — Stub Plugins (charmap needed)

| Game | Game ID | Plugin | Known Info |
|------|---------|--------|------------|
| Golden Sun | AGSE | gba_golden_sun | ⚠️ Staff credits (ASCII) extracted. Dialogue uses custom encoding — charmap needed |
| Golden Sun: The Lost Age | AGFE | gba_golden_sun_tla | Same engine as GS1 |
| Advance Wars | AWRE | gba_advance_wars | ASCII, menu-heavy |
| Mega Man Battle Network 2 | AM2P | gba_megaman_battle_network_2 | Same engine as MMBN1 |
| Mega Man Zero | AZCE | gba_megaman_zero | Custom encoding, ASCII subset |
| Shining Force | AF5E | gba_shining_force | ASCII, RPG text |
| CT Special Forces | AC7E | gba_ct_special_forces | ASCII |
| Custom Robo GX | ARJJ | gba_custom_robo_gx | Japanese-only, custom encoding |
| Metroid Zero Mission | BMXE | gba_metroid_zero_mission | Custom encoding (similar to Fusion but different offsets). TBL needed |
| Castlevania: Aria of Sorrow | A2CE | gba_castlevania | Pointer table not found |
| FF VI Advance | BZ6E | gba_ff6_advance | Pointer table not found |

## FFTA String Tables (DataCrystal, verified)

| Table | Pointer Table Offset | Text Start | Entries |
|-------|---------------------|------------|---------|
| Universal | 0x005567F0 | 0x005541B4 | 767 |
| Item/Location Names | 0x00526680 | 0x0052336C | 753 |
| Mission Names | 0x0055A64C | 0x00558008 | 512 |
| Random Names | 0x005680DC | 0x00566A00 | 725 |

## Summary

| Status | Count | Games |
|--------|-------|-------|
| ✅ Full | 13 | Mario&Luigi, FFTA, Zelda TMC, Wario Land 4, Astro Boy, FF5 Advance, FF4 Advance, Sonic Advance, KH:CoM, Phoenix Wright, MMBN, Castlevania AoS, Pokemon (partial) |
| ⚠️ Partial | 4 | Metroid Fusion, Pokemon Ruby, Pokemon Sapphire, Golden Sun |
| ❌ Broken | 0 | — |
| 🔧 Stub (old) | 3 | FF6 Advance, Fire Emblem ×2 |
| 🔧 Stub (new) | 9 | Advance Wars, MMBN2, Mega Man Zero, CT Special Forces, Custom Robo GX, Metroid ZM, FF1&2 Dawn of Souls, Castlevania CotM/HoD |

## How to Add a Game

1. Create `plugins/gba_<game_name>.py`
2. Implement `GamePlugin` with `game_id_pattern` + `get_text_segments(rom)`
3. Add verified charmap (DataCrystal / decomp / manual RE)
4. Test on real ROM — output must be readable English
5. Update this file

## Sources

- **Decomp projects**: Pret (Pokemon), zeldaret (Zelda TMC)
- **DataCrystal**: https://datacrystal.tcrf.net/
- **FF5 Hacking Wiki**: https://www.ff6hacking.com/ff5wiki/
- **FF6AE source**: https://github.com/fred65816/FF6AE
- **References**: `references/` directory
