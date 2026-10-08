# Known issues and limitations

What is **already broken or does not work**, as opposed to planned work —
that lives in `ROADMAP.md`. The split is deliberate: an issue is done when
the reproduction no longer reproduces, a task is done when the feature works,
and in one list they compete for attention incorrectly.

Check with `pytest tests/ -v`. A closed item moves to ROADMAP or is recorded
as resolved here, with the reason.

- [ ] Shortening a translation breaks round-trip — measured on the local
  corpus (32 non-stub ROMs, 74674 records; full run at
  `scripts_roms/out/census_console.log`). The class "a whitespace-only
  translation is written invisibly" did **not** reproduce: there are zero such
  records, blank translations never reach the write.
  - [x] **Visible `pad_byte` tail in the Golden Sun credits (107 records)** - closed.
    The cause was not `pad_byte` but the two record-length criteria it fed. Both
    now separate the region walk from the record walk:
    - the record walk takes the minimum run length itself
      (`_CREDITS_WALK_MIN_RUN` = 1) instead of reusing the probe length, and
      padding stays `0x20` - the area no longer loses records;
    - `_CREDITS_GAP` 0x40 -> 0x100, because gaps between credits grow with the
      shortening.

    With `pad_byte=0x00` the credits no longer collapse: 107 -> 41 before,
    108 of 109 now. One record is still lost: the density scan shifts 11 bytes
    forward and the first credit (`NINTENDO.` -> `NIN`) falls behind the boundary.
    That is recorded as an allowed loss in `test_shortening_credits_defects.py` -
    the collapse was 7 of 107.

    Census, whole corpus (74676 records): applied 64108 (85.85 %),
    `pad_visible` **0**, `third_value_corrupted` 0, `silent_no_write` 0,
    `lost_record` 1, **real damage 1 (0.00 %)** against 107 (0.14 %) before.

    **No invariant anchor found (hypothesis disproved).** `NINTENDO.` sits at
    `0x0F0AE4`, but that is itself the first credits record, so the probe
    shortens it (`NINTENDO.` -> `NIN`) and the anchor is gone on the patch.
    What the docstring claims sits `0x94` bytes earlier is not a pointer
    table either: the values there are `0x06010004, 0x06010008, ...` (GROM
    addresses in 0x06010000). No translation-invariant landmark exists in this
    ROM. The detector therefore still uses the length-dependent density
    scan, and the region still collapses under `pad_byte=0x00`; the visible
    tail is kept as the accepted compromise.

    **Next step and its verification (both rejected).** Taking the region from
    the fixed window does not survive `pad_byte=0x00` either: it leaves 41 of
    107 records, because the gaps between records grow with the size of the
    removal, so any gap walk scales with the shortening. Raising
    `_CREDITS_GAP` from 0x40 to 0x100 is worse: on the pristine ROM it adds 2
    false records (` and` @0x0F0BCC, `Maps` @0x0F0F2C) - continuations of
    real credit lines.

    Conclusion: no gap-threshold rule can hold the region together under 0x00
    padding. The direction that does not have to rediscover records is to write
    every credit to a fixed address range with explicit addresses, instead of
    scanning for them.
  - [x] **Latent loss of translations shorter than 5 characters** - CLOSED.
    The `_CREDITS_MIN_RUN` = 5 threshold drove both the region walk and the
    segment selection in `_ascii_credits_segments`, so a credit shorter than
    5 characters was absent from the manifest. The record walk now uses its own
    minimum (`_CREDITS_WALK_MIN_RUN` = 1), so selection follows length while the
    region does not. Measured: translations `K`, `Ka`, `Kar` into `Maps`
    @0x0F0F2C are written and read back. A longer translation is still refused
    as too long, which is correct (`Karta` = 5 bytes against 4 free).
    Anchor: `tests/test_shortening_credits_defects.py::TestGoldenSunCreditsNotMachineCode::test_short_credit_name_is_selected_and_writable`.

    The region boundary deliberately keeps the same threshold: at 1 it fires
    2 KB too early (`0x0F0339`), inside code rather than the credits.
  - [x] **`metroid_fusion_save_data` — CLOSED: it is not text.** The block
    looks like text (and was the only non-Golden-Sun `pad_visible` record) but
    it is save-slot signature data: `SAVE_END`, `Metroid_USVerE004`,
    `MetroidAGB-EUVerE004`, which the game compares byte for byte to validate a
    save. Any edit corrupts it, and shortening touched 67 of 104 bytes
    (measured). No pad fixes that. The segment stays visible in the manifest -
    it is a legitimate place for a translator to look - but declares
    `injectable=False`, so the injector refuses BEFORE writing instead of after.
    Anchor: `tests/test_shortening_credits_defects.py::TestMetroidSaveDataIsExtractOnly`.
    `[SPEED(2)]` or `[SPEED(1)]`. This is no longer a shift or a lost record but
    a substituted control code. Cause not established.
  - [x] **Tail cut by the decoder - FFTA CLOSED (7 records).** All 7 lost
    exactly one and the same last token: a name token with byte `C8` at the very
    end of the shortened string, right after the choice marker. After a single
    patch the bytes were correct, but on the **second** generation (translation
    taken from the panel, what the GUI does) the token was silently erased in
    the ROM: 3 bytes changed, no refusal, no report entry.
    **The cause was not compression but display.** `_strip_token_tail`
    (`core/extractor.py:526`, `:570` -> `strip_raw_token_tail`,
    `core/decoder.py:106-109`) strips a trailing run of raw tokens from the
    *shown* record. Byte `0xC8` is absent from `CHARMAP_FFTA_MULTI`, decodes as
    `[C8]`, while the choice marker is a named token; exactly `[C8]` vanished.
    The cause previously recorded here was the shrinking segment window - that
    is wrong, both proposed fixes were no-ops.
    **Fix:** the existing `trailing_raw_token` gate, already present in the
    generic path, was moved into the compressed path (`core/injector.py`,
    `_ends_with_raw_token` + `_compressed_original_text`). A translation ending
    with a raw token that the original did not end with is now refused with that
    reason in `last_affix_report`, visible to both the census and the GUI.
    Side effect: FFTA now reports **0 damage** (was 7), no record is lost and
    the bytes of refused segments stay untouched.
    Anchor: `tests/test_shortening_credits_defects.py::TestCompressedTrailingRawToken`.
  - [x] **Tail cut by the decoder, 4 records (Oracle).** Closed. Cause: the Oracle
    of Seasons dictionary translation changes text, but the dictionary itself is
    shared: `0x02..0x05` occupy two bytes and address a slot via
    `((b - 2) << 8) | next`, i.e. slots 0..1023. Measured on the current ROM:
    all 1024 slots are cited, referenced by 1765 of 1794 text records (plus 17
    nested dictionary-to-dictionary references). Decision: `oracle_seasons_dict`
    is `injectable: False` with `not_writable_reason: 'shared_dictionary'`, so
    Oracle text records go through the normal path. Real damage dropped to zero.
  - [ ] **Oracle of Seasons dictionary is not translatable (copy-on-write).**
    The refusal above is a workaround, not a fix. Real fix: rewrite every cited
    record as self-contained text without `0x02..0x05` codes. Cost: +ROM
    (20-60 bytes per record against 2, 1765 records), does not scale to 4-32 MB
    GBA without a relocation pool. See ROADMAP.

  - [x] **Remaining corruption, 2 records** (GS:TLA) - closed. The token walk for
    `0x11` in `plugins/gba_golden_sun_tla.py` glued **all** consecutive control
    bytes into one token, though its own docstring describes two. `11 04 11` became
    `{11 04 11}` instead of `{11 04}{11}`. The group is now capped at two bytes, as
    documented. The remaining record differed by grouping of text only, so
    `readback_census_probe.py` now compares canonically normalised text (grouping
    does not affect the bytes, so the last record was counted as damage by mistake).
    GS:TLA: damage **0**, applied 10 471 (84.03 %).
  - [x] **Golden Sun: The Lost Age credits are now extracted.** Closed: 101
    credits found, previously not extracted at all. The block lies at
    `0x1A1A10..0x1A2058` and is the same plain-ASCII shape as the GS credits, so
    the common code `credits_region` / `ascii_credits_segments` in
    `plugins/gba_golden_sun.py` is reused; TLA only supplies its own window and
    prefix. Anchor: `tests/test_golden_sun_tla.py::TestTLACredits`.

    One consequence measured along the way: the density scan alone does not pin
    the region start, because padding removes printable bytes, so the scan's
    walk jumps forward by 82 bytes. `TLA_CREDITS_AT` / `_CREDITS_AT` are
    therefore per-revision constants with a check (`_looks_like_credits`): if no
    dense block of credit lines follows, the scan stays in charge. Measured:
    lost credits 5 on TLA and 1 on GS down to 0 on both.
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
