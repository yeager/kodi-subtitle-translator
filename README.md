# Subtitle Translator for Kodi

[![GitHub Release](https://img.shields.io/github/v/release/yeager/kodi-subtitle-translator?label=version)](https://github.com/yeager/kodi-subtitle-translator/releases)
[![Transifex](https://img.shields.io/badge/translations-Transifex-blue)](https://app.transifex.com/danielnylander/kodi-subtitle-translator/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)

Automatically translate embedded and external subtitles in Kodi to your preferred language. Supports 10 translation services with automatic fallback and context-aware translation using media metadata.

## Features

- **Automatic subtitle translation** — translates subtitles on playback start
- **Context-aware translation** — uses film title, plot, genre, season/episode for better translations
- **Pure Python MKV extractor** — extracts embedded subtitles directly from MKV files without FFmpeg, streaming over SMB/NFS (no temp copy needed)
- **10 translation services** — Lingva (default, free), DeepL, Google Translate, Microsoft, OpenAI, Anthropic, LibreTranslate, Argos (offline), MyMemory, Yandex
- **Auto-fallback** — if selected service needs API key that's missing, falls back to Lingva
- **Embedded & external subtitles** — built-in MKV parser for embedded subs, also handles .srt/.ass/.ssa/.sub/.vtt files
- **Translation profiles** — Anime, Kids, Documentary, etc.
- **25 UI languages** — fully translated via Transifex
- **Translation cache** — avoids re-translating same content
- **Android/Shield support** — works out of the box, no FFmpeg needed for MKV files

## Context-Aware Translation (NEW in v0.11.0)

The addon automatically extracts metadata from the currently playing media and sends it to the translation engine for better, more accurate translations:

| Metadata | Used for |
|----------|----------|
| **Title / Original title** | Identify the work, keep proper nouns consistent |
| **Plot / Synopsis** | Resolve ambiguous words (e.g. "cell" = prison cell vs. biological cell) |
| **Genre** | Adjust tone (comedy = colloquial, drama = formal, sci-fi = technical) |
| **Season / Episode** | TV show continuity, recurring character names |
| **Year** | Period-appropriate language |
| **Tagline** | Quick thematic context |

### How it works per engine

- **DeepL Pro** — sends context via the `context` parameter (influences word choice without appearing in output)
- **OpenAI / Anthropic** — injects media info into the system prompt for fully context-aware translation
- **Other engines** — gracefully ignored (no context support)

### Example

Without context, "He's serving time in the yard" could be mistranslated. With the plot context "A prison drama about...", the translator correctly interprets "yard" as "gården" (prison yard) instead of "trädgården" (garden).

## DeepL Pro Features

When using DeepL with a Pro API key, the addon uses all available quality features:

| Feature | Effect |
|---------|--------|
| `model_type: quality_optimized` | Best possible translation quality |
| `formality: prefer_less` | Natural, less formal language (supported for Swedish, German, French, etc.) |
| `preserve_formatting` | Keeps whitespace, line breaks, and formatting intact |
| `split_sentences: nonewlines` | Preserves subtitle line structure |
| `context` | Media info for better word choice |
| `glossary_id` | Custom terminology lists |
| Auto endpoint detection | Detects PRO vs Free from API key (`:fx` suffix = Free) |

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

## Translation Services

| Service | API Key | Free Tier | Context | Speed |
|---------|:---:|:---:|:---:|:---:|
| **Lingva** (default) | ❌ | ✅ Unlimited | ❌ | ~50 lines/min |
| **DeepL** | ✅ | 500k chars/month | ✅ Full | ⚡ Fast (batch) |
| **OpenAI** (GPT) | ✅ | Pay-per-use | ✅ Full | ⚡ Fast (batch) |
| **Anthropic** (Claude) | ✅ | Pay-per-use | ✅ Full | ⚡ Fast (batch) |
| Google Translate | ✅ | Limited | ❌ | ⚡ Fast |
| Microsoft Translator | ✅ | 2M chars/month | ❌ | ⚡ Fast |
| LibreTranslate | ✅ | Self-hosted | ❌ | Medium |
| Argos Translate | ❌ | ✅ Offline | ❌ | Medium |
| MyMemory | ❌ | 5k chars/day | ❌ | Medium |
| Yandex | ✅ | Limited | ❌ | ⚡ Fast |

> **Tip:** For best quality, use DeepL Pro or OpenAI/Anthropic — they leverage media context for significantly better translations. Lingva is free but has no context support.

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
