# Known issues and limitations

What is **already broken or does not work**, as opposed to planned work —
that lives in `ROADMAP.md`. The split is deliberate: an issue is done when
the reproduction no longer reproduces, a task is done when the feature works,
and in one list they compete for attention incorrectly.

Check with `pytest tests/ -v`. A closed item **moves to `CHANGELOG.md`** and is
deleted from here: only open defects stay in this file, so a `[x]` checkbox
should never appear in it. `CHANGELOG.md` is deliberately listed in `.gitignore` because the release notes are published by hand at release time.

- [ ] Shortening a translation breaks round-trip — measured on the local
  corpus (32 non-stub ROMs, 74777 records; full run at
  `scripts_roms/out/census_run.log`). The class "a whitespace-only
  translation is written invisibly" did **not** reproduce: there are zero such
  records, blank translations never reach the write.
Oracle text records go
    through the normal path. Measured over the corpus: Oracle reports
    `dmg=0 third=0 lost=0 pad=0` (`scripts_roms/out/census_run.log`).
  - [ ] **Oracle of Seasons dictionary is not translatable (copy-on-write).**
    The refusal above is a workaround, not a fix. Real fix: rewrite every cited
    record as self-contained text without `0x02..0x05` codes. Cost: +ROM
    (20-60 bytes per record against 2, 1765 records), does not scale to 4-32 MB
    GBA without a relocation pool. See ROADMAP.
    **Measured: for Oracle itself there is room.** `Legend of Zelda, The -
    Oracle of Seasons (USA).gbc` (1 MB) has **615.7 KB of free bytes** in runs
    of >= 30 bytes, which covers the whole addition: 1765 slots x 20-60 bytes
    = 35300-105900 bytes. The reference itself stays 2 bytes - only its target
    address changes to point at a private copy. What remains is the mechanism
    and the GBA-scale shift.
    Caveat: 0x00 runs in a GBC ROM are not necessarily free (bank packing,
    save data, region-to-RAM), and runs that overlap occupied record slots have
    to be filtered out.

  - [ ] **Other Oracle and Pokémon damage: scale NOT established.** Record matching
    in the probe is hybrid, and once the record count changes the window contents
    stop being provable, so the lower bound cannot be turned into a scale. The
    pre-gate figures ("Oracle: 92 lost, 5 corrupted") are a historical
    measurement of that state, not a current number.
    **Hypothesis confirmed on real material.** A change in record count does
    break the matching: Crown yields 1285 records from the source and 1283 from
    the patched build, and the indices diverge from position 604 onwards
    (`out[604]` is `src[605]`, address `0x250001`). Recovering translations by
    index would therefore be wrong for everything after 604; the only correct
    key is the **address** (parsing `scripts_roms/crown_ru_full.gba` that way
    reproduced the existing batches exactly). The consequence is mechanical, not
    just numeric: any index-based matcher produces a plausible but wrong answer
    once the record count moves - including the census and hand-written analyses.

  The rule from the issue still holds and is now applied literally: any "this is
  junk" criterion must be **invariant to translation** — by pointer geometry,
  data layout or the number of unknown tokens, but never by text length and
  never by letter ratio. Rejected on that basis: a letter-ratio gate (it lost
  every Golden Sun credit) and a length threshold (it cut the `Music` and
  `Writing` staff-roll headings). **The old title was wrong:**
  `_drop_junk_windows` (`core/injector.py`) does not check length, it only
  drops token-only windows, so looking for the cause there is pointless.
  Verified and fixed for FF4/FF5 and Wario Land 4; the other games were never
  fixed.

  Closed in the current cycle: Wario Land 4 (fixed-slot tail), Golden Sun (the
  credits scan over machine code), Metroid Fusion (`pad_byte` in the credits), a
  blank translation in the pointer path, FFTA CRN, Advance Wars (the letter
  gate), Zelda GB/DX, and `silent_no_write` as a measurement artefact. Details
  and the measurements are in `CHANGELOG.md`, section `[1.6]`; the
  anchors are `tests/test_shortening_credits_defects.py`,
  `tests/test_ffta_crn_chain.py`, `tests/test_advance_wars_letter_gate.py` and
  `tests/test_generic_empty_translation.py`.

