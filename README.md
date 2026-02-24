# Subtitle Translator for Kodi

[![GitHub Release](https://img.shields.io/github/v/release/yeager/kodi-subtitle-translator?label=version)](https://github.com/yeager/kodi-subtitle-translator/releases)
[![Transifex](https://img.shields.io/badge/translations-Transifex-blue)](https://app.transifex.com/danielnylander/kodi-subtitle-translator/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)

Automatically translate embedded and external subtitles in Kodi to your preferred language. Supports 10 translation services with automatic fallback.

## Features

- **Automatic subtitle translation** — translates subtitles on playback start
- **Pure Python MKV extractor** — extracts embedded subtitles directly from MKV files without FFmpeg, streaming over SMB/NFS (no temp copy needed)
- **10 translation services** — Lingva (default, free), DeepL, Google Translate, Microsoft, OpenAI, Anthropic, LibreTranslate, Argos (offline), MyMemory, Yandex
- **Auto-fallback** — if selected service needs API key that's missing, falls back to Lingva
- **Embedded & external subtitles** — built-in MKV parser for embedded subs, also handles .srt/.ass/.ssa/.sub/.vtt files
- **Translation profiles** — Anime, Kids, Documentary, etc.
- **25 UI languages** — fully translated via Transifex
- **Translation cache** — avoids re-translating same content
- **Android/Shield support** — works out of the box, no FFmpeg needed for MKV files

## Installation

### From Yeager Repository (recommended — auto-updates)

1. Download [repository.yeager-1.0.1.zip](https://yeager.github.io/kodi-repo/repository.yeager-1.0.1.zip)
2. In Kodi: **Add-ons → Install from zip file** → select the downloaded zip
3. Go to **Add-ons → Install from repository → Yeager Repository → Services**
4. Install **Subtitle Translator**

### Manual install

Download the latest zip from [Releases](https://github.com/yeager/kodi-subtitle-translator/releases) and install from zip in Kodi.

## FFmpeg (optional)

**FFmpeg is optional.** The addon has a built-in pure Python MKV subtitle extractor that works without FFmpeg, including over SMB/NFS network paths. This is the primary extraction method on all platforms.

FFmpeg is used as a **fallback** for non-MKV containers (MP4, AVI, etc.) or if the built-in extractor fails. External subtitle files (.srt, etc.) never need FFmpeg.

| Platform | Installation |
|----------|-------------|
| **Windows** | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |
| **macOS** | `brew install ffmpeg` |
| **Linux** | `sudo apt install ffmpeg` or `sudo dnf install ffmpeg` |
| **Android/Shield** | The addon offers **automatic download** if FFmpeg fallback is needed. One click — no manual steps. |

### Android/Shield notes

The built-in Python extractor is the primary method on Android, avoiding FFmpeg permission issues with Android's scoped storage. FFmpeg auto-download is available as fallback if needed.

## Translation Services

| Service | API Key | Free Tier | Speed |
|---------|:---:|:---:|:---:|
| **Lingva** (default) | ❌ | ✅ Unlimited | ~50 lines/min |
| **DeepL** | ✅ | 500k chars/month | ⚡ Fast (batch) |
| Google Translate | ✅ | Limited | ⚡ Fast |
| Microsoft Translator | ✅ | 2M chars/month | ⚡ Fast |
| OpenAI (GPT) | ✅ | Pay-per-use | ⚡ Fast (batch) |
| Anthropic (Claude) | ✅ | Pay-per-use | ⚡ Fast (batch) |
| LibreTranslate | ✅ | Self-hosted | Medium |
| Argos Translate | ❌ | ✅ Offline | Medium |
| MyMemory | ❌ | 5k chars/day | Medium |
| Yandex | ✅ | Limited | ⚡ Fast |

> **Tip:** Lingva is free but rate-limited (~50 requests/min). For faster translations, use DeepL Free (500k chars/month) or set up your own LibreTranslate instance.

## Settings

The addon has four settings levels: Basic, Standard, Advanced, and Expert. Configure via **Add-ons → My add-ons → Services → Subtitle Translator → Configure**.

## Compatibility

- **Kodi 19 (Matrix)** and newer (Python 3)
- **Kodi 20 (Nexus)**, **21 (Omega)**, **22 (Piers)** — tested and working
- **Platforms**: Windows, macOS, Linux, Android, Android TV (Nvidia Shield)
- **Network**: SMB, NFS, local files — all supported via built-in MKV parser

## Translations

UI translations managed via [Transifex](https://app.transifex.com/danielnylander/kodi-subtitle-translator/). Currently available in 25 languages including Swedish, German, French, Spanish, and more.

## License

GPL-3.0-or-later

## Author

Daniel Nylander — [danielnylander.se](https://danielnylander.se)
