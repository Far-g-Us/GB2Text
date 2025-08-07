# GB Text Extraction Framework

[![License](https://img.shields.io/badge/License-Custom-blue.svg)](../../LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)

A universal framework for extracting and translating text from Game Boy, Game Boy Color, and Game Boy Advance ROM files with plugin support.

[//]: # (![GB Text Extractor Screenshot]&#40;screenshot.png&#41;)

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
git clone https://github.com/yourusername/gb-text-extractor.git
cd gb-text-extractor
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

#### This framework is designed to work with ROM files you legally own. To create a configuration for your game: 

- Launch the GUI with `python main.py --gui`
- Load your ROM file
- Use the "Create Configuration" button in Settings tab
- Save the configuration to `plugins/config/` directory

Important: Only create configurations for homebrew games you created yourself. Do not create configurations for commercial games.

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

#### The framework supports multiple encoding types: 

- English (ASCII-based)
- Japanese (Katakana/Hiragana)
- Russian (Cyrillic)

Configure the encoding in the Settings tab of the GUI. 

### 🛡️ Legal Safety Guidelines 

#### This project follows strict legal guidelines: 

- No commercial ROM files are included
- No game-specific plugins for commercial games
- All configurations must be for homebrew games
- Clear legal disclaimers in all documentation

### 📜 License 

#### This project is licensed under a custom license agreement that explicitly prohibits: 

- Use with illegal ROM copies
- Distribution of commercial game configurations
- Commercial use of the framework

See [LICENSE](LICENSE.md) for full details. 
 
### 🤝 Contributing 

Please read our [CONTRIBUTING](CONTRIBUTING.md)  for details on our code of conduct and the process for submitting pull requests. 

We welcome contributions that:

- Improve the core framework
- Add support for new homebrew games
- Enhance the documentation
- Fix bugs

We do NOT accept contributions that: 

- Add support for commercial games
- Include game-specific configurations for commercial titles
- Contain references to commercial game elements

### 🙏 Acknowledgments 

- Thanks to the homebrew community for inspiration
- Special thanks to contributors who helped make this project possible
     