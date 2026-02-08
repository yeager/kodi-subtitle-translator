# Subtitle Translator for Kodi

[![Kodi](https://img.shields.io/badge/Kodi-19%2B-blue.svg)](https://kodi.tv/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-yellow.svg)](https://python.org/)
[![Version](https://img.shields.io/badge/Version-0.9.2-orange.svg)](https://github.com/yeager/kodi-subtitle-translator)

Automatically translate embedded subtitles in your media files to your preferred language. No more hunting for subtitle files!

## ✨ Features

- **Automatic Detection** – Detects when no subtitle is available in your preferred language
- **Embedded Subtitle Extraction** – Extracts subtitles from MKV, MP4, and other containers using FFmpeg
- **External Subtitle Support** – Translate existing `.srt`, `.ass`, `.vtt` files alongside your video
- **Language Detection from Filenames** – Reads language codes from filenames (e.g., `movie.en.srt`, `movie.sv.srt`)
- **Auto-Load Target Subtitle** – Automatically loads existing subtitle in target language without prompting
- **Smart Source Selection** – Choose between embedded or external subtitles when both are available
- **10 Translation Services** – Free and paid options:
  - 🆓 **Lingva Translate** – Free, no API key required (default)
  - 🆓 **MyMemory** – Free, 1000 words/day
  - 🆓 **LibreTranslate** – Free, self-hostable
  - 🆓 **Argos Translate** – Offline translation
  - 💳 **DeepL Pro/Free** – High-quality translations
  - 💳 **Google Cloud Translation**
  - 💳 **Microsoft Azure Translator**
  - 🤖 **OpenAI GPT** – AI-powered context-aware translation
  - 🤖 **Anthropic Claude** – AI-powered translation
- **Automatic Fallback** – Falls back to alternative services on failure
- **Smart Caching** – Cached translations to avoid re-translating
- **Save Alongside Video** – Saves `movie.sv.srt` next to your video file
- **Auto-Resume Playback** – Pauses during translation, resumes when done
- **Multiple Output Formats** – SRT, ASS/SSA, WebVTT
- **Translation Profiles** – Standard, Anime, Kids, Formal, Casual
- **25 Languages** – Full UI translation support

## 📦 Installation

### From ZIP file
1. Download the latest release ZIP
2. In Kodi: **Settings → Add-ons → Install from zip file**
3. Select the downloaded ZIP file
4. The addon will be installed and started automatically

### Manual Installation
1. Clone or download this repository
2. Copy the folder to your Kodi addons directory:
   - **Linux:** `~/.kodi/addons/`
   - **Windows:** `%APPDATA%\Kodi\addons\`
   - **macOS:** `~/Library/Application Support/Kodi/addons/`
   - **Android:** `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/addons/`
3. Restart Kodi

### Android Installation

Kodi on Android works with this addon, but requires some extra setup for FFmpeg (needed to extract embedded subtitles).

#### Option 1: Use External Subtitle Files Only (No FFmpeg Needed)
If you only want to translate `.srt`, `.ass`, or `.vtt` files that are already next to your video files, **no FFmpeg is needed**. The addon will detect and offer to translate external subtitle files automatically.

#### Option 2: Install FFmpeg via Termux (for embedded subtitles)
1. Install [Termux](https://f-droid.org/en/packages/com.termux/) from F-Droid
2. In Termux, run: `pkg install ffmpeg`
3. In the addon's Expert settings, set **FFmpeg path** to:
   `/data/data/com.termux/files/usr/bin/ffmpeg`

#### Option 3: Place FFmpeg Binary Manually
1. Download a static FFmpeg binary for your Android architecture (ARM64/ARM/x86)
   - [FFmpeg static builds](https://johnvansickle.com/ffmpeg/) (use `arm64` for most modern devices)
2. Place the `ffmpeg` binary in Kodi's home directory:
   `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/ffmpeg`
3. Make it executable (via Termux or a file manager with root): `chmod +x ffmpeg`
4. The addon will auto-detect it, or set the path manually in Expert settings

#### Android Notes
- **Storage permissions:** Kodi needs storage access. Grant it in Android Settings → Apps → Kodi → Permissions
- **Scoped storage (Android 11+):** On Android 11 and later, file access is more restricted. Videos on external SD cards or USB drives may need to be accessed through Kodi's file manager rather than direct paths
- **Translation services that don't need FFmpeg:** All online translation services work on Android. Only extracting *embedded* subtitles from video files requires FFmpeg
- **Performance:** Translation speed depends on your network connection and the selected service. AI services (OpenAI, Anthropic) may be slower on mobile networks
- **Kodi versions:** Tested with Kodi 19 (Matrix), 20 (Nexus), and 21 (Omega) on Android

## ⚙️ Settings

Access via: **Settings → Add-ons → My add-ons → Services → Subtitle Translator → Configure**

Settings are organized by level. Change level via the gear icon in settings.

---

### 🟢 Basic (Level 0)

Essential settings for getting started.

| Setting | Description | Default |
|---------|-------------|---------|
| **Enable addon** | Turn the service on/off | ✅ On |
| **Target language** | Language to translate to | Swedish |
| **Translation service** | Which service to use | Lingva |

#### API Keys (shown when required)

| Service | Setting | Where to get |
|---------|---------|--------------|
| DeepL | DeepL API key | [deepl.com/pro-api](https://www.deepl.com/pro-api) |
| Google | Google Cloud API key | [cloud.google.com](https://cloud.google.com/translate) |
| Microsoft | Azure API key | [azure.microsoft.com](https://azure.microsoft.com/services/cognitive-services/translator/) |
| OpenAI | OpenAI API key | [platform.openai.com](https://platform.openai.com/api-keys) |
| Anthropic | Anthropic API key | [console.anthropic.com](https://console.anthropic.com/) |

---

### 🔵 Standard (Level 1)

Common settings most users will want to adjust.

| Setting | Description | Default |
|---------|-------------|---------|
| **Ask before translating** | Prompt before starting | ✅ On |
| **Save subtitle alongside video** | Save as `video.sv.srt` | ✅ On |
| **Show notifications** | Display progress | ✅ On |
| **Show progress dialog** | Visual progress bar | ✅ On |
| **Subtitle format** | Output format | SRT |
| **Translation profile** | Preset for content type | Standard |

#### Subtitle Formats

| Format | Description |
|--------|-------------|
| SRT | Simple, widely compatible |
| ASS/SSA | Supports styling, positioning |
| WebVTT | Web-friendly format |

#### Translation Profiles

| Profile | Description |
|---------|-------------|
| Standard | General-purpose translation |
| Anime | Preserves honorifics (-san, -kun, etc.) |
| Kids | Simplified language, censored profanity |
| Formal | Business/documentary style |
| Casual | Informal, conversational |

#### Service-Specific Options (shown when applicable)

| Service | Setting | Options |
|---------|---------|---------|
| OpenAI | Model | GPT-4o Mini, GPT-4o, GPT-4 Turbo |
| Anthropic | Model | Claude 3 Haiku, Sonnet, Opus |
| DeepL | Formality | Default, Formal, Informal |
| Microsoft | Region | West Europe, North Europe, East US, etc. |

---

### 🟡 Advanced (Level 2)

More options for experienced users.

| Setting | Description | Default |
|---------|-------------|---------|
| **Source language** | Language to translate from | Auto-detect |
| **Auto-translate** | Start without user prompt | ✅ On |
| **Cache translations** | Save for reuse | ✅ On |
| **Cache duration** | Days to keep cache | 30 |
| **Enable fallback** | Try other services on failure | ✅ On |
| **Fallback services** | Comma-separated list | mymemory,libretranslate |
| **Batch size** | Subtitles per API request | 20 |
| **Request timeout** | Seconds before timeout | 30 |

#### Service URLs (for self-hosted instances)

| Setting | Default |
|---------|---------|
| Lingva URL | https://lingva.ml |
| LibreTranslate URL | https://translate.argosopentech.com |
| LibreTranslate API key | (optional) |

---

### 🔴 Expert (Level 3)

Technical settings for power users.

| Setting | Description | Default |
|---------|-------------|---------|
| **Debug logging** | Verbose logging | ❌ Off |
| **Debug categories** | Which to log | all |
| **FFmpeg path** | Custom binary path | (auto) |
| **FFmpeg threads** | 0 = auto | 0 |
| **Max retries** | API retry attempts | 3 |
| **Retry delay** | Seconds between retries | 5 |
| **Rate limit** | Requests per minute | 10 |
| **Subtitle encoding** | Character encoding | UTF-8 |
| **OpenAI temperature** | Creativity (0-2) | 0.3 |
| **OpenAI base URL** | Custom API endpoint | (default) |

---

## 📄 External Subtitle Files

The addon can translate external subtitle files in addition to embedded subtitles.

### How it works

When you start playing a video, the addon checks for:
1. **Embedded subtitles** in the video file (MKV, MP4, etc.)
2. **External subtitle files** next to the video (e.g., `movie.en.srt`, `movie.eng.srt`)

### Source selection

| Scenario | Behavior |
|----------|----------|
| Both embedded + external found | Dialog asks which source to use |
| Only embedded found | Uses embedded (asks if "Ask before translating" is on) |
| Only external found | Uses external (asks if "Ask before translating" is on) |
| Neither found | Offers to browse for a subtitle file |

### Supported external formats

| Extension | Format |
|-----------|--------|
| `.srt` | SubRip |
| `.ass` / `.ssa` | Advanced SubStation Alpha |
| `.vtt` | WebVTT |
| `.sub` | MicroDVD (parsed as SRT) |

### File naming

The addon looks for external subtitles matching the video filename:

```
movie.mkv           # Your video
movie.en.srt        # ✅ Found (English)
movie.eng.srt       # ✅ Found (English)
movie.english.srt   # ✅ Found (English)
movie.srt           # ✅ Found (no language tag)
other.en.srt        # ❌ Not matched (different name)
```

### Network paths

External subtitles are supported on network paths (SMB/NFS), just like embedded subtitles.

---

## 🌐 Translation Services

### Free Services (No API Key)

| Service | Pros | Cons |
|---------|------|------|
| **Lingva** | Fast, no limits | Google Translate frontend |
| **MyMemory** | Good quality | 1000 words/day limit |
| **LibreTranslate** | Open source, self-hostable | Varies by instance |
| **Argos** | Works offline | Requires language packs |

### Paid Services (API Key Required)

| Service | Pros | Cons | Pricing |
|---------|------|------|---------|
| **DeepL** | Excellent quality | Limited languages | €5.49/month + usage |
| **Google** | Many languages | Per-character cost | $20/million chars |
| **Microsoft** | Good quality | Per-character cost | $10/million chars |

### AI Services (API Key Required)

| Service | Pros | Cons | Pricing |
|---------|------|------|---------|
| **OpenAI** | Context-aware, natural | Slower, more expensive | ~$0.15/million tokens |
| **Anthropic** | High quality | Slower | ~$0.25/million tokens |

---

## 🌍 Supported Languages

### Target Languages

| Code | Language | Code | Language | Code | Language |
|------|----------|------|----------|------|----------|
| sv | Swedish | pl | Polish | ja | Japanese |
| en | English | nl | Dutch | zh | Chinese (Simplified) |
| no | Norwegian | ru | Russian | zh-TW | Chinese (Traditional) |
| da | Danish | uk | Ukrainian | ko | Korean |
| fi | Finnish | cs | Czech | ar | Arabic |
| de | German | el | Greek | tr | Turkish |
| fr | French | hu | Hungarian | hi | Hindi |
| es | Spanish | ro | Romanian | th | Thai |
| it | Italian | he | Hebrew | vi | Vietnamese |
| pt | Portuguese | id | Indonesian | | |

### UI Languages (25)

Full interface translation: Swedish, English, German, French, Spanish, Italian, Dutch, Danish, Polish, Russian, Portuguese, Japanese, Chinese, Korean, Turkish, Arabic, Hindi, Thai, Vietnamese, Indonesian, Czech, Greek, Hungarian, Romanian, Ukrainian.

---

## 🔧 Requirements

- **Kodi 19 (Matrix)** or later
- **FFmpeg** – For extracting embedded subtitles (optional if only using external subtitle files)
  - Linux: Usually pre-installed (`apt install ffmpeg`)
  - Windows: [Download FFmpeg](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
  - Android: See [Android Installation](#android-installation) above
- **Internet connection** – For translation API access (except Argos)

---

## 📁 Project Structure

```
service.subtitletranslator/
├── addon.xml                 # Addon metadata (v0.9.2)
├── service.py                # Main service script
├── LICENSE                   # GPL-3.0-or-later
├── README.md                 # This file
├── lib/
│   ├── __init__.py
│   ├── dialogs.py            # UI dialogs
│   ├── progress_dialog.py    # Progress tracking
│   ├── subtitle_extractor.py # FFmpeg integration
│   ├── subtitle_parser.py    # SRT/ASS/VTT parsing
│   ├── translators.py        # Translation service adapters
│   └── advanced_features.py  # Profiles, caching, stats
└── resources/
    ├── icon.png              # Addon icon (512x512)
    ├── fanart.jpg            # Background (1920x1080)
    ├── settings.xml          # Settings definition (v2)
    └── language/             # 25 languages
        ├── resource.language.en_gb/
        ├── resource.language.sv_se/
        ├── resource.language.de_de/
        └── ...
```

---

## 🛠️ Troubleshooting

### Translation fails with 403 error
- LibreTranslate.com now requires API key
- Switch to **Lingva** or **MyMemory** (free, no key)
- Or use a different LibreTranslate instance

### Subtitles not extracted
- Ensure FFmpeg is installed and in PATH
- Check Expert settings for custom FFmpeg path
- Enable debug logging to see FFmpeg output

### Translation is slow
- Reduce batch size in Advanced settings
- Use a faster service (Lingva > AI services)
- Check your internet connection

### Playback doesn't resume
- Update to version 0.7.0+
- Check Kodi log for errors

---

## 🤝 Contributing

Contributions welcome!

- 🐛 Report bugs via GitHub Issues
- 💡 Suggest features
- 🌍 Improve translations
- 🔌 Add new translation services

---

## 📄 License

**GPL-3.0-or-later** – See [LICENSE](LICENSE) file.

---

## 👤 Author

**Daniel Nylander**
- 🌐 [danielnylander.se](https://danielnylander.se)
- 💻 [@yeager](https://github.com/yeager)

---

## 🙏 Credits

- [Kodi](https://kodi.tv/) – The ultimate entertainment center
- [FFmpeg](https://ffmpeg.org/) – Multimedia framework
- [Lingva](https://lingva.ml/) – Free translation frontend
- [LibreTranslate](https://libretranslate.com/) – Open-source translation
- [DeepL](https://www.deepl.com/) – Neural machine translation
- [OpenAI](https://openai.com/) – GPT language models
- [Anthropic](https://anthropic.com/) – Claude AI

---

**Enjoy your translated subtitles! 🎬🍿**
