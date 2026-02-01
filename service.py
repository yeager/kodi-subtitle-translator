# -*- coding: utf-8 -*-
"""
Subtitle Translator - Kodi Service
Automatically translates embedded subtitles when no subtitle is available
in the user's preferred language.
"""

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import json
import os
import hashlib
import time

# Lazy imports to avoid crashes at startup
SubtitleExtractor = None
get_translator = None
SubtitleParser = None
TranslationProgress = None
ErrorReporter = None
DebugLogger = None
show_translate_confirm = None
get_current_thumbnail = None
get_current_media_title = None

# Lazy-loaded globals
_addon = None
_addon_path = None
_addon_data = None
_cache_path = None
_error_reporter = None
_debug_logger = None


def get_addon():
    """Get addon instance (lazy loaded)."""
    global _addon
    if _addon is None:
        _addon = xbmcaddon.Addon()
    return _addon


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


def get_addon_path():
    """Get addon path (lazy loaded)."""
    global _addon_path
    if _addon_path is None:
        _addon_path = xbmcvfs.translatePath(get_addon().getAddonInfo('path'))
    return _addon_path


def get_addon_data():
    """Get addon data path (lazy loaded)."""
    global _addon_data
    if _addon_data is None:
        _addon_data = xbmcvfs.translatePath(get_addon().getAddonInfo('profile'))
        if not xbmcvfs.exists(_addon_data):
            xbmcvfs.mkdirs(_addon_data)
    return _addon_data


def get_cache_path():
    """Get cache path (lazy loaded)."""
    global _cache_path
    if _cache_path is None:
        _cache_path = os.path.join(get_addon_data(), 'cache')
        if not xbmcvfs.exists(_cache_path):
            xbmcvfs.mkdirs(_cache_path)
    return _cache_path


def init_libraries():
    """Initialize library imports (called from main)."""
    global SubtitleExtractor, get_translator, SubtitleParser
    global TranslationProgress, ErrorReporter, DebugLogger
    global show_translate_confirm, get_current_thumbnail, get_current_media_title
    global _error_reporter, _debug_logger
    
    from lib.subtitle_extractor import SubtitleExtractor as SE
    from lib.translators import get_translator as gt
    from lib.subtitle_parser import SubtitleParser as SP
    from lib.progress_dialog import TranslationProgress as TP, ErrorReporter as ER, DebugLogger as DL
    from lib.dialogs import show_translate_confirm as stc, get_current_thumbnail as gct, get_current_media_title as gcmt
    
    SubtitleExtractor = SE
    get_translator = gt
    SubtitleParser = SP
    TranslationProgress = TP
    ErrorReporter = ER
    DebugLogger = DL
    show_translate_confirm = stc
    get_current_thumbnail = gct
    get_current_media_title = gcmt
    
    # Initialize reporter and logger
    _error_reporter = ER(get_addon_data())
    _debug_logger = DL(get_addon_data())


def get_error_reporter():
    """Get error reporter instance."""
    global _error_reporter
    if _error_reporter is None:
        init_libraries()
    return _error_reporter


def get_debug_logger():
    """Get debug logger instance."""
    global _debug_logger
    if _debug_logger is None:
        init_libraries()
    return _debug_logger


# Use get_debug_logger() and get_error_reporter() functions


class SubtitleTranslatorMonitor(xbmc.Monitor):
    """Monitor for Kodi events."""
    
    def __init__(self):
        super().__init__()
        self.player = SubtitleTranslatorPlayer()
    
    def onSettingsChanged(self):
        """Called when addon settings are changed."""
        log("Settings changed, reloading configuration")
        self.player.reload_settings()


