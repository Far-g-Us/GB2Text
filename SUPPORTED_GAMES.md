# Supported Games

Games with text extraction support (verified charmap, decoder, tested on real ROM).

## Status Legend
- ✅ Full — CharMap verified, decoder working, tested
- ⚠️ Partial — Works but needs refinement
- 🔧 In Progress — Currently being developed
- ❌ Not supported

## GBA Games

| Game | Game ID | Plugin | CharMap Source | Status | Notes |
|------|---------|--------|----------------|--------|-------|
| Pokemon Emerald | BPEE | gba_pokemon | Pret pokeemerald decomp | ✅ Full | Exact charmap, LZ77 decompression |
| Pokemon Ruby | AXRE | gba_pokemon | Pret pokeemerald decomp | ✅ Full | Same charmap as Emerald |
| Pokemon Sapphire | AXVE | gba_pokemon | Pret pokeemerald decomp | ✅ Full | Same charmap as Emerald |
| Mario & Luigi: Superstar Saga | A88E | gba_mario_luigi_ss | ASCII verified from ROM | ✅ Full | Standard ASCII encoding |
| Final Fantasy Tactics Advance | AFXE/AGBJ/AGBE | gba_fft_advance | DataCrystal (7 pages) | ✅ Full | Multi-byte 0x8X XX, LZSS, 4 pointer tables, CRN names |
| Legend of Zelda: The Minish Cap | BJBE | gba_zelda_tmc | zeldaret/tmc decomp | ✅ Full | Tile-based ASCII, control codes 0x01-0x0F |
| Astro Boy: Omega Factor | AAFX | gba_astro_boy | Caesar cipher -1 | ✅ Full | Spanish text, shift encoding |
| Final Fantasy IV Advance | BZ4E | gba_ff4_advance | DataCrystal BZ4E | ✅ Full | Japanese hiragana, control codes |
| Final Fantasy V Advance | BZ5E | gba_ff5_advance | DataCrystal BZ5E | ✅ Full | Japanese hiragana, control codes |
| Fire Emblem | AE7E/AE7Y | gba_fire_emblem | FEBuilderGBA source | ✅ Full | FE control codes, Huffman (stub) |
| Fire Emblem: The Sacred Stones | BE8E/BE8P | gba_fire_emblem | FEBuilderGBA source | ✅ Full | FE control codes, Huffman (stub) |
| Wario Land 4 | WL4E | gba_wario_land_4 | DataCrystal TBL | ✅ Full | 1585 text entries verified |
| Castlevania: Aria of Sorrow | A2CE/A2CJ/A2CP | gba_castlevania | DataCrystal TBL | ⚠️ Partial | Multi-byte decoder, needs pointer tables |
| CT Special Forces | A4FE/A4FJ/A4FP | gba_ct_special_forces | DataCrystal TBL | ⚠️ Partial | Shifted ASCII encoding, no ROM to test |
| Custom Robo GX | AJIJ | gba_custom_robo_gx | DataCrystal TBL | ⚠️ Partial | Shift-JIS based, multi-byte 0xF8-FE, no ROM to test |
| Metroid Fusion | AMTE | gba_metroid_fusion | ASCII verified from ROM | ⚠️ Partial | Credits text works, dialogue needs pointer tables |
| Final Fantasy VI Advance | BZ6E | gba_ff6_advance | DataCrystal BZ6E | 🔧 In Progress | Stub, needs pointer tables |
| Castlevania: Circle of the Moon | A2ME | gba_castlevania_ctm | ASCII (same as AoS) | 🔧 In Progress | Stub, needs pointer tables |
| Castlevania: Harmony of Dissonance | ACHP | gba_castlevania_hod | ASCII (same as AoS) | 🔧 In Progress | Stub, needs pointer tables |
| Mega Man Battle Network | AREP | gba_megaman_battle_network | Stub (needs charmap) | 🔧 In Progress | Custom encoding, TextPet has tables |

## Not Supported Yet

| Game | Game ID | Priority | Notes |
|------|---------|----------|-------|
| Golden Sun | BPGJ | High | Popular JRPG |
| Golden Sun: The Lost Age | BPGO | High | Sequel |
| Metroid Zero Mission | APMX | Medium | Same engine as Fusion |
| Mega Man Battle Network 2 | AREQ | Medium | Same engine as MMBN1 |
| Advance Wars | A3AJ | Low | Strategy |
| Advance Wars 2 | A3BJ | Low | Strategy |
| Keitai Denjuu Telefang 2 | BTRA | Medium | Unique encoding |
| FF1 & II: Dawn of Souls | BPEJ | Medium | Same engine as FF4/5/6 |
| Densetsu no Stafy | AY9J | Low | Platformer |
| Dancing Sword Senkou | A22E | Low | Action RPG |

## FFTA String Tables (DataCrystal)

| Table | Pointer Table Offset | Text Start | Entries |
|-------|---------------------|------------|---------|
| Universal | 0x005567F0 | 0x005541B4 | 767 |
| Item/Location Names | 0x00526680 | 0x0052336C | 753 |
| Mission Names | 0x0055A64C | 0x00558008 | 512 |
| Random Names | 0x005680DC | 0x00566A00 | 725 |

## FFTA CRN Data

- CRN data starts at: 0x0855128C
- CRN pointer table at: 0x085516D0
- 107 character names (Marche, Mewt, Ritz, etc.)

## How to Add a Game

1. Create `plugins/gba_<game_name>.py` (or `gb_`/`gbc_` for other platforms)
2. Implement `GamePlugin` ABC with:
   - `game_id_pattern` property
   - `get_text_segments(rom)` method
3. Add charmap from decomp project / DataCrystal / manual RE
4. Add decoder class (optional, for complex encodings)
5. Add test in `tests/test_plugin.py`
6. Update this file with ✅ Full status

## Sources for CharMaps

- **Decomp projects**: Pret (Pokemon), zeldaret (Zelda TMC)
- **DataCrystal**: https://datacrystal.tcrf.net/
- **ROM analysis**: Test decoding against known strings
- **Community forums**: romhacking.net, ffhacktics.com
- **FEBuilderGBA**: Fire Emblem source code analysis
