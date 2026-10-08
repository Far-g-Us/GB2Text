# Known issues and limitations

What is **already broken or does not work**, as opposed to planned work —
that lives in `ROADMAP.md`. The split is deliberate: an issue is done when
the reproduction no longer reproduces, a task is done when the feature works,
and in one list they compete for attention incorrectly.

Check with `pytest tests/ -v`. A closed item **moves to `CHANGELOG.md`** and is
deleted from here: only open defects stay in this file, so a `[x]` checkbox
should never appear in it.

- [ ] Shortening a translation breaks round-trip — measured on the local
  corpus (32 non-stub ROMs, 74777 records; full run at
  `scripts_roms/out/census_console.log`). The class "a whitespace-only
  translation is written invisibly" did **not** reproduce: there are zero such
  records, blank translations never reach the write.
Oracle text records go
    through the normal path. Measured over the corpus: Oracle reports
    `dmg=0 third=0 lost=0 pad=0` (`scripts_roms/out/census_console.log`).
  - [ ] **Oracle of Seasons dictionary is not translatable (copy-on-write).**
    The refusal above is a workaround, not a fix. Real fix: rewrite every cited
    record as self-contained text without `0x02..0x05` codes. Cost: +ROM
    (20-60 bytes per record against 2, 1765 records), does not scale to 4-32 MB
    GBA without a relocation pool. See ROADMAP.

  - [ ] **Other Oracle and Pokémon damage: scale NOT established.** Record matching
    in the probe is hybrid, and once the record count changes the window contents
    stop being provable, so the lower bound cannot be turned into a scale. The
    pre-gate figures ("Oracle: 92 lost, 5 corrupted") are a historical
    measurement of that state, not a current number.

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
  and the measurements are in `CHANGELOG.md`, section `[Unreleased]`; the
  anchors are `tests/test_shortening_credits_defects.py`,
  `tests/test_ffta_crn_chain.py`, `tests/test_advance_wars_letter_gate.py` and
  `tests/test_generic_empty_translation.py`.

- [ ] CP866/JIS ambiguity: a pure 8-bit Russian (CP866) ROM without ASCII may be
  misdetected as Japanese — both encodings share the same byte ranges
  (0x80-0xDF). The detector prefers Russian when CP866-exclusive bytes
  (0xE0-0xFF) are present; for plugin-driven games the plugin's `segment['lang']`
  takes precedence over the heuristic.

- [ ] FE Huffman decoder doesn't work for Europe ROMs (tree addresses unknown)

- [ ] FF4/FF5 records that another pointer looks into cannot be shortened: their
  extent is defined by the terminator, which doubles as padding, so any
  shortening wipes the tail where the second record begins. Such a translation
  is now refused (the `has_mid_alias` flag) and the refusal shows up in the
  overflow report. Measured cost: 561 of the 646 translatable FF4 records
  (86.8%) cannot be shortened — a substantial limitation for Russian
  localization. The real solution is to relocate those hosts instead of writing
  in place (the `inject_language_block` mechanism already does this): the
  original bytes stay untouched, aliases survive by construction, and the
  translator is free to shorten anything. Narrower rules were measured and
  rejected: a threshold on the alias offset loses 191 aliases on FF4, and the
  "translation + EOS + original tail" scheme loses 74

- [ ] Pokémon GBA dialogues: the manifest `core/manifests/<game_code>.json` is
  static, so its `target` goes stale after a relocation. CLOSED partially: a
  relocation now frees the old block (zeros) and extraction follows the pointer
  when the old block is blank, cutting the parse at the terminator instead of
  the static `free_after` (which was clipping the last character). Green on the
  4 clean ROMs and on Radical Red. Blindly trusting the pointer does not work:
  on hacks the slots already disagree with the manifest on a CLEAN ROM, which
  is what broke identity — hence the requirement of two signals at once

- [ ] A character outside the table is silently replaced with a space in Pokémon
  fixed slots. With `strict=False`, neither `Gen1FixedDecoder` nor
  `PokemonFixedTextDecoder` raises — it substitutes a space, so an unmappable
  character lands in the ROM and the name shows up with a hole in game. The
  encoder prints a warning to the log, but neither class has a
  `last_unmapped_chars` attribute, so the GUI's "replaced characters" report
  stays empty and the translator gets no signal. Measured on Pokémon Red
  (`gen1_monster_names`): `ЖИВОТ` → five spaces, `ABCА` → `ABC ` (re-extraction
  gives `ABC `). The FireRed fixed tables do contain Cyrillic, so only genuinely
  absent symbols are affected there (CJK → space, for instance). A consequence:
  character substitution is in principle not caught by the `trailing_truncated`
  gate, because that one looks at shortening and the length is preserved here.
  The real fix is `strict=True` for fixed slots (the translation is then
  refused) or plumbing `last_unmapped_chars` out of these decoders into the
  report.

- [ ] **10 plugins load but extract 0 segments.**

  **Triage (2026):** these are not broken detectors, they are deliberate stubs.
  9 of the 10 carry `_is_stub = True`, `get_text_segments` returns `[]`, and
  they are 54-68 lines each (`gba_breath_of_fire.py`, `gba_fire_emblem.py`,
  `gbc_fire_emblem_reincarnation.py`, `gbc_harvest_moon.py`,
  `gbc_harvest_moon_2.py`, `gbc_harvest_moon_3.py`,
  `gbc_resident_evil_gaiden.py`, `gbc_smt_devil_children.py`,
  `gbc_super_mario_bros_deluxe.py`). The test harness skips them as stubs.

  Follow-up: either keep them as stubs, or implement them - as present plugins
  they read as real. See ROADMAP.
- [ ] Some games with non-standard encodings are not recognized