class SubtitleTranslatorPlayer(xbmc.Player):
    """Player monitor for subtitle translation."""
    
    def __init__(self):
        super().__init__()
        self.reload_settings()
        self.current_file = None
        self.translation_in_progress = False
    
    def reload_settings(self):
        """Reload settings from addon configuration."""
        self.enabled = get_setting_bool('enabled')
        self.auto_translate = get_setting_bool('auto_translate')
        self.show_notification = get_setting_bool('show_notification')
        self.ask_before_translate = get_setting_bool('ask_before_translate')
        self.target_language = get_setting('target_language')
        self.source_language = get_setting('source_language')
        self.translation_service = get_setting('translation_service')
        self.cache_translations = get_setting_bool('cache_translations')
        self.cache_days = get_setting_int('cache_days')
        self.save_alongside = get_setting_bool('save_alongside_video')
        self.subtitle_format = get_setting('subtitle_format')
        self.batch_size = get_setting_int('batch_size')
        self.debug = get_setting_bool('debug_logging')
        
        log(f"Settings loaded: target={self.target_language}, "
            f"source={self.source_language}, service={self.translation_service}")
    
    def onAVStarted(self):
        """Called when audio/video playback starts."""
        if not self.enabled:
            return
        
        try:
            self.current_file = self.getPlayingFile()
            log(f"Playback started: {self.current_file}")
            
            # Wait a moment for Kodi to load subtitle info
            xbmc.sleep(2000)
            
            if self.isPlaying():
                self.check_and_translate_subtitles()
        except Exception as e:
            log(f"Error in onAVStarted: {e}", level=xbmc.LOGERROR)
    
    def check_and_translate_subtitles(self):
        """Check if translation is needed and perform it."""
        if self.translation_in_progress:
            log("Translation already in progress, skipping")
            return
        
        try:
            # Get available subtitles
            available_subs = self.get_available_subtitles()
            log(f"Available subtitles: {available_subs}")
            
            # Check if target language is available
            target_available = any(
                sub.get('language', '').lower().startswith(self.target_language.lower())
                for sub in available_subs
            )
            
            if target_available:
                log(f"Subtitle already available in {self.target_language}")
                return
            
            # Find source subtitle
            source_sub = self.find_source_subtitle(available_subs)
            if not source_sub:
                log("No suitable source subtitle found")
                if self.show_notification:
                    notify(get_string(30703))  # No embedded subtitles found
                return
            
            # Ask user if configured
            if self.ask_before_translate:
                msg = get_string(30706).format(
                    self.get_language_name(self.target_language),
                    self.get_language_name(source_sub.get('language', 'en'))
                )
                # Show confirmation dialog with thumbnail
                thumbnail = get_current_thumbnail()
                media_title = get_current_media_title()
                
                if not show_translate_confirm(
                    title=get_addon_name(),
                    message=msg,
                    thumbnail=thumbnail,
                    media_title=media_title
                ):
                    log("User declined translation")
                    return
            
            # Perform translation
            self.translate_subtitle(source_sub)
            
        except Exception as e:
            log(f"Error checking subtitles: {e}", level=xbmc.LOGERROR)
    
    def get_available_subtitles(self):
        """Get list of available subtitles for current video."""
        subtitles = []
        
        # Get subtitle streams from video info
        info = self.getVideoInfoTag()
        
        # Use JSON-RPC to get detailed player info
        result = execute_jsonrpc('Player.GetProperties', {
            'playerid': 1,
            'properties': ['subtitles', 'currentsubtitle']
        })
        
        if result and 'subtitles' in result:
            subtitles = result['subtitles']
        
        return subtitles
    
    def find_source_subtitle(self, subtitles):
        """Find the best source subtitle for translation."""
        source_lang = self.source_language.lower()
        
        # First, try to find the specified source language
        if source_lang != 'auto':
            for sub in subtitles:
                lang = sub.get('language', '').lower()
                if lang.startswith(source_lang):
                    return sub
        
        # Fallback: look for English
        for sub in subtitles:
            lang = sub.get('language', '').lower()
            if lang.startswith('en'):
                return sub
        
        # Last resort: take the first subtitle
        if subtitles:
            return subtitles[0]
        
        return None
    
    def translate_subtitle(self, source_sub):
        """Translate the subtitle with progress tracking."""
        self.translation_in_progress = True
        progress = None
        
        try:
            get_debug_logger().info(f"Starting translation for: {self.current_file}", 'translation')
            get_debug_logger().debug(f"Source subtitle: {source_sub}", 'translation')
            
            # Check cache first
            cache_key = self.get_cache_key(source_sub)
            cached_path = self.get_cached_subtitle(cache_key)
            
            if cached_path and xbmcvfs.exists(cached_path):
                get_debug_logger().info(f"Cache hit: {cached_path}", 'cache')
                self.load_subtitle(cached_path)
                if self.show_notification:
                    notify(get_string(30705))  # Using cached translation
                return
            
            get_debug_logger().debug("Cache miss, starting translation", 'cache')
            
            # Initialize progress dialog
            progress = TranslationProgress(show_dialog=self.show_notification)
            progress.start(f"Translating to {self.get_language_name(self.target_language)}")
            
            # Extract subtitle from video
            progress.set_stage('extract', f"Extracting subtitles from video...")
            get_debug_logger().debug(f"Extracting subtitle index {source_sub.get('index', 0)}", 'ffmpeg')
            
            extractor = SubtitleExtractor(get_setting('ffmpeg_path'))
            subtitle_content = extractor.extract(
                self.current_file,
                source_sub.get('index', 0)
            )
            
            if not subtitle_content:
                error_msg = "Failed to extract subtitle - FFmpeg returned empty content"
                get_error_reporter().report_error('ffmpeg', error_msg, context={
                    'file': self.current_file,
                    'subtitle_index': source_sub.get('index', 0)
                })
                raise Exception(error_msg)
            
            get_debug_logger().debug(f"Extracted {len(subtitle_content)} bytes", 'ffmpeg')
            
            # Parse subtitle
            progress.set_stage('parse', "Parsing subtitle file...")
            parser = SubtitleParser()
            entries = parser.parse(subtitle_content)
            
            if not entries:
                error_msg = "No subtitle entries found in extracted content"
                get_error_reporter().report_error('parse', error_msg, context={
                    'content_length': len(subtitle_content),
                    'content_preview': subtitle_content[:500]
                })
                raise Exception(error_msg)
            
            get_debug_logger().info(f"Parsed {len(entries)} subtitle entries", 'parse')
            progress.total = len(entries)
            
            # Check for cancellation
            if progress.is_cancelled():
                get_debug_logger().info("Translation cancelled by user", 'translation')
                return
            
            # Get translator
            progress.set_stage('translate', f"Connecting to {self.translation_service}...")
            get_debug_logger().debug(f"Using translation service: {self.translation_service}", 'api')
            
            translator = get_translator(
                self.translation_service,
                self.get_service_config()
            )
            
            # Translate in batches with progress
            translated_entries = []
            batch_size = self.batch_size
            total_batches = (len(entries) + batch_size - 1) // batch_size
            
            get_debug_logger().debug(f"Translating in {total_batches} batches of {batch_size}", 'translation')
            
            for batch_num, i in enumerate(range(0, len(entries), batch_size)):
                if progress.is_cancelled():
                    get_debug_logger().info("Translation cancelled by user", 'translation')
                    return
                
                batch = entries[i:i + batch_size]
                texts = [e['text'] for e in batch]
                
                # Update progress
                progress.update(
                    i + len(batch),
                    f"Translating batch {batch_num + 1}/{total_batches}..."
                )
                
                try:
                    get_debug_logger().debug(f"Translating batch {batch_num + 1}: {len(texts)} entries", 'api')
                    import time as _time
                    start_time = _time.time()
                    
                    translated_texts = translator.translate_batch(
                        texts,
                        self.source_language,
                        self.target_language
                    )
                    
                    elapsed = (_time.time() - start_time) * 1000
                    get_debug_logger().timing(f"Batch {batch_num + 1} translation", elapsed)
                    
                except Exception as api_error:
                    get_error_reporter().report_error('api', f"Translation API error in batch {batch_num + 1}", api_error, {
                        'service': self.translation_service,
                        'batch_size': len(texts),
                        'source_lang': self.source_language,
                        'target_lang': self.target_language
                    })
                    progress.add_error(f"API error in batch {batch_num + 1}", str(api_error))
                    # Use original text as fallback
                    translated_texts = texts
                    progress.add_warning(f"Using original text for batch {batch_num + 1}")
                
                for j, entry in enumerate(batch):
                    translated_entry = entry.copy()
                    if j < len(translated_texts):
                        translated_entry['text'] = translated_texts[j]
                    translated_entries.append(translated_entry)
                
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(entries):
                    xbmc.sleep(500)
            
            # Format output
            progress.set_stage('format', "Formatting subtitle file...")
            get_debug_logger().debug(f"Generating {self.subtitle_format} output", 'format')
            
            output_content = parser.generate(
                translated_entries,
                self.subtitle_format
            )
            
            # Save subtitle
            progress.set_stage('save', "Saving translated subtitles...")
            output_path = self.save_subtitle(output_content, cache_key)
            get_debug_logger().info(f"Saved subtitle to: {output_path}", 'save')
            
            # Load the translated subtitle
            self.load_subtitle(output_path)
            
            # Complete
            summary = progress.get_summary()
            get_debug_logger().info(f"Translation complete: {summary}", 'translation')
            progress.complete(True, f"Translated {len(translated_entries)} subtitles in {summary['elapsed_time']}")
            
        except Exception as e:
            get_debug_logger().error(f"Translation failed: {e}", 'translation')
            get_error_reporter().report_error('translation', f"Translation failed: {str(e)}", e, {
                'file': self.current_file,
                'service': self.translation_service,
                'source_lang': self.source_language,
                'target_lang': self.target_language
            })
            
            if progress:
                progress.add_error(str(e))
                progress.complete(False)
            else:
                notify(get_string(30702), icon=xbmcgui.NOTIFICATION_ERROR)
        
        finally:
            self.translation_in_progress = False
    
    def get_cache_key(self, source_sub):
        """Generate a unique cache key for the subtitle."""
        key_data = f"{self.current_file}|{source_sub.get('index', 0)}|{self.target_language}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_cached_subtitle(self, cache_key):
        """Get path to cached subtitle if it exists and is valid."""
        if not self.cache_translations:
            return None
        
        cache_file = os.path.join(get_cache_path(), f"{cache_key}.{self.subtitle_format}")
        meta_file = os.path.join(get_cache_path(), f"{cache_key}.json")
        
        if not xbmcvfs.exists(cache_file) or not xbmcvfs.exists(meta_file):
            return None
        
        # Check cache age
        try:
            with xbmcvfs.File(meta_file, 'r') as f:
                meta = json.loads(f.read())
            
            cache_time = meta.get('timestamp', 0)
            max_age = self.cache_days * 24 * 60 * 60
            
            if time.time() - cache_time > max_age:
                log(f"Cache expired for {cache_key}")
                return None
            
            return cache_file
        except:
            return None
    
    def save_subtitle(self, content, cache_key):
        """Save translated subtitle to cache and optionally alongside video."""
        # Save to cache
        cache_file = os.path.join(get_cache_path(), f"{cache_key}.{self.subtitle_format}")
        meta_file = os.path.join(get_cache_path(), f"{cache_key}.json")
        
        with xbmcvfs.File(cache_file, 'w') as f:
            f.write(content)
        
        with xbmcvfs.File(meta_file, 'w') as f:
            f.write(json.dumps({
                'timestamp': time.time(),
                'source_file': self.current_file,
                'target_language': self.target_language
            }))
        
        output_path = cache_file
        
        # Optionally save alongside video
        if self.save_alongside:
            video_dir = os.path.dirname(self.current_file)
            video_name = os.path.splitext(os.path.basename(self.current_file))[0]
            alongside_path = os.path.join(
                video_dir,
                f"{video_name}.{self.target_language}.{self.subtitle_format}"
            )
            
            try:
                with xbmcvfs.File(alongside_path, 'w') as f:
                    f.write(content)
                output_path = alongside_path
                log(f"Saved subtitle alongside video: {alongside_path}")
            except Exception as e:
                log(f"Could not save alongside video: {e}", level=xbmc.LOGWARNING)
        
        return output_path
    
    def load_subtitle(self, path):
        """Load a subtitle file into the player."""
        self.setSubtitles(path)
        log(f"Loaded subtitle: {path}")
    
    def get_service_config(self):
        """Get configuration for the selected translation service."""
        config = {
            'timeout': get_setting_int('request_timeout')
        }
        
        if self.translation_service == 'deepl':
            config['api_key'] = get_setting('deepl_api_key')
            config['formality'] = get_setting('deepl_formality')
            config['free'] = False
        elif self.translation_service == 'deepl_free':
            config['api_key'] = get_setting('deepl_free_api_key')
            config['formality'] = get_setting('deepl_formality')
            config['free'] = True
        elif self.translation_service == 'libretranslate':
            config['url'] = get_setting('libretranslate_url')
            config['api_key'] = get_setting('libretranslate_api_key')
        elif self.translation_service == 'google':
            config['api_key'] = get_setting('google_api_key')
        elif self.translation_service == 'microsoft':
            config['api_key'] = get_setting('microsoft_api_key')
            config['region'] = get_setting('microsoft_region')
        elif self.translation_service == 'lingva':
            config['url'] = get_setting('lingva_url')
        elif self.translation_service == 'openai':
            config['api_key'] = get_setting('openai_api_key')
            config['model'] = get_setting('openai_model')
            base_url = get_setting('openai_base_url')
            if base_url:
                config['base_url'] = base_url
        elif self.translation_service == 'anthropic':
            config['api_key'] = get_setting('anthropic_api_key')
            config['model'] = get_setting('anthropic_model')
        elif self.translation_service == 'argos':
            config['package_path'] = get_setting('argos_package_path')
        
        return config
    
    def get_language_name(self, code):
        """Get human-readable language name from code."""
        names = {
            'sv': 'Svenska', 'en': 'English', 'de': 'Deutsch',
            'fr': 'Français', 'es': 'Español', 'it': 'Italiano',
            'no': 'Norsk', 'da': 'Dansk', 'fi': 'Suomi',
            'nl': 'Nederlands', 'pl': 'Polski', 'pt': 'Português',
            'ru': 'Русский', 'ja': '日本語', 'zh': '中文', 'ko': '한국어'
        }
        return names.get(code, code)


