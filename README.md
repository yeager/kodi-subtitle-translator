# Subtitle Translator for Kodi

[![GitHub Release](https://img.shields.io/github/v/release/yeager/kodi-subtitle-translator?label=version)](https://github.com/yeager/kodi-subtitle-translator/releases)
[![Transifex](https://img.shields.io/badge/translations-Transifex-blue)](https://app.transifex.com/danielnylander/kodi-subtitle-translator/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)

Automatically translate embedded and external subtitles in Kodi to your preferred language. Supports 10 translation services with automatic fallback.

## Features

- **Automatic subtitle translation** — translates subtitles on playback start
- **10 translation services** — Lingva (default, free), DeepL, Google Translate, Microsoft, OpenAI, Anthropic, LibreTranslate, Argos (offline), MyMemory, Yandex
- **Auto-fallback** — if selected service needs API key that's missing, falls back to Lingva
- **Embedded & external subtitles** — extracts embedded subs with FFmpeg, also handles .srt/.ass/.ssa/.sub/.vtt files
- **Translation profiles** — Anime, Kids, Documentary, etc.
- **25 UI languages** — fully translated via Transifex
- **Translation cache** — avoids re-translating same content
- **Android/Shield support** — automatic FFmpeg download, Termux detection

## Installation

### From Yeager Repository (recommended — auto-updates)

1. Download [repository.yeager-1.0.1.zip](https://yeager.github.io/kodi-repo/repository.yeager-1.0.1.zip)
2. In Kodi: **Add-ons → Install from zip file** → select the downloaded zip
3. Go to **Add-ons → Install from repository → Yeager Repository → Services**
4. Install **Subtitle Translator**

### Manual install

Download the latest zip from [Releases](https://github.com/yeager/kodi-subtitle-translator/releases) and install from zip in Kodi.

## FFmpeg (required for embedded subtitles)

FFmpeg is needed to extract subtitles embedded in video files (MKV, MP4, etc.). External subtitle files (.srt, etc.) work without FFmpeg.

| Platform | Installation |
|----------|-------------|
| **Windows** | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |
| **macOS** | `brew install ffmpeg` |
| **Linux** | `sudo apt install ffmpeg` or `sudo dnf install ffmpeg` |
| **Android/Shield** | The addon offers **automatic download** when FFmpeg is not found. One click — no manual steps needed. |

### Android/Shield manual alternative

If auto-download doesn't work:

1. Install [Termux](https://f-droid.org/packages/com.termux/) from F-Droid
2. Run: `termux-setup-storage` (grant permission)
3. Run: `pkg install ffmpeg`
4. Run: `cp $(which ffmpeg) ~/storage/shared/ffmpeg`

## Translation Services

| Service | API Key Required | Free Tier |
|---------|:---:|:---:|
| Lingva | ❌ | ✅ Unlimited |
| DeepL | ✅ | 500k chars/month |
| Google Translate | ✅ | Limited |
| Microsoft Translator | ✅ | 2M chars/month |
| OpenAI (GPT) | ✅ | Pay-per-use |
| Anthropic (Claude) | ✅ | Pay-per-use |
| LibreTranslate | ✅ | Self-hosted |
| Argos Translate | ❌ | ✅ Offline |
| MyMemory | ❌ | 5k chars/day |
| Yandex | ✅ | Limited |

## Settings

The addon has four settings levels: Basic, Standard, Advanced, and Expert. Configure via **Add-ons → My add-ons → Services → Subtitle Translator → Configure**.

## Compatibility

- **Kodi 19 (Matrix)** and newer (Python 3)
- **Kodi 22 (Piers)** nightly — tested and working
- **Platforms**: Windows, macOS, Linux, Android, Android TV (Nvidia Shield)

## Translations

UI translations managed via [Transifex](https://app.transifex.com/danielnylander/kodi-subtitle-translator/). Currently available in 25 languages including Swedish, German, French, Spanish, and more.

## License

GPL-3.0-or-later

## Author

Daniel Nylander — [danielnylander.se](https://danielnylander.se)
