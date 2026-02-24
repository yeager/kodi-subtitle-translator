# -*- coding: utf-8 -*-
"""
Pure Python MKV/Matroska subtitle extractor — streaming, low-memory.
No FFmpeg needed. Reads EBML elements sequentially, skipping video/audio.
Memory usage: ~10-50MB regardless of file size.
"""

import struct
import io
import os
import re
import xbmc
import xbmcvfs


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[MkvSubExtractor] {msg}", level)


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

# Container elements (have children, don't skip entirely)
CONTAINER_IDS = {SEGMENT, TRACKS, TRACK_ENTRY, CLUSTER, BLOCK_GROUP}


def _format_srt_time(ms):
    if ms < 0:
        ms = 0
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ml = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ml:03d}"


class StreamingReader:
    """Buffered reader over xbmcvfs.File with position tracking."""
    
    def __init__(self, vfs_file):
        self.vfs = vfs_file
        self.file_size = vfs_file.size()
        self.pos = 0
        self.buf = b''
        self.buf_pos = 0  # position in file where buf starts
        self.CHUNK = 256 * 1024  # 256KB read chunks
    
    def read(self, n):
        """Read exactly n bytes."""
        if n <= 0:
            return b''
        
        # Check if we have enough in buffer
        buf_offset = self.pos - self.buf_pos
        if 0 <= buf_offset and buf_offset + n <= len(self.buf):
            data = self.buf[buf_offset:buf_offset + n]
            self.pos += n
            return data
        
        # Need to read from file
        result = b''
        
        # Use any remaining buffer data first
        if 0 <= buf_offset < len(self.buf):
            result = self.buf[buf_offset:]
            self.pos += len(result)
            n -= len(result)
        
        # Read more from file
        while n > 0:
            read_size = max(self.CHUNK, n)
            self.buf_pos = self.pos
            self.buf = self.vfs.readBytes(read_size)
            if not self.buf:
                break
            take = min(n, len(self.buf))
            result += self.buf[:take]
            self.pos += take
            n -= take
        
        return result
    
    def skip(self, n):
        """Skip n bytes efficiently without reading into memory."""
        if n <= 0:
            return
        
        # Check if skip lands within current buffer
        buf_offset = self.pos - self.buf_pos
        if 0 <= buf_offset and buf_offset + n <= len(self.buf):
            self.pos += n
            return
        
        # Skip past buffer — need to consume from file
        # First consume remaining buffer
        buf_remaining = 0
        if 0 <= buf_offset < len(self.buf):
            buf_remaining = len(self.buf) - buf_offset
        
        file_skip = n - buf_remaining
        
        # Try seek first
        try:
            # We need to seek the underlying file to (current file read pos + file_skip)
            # But we don't know the file's internal position reliably, so seek absolute
            self.vfs.seek(self.pos + n, 0)
            self.pos += n
            self.buf = b''
            self.buf_pos = self.pos
            return
        except:
            pass
        
        # Fallback: read and discard in chunks
        # First, the underlying file is at buf_pos + len(buf)
        # We need to skip: file_skip - (len(buf) - buf_offset - buf_remaining) ... 
        # Actually simpler: just read and discard from vfs
        # The vfs read position is at buf_pos + len(self.buf) (end of what we last read)
        already_buffered = len(self.buf) - buf_offset if buf_offset >= 0 else 0
        to_read = n - already_buffered
        
        while to_read > 0:
            chunk = min(to_read, 1024 * 1024)
            data = self.vfs.readBytes(chunk)
            if not data:
                break
            to_read -= len(data)
        
        self.pos += n
        self.buf = b''
        self.buf_pos = self.pos
    
    def tell(self):
        return self.pos
    
    def at_end(self):
        return self.pos >= self.file_size


def _read_vint(reader):
    """Read EBML variable-length integer."""
    b = reader.read(1)
    if not b:
        return None, 0
    first = b[0]
    if first == 0:
        return None, 0
    length = 1
    mask = 0x80
    while length <= 8:
        if first & mask:
            break
        mask >>= 1
        length += 1
    if length > 8:
        return None, 0
    value = first & (mask - 1)
    if length > 1:
        rest = reader.read(length - 1)
        if len(rest) < length - 1:
            return None, 0
        for b2 in rest:
            value = (value << 8) | b2
    return value, length


def _read_element_id(reader):
    """Read EBML element ID."""
    b = reader.read(1)
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
    if length > 1:
        rest = reader.read(length - 1)
        if len(rest) < length - 1:
            return None, 0
        for b2 in rest:
            value = (value << 8) | b2
    return value, length


def _read_uint(data):
    val = 0
    for b in data:
        val = (val << 8) | b
    return val


