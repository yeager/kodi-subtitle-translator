# Repository and code review — 2026-09-13

Baseline: `52eac6291cf297bbc21c41cfdaacdc893a261fee` (v0.11.2).
The reviewed changes are prepared as v0.11.3. No paid translation APIs or user
media libraries were accessed during testing.

## Scope and resolved findings

| Area reviewed | Findings and corrections |
| --- | --- |
| Repository contents and packaging | Removed nine tracked Python bytecode files. Moved the useful subtitle fixture and diagnostic scripts into test/tool directories. Consolidated the two case-conflicting Swedish directories, preserving the newer translations. Added an explicit runtime-file package allowlist, reproducible ZIPs, package MD5 sidecars and CI checks. SVG source art remains in Git. |
| Playback orchestration (`service.py`) | Fixed the FFmpeg requirement preceding native extraction, omitted codec metadata, wrong JSON-RPC response nesting and subtitle index selection, overly broad sidecar filename matching, ignored automatic-translation setting, pause-state handling, cancelled dialog cleanup, overwriting existing sidecars, and attaching results after playback changed. |
| Translation services (`lib/translators.py`) | Fixed Microsoft's unserialized JSON array; stopped hiding provider errors behind original text; rejected malformed/incomplete output before timestamp pairing; passed real credentials and media context to fallbacks; sized DeepL requests including JSON escaping/options; encoded Lingva URL path slashes; decoded Google entities. Removed the false failure check that rejected valid unchanged names. Updated retired bundled Claude choices and made the model setting editable. |
| Settings and profiles | Connected all visible settings to their implementation: progress vs notifications, debug categories, profiles, FFmpeg threads, retries/delay, request rate, input encoding and OpenAI temperature. Added the previously unavailable DeepL glossary-ID setting. Profiles now drive supported tone guidance, line length and profanity processing. |
| Cache and files | Cache keys now include source file size/mtime when available, language, provider and configuration. Expired accessed entries are removed. Disabling caching produces temporary output removed after playback rather than permanent cached files. Temporary extraction paths are reserved using `mkstemp`. |
| Modern MKV parser | Fixed the method-name mismatch, stream numbering when bitmap tracks precede text tracks, FFmpeg global index mapping, BCP47 precedence, missed timestamp-scale metadata, incomplete video-only cues, VTT output selection, failed seeks and unbounded individual reads. Added NUL removal. |
| Legacy MKV parser | Rejects bitmap/laced data instead of decoding it as text, validates stream/header bounds, applies non-default time scales and rejects oversized reads. |
| Subtitle parser/output | Handles BOM, CRLF and NUL input. Preserves all dialogue words and long tokens rather than dropping text after two lines. Timing is preserved; the final display line can exceed the preferred width to avoid data loss. |
| Advanced helper library | Fixed literal backslashes in glossary replacements, shared mutable profile defaults and lost profile overrides, float timestamps, `None` rate-limit periods, truncated lines, proxy credential escaping, export path components and uncaught translator-factory errors. |
| Dialogs and diagnostics | Reviewed metadata, source selection, progress, errors and logging. Redacts URL credentials and common secret query/dictionary fields before logging/export; strips NULs at log sinks. Diagnostics show actual statistics instead of placeholder copy. |
| Android binaries | Downloads both FFmpeg and FFprobe on ARM64, with timeout, size bound, atomic replacement and pinned SHA-256 checks. Incorrect or partial downloads never become the executable. |
| Workflows | Pins and verifies Transifex CLI/FFmpeg source downloads, avoids mutable shell installer execution, makes FFmpeg releases immutable, prevents the addon build from running for FFmpeg tags, validates addon tag/version agreement and supplies package checksums. |
| Metadata, translations, documentation and artwork | XML/PO validation, source-message and settings-reference checks, removal of an unused requests dependency, correction of the claim of 25 translated UI languages (two runtime catalogs, 25 metadata languages). New user-facing labels have English and Swedish strings. |

## Installation failure in `yeager/kodi-repo`

The published repository requested MD5 package verification but returned **404**
for `service.subtitletranslator-0.9.22.zip.md5`. The ZIP itself returned **200**
without `Content-MD5`. This matches Kodi's failure path when neither checksum
source is available, and explains why direct ZIP installation can succeed.
The repository also advertised 0.9.22 while the addon had reached 0.11.2, and its
own indexed ZIP/artwork paths were incomplete.

The companion repository change supplies package checksums, repository installer
1.0.2 and artwork, current addon metadata/package, and an index/package validator.
Previously published archives are retained unchanged as release artifacts.

## Validation and limits

- Gitleaks **8.30.1**, official binary verified against the GitHub release SHA-256:
  no findings in either Git history or current directory scans; ZIP traversal
  enabled to depth 2. Addon history: 79 commits; repository scan: 27 commits.
- **41 offline tests passed**, including real FFmpeg-generated MKV input, provider
  transport/failure doubles, both playback translation paths and package contents.
- Both official Android binaries were downloaded and verified against the pinned
  hashes in a temporary directory; neither binary was executed.
- Python 3.8 syntax compatibility, undefined-name checks, XML, gettext PO,
  whitespace and runtime-package checks are run before submission.
- Full Kodi GUI playback, Android execution, live SMB/NFS servers and paid API
  account integration were not exercised. The review is not a guarantee that
  arbitrary malformed media or future provider changes can never reveal a bug.
- Secret scanning does not prove the absence of every possible credential format.
  Diagnostic redaction covers structured secret fields and credential-bearing
  URLs; it cannot infer every secret embedded in arbitrary prose.

## Primary references

- [Kodi repository resolution](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/Repository.cpp)
- [DeepL request limits](https://developers.deepl.com/docs/resources/usage-limits)
- [DeepL formality fallback](https://developers.deepl.com/api-reference/document/upload-and-translate-a-document)
- [Anthropic retired models and replacements](https://platform.claude.com/docs/en/about-claude/model-deprecations)
