# -*- coding: utf-8 -*-
"""
Subtitle Extractor - Extract embedded subtitles from video files using FFmpeg.
"""

import subprocess
import os
import tempfile
import json
import xbmc
import xbmcvfs


class SubtitleExtractor:
    """Extract subtitles from video files using FFmpeg."""
    
    def __init__(self, ffmpeg_path=None):
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._log(f"Initialized with FFmpeg: {self.ffmpeg_path}")
    
    def _find_ffmpeg(self):
        """Find FFmpeg executable."""
        # Common locations
        locations = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew ARM
            '/opt/local/bin/ffmpeg',  # MacPorts
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
        ]
        
        # Check Kodi's own FFmpeg (if bundled)
        try:
            kodi_path = xbmcvfs.translatePath('special://xbmc/')
            kodi_ffmpeg_locations = [
                os.path.join(kodi_path, 'system', 'ffmpeg'),
                os.path.join(kodi_path, 'ffmpeg'),
                os.path.join(kodi_path, 'bin', 'ffmpeg'),
            ]
            locations = kodi_ffmpeg_locations + locations
        except:
            pass
        
        for path in locations:
            if os.path.isfile(path) and self._test_ffmpeg(path):
                self._log(f"Found FFmpeg at: {path}")
                return path
        
        # Try to find in PATH using 'which' or 'where'
        try:
            cmd = ['which', 'ffmpeg'] if os.name != 'nt' else ['where', 'ffmpeg']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if path and self._test_ffmpeg(path):
                    self._log(f"Found FFmpeg in PATH: {path}")
                    return path
        except:
            pass
        
        # Last resort - hope 'ffmpeg' is in PATH
        if self._test_ffmpeg('ffmpeg'):
            return 'ffmpeg'
        
        self._log("FFmpeg not found!", xbmc.LOGERROR)
        return None
    
    def _test_ffmpeg(self, path):
        """Test if FFmpeg is available at the given path."""
        try:
            result = subprocess.run(
                [path, '-version'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            self._log(f"FFmpeg test failed for {path}: {e}", xbmc.LOGDEBUG)
            return False
    
    def _resolve_path(self, path):
        """
        Resolve Kodi special paths and handle network paths.
        Returns (local_path, is_temp, temp_path)
        """
        original_path = path
        
        # Translate Kodi special:// paths
        if path.startswith('special://'):
            path = xbmcvfs.translatePath(path)
            self._log(f"Translated special path: {original_path} -> {path}")
        
        # Handle SMB/NFS/other network paths - copy to temp
        network_prefixes = ('smb://', 'nfs://', 'ftp://', 'sftp://', 'http://', 'https://')
        if path.lower().startswith(network_prefixes):
            self._log(f"Network path detected, copying to temp: {path}")
            temp_path = self._copy_to_temp(path)
            if temp_path:
                return temp_path, True, temp_path
            else:
                self._log("Failed to copy network file to temp", xbmc.LOGERROR)
                return None, False, None
        
        # Check if file exists
        if not xbmcvfs.exists(path) and not os.path.exists(path):
            self._log(f"File not found: {path}", xbmc.LOGERROR)
            return None, False, None
        
        return path, False, None
    
    def _copy_to_temp(self, source_path):
        """Copy a file to temp directory for processing."""
        try:
            # Get file extension
            ext = os.path.splitext(source_path)[1] or '.mkv'
            
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
            os.close(temp_fd)
            
            # Copy using Kodi's VFS
            success = xbmcvfs.copy(source_path, temp_path)
            if success:
                self._log(f"Copied to temp: {temp_path}")
                return temp_path
            else:
                os.unlink(temp_path)
                return None
        except Exception as e:
            self._log(f"Error copying to temp: {e}", xbmc.LOGERROR)
            return None
    
    def get_subtitle_streams(self, video_path):
        """Get list of subtitle streams in the video file."""
        if not self.ffmpeg_path:
            self._log("FFmpeg not available", xbmc.LOGERROR)
            return []
        
        # Resolve path
        resolved_path, is_temp, temp_path = self._resolve_path(video_path)
        if not resolved_path:
            return []
        
        streams = []
        
        try:
            # Use ffprobe to get stream info
            ffprobe = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
            if not os.path.exists(ffprobe) and not self._test_ffmpeg(ffprobe):
                # ffprobe might be separate
                ffprobe = 'ffprobe'
            
            cmd = [
                ffprobe, '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 's',
                resolved_path
            ]
            
            self._log(f"Running ffprobe: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                
                for i, stream in enumerate(data.get('streams', [])):
                    streams.append({
                        'index': i,  # Relative subtitle stream index
                        'global_index': stream.get('index', i),  # Global stream index
                        'codec': stream.get('codec_name', 'unknown'),
                        'language': stream.get('tags', {}).get('language', 'und'),
                        'title': stream.get('tags', {}).get('title', ''),
                        'forced': stream.get('disposition', {}).get('forced', 0) == 1,
                        'default': stream.get('disposition', {}).get('default', 0) == 1,
                    })
                    
                self._log(f"Found {len(streams)} subtitle streams")
            else:
                self._log(f"ffprobe failed: {result.stderr}", xbmc.LOGWARNING)
                
        except json.JSONDecodeError as e:
            self._log(f"Failed to parse ffprobe output: {e}", xbmc.LOGERROR)
        except subprocess.TimeoutExpired:
            self._log("ffprobe timed out", xbmc.LOGERROR)
        except Exception as e:
            self._log(f"Error getting subtitle streams: {e}", xbmc.LOGERROR)
        finally:
            # Clean up temp file
            if is_temp and temp_path:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        return streams
    
    def extract(self, video_path, stream_index=0, output_format='srt'):
        """
        Extract a subtitle stream from a video file.
        
        Args:
            video_path: Path to the video file
            stream_index: Relative index of the subtitle stream (0 = first subtitle)
            output_format: Output format (srt, ass, vtt)
        
        Returns:
            Subtitle content as string, or None on failure
        """
        if not self.ffmpeg_path:
            self._log("FFmpeg not available", xbmc.LOGERROR)
            return None
        
        self._log(f"Extracting subtitle stream {stream_index} from {video_path}")
        
        # Resolve path
        resolved_path, is_temp_input, temp_input = self._resolve_path(video_path)
        if not resolved_path:
            return None
        
        # Create temp file for output
        temp_fd, output_path = tempfile.mkstemp(suffix=f'.{output_format}')
        os.close(temp_fd)
        
        try:
            # Build FFmpeg command
            # Use 0:s:N to select the Nth subtitle stream (relative index)
            cmd = [
                self.ffmpeg_path,
                '-y',  # Overwrite output
                '-hide_banner',
                '-loglevel', 'warning',
                '-i', resolved_path,
                '-map', f'0:s:{stream_index}',  # Select Nth subtitle stream
                '-c:s', self._get_codec(output_format),
                output_path
            ]
            
            self._log(f"Running FFmpeg: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                self._log(f"FFmpeg failed (code {result.returncode}): {error_msg}", xbmc.LOGERROR)
                
                # Try alternative extraction method
                content = self._extract_alternative(resolved_path, stream_index, output_format)
                if content:
                    return content
                return None
            
            # Check if output file was created and has content
            if not os.path.exists(output_path):
                self._log("FFmpeg did not create output file", xbmc.LOGERROR)
                return None
            
            # Read extracted subtitle
            with open(output_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            if not content or len(content.strip()) == 0:
                self._log("FFmpeg produced empty output", xbmc.LOGERROR)
                return None
            
            self._log(f"Successfully extracted {len(content)} bytes of subtitle data")
            return content
            
        except subprocess.TimeoutExpired:
            self._log("FFmpeg timed out after 5 minutes", xbmc.LOGERROR)
            return None
        except Exception as e:
            self._log(f"Extraction error: {e}", xbmc.LOGERROR)
            import traceback
            self._log(traceback.format_exc(), xbmc.LOGERROR)
            return None
        finally:
            # Clean up temp files
            try:
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
            
            if is_temp_input and temp_input:
                try:
                    os.unlink(temp_input)
                except:
                    pass
    
    def _extract_alternative(self, video_path, stream_index, output_format):
        """
        Alternative extraction method using global stream index.
        Some files need the global index instead of relative subtitle index.
        """
        self._log("Trying alternative extraction with global stream mapping...")
        
        # First, get the global stream index
        streams = self.get_subtitle_streams(video_path)
        if stream_index >= len(streams):
            self._log(f"Stream index {stream_index} out of range (have {len(streams)} streams)")
            return None
        
        global_index = streams[stream_index].get('global_index', stream_index)
        
        temp_fd, output_path = tempfile.mkstemp(suffix=f'.{output_format}')
        os.close(temp_fd)
        
        try:
            # Try with global stream index
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-hide_banner',
                '-loglevel', 'warning',
                '-i', video_path,
                '-map', f'0:{global_index}',  # Use global index
                '-c:s', self._get_codec(output_format),
                output_path
            ]
            
            self._log(f"Alternative FFmpeg: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                if content and len(content.strip()) > 0:
                    self._log(f"Alternative extraction succeeded: {len(content)} bytes")
                    return content
            
            return None
            
        except Exception as e:
            self._log(f"Alternative extraction failed: {e}", xbmc.LOGERROR)
            return None
        finally:
            try:
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
    
    def _get_codec(self, format_name):
        """Get FFmpeg codec name for subtitle format."""
        codecs = {
            'srt': 'srt',
            'subrip': 'srt',
            'ass': 'ass',
            'ssa': 'ass',
            'vtt': 'webvtt',
            'webvtt': 'webvtt',
            'sub': 'srt',
            'txt': 'srt',
        }
        return codecs.get(format_name.lower(), 'srt')
    
    def _log(self, message, level=xbmc.LOGINFO):
        """Log message."""
        xbmc.log(f"[SubtitleExtractor] {message}", level)
