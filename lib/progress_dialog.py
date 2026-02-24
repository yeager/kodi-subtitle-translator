# -*- coding: utf-8 -*-
"""
Progress Dialog and Error Reporting for Subtitle Translator
"""

import xbmc
import xbmcgui
import xbmcaddon
import traceback
import json
import os
import time
from datetime import datetime
import xbmcvfs


def get_addon():
    """Get addon instance lazily to avoid import-time errors."""
    return xbmcaddon.Addon()


def get_addon_id():
    """Get addon ID."""
    try:
        return get_addon().getAddonInfo('id')
    except:
        return 'service.subtitletranslator'


def get_addon_name():
    """Get addon name."""
    try:
        return get_addon().getAddonInfo('name')
    except:
        return 'Subtitle Translator'


class TranslationProgress:
    """
    Progress dialog for subtitle translation with detailed status updates.
    """
    
    def __init__(self, total_subtitles=0, show_dialog=True):
        self.total = total_subtitles
        self.current = 0
        self.show_dialog = show_dialog
        self.dialog = None
        self.start_time = None
        self.stage = 'init'
        self.stages = {
            'init': ('Initializing...', 0),
            'extract': ('Extracting...', 10),
            'parse': ('Parsing...', 20),
            'translate': ('Translating...', 30),
            'format': ('Formatting...', 90),
            'save': ('Saving...', 95),
            'complete': ('Complete!', 100)
        }
        self.cancelled = False
        self.errors = []
        self.warnings = []
    
    def start(self, title="Translating Subtitles"):
        """Start the progress dialog."""
        self.start_time = time.time()
        if self.show_dialog:
            self.dialog = xbmcgui.DialogProgress()
            init_msg = get_addon().getLocalizedString(30870) or "Initializing..."
            self.dialog.create(title, init_msg)
        self._log(f"Translation started - {self.total} subtitles to process")
    
    def set_stage(self, stage, message=None):
        """Set the current processing stage."""
        self.stage = stage
        stage_info = self.stages.get(stage, (stage, 50))
        display_message = message or stage_info[0]
        base_progress = stage_info[1]
        
        self._log(f"Stage: {stage} - {display_message}")
        
        if self.dialog and not self.cancelled:
            self.dialog.update(base_progress, display_message)
            self.cancelled = self.dialog.iscanceled()
    
    def update(self, current, message=None):
        """Update progress during translation stage."""
        self.current = current
        
        if self.total > 0:
            # Calculate progress within translation stage (30-90%)
            stage_progress = (current / self.total) * 60  # 60% of total bar for translation
            total_progress = 30 + int(stage_progress)  # Start at 30%
            percent = int((current / self.total) * 100)
        else:
            total_progress = 50
            percent = 50
        
        # Calculate ETA
        elapsed = time.time() - self.start_time if self.start_time else 0
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = (self.total - current) / rate if rate > 0 else 0
            eta_str = self._format_time(remaining)
        else:
            eta_str = "..."
        
        # Format message with clear percentage
        status_message = message or f"[{percent}%] {current}/{self.total}"
        full_message = f"{status_message}\n⏱ {eta_str}"
        
        if self.dialog and not self.cancelled:
            self.dialog.update(total_progress, full_message)
            self.cancelled = self.dialog.iscanceled()
        
        # Log every 10% progress
        if self.total > 0 and current % max(1, self.total // 10) == 0:
            self._log(f"Progress: {current}/{self.total} ({percent}%)")
    
    def add_error(self, error_msg, details=None):
        """Record an error."""
        error = {
            'time': datetime.now().isoformat(),
            'message': error_msg,
            'details': details,
            'stage': self.stage,
            'progress': f"{self.current}/{self.total}"
        }
        self.errors.append(error)
        self._log(f"ERROR: {error_msg}", xbmc.LOGERROR)
        if details:
            self._log(f"Details: {details}", xbmc.LOGERROR)
    
    def add_warning(self, warning_msg):
        """Record a warning."""
        self.warnings.append({
            'time': datetime.now().isoformat(),
            'message': warning_msg,
            'stage': self.stage
        })
        self._log(f"WARNING: {warning_msg}", xbmc.LOGWARNING)
    
    def is_cancelled(self):
        """Check if user cancelled."""
        if self.dialog:
            self.cancelled = self.dialog.iscanceled()
        return self.cancelled
    
    def complete(self, success=True, message=None):
        """Complete the progress dialog."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        if success:
            default_msg = get_addon().getLocalizedString(30871).format(self.current) if get_addon().getLocalizedString(30871) else f"Translated {self.current} subtitles"
            self.set_stage('complete', message or default_msg)
            self._log(f"Translation completed successfully in {self._format_time(elapsed)}")
        else:
            self._log(f"Translation failed after {self._format_time(elapsed)}", xbmc.LOGERROR)
        
        if self.dialog:
            self.dialog.close()
            self.dialog = None
        
        # Show summary notification
        if self.errors:
            xbmcgui.Dialog().notification(
                get_addon_name(),
                (get_addon().getLocalizedString(30872) or "Completed with {0} error(s)").format(len(self.errors)),
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
        elif success:
            xbmcgui.Dialog().notification(
                get_addon_name(),
                message or default_msg,
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
    
    def get_summary(self):
        """Get a summary of the translation process."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            'total_subtitles': self.total,
            'processed': self.current,
            'elapsed_time': self._format_time(elapsed),
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'cancelled': self.cancelled,
            'rate': f"{self.current / elapsed:.1f}/s" if elapsed > 0 else "N/A"
        }
    
    def _format_time(self, seconds):
        """Format seconds to readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds // 60:.0f}m {seconds % 60:.0f}s"
        else:
            return f"{seconds // 3600:.0f}h {(seconds % 3600) // 60:.0f}m"
    
    def _log(self, message, level=xbmc.LOGINFO):
        """Log message to Kodi log."""
        xbmc.log(f"[{get_addon_id()}] {message}", level)


class ErrorReporter:
    """
    Comprehensive error reporting and diagnostics.
    """
    
    def __init__(self, addon_data_path):
        self.log_path = os.path.join(addon_data_path, 'logs')
        self.error_log_path = os.path.join(addon_data_path, 'error_log.json')
        
        if not xbmcvfs.exists(self.log_path):
            xbmcvfs.mkdirs(self.log_path)
        
        self.errors = []
        self.load_errors()
    
    def load_errors(self):
        """Load existing error log."""
        if xbmcvfs.exists(self.error_log_path):
            try:
                with xbmcvfs.File(self.error_log_path, 'r') as f:
                    self.errors = json.loads(f.read())
            except:
                self.errors = []
    
    def save_errors(self):
        """Save error log."""
        # Keep only last 100 errors
        self.errors = self.errors[-100:]
        with xbmcvfs.File(self.error_log_path, 'w') as f:
            f.write(json.dumps(self.errors, indent=2, ensure_ascii=False))
    
    def report_error(self, error_type, message, exception=None, context=None):
        """
        Report an error with full context.
        
        Args:
            error_type: Category of error (api, ffmpeg, parse, etc.)
            message: Human-readable error message
            exception: Optional exception object
            context: Optional dict with additional context
        """
        error_entry = {
            'id': f"{int(time.time() * 1000)}",
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message,
            'exception': str(exception) if exception else None,
            'traceback': traceback.format_exc() if exception else None,
            'context': context or {},
            'system_info': self._get_system_info()
        }
        
        self.errors.append(error_entry)
        self.save_errors()
        
        # Log to Kodi
        self._log_error(error_entry)
        
        return error_entry['id']
    
    def _get_system_info(self):
        """Get system information for debugging."""
        try:
            return {
                'kodi_version': xbmc.getInfoLabel('System.BuildVersion'),
                'os': xbmc.getInfoLabel('System.OSVersionInfo'),
                'addon_version': get_addon().getAddonInfo('version'),
                'python_version': xbmc.getInfoLabel('System.PythonVersion') or 'Unknown',
                'free_memory': xbmc.getInfoLabel('System.FreeMemory'),
                'current_time': datetime.now().isoformat()
            }
        except:
            return {'error': 'Could not retrieve system info'}
    
    def _log_error(self, error_entry):
        """Log error to Kodi log with full details."""
        xbmc.log(f"[{get_addon_id()}] ===== ERROR REPORT =====", xbmc.LOGERROR)
        xbmc.log(f"[{get_addon_id()}] Type: {error_entry['type']}", xbmc.LOGERROR)
        xbmc.log(f"[{get_addon_id()}] Message: {error_entry['message']}", xbmc.LOGERROR)
        
        if error_entry['exception']:
            xbmc.log(f"[{get_addon_id()}] Exception: {error_entry['exception']}", xbmc.LOGERROR)
        
        if error_entry['traceback']:
            for line in error_entry['traceback'].split('\n'):
                if line.strip():
                    xbmc.log(f"[{get_addon_id()}] {line}", xbmc.LOGERROR)
        
        if error_entry['context']:
            xbmc.log(f"[{get_addon_id()}] Context: {json.dumps(error_entry['context'])}", xbmc.LOGERROR)
        
        xbmc.log(f"[{get_addon_id()}] ===== END ERROR REPORT =====", xbmc.LOGERROR)
    
    def get_recent_errors(self, count=10):
        """Get recent errors."""
        return self.errors[-count:]
    
    def get_errors_by_type(self, error_type):
        """Get errors of a specific type."""
        return [e for e in self.errors if e['type'] == error_type]
    
    def clear_errors(self):
        """Clear all errors."""
        self.errors = []
        self.save_errors()
    
    def export_diagnostics(self):
        """Export full diagnostics report."""
        report = {
            'generated': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'addon_settings': self._get_addon_settings(),
            'recent_errors': self.errors[-20:],
            'error_summary': self._get_error_summary()
        }
        
        report_path = os.path.join(self.log_path, f"diagnostics_{int(time.time())}.json")
        with xbmcvfs.File(report_path, 'w') as f:
            f.write(json.dumps(report, indent=2, ensure_ascii=False))
        
        return report_path
    
    def _get_addon_settings(self):
        """Get current addon settings (sanitized)."""
        settings = {}
        setting_ids = [
            'enabled', 'auto_translate', 'target_language', 'source_language',
            'translation_service', 'output_format', 'cache_enabled', 'debug_logging'
        ]
        
        for setting_id in setting_ids:
            try:
                value = get_addon().getSetting(setting_id)
                # Don't include API keys
                if 'api_key' not in setting_id and 'password' not in setting_id:
                    settings[setting_id] = value
            except:
                pass
        
        return settings
    
    def _get_error_summary(self):
        """Get summary of errors by type."""
        summary = {}
        for error in self.errors:
            error_type = error['type']
            if error_type not in summary:
                summary[error_type] = 0
            summary[error_type] += 1
        return summary


class DiagnosticsDialog:
    """
    Dialog for viewing diagnostics and error information.
    """
    
    def __init__(self, error_reporter):
        self.error_reporter = error_reporter
    
    def show(self):
        """Show diagnostics dialog."""
        options = [
            "View recent errors",
            "View system info",
            "Export diagnostics report",
            "Clear error log",
            "View translation statistics"
        ]
        
        dialog = xbmcgui.Dialog()
        selection = dialog.select("Diagnostics", options)
        
        if selection == 0:
            self._show_recent_errors()
        elif selection == 1:
            self._show_system_info()
        elif selection == 2:
            self._export_diagnostics()
        elif selection == 3:
            self._clear_errors()
        elif selection == 4:
            self._show_statistics()
    
    def _show_recent_errors(self):
        """Show recent errors in a dialog."""
        errors = self.error_reporter.get_recent_errors(10)
        
        if not errors:
            xbmcgui.Dialog().ok("Recent Errors", "No errors recorded.")
            return
        
        # Format errors for display
        error_list = []
        for e in reversed(errors):
            time_str = e['timestamp'].split('T')[1].split('.')[0]
            error_list.append(f"[{time_str}] {e['type']}: {e['message'][:50]}")
        
        dialog = xbmcgui.Dialog()
        selection = dialog.select("Recent Errors (newest first)", error_list)
        
        if selection >= 0:
            # Show full error details
            error = errors[-(selection + 1)]
            details = (
                f"Type: {error['type']}\n"
                f"Time: {error['timestamp']}\n"
                f"Message: {error['message']}\n"
            )
            if error['exception']:
                details += f"\nException: {error['exception']}"
            
            dialog.textviewer("Error Details", details)
    
    def _show_system_info(self):
        """Show system information."""
        info = self.error_reporter._get_system_info()
        
        text = "\n".join([f"{k}: {v}" for k, v in info.items()])
        xbmcgui.Dialog().textviewer("System Information", text)
    
    def _export_diagnostics(self):
        """Export diagnostics report."""
        path = self.error_reporter.export_diagnostics()
        xbmcgui.Dialog().ok(
            "Diagnostics Exported",
            f"Report saved to:\n{path}"
        )
    
    def _clear_errors(self):
        """Clear error log."""
        dialog = xbmcgui.Dialog()
        if dialog.yesno("Clear Errors", "Are you sure you want to clear all error logs?"):
            self.error_reporter.clear_errors()
            dialog.notification(get_addon_name(), "Error log cleared", xbmcgui.NOTIFICATION_INFO)
    
    def _show_statistics(self):
        """Show translation statistics."""
        # This would integrate with SubtitleStatistics from advanced_features.py
        xbmcgui.Dialog().ok("Statistics", "Statistics feature - see advanced_features.py")


class BatchProgressDialog:
    """
    Progress dialog for batch translation operations.
    """
    
    def __init__(self, total_videos):
        self.total_videos = total_videos
        self.current_video = 0
        self.dialog = None
        self.cancelled = False
        self.results = []
    
    def start(self):
        """Start batch progress dialog."""
        self.dialog = xbmcgui.DialogProgress()
        self.dialog.create(
            "Batch Translation",
            f"Processing 0/{self.total_videos} videos..."
        )
    
    def next_video(self, video_name, subtitle_count=0):
        """Move to next video."""
        self.current_video += 1
        progress = int((self.current_video / self.total_videos) * 100)
        
        message = (
            f"Video {self.current_video}/{self.total_videos}\n"
            f"{video_name}\n"
            f"Subtitles: {subtitle_count}"
        )
        
        if self.dialog:
            self.dialog.update(progress, message)
            self.cancelled = self.dialog.iscanceled()
    
    def record_result(self, video_name, success, error=None):
        """Record result for a video."""
        self.results.append({
            'video': video_name,
            'success': success,
            'error': error
        })
    
    def is_cancelled(self):
        """Check if cancelled."""
        if self.dialog:
            self.cancelled = self.dialog.iscanceled()
        return self.cancelled
    
    def complete(self):
        """Complete batch operation."""
        if self.dialog:
            self.dialog.close()
        
        # Show summary
        successful = len([r for r in self.results if r['success']])
        failed = len([r for r in self.results if not r['success']])
        
        message = f"Processed {self.total_videos} videos\n"
        message += f"Successful: {successful}\n"
        message += f"Failed: {failed}"
        
        if failed > 0:
            message += "\n\nFailed videos:"
            for r in self.results:
                if not r['success']:
                    message += f"\n- {r['video']}: {r['error']}"
        
        xbmcgui.Dialog().textviewer("Batch Translation Complete", message)
        
        return self.results


class DebugLogger:
    """
    Enhanced debug logging with levels and categories.
    """
    
    LEVELS = {
        'debug': xbmc.LOGDEBUG,
        'info': xbmc.LOGINFO,
        'warning': xbmc.LOGWARNING,
        'error': xbmc.LOGERROR
    }
    
    def __init__(self, addon_data_path, enabled=False):
        self.enabled = enabled
        self.log_file_path = os.path.join(addon_data_path, 'debug.log')
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.categories = set()  # Active categories
    
    def enable(self, categories=None):
        """Enable debug logging for specific categories."""
        self.enabled = True
        if categories:
            self.categories = set(categories)
    
    def disable(self):
        """Disable debug logging."""
        self.enabled = False
    
    def log(self, message, level='info', category='general'):
        """Log a message."""
        if not self.enabled and level != 'error':
            return
        
        if self.categories and category not in self.categories:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_level = self.LEVELS.get(level, xbmc.LOGINFO)
        
        formatted = f"[{timestamp}] [{level.upper()}] [{category}] {message}"
        
        # Log to Kodi
        xbmc.log(f"[{get_addon_id()}] {formatted}", log_level)
        
        # Log to file if debug enabled
        if self.enabled:
            self._write_to_file(formatted)
    
    def _write_to_file(self, message):
        """Write to debug log file."""
        try:
            # Check file size and rotate if needed
            if xbmcvfs.exists(self.log_file_path):
                stat = xbmcvfs.Stat(self.log_file_path)
                if stat.st_size() > self.max_file_size:
                    self._rotate_log()
            
            with xbmcvfs.File(self.log_file_path, 'a') as f:
                f.write(message + '\n')
        except:
            pass
    
    def _rotate_log(self):
        """Rotate log file."""
        try:
            backup_path = self.log_file_path + '.old'
            if xbmcvfs.exists(backup_path):
                xbmcvfs.delete(backup_path)
            xbmcvfs.rename(self.log_file_path, backup_path)
        except:
            pass
    
    def debug(self, message, category='general'):
        """Log debug message."""
        self.log(message, 'debug', category)
    
    def info(self, message, category='general'):
        """Log info message."""
        self.log(message, 'info', category)
    
    def warning(self, message, category='general'):
        """Log warning message."""
        self.log(message, 'warning', category)
    
    def error(self, message, category='general'):
        """Log error message."""
        self.log(message, 'error', category)
    
    def api(self, service, request_type, url, response_code=None, error=None):
        """Log API request/response."""
        if response_code:
            self.debug(f"API {service}: {request_type} {url} -> {response_code}", 'api')
        if error:
            self.error(f"API {service}: {request_type} {url} -> ERROR: {error}", 'api')
    
    def timing(self, operation, duration_ms):
        """Log timing information."""
        self.debug(f"TIMING {operation}: {duration_ms:.2f}ms", 'performance')
    
    def dump_object(self, name, obj, category='debug'):
        """Dump object to log for debugging."""
        try:
            if isinstance(obj, (dict, list)):
                dump = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
            else:
                dump = str(obj)
            
            self.debug(f"DUMP {name}:\n{dump}", category)
        except Exception as e:
            self.error(f"Failed to dump {name}: {e}", category)