class MkvSubtitleExtractor:
    """Extract text subtitles from MKV files — streaming, low memory."""
    
    def __init__(self):
        self.subtitle_tracks = []
    
    def extract_from_vfs(self, vfs_path, track_index=0):
        """Extract subtitle from Kodi VFS path (smb://, nfs://, etc).
        
        Streams through the file — never loads entire file into RAM.
        Only reads headers + subtitle blocks, skipping video/audio.
        """
        try:
            f = xbmcvfs.File(vfs_path, 'r')
            try:
                reader = StreamingReader(f)
                _log(f"File size: {reader.file_size / (1024*1024):.1f} MB")
                return self._extract_streaming(reader, track_index)
            finally:
                f.close()
        except Exception as e:
            _log(f"Error: {e}", xbmc.LOGERROR)
            import traceback
            _log(traceback.format_exc(), xbmc.LOGERROR)
            return None
    
    def extract_from_file(self, file_path, track_index=0):
        """Extract from local file."""
        try:
            f = xbmcvfs.File(file_path, 'r')
            try:
                reader = StreamingReader(f)
                return self._extract_streaming(reader, track_index)
            finally:
                f.close()
        except Exception as e:
            _log(f"Error: {e}", xbmc.LOGERROR)
            return None
    
    def _extract_streaming(self, reader, track_index):
        """Stream through MKV, extract subtitle entries."""
        
        # 1. Read EBML header
        eid, _ = _read_element_id(reader)
        if eid != EBML_HEADER:
            _log(f"Not MKV (header={hex(eid) if eid else None})", xbmc.LOGERROR)
            return None
        size, _ = _read_vint(reader)
        reader.skip(size)  # Skip EBML header content
        
        # 2. Read Segment
        eid, _ = _read_element_id(reader)
        if eid != SEGMENT:
            _log(f"No Segment found", xbmc.LOGERROR)
            return None
        _read_vint(reader)  # Segment size (often unknown/0xFFFFFFFFFFFFFF)
        
        # 3. Scan for Tracks, then parse Clusters
        self.subtitle_tracks = []
        subtitle_track_num = None
        codec_id = None
        subtitle_entries = []
        cluster_timecode = 0
        tracks_found = False
        
        while not reader.at_end():
            eid, eid_len = _read_element_id(reader)
            if eid is None:
                break
            size, size_len = _read_vint(reader)
            if size is None:
                break
            
            elem_data_pos = reader.tell()
            
            if eid == TRACKS:
                # Parse track entries
                self._parse_tracks(reader, elem_data_pos + size)
                tracks_found = True
                
                if not self.subtitle_tracks:
                    _log("No subtitle tracks found", xbmc.LOGERROR)
                    return None
                
                _log(f"Found {len(self.subtitle_tracks)} subtitle track(s): " +
                     ", ".join(f"#{t['number']} {t.get('language','?')} ({t.get('codec','')})"
                               for t in self.subtitle_tracks))
                
                if track_index >= len(self.subtitle_tracks):
                    _log(f"Track index {track_index} out of range", xbmc.LOGERROR)
                    return None
                
                target = self.subtitle_tracks[track_index]
                subtitle_track_num = target['number']
                codec_id = target.get('codec', '')
                _log(f"Target: track #{subtitle_track_num} ({codec_id})")
                
            elif eid == CLUSTER and tracks_found and subtitle_track_num is not None:
                # Parse cluster for subtitle blocks
                cluster_end = elem_data_pos + size
                cluster_timecode = 0
                
                while reader.tell() < cluster_end:
                    ceid, _ = _read_element_id(reader)
                    csize, _ = _read_vint(reader)
                    if ceid is None or csize is None:
                        break
                    
                    if ceid == TIMECODE:
                        tc_data = reader.read(csize)
                        cluster_timecode = _read_uint(tc_data)
                        
                    elif ceid == SIMPLE_BLOCK:
                        # Peek at track number to decide if we should read or skip
                        block_start = reader.tell()
                        entry = self._try_parse_subtitle_block(reader, csize, 
                                    cluster_timecode, subtitle_track_num, None)
                        # Ensure we're at the right position after
                        reader.skip(max(0, (block_start + csize) - reader.tell()))
                        if entry:
                            subtitle_entries.append(entry)
                            
                    elif ceid == BLOCK_GROUP:
                        bg_end = reader.tell() + csize
                        block_data = None
                        block_size = 0
                        duration = None
                        while reader.tell() < bg_end:
                            bgeid, _ = _read_element_id(reader)
                            bgsize, _ = _read_vint(reader)
                            if bgeid is None or bgsize is None:
                                break
                            if bgeid == BLOCK:
                                bstart = reader.tell()
                                entry = self._try_parse_subtitle_block(
                                    reader, bgsize, cluster_timecode,
                                    subtitle_track_num, None)
                                reader.skip(max(0, (bstart + bgsize) - reader.tell()))
                                if entry:
                                    block_data = entry
                            elif bgeid == BLOCK_DURATION:
                                dur = reader.read(bgsize)
                                duration = _read_uint(dur)
                            else:
                                reader.skip(bgsize)
                        if block_data:
                            if duration is not None:
                                block_data['end'] = block_data['start'] + duration
                            subtitle_entries.append(block_data)
                    else:
                        # Skip video/audio blocks
                        reader.skip(csize)
            else:
                # Skip non-relevant elements (video data, cues, tags, etc.)
                reader.skip(size)
        
        if not subtitle_entries:
            _log("No subtitle entries found", xbmc.LOGERROR)
            return None
        
        subtitle_entries.sort(key=lambda e: e['start'])
        _log(f"Extracted {len(subtitle_entries)} subtitle entries")
        
        # Format as SRT
        if codec_id and ('ASS' in codec_id or 'SSA' in codec_id):
            return self._format_ass_to_srt(subtitle_entries)
        return self._format_srt(subtitle_entries)
    
    def _try_parse_subtitle_block(self, reader, block_size, cluster_tc, target_track, duration):
        """Read block header; if it's our subtitle track, parse it. Otherwise skip."""
        if block_size < 4:
            return None
        
        # Read track number (VINT) — just first byte to check quickly
        b = reader.read(1)
        if not b:
            return None
        first = b[0]
        
        # Decode VINT for track number
        length = 1
        mask = 0x80
        while length <= 4:
            if first & mask:
                break
            mask >>= 1
            length += 1
        
        track_num = first & (mask - 1)
        if length > 1:
            rest = reader.read(length - 1)
            for b2 in rest:
                track_num = (track_num << 8) | b2
        
        if track_num != target_track:
            return None  # Not our track — caller will skip remaining bytes
        
        # This IS our subtitle track — read the rest
        tc_bytes = reader.read(2)
        if len(tc_bytes) < 2:
            return None
        relative_tc = struct.unpack('>h', tc_bytes)[0]
        
        flags = reader.read(1)  # flags byte
        
        # Remaining = subtitle text
        text_size = block_size - length - 3  # vint + 2 tc + 1 flags
        if text_size <= 0:
            return None
        
        text_data = reader.read(text_size)
        try:
            text = text_data.decode('utf-8', errors='replace').strip()
        except:
            return None
        
        if not text:
            return None
        
        start_ms = cluster_tc + relative_tc
        end_ms = start_ms + (duration if duration else 3000)
        
        return {'start': start_ms, 'end': end_ms, 'text': text}
    
    def _parse_tracks(self, reader, end_pos):
        """Parse Tracks element to find subtitle tracks."""
        while reader.tell() < end_pos:
            eid, _ = _read_element_id(reader)
            size, _ = _read_vint(reader)
            if eid is None or size is None:
                break
            if eid == TRACK_ENTRY:
                track = self._parse_track_entry(reader, reader.tell() + size)
                if track and track.get('type') == 17:  # Subtitle
                    self.subtitle_tracks.append(track)
            else:
                reader.skip(size)
    
    def _parse_track_entry(self, reader, end_pos):
        """Parse a single TrackEntry."""
        track = {}
        while reader.tell() < end_pos:
            eid, _ = _read_element_id(reader)
            size, _ = _read_vint(reader)
            if eid is None or size is None:
                break
            if eid == TRACK_NUMBER:
                track['number'] = _read_uint(reader.read(size))
            elif eid == TRACK_TYPE:
                track['type'] = _read_uint(reader.read(size))
            elif eid == CODEC_ID:
                track['codec'] = reader.read(size).decode('ascii', errors='replace')
            elif eid == LANGUAGE:
                track['language'] = reader.read(size).decode('ascii', errors='replace')
            elif eid == NAME:
                track['name'] = reader.read(size).decode('utf-8', errors='replace')
            elif eid == CODEC_PRIVATE:
                # Only keep for subtitle tracks (small), skip for video (can be huge)
                if size < 100000:
                    track['codec_private'] = reader.read(size)
                else:
                    reader.skip(size)
            else:
                reader.skip(size)
        return track if 'number' in track else None
    
    def _format_srt(self, entries):
        lines = []
        for i, e in enumerate(entries, 1):
            lines.append(str(i))
            lines.append(f"{_format_srt_time(e['start'])} --> {_format_srt_time(e['end'])}")
            lines.append(e['text'])
            lines.append('')
        return '\n'.join(lines)
    
    def _format_ass_to_srt(self, entries):
        srt = []
        for e in entries:
            text = e['text']
            parts = text.split(',', 8)
            if len(parts) >= 9:
                text = parts[8]
            text = re.sub(r'\{[^}]*\}', '', text)
            text = text.replace('\\N', '\n').replace('\\n', '\n').strip()
            if text:
                srt.append({'start': e['start'], 'end': e['end'], 'text': text})
        return self._format_srt(srt)
