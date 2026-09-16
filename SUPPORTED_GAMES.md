# Supported Games

All ROMs present in `test_roms/`, grouped by platform. The Region column shows
the ROM revisions used to verify each plugin. Games without a dedicated plugin
are listed with status "—".

## Status Legend
- ✅ Full — readable text on a real ROM
- ⚠️ Partial — part of the text extracts, some is garbled
- 🔧 Stub — plugin exists, not working yet (charmap/pointer table unknown)
- ❌ Broken — plugin exists, but output is garbled
- — No plugin — ROM present in `test_roms/`, but no dedicated plugin yet
  (only the generic GB/GBC plugins, which need a manual config)

## GBA Games — Working / Partial

| Game | Game ID | Region | Plugin | Status | Notes |
|------|---------|--------|--------|--------|-------|
| Mario & Luigi: Superstar Saga | A88E | USA | gba_mario_luigi_ss | ✅ Full | Table-based extraction + insertion: master pointer table @ 0x4EB000, 1024 entries × 5 languages (DE/FR/ES/EN/IT, slot-interleaved idx*5+slot), exact byte boundaries of self-terminating records (FF tokens, special glyphs, inline button icons 0x18/0x19/0x1E/0x1F). Per-record insertion: in-place when it fits, otherwise relocation into a free 0x00-run with a patch to its own slot only; catalog entries (e888/e1023) skipped verbatim; ROM expansion fallback. Other revisions (BTEJ/BTEP) not verified |
| Final Fantasy Tactics Advance | AFXE | USA | gba_fft_advance | ✅ Full | Multi-byte 0x8X XX (+ single-byte with 0x01 prefix), LZSS dialogues (marker 0x32, 1787 lines), 4 pointer tables, CRN; extraction + insertion: dialogues recompressed into the original LZSS window (skip_long on overflow), tables/CRN in-place. Dialogues always encoded with encode(force_multi=True) on insert: original LZSS blocks do not use the single-prefix 0x01, so the format is preserved |
| Legend of Zelda: The Minish Cap | BZME | USA | gba_zelda_tmc | ✅ Full | Text stored in "banks" (u32 offsets table + records terminated by 0x00; 0xFF is a control-code parameter/menu separator, not a terminator). Extraction of all banks: TMCTextDecoder with control codes (01:2 02:1 03:2 04:2 05:2 06:1 07:2 08:1 0C:1 0F:1) and [END]/[LINEBREAK]/[TAB]/[CC PP]/[MENUSEP]/[UNK] grammar. Per-record in-bank insertion: in-place when it fits, otherwise relocation into a free 0xFF-run within the bank zone (dest-base ≤ 0x4000), patching only its own table slot; 17 records with external references are protected from relocation; byte-identical round-trip (decode→encode == original) across all 70 banks, full extract→inject pipeline is identity, relocation is idempotent and re-scannable. Records with external references are skipped verbatim. Not verified on emulator/hardware |
| Final Fantasy V Advance | BZ5E | USA | gba_ff5_advance | ✅ Full | Pointer table @ 0x36DD64, 24036 entries; 0x4000 segment limit + filter (drops records with 2+ hex tokens and with <30% clean text) removes garbage pointers into data/padding — dialogues fully readable. Insertion: encoder supports single/multi-byte chrmap, control codes (PIC/PAUSE/LINEBREAK etc.) and hex tokens; round-trip across all 6594 segments |
| Final Fantasy IV Advance | BZ4E | USA | gba_ff4_advance | ✅ Full | Complete TBL: 0x00-0x7F single-byte + 0xC2XX-0xD6XX multi-byte kanji; pointer base 0x2E3670 (fixes the 0x624C shift that truncated lines mid-word); filter removes single glyphs from the charmap catalog and empty records; dialogues/menus intact. Insertion: encoder (single/multi-byte chrmap + control codes NAME/PIC/LINEBREAK + hex tokens), byte-identical round-trip across all 4744 segments |
| Golden Sun | AGSE | USA/Europe | gba_golden_sun | ✅ Full | Contextual Huffman (256 trees), 10,722 lines in 42 files + ASCII credits. Extraction and insertion (recompression with the game's trees; long translations are skipped) |
| Castlevania: Aria of Sorrow | A2CE | USA | gba_castlevania | ✅ Full | Pointer-based table extraction: table @ 0x506B38, 2895 records (en_ui 40 / en 973 / fr 1103 / de 779), exact byte boundaries, control codes and page breaks ([PAGEBREAK]) preserved. Insertion at the language-block level (encode + record repacking; in-place when it fits, otherwise relocation into a free 0x00-run with target patching; GBA header checksum is not recalculated). Story dialogues are covered by the table (verified). Open: AGBE/AGBJ not verified |
| Metroid Fusion | AMTE | USA | gba_metroid_fusion | ✅ Full | 1239 dialogue lines via pointer tables, 4 ASCII blocks (credits/save) via MetroidFusionAsciiDecoder; byte-identical round-trip verified |
| Wario Land 4 | AWAE | USA/Europe | gba_wario_land_4 | ✅ Full | 80 known locations (passages, levels, diary, music, shops — 6×Mini-Game Shop) with EN-only windows; charmap: 0x00-0x3F digits/upper/lower + 0xE1-0xF2 punctuation + 0xFF space; multi-language records trimmed to EN run; round-trip inject→re-extract verified. DataCrystal TBL has 15 additional romaji music-track names at 0x6D310E-0x6D3378 (JP-only, unstable record boundaries 1-15 FF, trailing binary in charmap range — excluded). 3 TBL offsets corrected against real ROM. |
| Pokemon Emerald | BPEE | USA/Europe | gba_pokemon | ✅ Full | Fixed-width tables (names 412×11b, attacks 355×13b, abilities 78×13b, types 18×7b) + pointer-based dialogues (address-only manifest, 2089 dialogue targets); byte-level slot extraction, round-trip extract→inject→extract verified on real ROM; in-place dialogue injection with overflow report |
| Pokemon Ruby | AXVE | USA | gba_pokemon | ✅ Full | Fixed-width tables (names 412×11b, attacks 355×13b, abilities 78×13b, types 18×7b) + pointer-based dialogues (address-only manifest, 1262 dialogue targets); round-trip verified on real ROM; in-place dialogue injection with overflow report |
| Pokemon Sapphire | AXPE | USA | gba_pokemon | ✅ Full | Fixed-width tables (names 412×11b, attacks 355×13b, abilities 78×13b, types 18×7b) + pointer-based dialogues (address-only manifest, 1264 dialogue targets); round-trip verified on real ROM; in-place dialogue injection with overflow report |
| Pokemon FireRed | BPRE | USA | gba_pokemon | ✅ Full | Fixed-width tables (names 412×11b, attacks 355×13b, abilities 78×13b, types 18×7b) + pointer-based dialogues (address-only manifest, 1289 dialogue targets); round-trip verified on real ROM; in-place dialogue injection with overflow report |
| Pokemon LeafGreen | BPGE | USA | gba_pokemon | ✅ Full | Fixed-width tables (names 412×11b, attacks 355×13b, abilities 78×13b, types 18×7b) + pointer-based dialogues (address-only manifest, 1292 dialogue targets); round-trip verified on real ROM; in-place dialogue injection with overflow report |

## GBA Games — Broken / Stub

| Game | Game ID | Region | Plugin | Status | Problem |
|------|---------|--------|--------|--------|---------|
| Astro Boy: Omega Factor | BTAE | USA | gba_astro_boy | 🔧 Stub | is_stub=True: naive Caesar scan produced ~22k garbage segments; pointer table unknown |
| Sonic Advance | ASOE | USA | gba_sonic_advance | 🔧 Stub | is_stub=True: "length prefix + ASCII" heuristic produced garbage, credits decode to spaces |
| Kingdom Hearts: Chain of Memories | B8CE | USA | gba_kingdom_hearts_com | 🔧 Stub | is_stub=True: unreadable output (wrong encoding/offsets) |
| Phoenix Wright: Ace Attorney | ASBJ | Japan | gba_phoenix_wright | 🔧 Stub | is_stub=True: unreadable output (wrong encoding/layout for the T-En ROM) |
| Mega Man Battle Network | AREP | Europe | gba_megaman_battle_network | 🔧 Stub | 0 segments (encoding/table unknown) |
| FF VI Advance | BZ6E | USA | gba_ff6_advance | 🔧 Stub | 0 segments, no pointer table |
| Fire Emblem (Europe) | AE7Y | Europe | gba_fire_emblem | 🔧 Stub | is_stub=True: Huffman tree format not implemented; FE7 codes BE7E/BE7J also detected |
| Fire Emblem: Sacred Stones | BE8E | USA | gba_fire_emblem | 🔧 Stub | is_stub=True: Huffman tree format not implemented; codes BE8P/BE8J also detected |
| Castlevania: Circle of the Moon | AAME | USA | gba_castlevania_ctm | 🔧 Stub | 0 segments, charmap unknown |
| Castlevania: Harmony of Dissonance | ACHP | Europe | gba_castlevania_hod | 🔧 Stub | 0 segments, charmap unknown |

## GBA Games — Stub Plugins (charmap / pointer table needed)

| Game | Game ID | Region | Plugin | Status | Known Info |
|------|---------|--------|--------|--------|------------|
| Golden Sun: The Lost Age | AGFE | USA/Europe | gba_golden_sun_tla | ✅ Full | Contextual Huffman (same engine as GS1), decoder/encoder + full extract→inject→extract round-trip verified on the real ROM (12461 dialogue segments, byte-identical) |
| Advance Wars | AWRE | USA | gba_advance_wars | 🔧 Stub | ASCII, menu-heavy |
| Mega Man Battle Network 2 | AM2P | Europe | gba_megaman_battle_network_2 | 🔧 Stub | 0 segments, same engine as MMBN1 |
| Mega Man Zero | AZCE | USA/Europe | gba_megaman_zero | 🔧 Stub | Custom encoding, ASCII subset |
| Shining Force | AF5E | USA | gba_shining_force | 🔧 Stub | ASCII, RPG text |
| CT Special Forces | AC7E | USA | gba_ct_special_forces | 🔧 Stub | ASCII |
| Custom Robo GX | ARJJ | Japan | gba_custom_robo_gx | 🔧 Stub | Japanese-only, custom encoding |
| Metroid Zero Mission | BMXE | USA | gba_metroid_zero_mission | 🔧 Stub | Custom encoding (similar to Fusion but different offsets). TBL needed |
| FF I & II: Dawn of Souls | BFFE | USA | gba_ff12_dawn_of_souls | 🔧 Stub | TBL provided, pointer table location unknown |
| Sonic Advance 2 | A2NE | USA | gba_sonic_advance | 🔧 Stub | is_stub=True: text engine differs from SA1, structure not implemented |
| Breath of Fire | ABFE | USA | gba_breath_of_fire | 🔧 Stub | is_stub=True: pointer table candidate @ 0x117DD4, targets ~0x101238, custom charmap (not ASCII). RE as a separate task |
| Keitai Denjuu Telefang 2 | ATPJ | Japan | gba_telefang_2 | 🔧 Stub | is_stub=True: pointer table candidate @ 0x101650, targets ~0x0FCF10, Japanese strings. RE as a separate task |

## FFTA String Tables (DataCrystal, verified)

| Table | Pointer Table Offset | Text Start | Entries |
|-------|---------------------|------------|---------|
| Universal | 0x005567F0 | 0x005541B4 | 767 |
| Item/Location Names | 0x00526680 | 0x0052336C | 753 |
| Mission Names | 0x0055A64C | 0x00558008 | 512 |
| Random Names | 0x005680DC | 0x00566A00 | 725 |

## GB Games — Working / Partial

| Game | Game ID | Region | Plugin | Status | Notes |
|------|---------|--------|--------|--------|-------|
| Pokemon: Red Version | GB_POKEMONRED | USA/Europe | gb_pokemon_gen1 | ✅ Full | Gen1 fixed tables (item names @ 0x472B, monster names @ 0x1C21E fixed-width 10, move names @ 0xB0000), Gen1 charmap (from pret/pokered), terminator 0x50, `pad_byte=0x50` on insert; round-trip extract→inject→extract verified on the real ROM. SGB Enhanced (flag 0x146 = 0x03) |
| Pokemon: Blue Version | GB_POKEMONBLUE | USA/Europe | gb_pokemon_gen1 | ✅ Full | Gen1 plugin (same as Red); round-trip verified on real ROM. SGB Enhanced (flag 0x146 = 0x03) |
| Pokemon: Green Version | GB_POKEMONGREEN | USA/Europe | gb_pokemon_gen1 | ✅ Full | Gen1 plugin; T-En patched ROM. SGB Enhanced (flag 0x146 = 0x03) |
| Pokemon: Yellow Version | GBC_POKEMONYELLOW | USA/Europe | gb_pokemon_gen1 | ✅ Full | Gen1 plugin; round-trip verified. SGB Enhanced (flag 0x146 = 0x03). File is `.gb` but core detects `gbc` (CGB flag 0x80) → game_id `GBC_POKEMONYELLOW` |
| Legend of Zelda: Link's Awakening | GB_ZELDA | USA/Europe | gb_zelda_awakening | ✅ Full | Direct ASCII, 0x5E=apostrophe, terminator 0xFF, split 0xFE; 7 segments (6 dialog + credits) at 0x26700-0x77FB6; ZeldaTextDecoder shared with DX; round-trip verified on real ROM. Not SGB Enhanced |

## GBC Games — Working / Partial

| Game | Game ID | Region | Plugin | Status | Notes |
|------|---------|--------|--------|--------|-------|
| Legend of Zelda: Link's Awakening DX | GBC_ZELDADXAE | USA/Europe | gbc_zelda_awakening_dx | ✅ Full | Same engine as GB (ASCII, 0x5E=apostrophe, 0xFF terminator, 0xFE split); 6 segments (5 dialog + credits) at 0x26800-0x77FCC; shared ZeldaTextDecoder; round-trip verified on real ROM. SGB Enhanced (flag 0x146 = 0x03) |
| Pokemon Gold | GBC_POKEMONGLDAAUE | USA/Europe | gbc_pokemon_gsc | ✅ Full | Gen2 charmap (=Gen1), 4 tables: item_names, trainer_class_names, monster_names (fixed-width 10), move_names — verified against test ROM (GBC_POKEMONGLDAAUE, 2MB MBC3+SGB) |
| Legend of Zelda: Oracle of Seasons | GBC_ZELDADINAZ7E | USA/Australia | gbc_zelda_seasons | ✅ Full | Full text pool via high-index/pointer tables (0-3 dict, 4-0x63 text), mini-dictionary (2-byte refs 0x02-0x05), control codes (COL/SPEED/POS/JUMP/CALL etc.), kanji/accented Latin as Unicode, bracket tokens. Inserter: verbatim byte-copy for unchanged strings + greedy dictionary recompression for new translations; full extract→inject→extract round-trip verified on real ROM. Not SGB Enhanced (flag 0x146 = 0x00) |

## GBC Games — Stub Plugins

Dedicated GBC stub-plugins exist for every GBC ROM in `test_roms/`. No
`GenericGBCPlugin` route is needed anymore. SGB Enhanced = flag 0x146 = 0x03
in the cartridge header (Super Game Boy extensions on SNES).

| Game | Game ID | Region | Plugin | Status | Notes |
|------|---------|--------|--------|--------|-------|
| Harvest Moon GBC | GBC_HARVESTMOONGB | USA | gbc_harvest_moon | 🔧 Stub | Detected (GBC_HARVESTMOONGB); text layout unknown, needs RE. SGB Enhanced (flag 0x146 = 0x03) |
| Harvest Moon 2 GBC | GBC_HMOON2CGBBM2E | USA | gbc_harvest_moon_2 | 🔧 Stub | Non-ASCII charmap (A-Z 0x0A-0x23, a-z 0x24-0x3D, control 0xF0-0xF8); DataCrystal TBL available, structure not implemented. SGB Enhanced (flag 0x146 = 0x03) |
| Harvest Moon 3 GBC | GBC_HMOON3CGBBWAE | USA | gbc_harvest_moon_3 | 🔧 Stub | Detected (GBC_HMOON3CGBBWAE); text layout unknown, needs RE. Not SGB Enhanced (flag 0x146 = 0x00) |
| Fire Emblem: The Reincarnation of Light and Dark | GBC_SUPERSLG | Asia (T-En) | gbc_fire_emblem_reincarnation | 🔧 Stub | Detected (GBC_SUPERSLG, title "SUPER SLG"); T-En patched ROM, text layout unknown. Not SGB Enhanced (flag 0x146 = 0x00) |
| Resident Evil Gaiden | GBC_RESEVILGDARHE | USA | gbc_resident_evil_gaiden | 🔧 Stub | Detected (GBC_RESEVILGDARHE); text layout unknown, needs RE. Not SGB Enhanced (flag 0x146 = 0x00) |
| Shin Megami Tensei Devil Children | GBC_DEBITIRUBBHEJ | Japan (T-En) | gbc_smt_devil_children | 🔧 Stub | Detected (GBC_DEBITIRUBBHEJ); T-En patched ROM, text layout unknown. SGB Enhanced (flag 0x146 = 0x03) |
| Super Mario Bros. Deluxe | GBC_MARIODELUXAHYE | USA/Europe | gbc_super_mario_bros_deluxe | 🔧 Stub | Detected (GBC_MARIODELUXAHYE); text layout unknown, needs RE. Not SGB Enhanced (flag 0x146 = 0x00) |

## Summary

| Status | Count | Games |
|--------|-------|-------|
| ✅ Full | 23 | FFTA (GBA), Zelda TMC (GBA), FF5 Advance (GBA), FF4 Advance (GBA), Golden Sun (GBA), Mario & Luigi SS (GBA), Castlevania AoS (GBA), Metroid Fusion (GBA), Wario Land 4 (GBA), Pokemon Emerald (GBA), Pokemon Ruby (GBA), Pokemon Sapphire (GBA), Pokemon FireRed (GBA), Pokemon LeafGreen (GBA), Pokemon Red/Blue/Green/Yellow (GB/GBC), Pokemon Gold (GBC), Zelda Link's Awakening (GB + DX), Zelda Oracle of Seasons (GBC), Golden Sun: The Lost Age (GBA) |
| ⚠️ Partial | 0 | — |
| ❌ Broken | 0 | |
| 🔧 Stub | 28 | Astro Boy, Sonic Advance ×2, Kingdom Hearts CoM, Phoenix Wright, FF6 Advance, Fire Emblem ×2, Mega Man Battle Network ×2, Advance Wars, Mega Man Zero, Shining Force, CT Special Forces, Custom Robo GX, Metroid ZM, FF1&2 Dawn of Souls, Castlevania CotM/HoD, Breath of Fire, Telefang 2, Harvest Moon 1/2/3, Resident Evil Gaiden, SMT Devil Children, Super Mario Bros. Deluxe, Fire Emblem Reincarnation (T-En) |
| — No plugin | 0 | |

Total: 51 ROMs in test_roms (36 GBA + 10 GBC + 5 GB); 51 covered by plugins (36 GBA + 10 GBC + 5 GB).

## How to Add a Game

1. Create `plugins/<platform>_<game_name>.py` (`gba_`, `gb_`, `gbc_` prefix)
2. Implement `GamePlugin` with `game_id_pattern` + `get_text_segments(rom)`
3. Add verified charmap (DataCrystal / decomp / manual RE)
4. Test on a real ROM — output must be readable English
5. Update this file (including the Region column)

## Sources

- **Decomp projects**: Pret (Pokemon), zeldaret (Zelda TMC)
- **DataCrystal**: https://datacrystal.tcrf.net/
- **FF5 Hacking Wiki**: https://www.ff6hacking.com/ff5wiki/
- **FF6AE source**: https://github.com/fred65816/FF6AE
- **References**: `references/` directory