- [ ] CP866/JIS ambiguity: a pure Russian 8-bit ROM (CP866) without ASCII can be
  misdetected as Japanese - both encodings share a byte range (0x80-0xDF). The
  detector prefers Russian when CP866-exclusive bytes (0xE0-0xFD) are present; for
  plugin games the language from `segment['lang']` takes priority over the
  heuristic.
    **Measured: the defect reproduces, but the fix was reverted as
  unvalidatable.** On a synthetic window of real Russian CP866 text containing no
  Japanese at all, `core/scanner.py::detect_multiple_languages` returns
  `['russian', 'japanese']` - with `russian_density 0.831`, `japanese_density
  0.630`, `cyr_exclusive 0.201`. The Japanese density there is an artifact of the
  overlapping ranges, not a language signal. Plugin `prefer_lang='ru'` does not
  fix it: `japanese` still comes back second.
    The proposed rule ("add japanese only when `japanese_density >
  russian_density`") was reverted. A corpus run showed it removes `japanese`
  from genuinely Japanese games (Custom Robo GX (Japan), Mega Man Zero, Mega Man
  Battle Network, Metroid - Zero Mission). The reason is that the "russian"
  signal is itself false there: on those windows `cyr_exclusive` sits at
  0.31-0.39 with an SJIS pair structure of 0.54-1.00.
    The main reason there is nothing to validate against: all measurements were
  taken at ROM OFFSETS (`0x100000`), not at real text windows, and such bytes are
  graphics and code rather than text, so their densities carry no language
  meaning. The synthetic case reproduces the defect honestly, but carrying a
  rule over to real windows without real windows in hand would mean changing the
  detector on a hunch - and as measured, it would silently break Japanese games.
    **What closing this needs:** measurements on real text windows (via
  extraction, not a fixed offset) for at least one pure-Russian CP866 game and
  one real Japanese SJIS game, then the rule can be chosen. Also decide whether
  plugin `prefer_lang` should strip secondary languages rather than only reorder
    them - today it only reorders.

- [ ] Fire Emblem GBA is unsupported, and the FE Huffman path is wired to
  nothing.
    **The previous wording of this item was wrong: the decoder is not
  "broken for Europe ROMs", there is simply nothing for it to run against.**
  Measured (`scripts_roms/fe_huffman_probe.py`):
  - `decompress_text_block()` is called **from tests only**
    (`tests/test_wins5a_coverage.py`, `tests/test_wins6_coverage.py`); no plugin
    in working code calls it;
  - `FE_HUFFMAN_CONSTANTS` was never read, and its values (`0x08000000` in all
    three fields) are the ROM base, i.e. placeholders. Removed;
  - the `FF4`/`FF5` prefixes in this project are **Final Fantasy** IV/V Advance
    (`BZ4E`/`BZ5E`), and those work: 1761 and 5241 records. Fire Emblem is
    `AE7Y` and `BE8P`, and **there is no plugin for it at all**;
  - both Fire Emblem Europe ROMs in the corpus yield **0 segments**.
  **What is needed to make this measurable at all:** a Fire Emblem (FE7/FE8)
  plugin with pointers and a layout. Only then can it be checked whether the
  text is Huffman-compressed, and real tree addresses would appear. Until then,
  "tree addresses are unknown" is a consequence of the missing plugin, not a
  separate task. The decoder itself remains test-covered and ready to call.

- [ ] FF4/FF5 records that another pointer looks into cannot be shortened: their
  extent is defined by the terminator, which doubles as padding, so any
  shortening wipes the tail where the second record begins. Such a translation
  is now refused (the `has_mid_alias` flag) and the refusal shows up in the
  overflow report. Measured cost: 561 of the 646 translatable FF4 records
  (86.8%) and 40 of 4900 on FF5 (0.8%) cannot be shortened — a substantial
  limitation for Russian
  localization. The real solution is to relocate those hosts instead of writing
  in place (the `inject_language_block` mechanism already does this): the
  original bytes stay untouched, aliases survive by construction, and the
  translator is free to shorten anything. Narrower rules were measured and
  rejected: a threshold on the alias offset loses 191 aliases on FF4, and the
  "translation + EOS + original tail" scheme loses 74

- [ ] Pokemon GBA dialogues: the manifest `core/manifests/<game_code>.json` is
  static, so its `target` goes stale after a relocation. Relocation is handled:
  the old block is freed (zeros) and extraction follows the pointer when the old
  block is blank, cutting the parse at the terminator instead of the static
  `free_after` (which was clipping the last character). Green on the 4 clean ROMs
  and on Radical Red.
    **Previous hypothesis disproved: the blocker is not the guard, it is the
    hack's charmap.** The guard really does differ - on
    `Moemon Fire Red ruRevival Project2.0.gba` the ROM guard is `8DE4FEE2`
    against a manifest guard of `5CC9451F`, so `entries_for_rom` disables the
    whole segment (0 records out of 1289 valid). But the guard patch was written,
    measured, and then **reverted on purpose**, because enabling the segment while
    the layout is still wrong is worse than leaving it off.
    Measurements of the patch that works: when the guard differs, keeping only
  records whose slot points exactly at `target` revives the segment - **0 -> 714
  dialogues, 679 with Cyrillic**; clean FireRed still returns all 1289; the BPRE
  manifest confirms 0 of 1289 on Emerald/Ruby/Sapphire, so foreign ROMs are still
  refused. Of the 1289 records, 718 keep their slots and 571 do not; the latter
  have scattered deltas (147 distinct values, -2 to -13), so this is not one
  uniform shift that could be corrected, and their `target` holds truncated text
  (`Ya`, `A`, `TVIE`) because the address lands mid-line.
    Why it was reverted: the hack has its own character layout while the plugin
  decodes with `CHARMAP_FIRERED`. The same run at `0x172A1A` reads as scrambled
  uppercase by FireRed and as `сильнее` by the hack layout
  (`scripts_roms/moemon_charmap_partial.json`). The text is therefore decoded
  wrongly and re-encoding cannot reproduce it: `test_identity_roundtrip` fails on
  this ROM, `714 -> 1210` records. Enabling it would feed scrambled Russian into a
  translation project and break round-trip.
    **What is actually needed:** the full hack layout (the partial one is not
  enough), after which the guard can be relaxed the measured way above.

- [ ] **Cyrillic is absent from the Gen1 Pokemon charmap, so any Russian line
  still becomes spaces in fixed slots.** The reporting half is done: all three
  encoders reset and fill `last_unmapped_chars`, `TextInjector.collect_unmapped_chars()`
  reads it and the GUI prints it. The charmap itself is unchanged and the
  decoder still cannot encode the letters - the missing part is the glyph work.
  **Measured on Gen1:** `CHARMAP_GEN1` holds 119 characters and zero Cyrillic,
  so `encode('ЖИВОТ')` reports `['Ж', 'И', 'В', 'О', 'Т']`. Picking glyphs for Cyrillic in Gen1 is the
  remaining task. **FireRed already passes:** it carries Cyrillic and its
  `last_unmapped_chars` stays empty for real text. Anchors:
  `tests/test_gba_pokemon.py::TestUnmappedCharTracking`,
  `tests/test_gb_pokemon_gen1.py::test_gen1_fixed_decoder_tracks_unmapped_chars`.

- [ ] **Plugins that load but extract 0 segments.**

  **Triage:** these are not broken detectors, they are deliberate stubs. In the
  working tree `True` stands in 25 plugins (`plugins/gba_sonic_advance.py`,
  `plugins/gba_metroid_zero_mission.py`, `plugins/gba_astro_boy.py`,
  `plugins/gba_castlevania_hod.py`, and others), and `census_run.log` lists 21
  stub ROMs. The earlier figure "10 plugins, 9 of 10" was outdated and its list
  of codes no longer holds; the current count is 21 stubs.
  Consequence: either these games get implemented, or the stubs are removed and
  no plugin is advertised for them. See ROADMAP.

## Full-corpus extract / translate / insert run (measured 2026-10-08)

Run: `scripts_roms/readback_census_probe.py` over 32 non-stub ROMs, 74777
records, log at `scripts_roms/out/census_run.log`. **Caveat on what this
measures:** the census substitutes a **shortened** translation, so a refusal
here means "does not accept shortening", not "the game cannot be translated".
A plain substitution is not exercised. Damage is zero throughout
(`third_value_corrupted` 0, `lost_record` 0, `pad_visible` 0,
`silent_no_write` 0, `readonly_corrupted` 0).

- [ ] **`language_block` writes nothing: 0 of 2895.** The only game on this path
  is Castlevania: Aria of Sorrow, and not one of its 2895 records
  (`cvas_en_ui_*`, segments `cvas_en_ui_0/1/2`, `not_writable_by_design`) is
  written. So the game does not translate at all in the shipped build even
  though the plugin loads and returns segments. The path exists in code and
  does nothing in this corpus - the largest uncovered area found.
  **The refusal is reasoned, not accidental.** The pointer table at `0x506B38`,
  2895 entries of 4 bytes, divides into language blocks (`CVAS_LANG_BLOCKS`,
  `plugins/gba_castlevania.py:110`): `(0, 40) en_ui`, `(40, 1013) en`,
  `(1013, 2116) fr`, `(2116, 2895) de`. So the ROM carries **three** scripts plus
  the UI. Writing into the `en` block needs two things the project does not have:
  Cyrillic glyphs in the GBA tile font, and a new language slot in the game - the
  `fr` and `de` scripts keep pointing at their own blocks, and adding a record
  does not create a slot. Translating a pointer range means relocating a whole
  language (as the code comment says), so this is the same class of task as
  Oracle's copy-on-write. Practical consequence for a translator: of the 2895
  records only the 973 of the `en` block (40-1013) are translatable in principle,
  and even those once a font exists.
    **Clarified by measurement: the refusal had no reason, now it is explained.**
  Segments were returned with `injectable: False` and an empty
  `not_writable_reason`, so the GUI showed "read_only" - blaming the game for
  something it does not have: the ROM is writable throughout, and the refusal is
  not about write permission but about the missing font and slot. The reason is
  now set: `lang_block_requires_font_and_slot` (`plugins/gba_castlevania.py`).
  The census classifies by the `injectable` flag itself, so the numbers did not
  move: 2895 records, 0 written, `not_writable_by_design` 2895, real damage 0.
  Measurement: `scripts_roms/cvas_lang_block_probe.py`.
- [ ] **Compressed path: there is no way to re-encode shortened text, 5559
  records.** The `recompress_skipped_by_design` class turned out not to be a few
  large segments but **thousands of separate single-string ones**. A GS segment
  is one string from the string table: `gs_dialogue_f00_004` has a 23-byte
  window for 56 characters of text, so records are not grouped into ranges.
  Measured from the `readback_census.json` artifact: Golden Sun - 10 722
  compressed segments, **7 763 written**, **2 959 not recompressed**; The Lost
  Age - 12 461, 9 868 written, 2 593 not recompressed; FFTA - 1 787, 1 780
  written, 7 not recompressed.
  **Cause established:** the game's Huffman trees only assign codes to
  (previous byte, byte) pairs that actually occur in the data. Shortening moves
  control codes into a new context, and that pair has no code:
  `char 0x01 not encodable after 0x03` (481 cases), `char 0x1E after 0x03`
  (383), `char 0x02 after 0x6F` (54) and so on. The refusal is therefore
  correct - the encoder physically cannot represent such a stream. It is a
  format limitation, not a translation error.
  **Visibility restored:** the exception used to go to `logger.debug` and never
  reached a report, so the census only saw `info['ok'] is False`. The injector
  now writes `last_compress_report` with the reason
  (`compressed_recompress_failed` / `compressed_too_long`) and the probe emits
  `segment_refused_reason:<segment>:<reason>`.
  **Checked: the pairs can be worked around, but that does not solve it.** All
  256 bytes have at least one context, so every absent pair `(prev, byte)` does
  have a code in some other context. A BRIDGE workaround was implemented and
  measured: a byte X is inserted into the stream, which then reads as
  `prev -> X -> byte`. Over 800 Golden Sun windows: 558 encode without bridges,
  585 with them (+3.4%), costing 27 bridges across 585 records (0.05 per
  record), with no growth of the stream (median 0.5x the window) and only 1 of
  800 failing to fit.
  **The encoder with bridges was NOT shipped - it breaks round-trip.** The
  "invisible bridge" check turned out to be false: decoding immediately with
  the same decoder gave 585 clean results, but a full round-trip (write to ROM,
  then re-extract) showed real corruption: `gs_dialogue_f03_104` -> `msalcory`,
  `gs_dialogue_f10_042` -> `IRI`. Those records use no bridges at all, their
  stream is shorter than the window, and the tail of the old compressed string
  is extracted as characters: previously such cases refused honestly and left
  the ROM untouched, whereas with bridges they pass and write an incomplete
  stream. So bridges require filling the window remainder, which the compressed
  path does not do.
  **Conclusion:** the limit is structural, not algorithmic. 26.9% of records
  (215 of 800) cannot be represented at all; the rest refuse honestly and do
  not damage the ROM. Shortening compressed text is unreachable in principle,
  and localizing Golden Sun and The Lost Age down this path is not
  recommended.
  Measurements: `scripts_roms/gs_bridge_probe.py` (bridge economy),
  `scripts_roms/gs_bridge_roundtrip.py` (cleanliness on immediate decode),
  `scripts_roms/gs_bridge_poc.py` (post-mortem of the corruption).
  After the `_shorten` fix the share grew: `recompress_skipped_by_design`
  **5559 (7.43 %)**, the compressed path writes 19 411 of 24 970 (77.7 %) against
  20 728 before - shortening became aggressive enough to stop collapsing into
  emptiness.
- [ ] **Records refused by design plus one whole segment.** `refused_by_design`
  **872 (1.17 %)**: `generic` 733 and `pointer_dialogues` 139. `segment_refused`
  is **1**, the single example being `ff5_text_13829` (Final Fantasy V Advance).
  The earlier claim of "7 segments, including `gs_credits_0f0bcc`" was wrong: the
  false `' and'` credit continuation disappeared with the credits-boundary fix,
  not with a shorter list.
- [ ] **Pokemon Crown: most Russian translations do not fit their slots** -
  **checked: the relocation machinery works, the old figure is stale.**
  **Measured** (`scripts_roms/crown_fit_probe.py`): of 1285 batches,
  **457 do not fit** in place (index 5 needs 32 bytes and has 30), 828 fit, and
  0 fail to encode.
  **Which is exactly what the relocation does.** `crown_roundtrip_proof.py` runs
  with `relocate=True` and reports **457 relocations** - a match. Refusals 0,
  records 1285 out of 1285, 0 lost.
  The old figure (336 not fitting, 825 landing) was measured on the stale
  artifact, which lost records and never ran relocation, so it reported English
  left in place and blamed a mechanism that works.
- [ ] **The census cannot see real translations, which corrupts the measurement of
  all the work.** A `--translations scripts_roms/ru_batch*.json` mode was added:
  it substitutes real translations instead of shortening. The first
  classification counted them as corruption: `applied` 0,
  `third_value_corrupted` 2058 out of 1285 records. **After fixing the
  classification** (it now uses the same transform as the injector, plus a
  text fallback for relocated records) the measurement on Crown (a copy in temp,
  the original in test_game/ untouched) is:
  | mode | shortened translation | real translations |
  |---|---|---|
  | `applied` | **2081** | **1462** |
  | `third_value_corrupted` | 0 | **599** |
  So of 1285 real translations, 1462 were written and confirmed by read-back while
  599 did not match. That is a measurable share (46.6%), not "everything broke".
  **The suspect was checked, and it was the cause.** `ru_map` was built from
  batch indices for EVERY extraction group, although the batches belong to
  `pokemon_firered_dialogues`. On Crown that produced **834 extra substitutions**
  on top of the 1285 correct ones: names (386), attacks (354), abilities (77) and
  types (17) were all receiving translations from dialogue indices.
  Fixed: the batches are now matched against a single segment, chosen by matching
  the record count to the batch size (`_guess_batch_segment`), with a
  `--translations-segment` flag to name it explicitly.
  **Measured before/after on one ROM:** `ru_map` 1884 -> 1113, `applied`
  1462 -> 2065, `third_value_corrupted` **599 -> 17**. So 582 of the mismatches
  were a measurement error, not an insertion defect.
  **Left to do:** the 17 remaining mismatches out of 1285 (1.3%). The text
  fallback cannot distinguish identical strings - relocations need an
  "old target -> new target" mapping via `last_relocate_report`, which would stop
  the matching from depending on the text at all.

- [ ] **Two Crown records are lost during injection** - **checked: the production
  path is fine, the damage was in the old artifact.**
  **Proof** (`scripts_roms/crown_roundtrip_proof.py`, real Russian translations,
  `relocate=True`):
  1. `records 1285 -> 1285` - not one dropped;
  2. `missing translations: 0` - all 1285 read back by text;
  3. `old texts that accidentally survived: 0` - every English string was
     replaced;
  4. `DROUGHT @0x24FFCB -> '   ЗАСУХА'`, `SHELL ARMOR @0x25000D -> '  ПАНЦИРЬ'` -
     **both are at their own addresses**;
  5. `bytes changed: 27 306 | unexplained by a window or relocation: 0` - every
     change falls inside a text window, a relocation destination (457) or a
     pointer slot holding an address;
  6. `refusals: 0 | mid-alias: 0 | overlap: 0 | unmapped: []`.
  **Where the loss really was:** the stale artifact `scripts_roms/crown_ru_full.gba`
  holds 1283 records; the loss happened while building it.
  `crown_ru_full_build.py` takes its base from `FONTED`, and the missing
  `TMP/crown_ru_font.gba` made the build read back an already-truncated ROM, so
  the loss compounded. Rebuilding requires a font-patched source ROM, which is
  not in the tree.

- [ ] **`readonly` 2481 is the Oracle dictionary, extract-only by decision.**
  Not a defect; recorded here so the 2481 do not read as loss: 1024 of them are
  dictionary slots, the rest are read-only FF4 segments.

- [ ] Some games with non-standard encodings are not recognized
