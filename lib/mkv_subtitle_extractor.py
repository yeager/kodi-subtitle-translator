# -*- coding: utf-8 -*-
"""
Pure Python MKV/Matroska subtitle extractor.
No FFmpeg needed — reads EBML/Matroska container directly.
Supports SRT (SubRip) and ASS/SSA embedded text subtitles.
"""

import struct
import io
import os
import xbmc
import xbmcvfs


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[MkvSubExtractor] {msg}", level)


def _read_vint(f):
    """Read a variable-length integer (VINT) from EBML stream."""
    b = f.read(1)
    if not b:
        return None, 0
    first = b[0]
    if first == 0:
        return None, 0
    # Determine length from leading bits
    length = 1
    mask = 0x80
    while length <= 8:
        if first & mask:
            break
        mask >>= 1
        length += 1
    if length > 8:
        return None, 0
    # Read value
    value = first & (mask - 1)  # Strip length bits
    for _ in range(length - 1):
        b2 = f.read(1)
        if not b2:
            return None, 0
        value = (value << 8) | b2[0]
    return value, length


def _read_element_id(f):
    """Read an EBML element ID."""
    b = f.read(1)
    if not b:
        return None, 0
    first = b[0]
    if first == 0:
        return None, 0
    length = 1
    mask = 0x80
    while length <= 4:
        if first & mask:
            break
        mask >>= 1
        length += 1
    if length > 4:
        return None, 0
    value = first
    for _ in range(length - 1):
        b2 = f.read(1)
        if not b2:
            return None, 0
        value = (value << 8) | b2[0]
    return value, length


def _read_uint(data):
    """Read unsigned int from bytes."""
    val = 0
    for b in data:
        val = (val << 8) | b
    return val


# Key EBML/Matroska element IDs
EBML_HEADER = 0x1A45DFA3
SEGMENT = 0x18538067
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
TRACK_NUMBER = 0xD7
TRACK_TYPE = 0x83
CODEC_ID = 0x86
LANGUAGE = 0x22B59C
CODEC_PRIVATE = 0x63A2
CLUSTER = 0x1F43B675
TIMECODE = 0xE7
SIMPLE_BLOCK = 0xA3
BLOCK_GROUP = 0xA0
BLOCK = 0xA1
BLOCK_DURATION = 0x9B
NAME = 0x536E
TRACK_UID = 0x73C5


def _format_srt_time(ms):
    """Format milliseconds to SRT timestamp."""
    if ms < 0:
        ms = 0
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


