# -*- coding: utf-8 -*-
"""
Subtitle Extractor - Extract embedded subtitles from video files using FFmpeg.
"""

import subprocess
import os
import tempfile
import xbmc
import xbmcvfs


class SubtitleExtractor:
    """Extract subtitles from video files using FFmpeg."""
    
    def __init__(self, ffmpeg_path=None):
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
    
    def _find_ffmpeg(self):
        """Find FFmpeg executable."""
        # Common locations
        locations = [
            'ffmpeg',  # In PATH
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
        ]
        
        # Check Kodi's own FFmpeg
        kodi_ffmpeg = os.path.join(
            xbmcvfs.translatePath('special://xbmc/'),
            'system', 'ffmpeg'
        )
        locations.insert(0, kodi_ffmpeg)
        
        for path in locations:
            if self._test_ffmpeg(path):
                self._log(f"Found FFmpeg at: {path}")
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(
                ['which', 'ffmpeg'] if os.name != 'nt' else ['where', 'ffmpeg'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                self._log(f"Found FFmpeg in PATH: {path}")
                return path
        except:
            pass
        
        return 'ffmpeg'  # Hope it's in PATH
    
    def _test_ffmpeg(self, path):
        """Test if FFmpeg is available at the given path."""
        try:
            result = subprocess.run(
                [path, '-version'],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def get_subtitle_streams(self, video_path):
        """Get list of subtitle streams in the video file."""
        streams = []
        
        try:
            # Use ffprobe to get stream info
            ffprobe = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
            
            result = subprocess.run(
                [
                    ffprobe, '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_streams',
                    '-select_streams', 's',
                    video_path
                ],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for i, stream in enumerate(data.get('streams', [])):
                    streams.append({
                        'index': stream.get('index', i),
                        'codec': stream.get('codec_name', 'unknown'),
                        'language': stream.get('tags', {}).get('language', 'und'),
                        'title': stream.get('tags', {}).get('title', ''),
                        'forced': stream.get('disposition', {}).get('forced', 0) == 1,
                        'default': stream.get('disposition', {}).get('default', 0) == 1,
                    })
        except Exception as e:
            self._log(f"Error getting subtitle streams: {e}", xbmc.LOGERROR)
        
        return streams
    
    def extract(self, video_path, stream_index=0, output_format='srt'):
        """
        Extract a subtitle stream from a video file.
        
        Args:
            video_path: Path to the video file
            stream_index: Index of the subtitle stream to extract
            output_format: Output format (srt, ass, vtt)
        
        Returns:
            Subtitle content as string, or None on failure
        """
        self._log(f"Extracting subtitle stream {stream_index} from {video_path}")
        
        # Handle Kodi special paths
        if video_path.startswith('special://'):
            video_path = xbmcvfs.translatePath(video_path)
        
        # Create temp file for output
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=f'.{output_format}', delete=False
        ) as f:
            output_path = f.name
        
        try:
            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-y',  # Overwrite output
                '-i', video_path,
                '-map', f'0:s:{stream_index}',  # Select subtitle stream
                '-c:s', self._get_codec(output_format),
                output_path
            ]
            
            self._log(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                self._log(f"FFmpeg error: {result.stderr}", xbmc.LOGERROR)
                return None
            
            # Read extracted subtitle
            with xbmcvfs.File(output_path, 'r') as f:
                content = f.read()
            
            # Handle bytes if necessary
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            
            self._log(f"Extracted {len(content)} bytes of subtitle data")
            return content
            
        except subprocess.TimeoutExpired:
            self._log("FFmpeg timed out", xbmc.LOGERROR)
            return None
        except Exception as e:
            self._log(f"Extraction error: {e}", xbmc.LOGERROR)
            return None
        finally:
            # Clean up temp file
            try:
                os.unlink(output_path)
            except:
                pass
    
    def _get_codec(self, format_name):
        """Get FFmpeg codec name for subtitle format."""
        codecs = {
            'srt': 'srt',
            'ass': 'ass',
            'ssa': 'ass',
            'vtt': 'webvtt',
            'sub': 'subrip',
        }
        return codecs.get(format_name.lower(), 'srt')
    
    def _log(self, message, level=xbmc.LOGINFO):
        """Log message."""
        xbmc.log(f"[SubtitleExtractor] {message}", level)
