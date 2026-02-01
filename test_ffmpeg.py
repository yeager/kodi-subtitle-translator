#!/usr/bin/env python3
"""
Test FFmpeg subtitle extraction outside of Kodi.
Usage: python3 test_ffmpeg.py /path/to/video.mkv
"""

import subprocess
import json
import sys
import os
import tempfile


def find_ffmpeg():
    """Find FFmpeg executable."""
    locations = [
        '/opt/homebrew/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/usr/bin/ffmpeg',
    ]
    
    for path in locations:
        if os.path.isfile(path):
            return path
    
    # Try PATH
    try:
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    return 'ffmpeg'


def get_subtitle_streams(video_path, ffmpeg_path):
    """Get subtitle streams from video."""
    ffprobe = ffmpeg_path.replace('ffmpeg', 'ffprobe')
    
    cmd = [
        ffprobe, '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 's',
        video_path
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return []
    
    data = json.loads(result.stdout)
    streams = []
    
    for i, stream in enumerate(data.get('streams', [])):
        streams.append({
            'index': i,
            'global_index': stream.get('index', i),
            'codec': stream.get('codec_name', 'unknown'),
            'language': stream.get('tags', {}).get('language', 'und'),
            'title': stream.get('tags', {}).get('title', ''),
        })
    
    return streams


def extract_subtitle(video_path, stream_index, ffmpeg_path):
    """Extract subtitle to temp file."""
    temp_fd, output_path = tempfile.mkstemp(suffix='.srt')
    os.close(temp_fd)
    
    cmd = [
        ffmpeg_path,
        '-y',
        '-hide_banner',
        '-loglevel', 'warning',
        '-i', video_path,
        '-map', f'0:s:{stream_index}',
        '-c:s', 'srt',
        output_path
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        os.unlink(output_path)
        return None
    
    with open(output_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    os.unlink(output_path)
    return content


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_ffmpeg.py /path/to/video.mkv")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        sys.exit(1)
    
    ffmpeg_path = find_ffmpeg()
    print(f"Using FFmpeg: {ffmpeg_path}")
    print(f"Video: {video_path}")
    print()
    
    # Get streams
    print("=== Subtitle Streams ===")
    streams = get_subtitle_streams(video_path, ffmpeg_path)
    
    if not streams:
        print("No subtitle streams found!")
        sys.exit(1)
    
    for s in streams:
        print(f"  [{s['index']}] {s['language']} - {s['codec']} - {s['title']}")
    
    print()
    
    # Extract first subtitle
    print("=== Extracting first subtitle ===")
    content = extract_subtitle(video_path, 0, ffmpeg_path)
    
    if content:
        lines = content.split('\n')
        print(f"Extracted {len(content)} bytes, {len(lines)} lines")
        print()
        print("First 20 lines:")
        print("-" * 40)
        for line in lines[:20]:
            print(line)
    else:
        print("Extraction failed!")
        sys.exit(1)
    
    print()
    print("=== SUCCESS ===")


if __name__ == '__main__':
    main()