# Helper functions
def get_setting(key):
    """Get addon setting."""
    return get_addon().getSetting(key)

def get_setting_bool(key):
    """Get boolean addon setting."""
    return get_addon().getSettingBool(key)

def get_setting_int(key):
    """Get integer addon setting."""
    return get_addon().getSettingInt(key)

def get_string(string_id):
    """Get localized string."""
    return get_addon().getLocalizedString(string_id)

def log(message, level=xbmc.LOGINFO):
    """Log message to Kodi log."""
    xbmc.log(f"[{get_addon_id()}] {message}", level)

def notify(message, icon=xbmcgui.NOTIFICATION_INFO, time=5000):
    """Show notification."""
    xbmcgui.Dialog().notification(get_addon_name(), message, icon, time)

def execute_jsonrpc(method, params=None):
    """Execute JSON-RPC command."""
    request = {
        'jsonrpc': '2.0',
        'method': method,
        'params': params or {},
        'id': 1
    }
    response = xbmc.executeJSONRPC(json.dumps(request))
    return json.loads(response).get('result')


def main():
    """Main entry point."""
    try:
        # Initialize libraries first
        init_libraries()
        log("Subtitle Translator service started")
        
        monitor = SubtitleTranslatorMonitor()
        
        while not monitor.abortRequested():
            if monitor.waitForAbort(1):
                break
        
        log("Subtitle Translator service stopped")
    except Exception as e:
        xbmc.log(f"[SubtitleTranslator] Fatal error: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"[SubtitleTranslator] {traceback.format_exc()}", xbmc.LOGERROR)


if __name__ == '__main__':
    main()
