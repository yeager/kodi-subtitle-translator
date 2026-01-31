# -*- coding: utf-8 -*-
"""
Subtitle Parser - Parse and generate subtitle files in various formats.
"""

import re
from html import unescape


class SubtitleParser:
    """Parse and generate subtitles in SRT, ASS, and VTT formats."""
    
    def parse(self, content, format_hint=None):
        """
        Parse subtitle content into a list of entries.
        
        Each entry is a dict with:
        - index: Subtitle number
        - start: Start time in milliseconds
        - end: End time in milliseconds
        - text: Subtitle text
        - style: Optional styling info (for ASS)
        
        Returns list of entries.
        """
        if not content:
            return []
        
        # Auto-detect format if not specified
        if not format_hint:
            format_hint = self._detect_format(content)
        
        if format_hint == 'srt':
            return self._parse_srt(content)
        elif format_hint in ('ass', 'ssa'):
            return self._parse_ass(content)
        elif format_hint == 'vtt':
            return self._parse_vtt(content)
        else:
            # Try SRT as fallback
            return self._parse_srt(content)
    
    def generate(self, entries, output_format='srt'):
        """
        Generate subtitle content from entries.
        
        Args:
            entries: List of subtitle entries
            output_format: Output format (srt, ass, vtt)
        
        Returns subtitle content as string.
        """
        if output_format == 'srt':
            return self._generate_srt(entries)
        elif output_format in ('ass', 'ssa'):
            return self._generate_ass(entries)
        elif output_format == 'vtt':
            return self._generate_vtt(entries)
        else:
            return self._generate_srt(entries)
    
    def _detect_format(self, content):
        """Detect subtitle format from content."""
        content_lower = content.lower()
        
        if '[script info]' in content_lower or 'dialogue:' in content_lower:
            return 'ass'
        elif 'webvtt' in content_lower[:50]:
            return 'vtt'
        else:
            return 'srt'
    
    def _parse_srt(self, content):
        """Parse SRT format subtitles."""
        entries = []
        
        # Split into blocks
        blocks = re.split(r'\n\n+', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            try:
                # Parse index
                index = int(lines[0].strip())
                
                # Parse timing
                timing_match = re.match(
                    r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
                    lines[1].strip()
                )
                if not timing_match:
                    continue
                
                start = self._parse_srt_time(timing_match.group(1))
                end = self._parse_srt_time(timing_match.group(2))
                
                # Get text (remaining lines)
                text = '\n'.join(lines[2:])
                text = self._clean_text(text)
                
                entries.append({
                    'index': index,
                    'start': start,
                    'end': end,
                    'text': text
                })
            except (ValueError, IndexError):
                continue
        
        return entries
    
    def _parse_ass(self, content):
        """Parse ASS/SSA format subtitles."""
        entries = []
        
        # Find dialogue lines
        for line in content.split('\n'):
            line = line.strip()
            if not line.lower().startswith('dialogue:'):
                continue
            
            try:
                # Parse dialogue line
                # Format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
                parts = line.split(',', 9)
                if len(parts) < 10:
                    continue
                
                start = self._parse_ass_time(parts[1])
                end = self._parse_ass_time(parts[2])
                style = parts[3]
                text = parts[9]
                
                # Remove ASS formatting codes
                text = re.sub(r'\{[^}]*\}', '', text)
                text = text.replace('\\N', '\n').replace('\\n', '\n')
                text = self._clean_text(text)
                
                entries.append({
                    'index': len(entries) + 1,
                    'start': start,
                    'end': end,
                    'text': text,
                    'style': style
                })
            except (ValueError, IndexError):
                continue
        
        return entries
    
    def _parse_vtt(self, content):
        """Parse WebVTT format subtitles."""
        entries = []
        
        # Skip header
        lines = content.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                start_idx = i
                break
            elif line.strip().upper() == 'WEBVTT':
                continue
        
        # Parse cues
        current_block = []
        for line in lines[start_idx:]:
            if line.strip():
                current_block.append(line)
            elif current_block:
                # Process block
                entry = self._parse_vtt_block(current_block)
                if entry:
                    entry['index'] = len(entries) + 1
                    entries.append(entry)
                current_block = []
        
        # Don't forget last block
        if current_block:
            entry = self._parse_vtt_block(current_block)
            if entry:
                entry['index'] = len(entries) + 1
                entries.append(entry)
        
        return entries
    
    def _parse_vtt_block(self, lines):
        """Parse a single VTT cue block."""
        try:
            # Find timing line
            timing_line = None
            text_start = 0
            
            for i, line in enumerate(lines):
                if '-->' in line:
                    timing_line = line
                    text_start = i + 1
                    break
            
            if not timing_line:
                return None
            
            # Parse timing
            match = re.match(
                r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})',
                timing_line.strip()
            )
            if not match:
                # Try without hours
                match = re.match(
                    r'(\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}\.\d{3})',
                    timing_line.strip()
                )
                if not match:
                    return None
            
            start = self._parse_vtt_time(match.group(1))
            end = self._parse_vtt_time(match.group(2))
            
            # Get text
            text = '\n'.join(lines[text_start:])
            text = self._clean_text(text)
            
            return {
                'start': start,
                'end': end,
                'text': text
            }
        except:
            return None
    
    def _parse_srt_time(self, time_str):
        """Parse SRT time format to milliseconds."""
        time_str = time_str.replace(',', '.')
        match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return ((h * 3600) + (m * 60) + s) * 1000 + ms
        return 0
    
    def _parse_ass_time(self, time_str):
        """Parse ASS time format to milliseconds."""
        match = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', time_str.strip())
        if match:
            h, m, s, cs = map(int, match.groups())
            return ((h * 3600) + (m * 60) + s) * 1000 + cs * 10
        return 0
    
    def _parse_vtt_time(self, time_str):
        """Parse VTT time format to milliseconds."""
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, rest = parts
            s, ms = rest.split('.')
            return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
        elif len(parts) == 2:
            m, rest = parts
            s, ms = rest.split('.')
            return (int(m) * 60 + int(s)) * 1000 + int(ms)
        return 0
    
    def _format_srt_time(self, ms):
        """Format milliseconds to SRT time format."""
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def _format_vtt_time(self, ms):
        """Format milliseconds to VTT time format."""
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    
    def _format_ass_time(self, ms):
        """Format milliseconds to ASS time format."""
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        cs = (ms % 1000) // 10
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
    
    def _clean_text(self, text):
        """Clean and normalize subtitle text."""
        # Decode HTML entities
        text = unescape(text)
        
        # Remove HTML tags but keep their content
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _generate_srt(self, entries):
        """Generate SRT format subtitles."""
        output = []
        
        for entry in entries:
            output.append(str(entry['index']))
            output.append(
                f"{self._format_srt_time(entry['start'])} --> "
                f"{self._format_srt_time(entry['end'])}"
            )
            output.append(entry['text'])
            output.append('')
        
        return '\n'.join(output)
    
    def _generate_vtt(self, entries):
        """Generate WebVTT format subtitles."""
        output = ['WEBVTT', '']
        
        for entry in entries:
            output.append(
                f"{self._format_vtt_time(entry['start'])} --> "
                f"{self._format_vtt_time(entry['end'])}"
            )
            output.append(entry['text'])
            output.append('')
        
        return '\n'.join(output)
    
    def _generate_ass(self, entries):
        """Generate ASS format subtitles."""
        output = [
            '[Script Info]',
            'Title: Translated Subtitle',
            'ScriptType: v4.00+',
            'Collisions: Normal',
            'PlayDepth: 0',
            '',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
            'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
            'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
            'Alignment, MarginL, MarginR, MarginV, Encoding',
            'Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,'
            '&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1',
            '',
            '[Events]',
            'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
        ]
        
        for entry in entries:
            text = entry['text'].replace('\n', '\\N')
            style = entry.get('style', 'Default')
            output.append(
                f"Dialogue: 0,{self._format_ass_time(entry['start'])},"
                f"{self._format_ass_time(entry['end'])},{style},,0,0,0,,{text}"
            )
        
        return '\n'.join(output)
