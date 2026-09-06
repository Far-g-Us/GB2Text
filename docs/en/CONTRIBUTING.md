# Contributing to GB Text Extraction Framework

Thank you for your interest in contributing to GB Text Extraction Framework! This document explains how you can help develop the project while respecting legal boundaries.

## ⚠️ Important Legal Notice

**Before contributing, please review our [LICENSE](../../LICENSE.md).**

This project:
- Does NOT contain or distribute any commercial ROM files
- Is intended ONLY for use with legally-owned ROM files (homebrew or legally acquired)
- Must NOT be used to facilitate unauthorized copying or distribution of copyrighted content

**Violations of these rules will result in rejection of your contribution and possible removal from the project.**

## How to Contribute Safely

### 1. Configuration Files (`plugins/config/`)

- **Allowed** to add configurations ONLY for:
  - Homebrew games you created yourself
  - Generic examples not tied to real commercial games

- **NOT allowed** to add configurations for:
  - Commercial games (Pokémon, Zelda, etc.)
  - ROM files you do not legally own

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

- **NOT allowed** to add:
  - Game-specific character mappings (e.g., Pokémon abbreviations like "PK", "MN")
  - Exact charmap tables matching commercial game structures
  - Elements that could be considered trademarked content

### 3. Guides (`guides/`)

- **Allowed** to create guides for:
  - Homebrew games you created
  - General framework usage principles

- **NOT allowed** to create guides for:
  - Specific commercial games
  - Working with unauthorized ROM copies

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
- Avoid mentioning commercial games in code
- Write clear comments in English
- Keep code style consistent with the existing codebase

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

**Bad examples:**
- Adding a plugin with exact charmap tables for commercial games
- Including specific text segment addresses from commercial ROMs
- Creating guides for working with unauthorized game copies
- Adding copyrighted dialogue text to the repository

## Mandatory Confirmation

Before your contribution is accepted, you must confirm:

> "I confirm that my contribution:
> 1. Does not contain information specific to commercial games
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
