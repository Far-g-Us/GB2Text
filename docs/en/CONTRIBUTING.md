# Contributing to GB2Text

Thank you for your interest in contributing to GB2Text — the GB Text Extraction Tool! This document explains how you can help develop the project while respecting legal boundaries.

## ⚠️ Important Legal Notice

**Before contributing, please review our [LICENSE](../../LICENSE.md).**

This project:
- Does NOT contain or distribute any commercial ROM files
- Is intended ONLY for use with legally-owned ROM files (homebrew or legally acquired)
- Must NOT be used to facilitate unauthorized copying or distribution of copyrighted content

**Violations of these rules will result in rejection of your contribution and possible removal from the project.**

## How to Contribute Safely

### 1. Configuration Files (`plugins/config/`)

- **Allowed** to add configurations for:
  - Games whose ROM files you legally own (homebrew or commercial)
  - Generic examples that demonstrate the configuration format

- **NOT allowed** to add:
  - Any copyrighted game text, dialogue, or assets
  - ROM files, ROM dumps, or links to download ROMs
  - Instructions for acquiring ROM files you do not legally own

- **Example of a safe configuration**:
  ```json
  {
    "game_id_pattern": "^MY_HOMEBREW_[A-Z0-9]+_[0-9A-F]{2}$",
    "segments": [
      {
        "name": "main_text",
        "start": "0x4000",
        "end": "0x5000",
        "charmap": {
          "0x20": " ",
          "0x41": "A",
          "0x42": "B",
          "0xFF": "[END]"
        }
      }
    ]
  }
  ```

### 2. Character Tables and Encodings

- **Allowed** to add:
  - Basic ASCII characters (A-Z, a-z, 0-9, punctuation)
  - Generic Japanese characters (hiragana, katakana) not tied to specific games
  - Character mappings reverse-engineered from games whose ROM files you legally own (offsets and encodings only, no extracted dialog text)

- **NOT allowed** to add:
  - Extracted dialogue text or item names from commercial games
  - Full ROM data or any copyrighted asset

### 3. Guides (`guides/`)

- **Allowed** to create guides for:
  - How to configure and use the tool
  - Reverse-engineering workflows using your own legally-owned ROMs

- **NOT allowed** to create guides for:
  - Working with unauthorized ROM copies
  - Reproducing copyrighted game content

## Contribution Process

### 1. Create an Issue Before Starting Work
- Discuss whether your idea aligns with the project's legal requirements
- Ensure your contribution does not infringe on copyrights

### 2. Create a Branch for Your Work

```bash
git checkout -b feature/your-feature-name
```

### 3. Follow Code Standards
- Add the legal notice header to every source file
- Write clear comments in English
- Keep code style consistent with the existing codebase
- Add tests for new functionality

### 4. Create a Pull Request
- Clearly explain how your contribution meets legal requirements
- Specify which games (if any) are supported by your contribution
- Confirm you follow all rules in this document
- Include tests for new functionality when applicable

## Testing Your Changes

Before submitting a PR, run the test suite:

```bash
pytest tests/ -v
```

Ensure all tests pass and coverage remains above 80% for core modules.

## 🐞 Debugging and Diagnostics

If you encounter a problem, please collect diagnostic information before creating an issue:

1. Make sure you have `sha1sum` installed (usually part of coreutils)
2. Run the diagnostic script:
```bash
chmod +x scripts/diagnostics.sh
./scripts/diagnostics.sh your_file.gb
# or on Windows:
scripts\diagnostics.bat your_file.gb
```
3. Attach the resulting directory to your GitHub issue

This will significantly speed up the debugging process.

## Examples of Safe Contributions

**Good examples:**
- Adding support for a new compression algorithm (game-agnostic)
- Improving the automatic charmap detection algorithm
- Creating templates for homebrew game plugins
- Fixing bugs in core extraction/injection logic
- Improving test coverage
- Adding new language support to the UI
- Adding a game plugin with verified offsets/encodings for a ROM you legally own (without including extracted text)

**Bad examples:**
- Including extracted dialog or copyrighted text in the repository
- Including ROM files or links to download ROMs
- Creating guides for working with unauthorized game copies
- Adding copyrighted dialogue text to the repository

## Mandatory Confirmation

Before your contribution is accepted, you must confirm:

> "I confirm that my contribution:
> 1. Does not contain copyrighted game text, ROM files, or links to ROM downloads
> 2. Is intended ONLY for use with legally-owned ROM files
> 3. Does not infringe on third-party copyrights
> 4. Complies with all requirements in the LICENSE and this document"

## Code Style

- Python 3.11+ compatible
- Use type hints where appropriate
- Follow PEP 8 style guidelines
- Run `ruff check .` before submitting
- Add docstrings to public functions and classes

## Thank You

Your compliance with these rules helps keep the project safe and accessible to legitimate users. Together, we can create a powerful tool for research and educational purposes while respecting intellectual property rights.

Nintendo, Pokémon, The Legend of Zelda, and all related trademarks are the property of their respective owners.