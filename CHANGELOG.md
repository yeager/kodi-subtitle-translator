# Changelog

All notable changes to Subtitle Translator for Kodi will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [0.9.3] - 2026-02-08

### Fixed
- **DeepL Free API key reading** — was looking for wrong setting key `deepl_free_api_key` instead of `deepl_api_key`, causing DeepL Free to never find the configured API key

### Thanks
- Nanomani for the bug report!

## [0.9.2] - 2026-02-08

### Added
- **Auto-fallback to Lingva** — if the selected translation service (DeepL, Google, Microsoft, OpenAI, Anthropic) requires an API key that is missing or empty, the addon automatically falls back to Lingva and shows a notification
- **API key validation on settings load** — warns user immediately when a service requiring an API key has none configured
- **Better completion notification** — shows which service was used and elapsed time, e.g. "Translated 749 lines (Lingva) in 1m 39s"
- **`_format_elapsed()`** — human-readable elapsed time formatting
- **`_get_fallback_config()`** — config builder for fallback services
- **`_auto_fallback_if_needed()`** — automatic service fallback logic
- **`_validate_api_key_on_load()`** — settings validation with Kodi notification

## [0.9.1] - 2026-02-08

### Fixed
- **NoneType crash** — `show_subtitle_source_dialog` and `browse_subtitle_file` were missing from `global` declaration in `init_libraries()`, causing `'NoneType' object is not callable` when both embedded and external subtitles were found
- **Target language check** — now checks for target language in both embedded AND external subtitles before offering to translate

### Added
- **Language code parsing from filenames** — reads language from external subtitle filenames (e.g., `.en.srt` → English, `.sv.srt` → Swedish) to identify source language
- **Auto-load external target subtitle** — if an external subtitle already exists in the target language (e.g., `movie.sv.srt` when target is Swedish), it's loaded automatically without prompting for translation
- **`find_external_subtitle_for_language()`** — new method to check if an external subtitle exists for a specific language
- **`_list_external_subtitles()`** — new method to enumerate all external subtitles with parsed language codes
- **`_parse_language_from_filename()`** — new method to extract language code from subtitle filenames
- **`_get_language_variants()`** — comprehensive language code variant matching (e.g., `en`/`eng`/`english` all match)

## [0.9.0] - 2026-02-07

### Added
- **Android support** — full compatibility with Kodi on Android devices
- Auto-detect FFmpeg on Android (Termux, bundled, manual placement)
- Android-specific FFmpeg search paths (`/data/data/com.termux/files/usr/bin/ffmpeg`, Kodi home dir, etc.)
- `is_android()` platform detection helper
- `get_android_ffmpeg_locations()` for comprehensive FFmpeg discovery on Android
- `get_kodi_temp_path()` — use Kodi's `special://temp/` for temp files (Android-safe)
- `_make_temp_file()` helper for creating temp files in Kodi's temp directory
- Optional `tools.ffmpeg` addon dependency in `addon.xml`
- Android installation guide in README (Termux, manual binary, external-only)
- Graceful fallback when FFmpeg is unavailable (external subtitles still work)

### Changed
- Temp file handling now uses Kodi's temp directory instead of system `tempfile`, ensuring compatibility with Android's scoped storage
- FFmpeg search order refactored: platform-specific paths checked first, then Kodi bundled paths, then `PATH`
- Deduplicated FFmpeg search locations

## [0.8.2] - 2025-01-25

### Added
- Translations for string 30719 (target language already exists notification) in all 25 languages

## [0.8.1] - 2025-01-24

### Fixed
- Show notification when target language subtitle already exists
- Improved logging for debugging translation flow
- Better feedback when no dialogs appear

## [0.8.0] - 2025-01-20

### Added
- External subtitle file translation support
- New subtitle source selection dialog (embedded vs external)
- Browse for subtitle files manually
- Support for `.srt`, `.ass`, `.ssa`, `.sub`, `.vtt` external files

## [0.7.3] - 2025-01-15

### Fixed
- Show dialog when no embedded subtitles found

## [0.7.2] - 2025-01-10

### Fixed
- SMB/NFS path handling (no more mixed slashes)
- Clarified DeepL labels (API key required)

## [0.7.1] - 2025-01-05

### Added
- Auto-select newly translated subtitles
- Fallback translation services on failure
- Abort on repeated errors (3+ consecutive or <50% success)
- Lingva as default (LibreTranslate now requires API key)

### Fixed
- Lazy-loading of dialogs

## [0.7.0] - 2025-01-01

### Added
- Initial beta release
- Support for 10 translation services
- Automatic subtitle extraction with FFmpeg
- Configurable language preferences
- Translation profiles (Anime, Kids, Documentary, etc.)
- Offline translation with Argos Translate
- Basic, Standard, Advanced, and Expert settings levels
- 25 UI languages

---

**License:** GPL-3.0-or-later
