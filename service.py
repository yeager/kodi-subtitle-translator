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
from lib.subtitle_extractor import SubtitleExtractor
from lib.translators import get_translator
from lib.subtitle_parser import SubtitleParser

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# Ensure addon data folder exists
if not xbmcvfs.exists(ADDON_DATA):
    xbmcvfs.mkdirs(ADDON_DATA)

CACHE_PATH = os.path.join(ADDON_DATA, 'cache')
if not xbmcvfs.exists(CACHE_PATH):
    xbmcvfs.mkdirs(CACHE_PATH)


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
                    notify(get_string(30603))  # No embedded subtitles found
                return
            
            # Ask user if configured
            if self.ask_before_translate:
                msg = get_string(30606).format(
                    self.get_language_name(self.target_language),
                    self.get_language_name(source_sub.get('language', 'en'))
                )
                if not xbmcgui.Dialog().yesno(ADDON_NAME, msg):
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
        """Translate the subtitle."""
        self.translation_in_progress = True
        
        try:
            if self.show_notification:
                notify(get_string(30600))  # Translating subtitles...
            
            # Check cache first
            cache_key = self.get_cache_key(source_sub)
            cached_path = self.get_cached_subtitle(cache_key)
            
            if cached_path and xbmcvfs.exists(cached_path):
                log(f"Using cached translation: {cached_path}")
                self.load_subtitle(cached_path)
                if self.show_notification:
                    notify(get_string(30601))  # Translation complete
                return
            
            # Extract subtitle from video
            extractor = SubtitleExtractor(get_setting('ffmpeg_path'))
            subtitle_content = extractor.extract(
                self.current_file,
                source_sub.get('index', 0)
            )
            
            if not subtitle_content:
                raise Exception("Failed to extract subtitle")
            
            # Parse subtitle
            parser = SubtitleParser()
            entries = parser.parse(subtitle_content)
            
            if not entries:
                raise Exception("No subtitle entries found")
            
            log(f"Extracted {len(entries)} subtitle entries")
            
            # Get translator
            translator = get_translator(
                self.translation_service,
                self.get_service_config()
            )
            
            # Translate in batches
            translated_entries = []
            batch_size = self.batch_size
            
            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                texts = [e['text'] for e in batch]
                
                translated_texts = translator.translate_batch(
                    texts,
                    self.source_language,
                    self.target_language
                )
                
                for j, entry in enumerate(batch):
                    translated_entry = entry.copy()
                    translated_entry['text'] = translated_texts[j]
                    translated_entries.append(translated_entry)
                
                # Small delay between batches
                if i + batch_size < len(entries):
                    xbmc.sleep(500)
            
            # Generate output subtitle
            output_content = parser.generate(
                translated_entries,
                self.subtitle_format
            )
            
            # Save subtitle
            output_path = self.save_subtitle(output_content, cache_key)
            
            # Load the translated subtitle
            self.load_subtitle(output_path)
            
            if self.show_notification:
                notify(get_string(30601))  # Translation complete
            
            log(f"Translation complete: {output_path}")
            
        except Exception as e:
            log(f"Translation failed: {e}", level=xbmc.LOGERROR)
            if self.show_notification:
                notify(get_string(30602), icon=xbmcgui.NOTIFICATION_ERROR)
        
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
        
        cache_file = os.path.join(CACHE_PATH, f"{cache_key}.{self.subtitle_format}")
        meta_file = os.path.join(CACHE_PATH, f"{cache_key}.json")
        
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
        cache_file = os.path.join(CACHE_PATH, f"{cache_key}.{self.subtitle_format}")
        meta_file = os.path.join(CACHE_PATH, f"{cache_key}.json")
        
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
    return ADDON.getSetting(key)

def get_setting_bool(key):
    """Get boolean addon setting."""
    return ADDON.getSettingBool(key)

def get_setting_int(key):
    """Get integer addon setting."""
    return ADDON.getSettingInt(key)

def get_string(string_id):
    """Get localized string."""
    return ADDON.getLocalizedString(string_id)

def log(message, level=xbmc.LOGINFO):
    """Log message to Kodi log."""
    xbmc.log(f"[{ADDON_ID}] {message}", level)

def notify(message, icon=xbmcgui.NOTIFICATION_INFO, time=5000):
    """Show notification."""
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon, time)

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
    log("Subtitle Translator service started")
    
    monitor = SubtitleTranslatorMonitor()
    
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    
    log("Subtitle Translator service stopped")


if __name__ == '__main__':
    main()
