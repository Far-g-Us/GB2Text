# 📥 Download GB2Text

Get GB2Text, the GB text extraction &amp; translation tool, from the official
source only.

## ⚠️ Legal Disclaimer

> **This tool is intended ONLY for analysis of ROM files that you legally own.**
> Read, extract, translate, or reinsert text ONLY in ROM files that you
> homebrew-created yourself or legally acquired and have the right to analyze —
> never in ROM files you downloaded or do not own.
>
> Nintendo, Pokémon, The Legend of Zelda, and all related trademarks are the
> property of their respective owners. This project is not affiliated with or
> endorsed by Nintendo.
>
> **This project does NOT contain or distribute any commercial ROM files.**

## 🗔 Windows

- ✅ **Windows 10/11** (64-bit) — standalone `GB2Text.exe`
  (no Python required)
- ✅ Portable — runs without installation, keeps settings in
  `%APPDATA%\GB2Text\`
- ✅ DPI-aware, tested on Windows 10/11

### [⬇️ Download GB2Text.exe (Windows)](https://github.com/Far-g-Us/GB2Text/releases/latest/download/GB2Text.exe)

*No Android / iOS builds. Windows build is the official release channel.*

## 🐧 Linux / 🍎 macOS

These platforms are not shipped as prebuilt binaries in this repo. Build from
source (Python 3.11+):

```bash
git clone https://github.com/Far-g-Us/GB2Text.git
cd GB2Text
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py --gui             # graphical mode
```

## 🔌 Plugins

GB2Text works with ROM files that you legally own. Plugins add support for
specific games — see [Supported Games](../../SUPPORTED_GAMES.md) and the
[community plugin catalog](README.md#-community-plugins--custom-fonts).

> Only ever use GB2Text with ROM files you have legally acquired or created.
