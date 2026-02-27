# -*- coding: utf-8 -*-
"""
MKV Streaming Parser - Extract subtitles from MKV files without downloading.

Parses EBML/Matroska structure using xbmcvfs.File for network file support.
Only reads metadata and subtitle data, skipping video/audio entirely.
"""

import struct
import xbmc
import xbmcvfs

# EBML Element IDs
EBML_HEADER = 0x1A45DFA3
SEGMENT = 0x18538067
SEEK_HEAD = 0x114D9B74
SEEK = 0x4DBB
SEEK_ID = 0x53AB
SEEK_POSITION = 0x53AC
INFO = 0x1549A966
TIMECODE_SCALE = 0x2AD7B1
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
TRACK_NUMBER = 0xD7
TRACK_TYPE = 0x83
CODEC_ID = 0x86
CODEC_PRIVATE = 0x63A2
TRACK_NAME = 0x536E
LANGUAGE = 0x22B59C
LANGUAGE_BCP47 = 0x22B59D
DEFAULT_DURATION = 0x23E383
FLAG_DEFAULT = 0x88
FLAG_FORCED = 0x55AA
CUES = 0x1C53BB6B
CUE_POINT = 0xBB
CUE_TIME = 0xB3
CUE_TRACK_POSITIONS = 0xB7
CUE_TRACK = 0xF7
CUE_CLUSTER_POSITION = 0xF1
CLUSTER = 0x1F43B675
CLUSTER_TIMESTAMP = 0xE7
SIMPLE_BLOCK = 0xA3
BLOCK_GROUP = 0xA0
BLOCK = 0xA1
BLOCK_DURATION = 0x9B

TRACK_TYPE_SUBTITLE = 17

CODEC_MAP = {
    'S_TEXT/UTF8': 'srt',
    'S_TEXT/ASS': 'ass',
    'S_TEXT/SSA': 'ssa',
    'S_TEXT/WEBVTT': 'vtt',
}


class BufferedReader:
    """Buffered reader wrapper around xbmcvfs.File for efficient network I/O."""

    def __init__(self, file_obj, buffer_size=65536):
        self._file = file_obj
        self._buffer = b''
        self._buffer_pos = 0
        self._file_pos = 0
        self._buffer_start = 0
        self._buffer_size = buffer_size
        self._eof = False

    def tell(self):
        return self._file_pos

    def seek(self, offset):
        """Seek to absolute position."""
        if self._buffer_start <= offset < self._buffer_start + len(self._buffer):
            self._buffer_pos = offset - self._buffer_start
            self._file_pos = offset
            return True
        self._buffer = b''
        self._buffer_pos = 0
        self._buffer_start = offset
        self._file_pos = offset
        self._eof = False
        try:
            self._file.seek(offset, 0)
            return True
        except Exception:
            return False

    def read(self, size):
        """Read exactly size bytes (or fewer at EOF)."""
        result = b''
        remaining = size
        while remaining > 0:
            available = len(self._buffer) - self._buffer_pos
            if available > 0:
                chunk_size = min(available, remaining)
                result += self._buffer[self._buffer_pos:self._buffer_pos + chunk_size]
                self._buffer_pos += chunk_size
                self._file_pos += chunk_size
                remaining -= chunk_size
            if remaining > 0:
                if self._eof:
                    break
                read_size = max(self._buffer_size, remaining)
                data = self._file.readBytes(read_size)
                if not data:
                    self._eof = True
                    break
                self._buffer = bytes(data)
                self._buffer_start = self._file_pos
                self._buffer_pos = 0
        return result


def read_vint(reader):
    """
    Read an EBML variable-length integer (data size).
    Returns (value, length) where value has the VINT_MARKER masked out.
    Returns (None, 0) on error.
    """
    first = reader.read(1)
    if not first:
        return None, 0
    b = first[0]
    if b == 0:
        return None, 0
    length = 1
    mask = 0x80
    while length <= 8:
        if b & mask:
            break
        mask >>= 1
        length += 1
    if length > 8:
        return None, 0
    value = b & (mask - 1)
    if length > 1:
        rest = reader.read(length - 1)
        if len(rest) < length - 1:
            return None, 0
        for byte in rest:
            value = (value << 8) | byte
    return value, length


