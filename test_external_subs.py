#!/usr/bin/env python3
"""
Test external subtitle handling outside of Kodi.
Usage: python3 test_external_subs.py /path/to/subtitle.srt
"""

import sys
import os

# Add lib to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.subtitle_parser import SubtitleParser


def test_parse_srt(content):
    """Test SRT parsing."""
    parser = SubtitleParser()
    entries = parser.parse(content, 'srt')
    return entries


def test_parse_ass(content):
    """Test ASS parsing."""
    parser = SubtitleParser()
    entries = parser.parse(content, 'ass')
    return entries


def test_generate_srt(entries):
    """Test SRT generation."""
    parser = SubtitleParser()
    return parser.generate(entries, 'srt')


def read_subtitle_file(path):
    """Read subtitle file with encoding detection."""
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                content = f.read()
            print(f"✅ Read with encoding: {enc}")
            return content
        except UnicodeDecodeError:
            continue
    
    # Last resort: binary with replace
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_external_subs.py /path/to/subtitle.srt")
        print()
        print("Will test:")
        print("  - Reading external subtitle file")
        print("  - Parsing subtitle content")
        print("  - Re-generating subtitle output")
        sys.exit(1)
    
    sub_path = sys.argv[1]
    
    if not os.path.exists(sub_path):
        print(f"❌ File not found: {sub_path}")
        sys.exit(1)
    
    print(f"📁 Testing: {sub_path}")
    print()
    
    # Read file
    print("=== Reading File ===")
    content = read_subtitle_file(sub_path)
    print(f"   Size: {len(content)} bytes")
    print(f"   Lines: {len(content.splitlines())}")
    print()
    
    # Detect format
    ext = os.path.splitext(sub_path)[1].lower()
    format_map = {
        '.srt': 'srt',
        '.ass': 'ass',
        '.ssa': 'ass',
        '.vtt': 'vtt',
        '.sub': 'srt'
    }
    fmt = format_map.get(ext, 'srt')
    print(f"   Format: {fmt} (from extension: {ext})")
    print()
    
    # Parse
    print("=== Parsing ===")
    parser = SubtitleParser()
    entries = parser.parse(content, fmt)
    
    if not entries:
        print("❌ No entries parsed!")
        print()
        print("First 500 chars of content:")
        print("-" * 40)
        print(content[:500])
        sys.exit(1)
    
    print(f"✅ Parsed {len(entries)} subtitle entries")
    print()
    
    # Show first few entries
    print("=== First 5 Entries ===")
    for entry in entries[:5]:
        print(f"   [{entry['index']}] {entry['start']}ms - {entry['end']}ms")
        # Truncate long text
        text = entry['text']
        if len(text) > 60:
            text = text[:60] + "..."
        print(f"       \"{text}\"")
    print()
    
    # Test regeneration
    print("=== Regenerate as SRT ===")
    output = parser.generate(entries, 'srt')
    print(f"   Output size: {len(output)} bytes")
    print()
    print("First 500 chars of output:")
    print("-" * 40)
    print(output[:500])
    print()
    
    # Summary
    print("=== Summary ===")
    print(f"✅ File read: OK")
    print(f"✅ Parsing: {len(entries)} entries")
    print(f"✅ Generation: {len(output)} bytes")
    print()
    print("🎉 All tests passed!")


if __name__ == '__main__':
    main()
