# Subtitle Translator for Kodi

[![Kodi](https://img.shields.io/badge/Kodi-19%2B-blue.svg)](https://kodi.tv/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-yellow.svg)](https://python.org/)

Automatically translate embedded subtitles in your media files to your preferred language. No more hunting for subtitle files!

## ✨ Features

- **Automatic Detection** – Detects when no subtitle is available in your preferred language
- **Embedded Subtitle Extraction** – Extracts subtitles from MKV, MP4, and other containers using FFmpeg
- **Multiple Translation Services** – Choose from free and paid services:
  - 🆓 **LibreTranslate** – Free, open-source, self-hostable
  - 🆓 **MyMemory** – Free tier available (1000 words/day)
  - 🆓 **Lingva Translate** – Free Google Translate frontend
  - 💳 **DeepL** – High-quality translations (API key required)
  - 💳 **DeepL Free** – Free tier with API key
  - 💳 **Google Cloud Translation** – API key required
  - 💳 **Microsoft Translator** – API key required
- **Smart Caching** – Translated subtitles are cached to avoid re-translating
- **Multiple Output Formats** – SRT, ASS/SSA, WebVTT
- **Preserve Styling** – Keeps original timing and formatting (ASS/SSA)
- **20+ Languages Supported** – Swedish, Norwegian, Danish, Finnish, German, French, Spanish, Italian, Portuguese, Polish, Dutch, Russian, Japanese, Chinese, Korean, and more

## 📦 Installation

### From ZIP file
1. Download the latest release ZIP
2. In Kodi: **Settings → Add-ons → Install from zip file**
3. Select the downloaded ZIP file
4. The addon will be installed and started automatically

### Manual Installation
1. Clone or download this repository
2. Copy the `service.subtitletranslator` folder to your Kodi addons directory:
   - **Linux:** `~/.kodi/addons/`
   - **Windows:** `%APPDATA%\Kodi\addons\`
   - **macOS:** `~/Library/Application Support/Kodi/addons/`
3. Restart Kodi

## ⚙️ Configuration

Access settings via **Settings → Add-ons → My add-ons → Services → Subtitle Translator → Configure**

### General Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Enable addon | Turn the service on/off | On |
| Auto-translate | Automatically translate when subtitle is missing | On |
| Show notifications | Display progress notifications | On |
| Ask before translating | Prompt before starting translation | On |

### Language Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Target language | Language to translate subtitles to | Swedish |
| Source language | Preferred source language (or Auto) | English |
| Fallback languages | Comma-separated list of fallback languages | en,sv |

### Translation Service Configuration

#### Free Services (No API Key Required)

**LibreTranslate**
```
Service: LibreTranslate
URL: https://libretranslate.com (or self-hosted instance)
API Key: (optional, for private instances)
```

**MyMemory**
```
Service: MyMemory
No configuration required (1000 words/day free)
```

**Lingva Translate**
```
Service: Lingva
URL: https://lingva.ml (or alternative instance)
```

#### Paid Services (API Key Required)

**DeepL**
```
Service: DeepL / DeepL Free
API Key: Your DeepL API key
Formality: Default / Formal / Informal
```
Get your API key at: https://www.deepl.com/pro-api

**Google Cloud Translation**
```
Service: Google Translate
API Key: Your Google Cloud API key
```
Get your API key at: https://cloud.google.com/translate

**Microsoft Translator**
```
Service: Microsoft Translator
API Key: Your Azure subscription key
Region: westeurope (or your region)
```
Get your API key at: https://azure.microsoft.com/services/cognitive-services/translator/

### Subtitle Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Output format | SRT, ASS/SSA, or WebVTT | SRT |
| Preserve timing | Keep original subtitle timing | On |
| Preserve formatting | Keep styling (ASS/SSA only) | On |
| Cache translations | Save translated subtitles for reuse | On |
| Cache duration | Days to keep cached translations | 30 |
| Save alongside video | Save subtitle file next to video | Off |

### Advanced Settings

| Setting | Description | Default |
|---------|-------------|---------|
| FFmpeg path | Custom FFmpeg binary path | (auto-detect) |
| Batch size | Subtitles per translation request | 50 |
| Request timeout | API timeout in seconds | 30 |
| Debug logging | Enable verbose logging | Off |

## 🔧 Requirements

- **Kodi 19 (Matrix)** or later
- **FFmpeg** – For extracting embedded subtitles
  - Usually pre-installed on Linux
  - Windows: [Download FFmpeg](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
- **Internet connection** – For translation API access

## 🌐 Supported Languages

| Code | Language | Code | Language |
|------|----------|------|----------|
| sv | Swedish | pl | Polish |
| no | Norwegian | nl | Dutch |
| da | Danish | ru | Russian |
| fi | Finnish | ja | Japanese |
| de | German | zh | Chinese |
| fr | French | ko | Korean |
| es | Spanish | ar | Arabic |
| it | Italian | tr | Turkish |
| pt | Portuguese | hi | Hindi |
| en | English | uk | Ukrainian |

## 📁 File Structure

```
service.subtitletranslator/
├── addon.xml              # Addon metadata
├── service.py             # Main service script
├── LICENSE                # MIT License
├── README.md              # This file
├── lib/
│   ├── __init__.py
│   ├── subtitle_extractor.py  # FFmpeg integration
│   ├── subtitle_parser.py     # SRT/ASS/VTT parsing
│   └── translators.py         # Translation service adapters
└── resources/
    ├── icon.png           # Addon icon (512x512)
    ├── fanart.jpg         # Background image (1920x1080)
    ├── settings.xml       # Settings definition
    └── language/
        ├── resource.language.en_gb/
        │   └── strings.po
        └── resource.language.sv_se/
            └── strings.po
```

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Add support for more translation services
- Improve translations

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Daniel Nylander**
- Website: [danielnylander.se](https://danielnylander.se)
- GitHub: [@yeager](https://github.com/yeager)

## 🙏 Credits

- [Kodi](https://kodi.tv/) – The ultimate entertainment center
- [FFmpeg](https://ffmpeg.org/) – Multimedia framework
- [LibreTranslate](https://libretranslate.com/) – Open-source translation API
- [DeepL](https://www.deepl.com/) – High-quality neural machine translation

---

**Enjoy your translated subtitles! 🎬**