def read_element_id(reader):
    """
    Read an EBML element ID (VINT_MARKER is kept in the value).
    Returns (id, length). Returns (None, 0) on error.
    """
    first = reader.read(1)
    if not first:
        return None, 0
    b = first[0]
    if b == 0:
        return None, 0
    length = 1
    mask = 0x80
    while length <= 4:
        if b & mask:
            break
        mask >>= 1
        length += 1
    if length > 4:
        return None, 0
    value = b
    if length > 1:
        rest = reader.read(length - 1)
        if len(rest) < length - 1:
            return None, 0
        for byte in rest:
            value = (value << 8) | byte
    return value, length


def read_uint(data):
    """Read unsigned integer from bytes."""
    value = 0
    for b in data:
        value = (value << 8) | b
    return value


def read_block_header(data):
    """
    Parse block/SimpleBlock header from raw bytes.
    Returns (track_number, timestamp_offset, flags, header_size).
    """
    if len(data) < 4:
        return None, 0, 0, 0
    b = data[0]
    length = 1
    mask = 0x80
    while length <= 4:
        if b & mask:
            break
        mask >>= 1
        length += 1
    if length > 4 or len(data) < length + 3:
        return None, 0, 0, 0
    track_num = b & (mask - 1)
    for i in range(1, length):
        track_num = (track_num << 8) | data[i]
    ts_offset = struct.unpack('>h', data[length:length + 2])[0]
    flags = data[length + 2]
    return track_num, ts_offset, flags, length + 3


class MKVSubtitleTrack:
    """Information about a subtitle track in an MKV file."""

    def __init__(self):
        self.number = 0
        self.uid = 0
        self.codec_id = ''
        self.codec_private = b''
        self.language = 'und'
        self.name = ''
        self.default = False
        self.forced = False
        self.default_duration = 0

    @property
    def format(self):
        return CODEC_MAP.get(self.codec_id, '')

    def __repr__(self):
        return (f"MKVSubtitleTrack(num={self.number}, codec={self.codec_id}, "
                f"lang={self.language}, name={self.name})")


class SubtitleBlock:
    """A single subtitle block extracted from the MKV."""

    def __init__(self, track_number, timestamp_ms, duration_ms, data):
        self.track_number = track_number
        self.timestamp_ms = timestamp_ms
        self.duration_ms = duration_ms
        self.data = data

    @property
    def text(self):
        try:
            return self.data.decode('utf-8')
        except UnicodeDecodeError:
            return self.data.decode('utf-8', errors='replace')


