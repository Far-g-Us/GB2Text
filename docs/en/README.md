# GB2Text

[![License](https://img.shields.io/badge/License-Custom-blue.svg)](../../LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)

**GB Text Extraction Tool** — a universal tool for extracting and translating text from Game Boy, Game Boy Color, and Game Boy Advance ROM files with plugin support.

<p align="center">
  <img src="../../assets/readme/hero.svg" width="100%" alt="GB2Text: extract and reinsert text from Game Boy, Game Boy Color and Game Boy Advance ROM files with a plugin API">
</p>

## ⚠️ Legal Disclaimer

**This project is intended ONLY for analysis of ROM files that you legally own.** 
You must use this tool ONLY with homebrew ROM files that you created yourself or with commercial ROM files that you have legally acquired.

Nintendo, Pokémon, The Legend of Zelda, and all related trademarks are the property of their respective owners.

**This project does NOT contain or distribute any commercial ROM files.**

## 🚀 Features

- Extract text from GB, GBC, and GBA ROM files
- GUI interface for easy text editing and translation
- Support for custom character maps
- Automatic text segment detection
- Text injection back into ROM files
- Plugin system for game-specific configurations
- Support for multiple languages (English, Japanese, Russian)

## 📦 Installation

### Requirements
- Python 3.11
- tkinter (usually included with Python)

### Setup
```bash
git clone https://github.com/Far-g-Us/GB2Text.git
cd GB2Text
# Create a virtual environment (recommended — do NOT install dependencies globally)
python -m venv .venv
# Activate it:
#   Windows:
.venv\Scripts\activate
#   Linux / macOS:
#   source .venv/bin/activate
pip install -r requirements.txt
```
### 🖥️ Usage
#### GUI Mode (Recommended) 

```bash
python main.py --gui
# Or with a specific ROM file
python main.py --gui your_game.gb
```

#### Command Line Mode
```bash
# Extract text to console
python main.py your_game.gb

# Extract text to JSON
python main.py your_game.gb --output json
```

## 🧩 Creating Custom Configurations 

#### This tool is designed to work with ROM files you legally own. To create a configuration for your game: 

- Launch the GUI with `python main.py --gui`
- Load your ROM file
- Use the "Create Configuration" button in Settings tab
- Save the configuration to `plugins/config/` directory

Leave static game-specific configuration files in `plugins/config/` out of the repository unless they are approved by the maintainers. Game plugins (`.py`) follow the contribution process in [CONTRIBUTING](CONTRIBUTING.md).

### Example configuration structure:
```json
{
  "game_id_pattern": "^HOME_BREW_[A-Z0-9]+_[0-9A-F]{2}$",
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

## 🌐 Multi-language Support 

#### The tool supports multiple encoding types: 

- English (ASCII-based)
- Japanese (Katakana/Hiragana)
- Russian (Cyrillic)

Configure the encoding in the Settings tab of the GUI. 

## 🤖 Agent API / Automation

A dedicated `api/` module provides programmatic access for agents, scripts, and headless workflows — three interfaces sharing one contract:

| Interface | Entry point | Notes |
|-----------|-------------|-------|
| **Python SDK** | `from api import _core` (REPL / Jupyter) | `resolve_rom`, `detect`, `extract`, `inject`, `list_plugins`, `get_version`, `load_json_file` |
| **CLI** | `python -m api.cli <command> --json` | Subcommands: `plugins`, `detect`, `extract`, `inject`, `serve` — exit codes 0/1/2 |
| **HTTP / JSON** | `python -m api.cli serve` (default 127.0.0.1:8080) | Endpoints: `/health`, `/plugins`, `/detect`, `/extract`, `/inject` — body-size limits, timeout, 503 BUSY |

All three return a stable response schema: `{"ok": bool, "data": ... | "error": {"code", "message"}}`.

Full contract, security design, and examples: **[API_AGENTS.md](API_AGENTS.md)**.

### 🛡️ Legal Safety Guidelines 

#### This project follows strict legal guidelines: 

- No commercial ROM files are included
- Plugins define offsets and encodings only; no copyrighted game text is stored in the repository
- `core/manifests/*.json` contain only numeric ROM structures (text offsets, free-after sizes, pointer offsets) generated locally from your own legally owned ROM via `scripts_roms/generate_manifest.py`; no game text, assets, or code
- Only document/configure ROMs that you legally own
- Clear legal disclaimers in all documentation

### 📜 License 

#### This project is licensed under a custom license agreement (see [LICENSE](../../LICENSE.md) for full details) that requires: 

- Use ONLY with ROM files you have legally acquired and have the right to analyze
- No creating or distributing unauthorized copies of commercial games
- No circumventing copyright protection mechanisms
- No infringing intellectual property rights of game developers/publishers 
  
### 🤝 Contributing 

Please read our [CONTRIBUTING](CONTRIBUTING.md)  for details on our code of conduct and the process for submitting pull requests. 

We welcome contributions that:

- Improve the core tool
- Add support for new games you legally own
- Enhance the documentation
- Fix bugs

### 🙏 Acknowledgments 

- Thanks to the homebrew community for inspiration
- Special thanks to contributors who helped make this project possible

## 🧪 Testing

Run tests with:
```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

See [tests/README.md](../../tests/README.md) for detailed testing documentation.