class MkvSubtitleExtractor:
    """Extract text subtitles from MKV files using pure Python."""
    
    def __init__(self):
        self.tracks = []
        self.subtitle_tracks = []
    
    def extract_from_file(self, file_path, track_index=0):
        """Extract subtitle from a local file.
        
        Args:
            file_path: Path to MKV file (local only, not smb://)
            track_index: Which subtitle track (0 = first)
        
        Returns:
            SRT content as string, or None
        """
        try:
            with open(file_path, 'rb') as f:
                return self._extract(f, track_index)
        except Exception as e:
            _log(f"Error extracting from {file_path}: {e}", xbmc.LOGERROR)
            return None
    
    def extract_from_vfs(self, vfs_path, track_index=0):
        """Extract subtitle from a Kodi VFS path (smb://, nfs://, etc).
        
        Streams the file — does NOT copy the entire file to temp.
        Only reads headers + subtitle blocks, skipping video/audio data.
        
        Args:
            vfs_path: Kodi VFS path (e.g. smb://server/share/movie.mkv)
            track_index: Which subtitle track (0 = first)
        
        Returns:
            SRT content as string, or None
        """
        try:
            f = xbmcvfs.File(vfs_path, 'r')
            try:
                return self._extract_streaming(f, track_index)
            finally:
                f.close()
        except Exception as e:
            _log(f"Error extracting from {vfs_path}: {e}", xbmc.LOGERROR)
            return None
    
    def _extract_streaming(self, vfs_file, track_index):
        """Extract from xbmcvfs.File using streaming reads."""
        # Read file into a BytesIO for seeking (we need random access for EBML)
        # But only read what we need: first ~50MB for headers, then seek through clusters
        
        # First pass: read headers to find tracks (usually in first 10MB)
        _log("Reading MKV headers...")
        header_data = vfs_file.readBytes(10 * 1024 * 1024)  # 10MB
        if not header_data:
            _log("Failed to read file header", xbmc.LOGERROR)
            return None
        
        buf = io.BytesIO(header_data)
        
        # Parse EBML header
        eid, _ = _read_element_id(buf)
        if eid != EBML_HEADER:
            _log(f"Not a valid MKV file (header ID: {hex(eid) if eid else 'None'})", xbmc.LOGERROR)
            return None
        
        size, _ = _read_vint(buf)
        buf.seek(size, 1)  # Skip EBML header content
        
        # Find Segment
        eid, _ = _read_element_id(buf)
        if eid != SEGMENT:
            _log(f"Expected Segment, got {hex(eid) if eid else 'None'}", xbmc.LOGERROR)
            return None
        
        seg_size, _ = _read_vint(buf)
        segment_start = buf.tell()
        
        # Parse tracks from header
        self.tracks = []
        self.subtitle_tracks = []
        subtitle_track_num = None
        codec_id = None
        codec_private = None
        
        # Scan for Tracks element
        while buf.tell() < len(header_data) - 4:
            pos = buf.tell()
            eid, eid_len = _read_element_id(buf)
            if eid is None:
                break
            size, size_len = _read_vint(buf)
            if size is None:
                break
            
            if eid == TRACKS:
                # Parse track entries
                tracks_end = buf.tell() + size
                while buf.tell() < tracks_end:
                    teid, _ = _read_element_id(buf)
                    tsize, _ = _read_vint(buf)
                    if teid is None or tsize is None:
                        break
                    if teid == TRACK_ENTRY:
                        track = self._parse_track_entry(buf, buf.tell() + tsize)
                        if track:
                            self.tracks.append(track)
                            if track['type'] == 17:  # Subtitle
                                self.subtitle_tracks.append(track)
                    else:
                        buf.seek(tsize, 1)
                break
            elif eid == CLUSTER:
                # We've reached cluster data without finding tracks in header
                break
            else:
                if size > len(header_data):
                    break
                buf.seek(size, 1)
        
        if not self.subtitle_tracks:
            _log("No subtitle tracks found in MKV", xbmc.LOGERROR)
            return None
        
        _log(f"Found {len(self.subtitle_tracks)} subtitle track(s): "
             + ", ".join(f"#{t['number']} {t.get('language','?')} ({t.get('codec','')})" 
                        for t in self.subtitle_tracks))
        
        if track_index >= len(self.subtitle_tracks):
            _log(f"Track index {track_index} out of range", xbmc.LOGERROR)
            return None
        
        target_track = self.subtitle_tracks[track_index]
        subtitle_track_num = target_track['number']
        codec_id = target_track.get('codec', '')
        codec_private = target_track.get('codec_private', b'')
        
        _log(f"Extracting track #{subtitle_track_num} ({target_track.get('language','?')}, {codec_id})")
        
        # Now we need to read through ALL clusters to find subtitle blocks
        # Read the ENTIRE file (subtitle blocks can be anywhere)
        _log("Reading full file for subtitle extraction...")
        file_size = vfs_file.size()
        
        # We already have first 10MB, read the rest
        remaining = vfs_file.readBytes(file_size)
        if remaining:
            full_data = header_data + remaining
        else:
            full_data = header_data
        
        _log(f"Total data: {len(full_data) / (1024*1024):.1f} MB")
        
        # Parse clusters for subtitle blocks
        buf = io.BytesIO(full_data)
        # Seek to segment start
        buf.seek(segment_start)
        
        subtitle_entries = []
        cluster_timecode = 0
        
        while buf.tell() < len(full_data) - 4:
            eid, eid_len = _read_element_id(buf)
            if eid is None:
                break
            size, size_len = _read_vint(buf)
            if size is None:
                break
            
            elem_start = buf.tell()
            
            if eid == CLUSTER:
                # Parse cluster contents
                cluster_end = elem_start + size
                cluster_timecode = 0
                
                while buf.tell() < cluster_end - 2:
                    ceid, _ = _read_element_id(buf)
                    csize, _ = _read_vint(buf)
                    if ceid is None or csize is None:
                        break
                    
                    if ceid == TIMECODE:
                        tc_data = buf.read(csize)
                        cluster_timecode = _read_uint(tc_data)
                    elif ceid == SIMPLE_BLOCK:
                        block_data = buf.read(csize)
                        entry = self._parse_block(block_data, cluster_timecode, 
                                                  subtitle_track_num, None)
                        if entry:
                            subtitle_entries.append(entry)
                    elif ceid == BLOCK_GROUP:
                        bg_end = buf.tell() + csize
                        block_data = None
                        duration = None
                        while buf.tell() < bg_end:
                            bgeid, _ = _read_element_id(buf)
                            bgsize, _ = _read_vint(buf)
                            if bgeid is None or bgsize is None:
                                break
                            if bgeid == BLOCK:
                                block_data = buf.read(bgsize)
                            elif bgeid == BLOCK_DURATION:
                                dur_data = buf.read(bgsize)
                                duration = _read_uint(dur_data)
                            else:
                                buf.seek(bgsize, 1)
                        if block_data:
                            entry = self._parse_block(block_data, cluster_timecode,
                                                      subtitle_track_num, duration)
                            if entry:
                                subtitle_entries.append(entry)
                    else:
                        buf.seek(csize, 1)
            elif eid in (TRACKS, 0x1549A966, 0x1C53BB6B, 0x1254C367):
                # Known non-cluster elements: Tracks, SegmentInfo, Cues, Tags
                buf.seek(size, 1)
            else:
                buf.seek(size, 1)
        
        if not subtitle_entries:
            _log("No subtitle entries found in clusters", xbmc.LOGERROR)
            return None
        
        # Sort by timestamp
        subtitle_entries.sort(key=lambda e: e['start'])
        _log(f"Extracted {len(subtitle_entries)} subtitle entries")
        
        # Format as SRT
        if 'ASS' in codec_id or 'SSA' in codec_id:
            return self._format_ass_to_srt(subtitle_entries, codec_private)
        else:
            return self._format_srt(subtitle_entries)
    
    def _parse_track_entry(self, buf, end_pos):
        """Parse a TrackEntry element."""
        track = {}
        while buf.tell() < end_pos:
            eid, _ = _read_element_id(buf)
            size, _ = _read_vint(buf)
            if eid is None or size is None:
                break
            
            if eid == TRACK_NUMBER:
                track['number'] = _read_uint(buf.read(size))
            elif eid == TRACK_TYPE:
                track['type'] = _read_uint(buf.read(size))
            elif eid == CODEC_ID:
                track['codec'] = buf.read(size).decode('ascii', errors='replace')
            elif eid == LANGUAGE:
                track['language'] = buf.read(size).decode('ascii', errors='replace')
            elif eid == CODEC_PRIVATE:
                track['codec_private'] = buf.read(size)
            elif eid == NAME:
                track['name'] = buf.read(size).decode('utf-8', errors='replace')
            else:
                buf.seek(size, 1)
        
        return track if 'number' in track else None
    
    def _parse_block(self, data, cluster_timecode, target_track_num, duration):
        """Parse a Block/SimpleBlock and extract subtitle text."""
        if len(data) < 4:
            return None
        
        buf = io.BytesIO(data)
        # Read track number (VINT)
        track_num, vint_len = _read_vint(buf)
        if track_num != target_track_num:
            return None
        
        # Read timecode (int16, relative to cluster)
        tc_bytes = buf.read(2)
        if len(tc_bytes) < 2:
            return None
        relative_tc = struct.unpack('>h', tc_bytes)[0]
        
        # Flags byte
        flags = buf.read(1)
        if not flags:
            return None
        
        # Rest is the subtitle data
        text_data = buf.read()
        if not text_data:
            return None
        
        try:
            text = text_data.decode('utf-8', errors='replace').strip()
        except:
            return None
        
        if not text:
            return None
        
        start_ms = cluster_timecode + relative_tc
        # Default duration: 3 seconds if not specified
        end_ms = start_ms + (duration if duration else 3000)
        
        return {
            'start': start_ms,
            'end': end_ms,
            'text': text
        }
    
    def _format_srt(self, entries):
        """Format subtitle entries as SRT."""
        lines = []
        for i, entry in enumerate(entries, 1):
            lines.append(str(i))
            lines.append(f"{_format_srt_time(entry['start'])} --> {_format_srt_time(entry['end'])}")
            lines.append(entry['text'])
            lines.append('')
        return '\n'.join(lines)
    
    def _format_ass_to_srt(self, entries, codec_private):
        """Convert ASS/SSA subtitle entries to SRT format."""
        # ASS block format: ReadOrder, Layer, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        srt_entries = []
        for entry in entries:
            text = entry['text']
            # ASS format: fields separated by commas, text is after 8th comma
            parts = text.split(',', 8)
            if len(parts) >= 9:
                text = parts[8]
            # Strip ASS formatting tags
            import re
            text = re.sub(r'\{[^}]*\}', '', text)
            text = text.replace('\\N', '\n').replace('\\n', '\n')
            text = text.strip()
            if text:
                srt_entries.append({
                    'start': entry['start'],
                    'end': entry['end'],
                    'text': text
                })
        
        return self._format_srt(srt_entries)