class MKVStreamingParser:
    """
    Parse MKV files to extract subtitles using streaming I/O.

    Uses xbmcvfs.File for network file access (SMB, NFS, etc.).
    Only reads metadata and subtitle data, never touches video/audio data.
    """

    def __init__(self):
        self._timecode_scale = 1000000  # Default: 1ms in nanoseconds
        self._segment_start = 0
        self._tracks = []
        self._cues = []
        self._subtitle_blocks = []

    def _reset(self):
        """Reset state for a new parse."""
        self._timecode_scale = 1000000
        self._segment_start = 0
        self._tracks = []
        self._cues = []
        self._subtitle_blocks = []

    def extract_subtitles(self, file_path, stream_index=0, output_format='srt'):
        """
        Extract subtitles from an MKV file.

        Args:
            file_path: Path to the MKV file (can be smb://, nfs://, etc.)
            stream_index: Index of the subtitle stream to extract (0-based)
            output_format: Desired output format ('srt', 'ass', 'ssa')

        Returns:
            Subtitle content as string, or None on failure.
        """
        self._reset()
        self._log(f"Opening {file_path}")

        file_obj = None
        try:
            file_obj = xbmcvfs.File(file_path)
            reader = BufferedReader(file_obj)

            # Step 1: Validate EBML header
            if not self._read_ebml_header(reader):
                self._log("Not a valid EBML/MKV file", xbmc.LOGWARNING)
                return None

            # Step 2: Find Segment
            seg_data_start, seg_size = self._find_segment(reader)
            if seg_data_start is None:
                self._log("Segment element not found", xbmc.LOGWARNING)
                return None
            self._segment_start = seg_data_start

            # Step 3: Parse segment headers (SeekHead, Info, Tracks)
            seek_positions = {}
            self._parse_segment_headers(reader, seg_data_start, seg_size, seek_positions)

            # Step 4: If Tracks not found inline, use SeekHead
            if not self._tracks:
                tracks_pos = seek_positions.get(TRACKS)
                if tracks_pos is not None:
                    reader.seek(self._segment_start + tracks_pos)
                    elem_id, _ = read_element_id(reader)
                    elem_size, _ = read_vint(reader)
                    if elem_id == TRACKS and elem_size is not None:
                        self._parse_tracks(reader, elem_size)

            if not self._tracks:
                self._log("No subtitle tracks found", xbmc.LOGWARNING)
                return None

            self._log(f"Found {len(self._tracks)} subtitle track(s)")

            if stream_index >= len(self._tracks):
                self._log(f"Stream index {stream_index} out of range "
                          f"(have {len(self._tracks)} tracks)", xbmc.LOGWARNING)
                return None

            target_track = self._tracks[stream_index]
            self._log(f"Extracting track {target_track.number}: "
                      f"{target_track.codec_id} ({target_track.language})")

            # Step 5: Parse Cues for cluster seek table
            cues_pos = seek_positions.get(CUES)
            if cues_pos is not None:
                reader.seek(self._segment_start + cues_pos)
                elem_id, _ = read_element_id(reader)
                elem_size, _ = read_vint(reader)
                if elem_id == CUES and elem_size is not None:
                    self._parse_cues(reader, elem_size)
                    self._log(f"Parsed {len(self._cues)} cue points")

            # Step 6: Extract subtitle blocks from clusters
            self._extract_from_clusters(reader, target_track, seg_data_start, seg_size)

            if not self._subtitle_blocks:
                self._log("No subtitle blocks found", xbmc.LOGWARNING)
                return None

            self._subtitle_blocks.sort(key=lambda b: b.timestamp_ms)
            self._log(f"Extracted {len(self._subtitle_blocks)} subtitle blocks")

            # Step 7: Reassemble output
            content = self._reassemble(target_track, output_format)
            if content and len(content.strip()) > 0:
                self._log(f"Successfully extracted {len(content)} bytes")
                return content

            self._log("Reassembly produced empty output", xbmc.LOGWARNING)
            return None

        except Exception as e:
            self._log(f"Error: {e}", xbmc.LOGERROR)
            import traceback
            self._log(traceback.format_exc(), xbmc.LOGERROR)
            return None
        finally:
            if file_obj:
                try:
                    file_obj.close()
                except Exception:
                    pass

    def get_subtitle_streams(self, file_path):
        """
        Get list of subtitle streams in an MKV file.

        Returns list of dicts compatible with SubtitleExtractor format,
        or None if the file cannot be parsed.
        """
        self._reset()
        self._log(f"Scanning tracks in {file_path}")

        file_obj = None
        try:
            file_obj = xbmcvfs.File(file_path)
            reader = BufferedReader(file_obj)

            if not self._read_ebml_header(reader):
                return None

            seg_data_start, seg_size = self._find_segment(reader)
            if seg_data_start is None:
                return None
            self._segment_start = seg_data_start

            seek_positions = {}
            self._parse_segment_headers(reader, seg_data_start, seg_size, seek_positions)

            if not self._tracks:
                tracks_pos = seek_positions.get(TRACKS)
                if tracks_pos is not None:
                    reader.seek(self._segment_start + tracks_pos)
                    elem_id, _ = read_element_id(reader)
                    elem_size, _ = read_vint(reader)
                    if elem_id == TRACKS and elem_size is not None:
                        self._parse_tracks(reader, elem_size)

            if not self._tracks:
                return None

            streams = []
            for i, track in enumerate(self._tracks):
                codec_name = 'unknown'
                fmt = track.format
                if fmt == 'srt':
                    codec_name = 'subrip'
                elif fmt in ('ass', 'ssa'):
                    codec_name = 'ass'
                elif fmt == 'vtt':
                    codec_name = 'webvtt'
                streams.append({
                    'index': i,
                    'global_index': track.number,
                    'codec': codec_name,
                    'language': track.language,
                    'title': track.name,
                    'forced': track.forced,
                    'default': track.default,
                })
            return streams

        except Exception as e:
            self._log(f"Stream scan error: {e}", xbmc.LOGERROR)
            return None
        finally:
            if file_obj:
                try:
                    file_obj.close()
                except Exception:
                    pass

    # ── EBML header & Segment ────────────────────────────────────────

    def _read_ebml_header(self, reader):
        """Read and validate EBML header."""
        elem_id, _ = read_element_id(reader)
        if elem_id != EBML_HEADER:
            return False
        elem_size, _ = read_vint(reader)
        if elem_size is None:
            return False
        reader.read(elem_size)  # skip header contents
        return True

    def _find_segment(self, reader):
        """Find the Segment element. Returns (data_start_offset, size)."""
        elem_id, _ = read_element_id(reader)
        if elem_id != SEGMENT:
            return None, None
        elem_size, _ = read_vint(reader)
        if elem_size is None:
            return None, None
        return reader.tell(), elem_size

    # ── Segment children parsing ─────────────────────────────────────

    def _parse_segment_headers(self, reader, seg_start, seg_size, seek_positions):
        """Parse Segment children until we hit clusters or have enough info."""
        end_pos = seg_start + seg_size
        # Limit scan to first 100MB to avoid reading entire file
        max_scan = min(end_pos, seg_start + 100 * 1024 * 1024)
        reader.seek(seg_start)

        found_tracks = False
        found_seekhead = False

        while reader.tell() < max_scan:
            elem_start = reader.tell()
            elem_id, id_len = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, size_len = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()

            if elem_id == SEEK_HEAD:
                self._parse_seekhead(reader, elem_size, seek_positions)
                found_seekhead = True
            elif elem_id == INFO:
                self._parse_info(reader, elem_size)
            elif elem_id == TRACKS:
                self._parse_tracks(reader, elem_size)
                found_tracks = True
            elif elem_id == CLUSTER:
                # Stop at first cluster
                reader.seek(elem_start)
                break
            # Skip to next element
            reader.seek(data_start + elem_size)

            if found_tracks and found_seekhead:
                break

    def _parse_seekhead(self, reader, size, seek_positions):
        """Parse SeekHead to get positions of other top-level elements."""
        end_pos = reader.tell() + size
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == SEEK:
                self._parse_seek_entry(reader, elem_size, seek_positions)
            reader.seek(data_start + elem_size)

    def _parse_seek_entry(self, reader, size, seek_positions):
        """Parse a single Seek entry (SeekID + SeekPosition)."""
        end_pos = reader.tell() + size
        seek_id = None
        seek_pos = None
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == SEEK_ID:
                seek_id = read_uint(reader.read(elem_size))
            elif elem_id == SEEK_POSITION:
                seek_pos = read_uint(reader.read(elem_size))
            reader.seek(data_start + elem_size)
        if seek_id is not None and seek_pos is not None:
            seek_positions[seek_id] = seek_pos

    def _parse_info(self, reader, size):
        """Parse Info element for TimecodeScale."""
        end_pos = reader.tell() + size
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == TIMECODE_SCALE:
                self._timecode_scale = read_uint(reader.read(elem_size))
                self._log(f"TimecodeScale: {self._timecode_scale} ns")
            reader.seek(data_start + elem_size)

    # ── Tracks ───────────────────────────────────────────────────────

    def _parse_tracks(self, reader, size):
        """Parse Tracks element to find subtitle tracks."""
        end_pos = reader.tell() + size
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == TRACK_ENTRY:
                track = self._parse_track_entry(reader, elem_size)
                if track:
                    self._tracks.append(track)
            reader.seek(data_start + elem_size)

    def _parse_track_entry(self, reader, size):
        """Parse a TrackEntry. Returns MKVSubtitleTrack if subtitle, else None."""
        end_pos = reader.tell() + size
        track_number = 0
        track_type = 0
        codec_id = ''
        codec_private = b''
        language = 'und'
        name = ''
        is_default = False
        is_forced = False
        default_duration = 0

        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()

            if elem_id == TRACK_NUMBER:
                track_number = read_uint(reader.read(elem_size))
            elif elem_id == TRACK_TYPE:
                track_type = read_uint(reader.read(elem_size))
            elif elem_id == CODEC_ID:
                codec_id = reader.read(elem_size).decode('ascii', errors='replace')
            elif elem_id == CODEC_PRIVATE:
                codec_private = reader.read(elem_size)
            elif elem_id == LANGUAGE:
                language = reader.read(elem_size).decode('ascii', errors='replace').rstrip('\x00')
            elif elem_id == LANGUAGE_BCP47:
                # BCP47 overrides the legacy Language element
                language = reader.read(elem_size).decode('ascii', errors='replace').rstrip('\x00')
            elif elem_id == TRACK_NAME:
                name = reader.read(elem_size).decode('utf-8', errors='replace')
            elif elem_id == FLAG_DEFAULT:
                is_default = read_uint(reader.read(elem_size)) == 1
            elif elem_id == FLAG_FORCED:
                is_forced = read_uint(reader.read(elem_size)) == 1
            elif elem_id == DEFAULT_DURATION:
                default_duration = read_uint(reader.read(elem_size))

            reader.seek(data_start + elem_size)

        if track_type != TRACK_TYPE_SUBTITLE:
            return None
        if codec_id not in CODEC_MAP:
            self._log(f"Skipping unsupported subtitle codec: {codec_id}", xbmc.LOGDEBUG)
            return None

        track = MKVSubtitleTrack()
        track.number = track_number
        track.codec_id = codec_id
        track.codec_private = codec_private
        track.language = language
        track.name = name
        track.default = is_default
        track.forced = is_forced
        track.default_duration = default_duration
        return track

    # ── Cues ─────────────────────────────────────────────────────────

    def _parse_cues(self, reader, size):
        """Parse Cues element to build cluster seek table."""
        end_pos = reader.tell() + size
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == CUE_POINT:
                self._parse_cue_point(reader, elem_size)
            reader.seek(data_start + elem_size)

    def _parse_cue_point(self, reader, size):
        """Parse a CuePoint entry."""
        end_pos = reader.tell() + size
        cue_time = 0
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == CUE_TIME:
                cue_time = read_uint(reader.read(elem_size))
            elif elem_id == CUE_TRACK_POSITIONS:
                cue_track, cluster_pos = self._parse_cue_track_positions(reader, elem_size)
                if cue_track is not None and cluster_pos is not None:
                    self._cues.append((cue_time, cue_track, cluster_pos))
            reader.seek(data_start + elem_size)

    def _parse_cue_track_positions(self, reader, size):
        """Parse CueTrackPositions. Returns (track_number, cluster_position)."""
        end_pos = reader.tell() + size
        cue_track = None
        cluster_pos = None
        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()
            if elem_id == CUE_TRACK:
                cue_track = read_uint(reader.read(elem_size))
            elif elem_id == CUE_CLUSTER_POSITION:
                cluster_pos = read_uint(reader.read(elem_size))
            reader.seek(data_start + elem_size)
        return cue_track, cluster_pos

    # ── Cluster extraction ───────────────────────────────────────────

    def _extract_from_clusters(self, reader, target_track, seg_start, seg_size):
        """Extract subtitle blocks from clusters."""
        track_num = target_track.number

        if self._cues:
            # Build set of cluster offsets from Cues
            sub_clusters = set()
            all_clusters = set()
            for _, cue_track, cluster_pos in self._cues:
                all_clusters.add(cluster_pos)
                if cue_track == track_num:
                    sub_clusters.add(cluster_pos)

            if sub_clusters:
                cluster_offsets = sorted(sub_clusters)
                self._log(f"Seeking to {len(cluster_offsets)} clusters "
                          f"(subtitle cue entries)")
            else:
                cluster_offsets = sorted(all_clusters)
                self._log(f"No subtitle cues, scanning all "
                          f"{len(cluster_offsets)} clusters")

            for offset in cluster_offsets:
                abs_offset = seg_start + offset
                reader.seek(abs_offset)
                elem_id, _ = read_element_id(reader)
                if elem_id != CLUSTER:
                    continue
                elem_size, _ = read_vint(reader)
                if elem_size is None:
                    continue
                self._parse_cluster(reader, elem_size, track_num)
        else:
            # No Cues: linear scan through all clusters
            self._log("No Cues found, performing linear cluster scan")
            self._scan_clusters_linear(reader, seg_start, seg_size, track_num)

    def _scan_clusters_linear(self, reader, seg_start, seg_size, target_track_num):
        """Scan all clusters linearly, extracting subtitle blocks as we go."""
        end_pos = seg_start + seg_size
        reader.seek(seg_start)
        cluster_count = 0

        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()

            if elem_id == CLUSTER:
                cluster_count += 1
                self._parse_cluster(reader, elem_size, target_track_num)

            reader.seek(data_start + elem_size)

        self._log(f"Linear scan: processed {cluster_count} clusters")

    def _parse_cluster(self, reader, size, target_track_num):
        """Parse a Cluster to extract subtitle blocks for the target track."""
        end_pos = reader.tell() + size
        cluster_timestamp = 0

        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()

            if elem_id == CLUSTER_TIMESTAMP:
                cluster_timestamp = read_uint(reader.read(elem_size))
            elif elem_id == SIMPLE_BLOCK:
                # Peek at track number to skip non-subtitle blocks efficiently
                track_num = self._peek_block_track(reader, elem_size)
                if track_num == target_track_num:
                    reader.seek(data_start)
                    data = reader.read(elem_size)
                    self._process_block(data, cluster_timestamp,
                                        target_track_num, 0)
            elif elem_id == BLOCK_GROUP:
                self._parse_block_group(reader, elem_size,
                                        cluster_timestamp, target_track_num)

            reader.seek(data_start + elem_size)

    def _peek_block_track(self, reader, block_size):
        """Peek at block header to get track number without reading full data."""
        if block_size < 4:
            return None
        pos = reader.tell()
        peek = reader.read(min(4, block_size))
        reader.seek(pos)
        if not peek:
            return None
        b = peek[0]
        if b & 0x80:
            return b & 0x7F
        elif len(peek) >= 2 and (b & 0x40):
            return ((b & 0x3F) << 8) | peek[1]
        elif len(peek) >= 3 and (b & 0x20):
            return ((b & 0x1F) << 16) | (peek[1] << 8) | peek[2]
        elif len(peek) >= 4 and (b & 0x10):
            return ((b & 0x0F) << 24) | (peek[1] << 16) | (peek[2] << 8) | peek[3]
        return None

    def _parse_block_group(self, reader, size, cluster_timestamp, target_track_num):
        """Parse a BlockGroup to extract subtitle block with duration."""
        end_pos = reader.tell() + size
        block_data = None
        block_duration = 0

        while reader.tell() < end_pos:
            elem_id, _ = read_element_id(reader)
            if elem_id is None:
                break
            elem_size, _ = read_vint(reader)
            if elem_size is None:
                break
            data_start = reader.tell()

            if elem_id == BLOCK:
                track_num = self._peek_block_track(reader, elem_size)
                if track_num == target_track_num:
                    reader.seek(data_start)
                    block_data = reader.read(elem_size)
                else:
                    # Not our track, skip entire BlockGroup
                    return
            elif elem_id == BLOCK_DURATION:
                block_duration = read_uint(reader.read(elem_size))

            reader.seek(data_start + elem_size)

        if block_data:
            self._process_block(block_data, cluster_timestamp,
                                target_track_num, block_duration)

    def _process_block(self, data, cluster_timestamp, target_track_num, duration):
        """Process a block and add to subtitle_blocks if it matches."""
        track_num, ts_offset, flags, header_size = read_block_header(data)
        if track_num is None or track_num != target_track_num:
            return

        # Check for lacing (unusual for subtitles)
        lacing = (flags >> 1) & 0x03
        if lacing != 0:
            self._log(f"Skipping laced subtitle block", xbmc.LOGDEBUG)
            return

        # Absolute timestamp in timecode scale units, then to milliseconds
        abs_timestamp = cluster_timestamp + ts_offset
        timestamp_ms = abs_timestamp * self._timecode_scale // 1000000
        duration_ms = duration * self._timecode_scale // 1000000 if duration else 0

        sub_data = data[header_size:]
        if sub_data:
            self._subtitle_blocks.append(
                SubtitleBlock(track_num, timestamp_ms, duration_ms, sub_data)
            )

    # ── Reassembly ───────────────────────────────────────────────────

    def _reassemble(self, track, output_format):
        """Reassemble subtitle blocks into the desired output format."""
        if track.format in ('ass', 'ssa') and output_format in ('ass', 'ssa'):
            return self._reassemble_ass(track)
        return self._reassemble_srt(track)

    def _reassemble_srt(self, track):
        """Reassemble subtitle blocks into SRT format."""
        lines = []
        idx = 0
        for i, block in enumerate(self._subtitle_blocks):
            text = block.text.strip()
            if not text:
                continue

            # For ASS source, clean up to plain text
            if track.format in ('ass', 'ssa'):
                text = self._ass_to_plain_text(text)
                if not text:
                    continue

            idx += 1
            start_time = self._format_srt_time(block.timestamp_ms)

            if block.duration_ms > 0:
                end_ms = block.timestamp_ms + block.duration_ms
            elif i + 1 < len(self._subtitle_blocks):
                end_ms = self._subtitle_blocks[i + 1].timestamp_ms
            else:
                end_ms = block.timestamp_ms + 3000
            end_time = self._format_srt_time(end_ms)

            lines.append(str(idx))
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")

        return '\n'.join(lines)

    def _reassemble_ass(self, track):
        """Reassemble subtitle blocks into ASS/SSA format."""
        lines = []

        # Header from CodecPrivate
        if track.codec_private:
            header = track.codec_private.decode('utf-8', errors='replace').rstrip('\n')
            lines.append(header)
            if '[Events]' not in header:
                lines.append('')
                lines.append('[Events]')
                lines.append('Format: Layer, Start, End, Style, Name, '
                             'MarginL, MarginR, MarginV, Effect, Text')
        else:
            lines.append('[Script Info]')
            lines.append('ScriptType: v4.00+')
            lines.append('PlayResX: 384')
            lines.append('PlayResY: 288')
            lines.append('')
            lines.append('[V4+ Styles]')
            lines.append('Format: Name, Fontname, Fontsize, PrimaryColour, '
                         'SecondaryColour, OutlineColour, BackColour, Bold, '
                         'Italic, Underline, StrikeOut, ScaleX, ScaleY, '
                         'Spacing, Angle, BorderStyle, Outline, Shadow, '
                         'Alignment, MarginL, MarginR, MarginV, Encoding')
            lines.append('Style: Default,Arial,20,&H00FFFFFF,&H0000FFFF,'
                         '&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,'
                         '10,10,10,1')
            lines.append('')
            lines.append('[Events]')
            lines.append('Format: Layer, Start, End, Style, Name, '
                         'MarginL, MarginR, MarginV, Effect, Text')

        for block in self._subtitle_blocks:
            text = block.text.strip()
            if not text:
                continue

            start_time = self._format_ass_time(block.timestamp_ms)
            if block.duration_ms > 0:
                end_ms = block.timestamp_ms + block.duration_ms
            else:
                end_ms = block.timestamp_ms + 3000
            end_time = self._format_ass_time(end_ms)

            # MKV ASS block format:
            # ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
            parts = text.split(',', 8)
            if len(parts) >= 9:
                layer = parts[1]
                style = parts[2]
                name = parts[3]
                margin_l = parts[4]
                margin_r = parts[5]
                margin_v = parts[6]
                effect = parts[7]
                dialogue_text = parts[8]
                lines.append(
                    f"Dialogue: {layer},{start_time},{end_time},"
                    f"{style},{name},{margin_l},{margin_r},{margin_v},"
                    f"{effect},{dialogue_text}"
                )
            else:
                lines.append(
                    f"Dialogue: 0,{start_time},{end_time},"
                    f"Default,,0000,0000,0000,,{text}"
                )

        return '\n'.join(lines) + '\n'

    @staticmethod
    def _format_srt_time(ms):
        """Format milliseconds as SRT timestamp: HH:MM:SS,mmm"""
        if ms < 0:
            ms = 0
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @staticmethod
    def _format_ass_time(ms):
        """Format milliseconds as ASS timestamp: H:MM:SS.CC"""
        if ms < 0:
            ms = 0
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        centiseconds = (ms % 1000) // 10
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def _ass_to_plain_text(text):
        """Convert ASS dialogue data to plain text for SRT output."""
        # MKV ASS: ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        parts = text.split(',', 8)
        if len(parts) >= 9:
            text = parts[8]
        import re
        text = re.sub(r'\{\\[^}]*\}', '', text)
        text = text.replace('\\N', '\n').replace('\\n', '\n')
        return text.strip()

    def _log(self, message, level=xbmc.LOGINFO):
        """Log message."""
        xbmc.log(f"[MKVStreaming] {message}", level)
