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
show_subtitle_source_dialog = None
browse_subtitle_file = None

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
    global show_subtitle_source_dialog, browse_subtitle_file
    global _error_reporter, _debug_logger
    
    from lib.subtitle_extractor import SubtitleExtractor as SE
    from lib.translators import get_translator as gt
    from lib.subtitle_parser import SubtitleParser as SP
    from lib.progress_dialog import TranslationProgress as TP, ErrorReporter as ER, DebugLogger as DL
    from lib.dialogs import show_translate_confirm as stc, get_current_thumbnail as gct, get_current_media_title as gcmt, show_subtitle_source_dialog as sssd, browse_subtitle_file as bsf
    
    SubtitleExtractor = SE
    get_translator = gt
    SubtitleParser = SP
    TranslationProgress = TP
    ErrorReporter = ER
    DebugLogger = DL
    show_translate_confirm = stc
    get_current_thumbnail = gct
    get_current_media_title = gcmt
    show_subtitle_source_dialog = sssd
    browse_subtitle_file = bsf
    
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
        
        # Validate API key for services that require one
        self._validate_api_key_on_load()
        
        log(f"Settings loaded: target={self.target_language}, "
            f"source={self.source_language}, service={self.translation_service}")
    
    # Services that require an API key and their setting keys
    _API_KEY_SERVICES = {
        'deepl': 'deepl_api_key',
        'deepl_free': 'deepl_api_key',
        'google': 'google_api_key',
        'microsoft': 'microsoft_api_key',
        'openai': 'openai_api_key',
        'anthropic': 'anthropic_api_key',
    }
    
    def _service_needs_api_key(self, service=None):
        """Check if a service requires an API key."""
        service = service or self.translation_service
        return service in self._API_KEY_SERVICES
    
    def _get_api_key_for_service(self, service=None):
        """Get the API key for a service, or empty string if none."""
        service = service or self.translation_service
        setting_key = self._API_KEY_SERVICES.get(service)
        if setting_key:
            return get_setting(setting_key)
        return ''
    
    def _validate_api_key_on_load(self):
        """Validate API key at settings load time and notify user if missing."""
        if self._service_needs_api_key() and not self._get_api_key_for_service():
            service_name = self.translation_service.replace('_', ' ').title()
            msg = get_string(30851).format(service_name)  # "{0} requires an API key..."
            log(msg, level=xbmc.LOGWARNING)
            try:
                notify(msg, icon=xbmcgui.NOTIFICATION_WARNING)
            except Exception:
                pass
    
    def _ensure_ffmpeg_available(self, configured_path=None):
        """Check if FFmpeg is available. If not, show a dialog with options.
        
        Returns:
            FFmpeg path string if found, or None if user cancelled.
        """
        from lib.subtitle_extractor import SubtitleExtractor as SE, is_android, download_ffmpeg_android
        
        while True:
            # Try creating extractor with configured path
            test_extractor = SE(configured_path if configured_path else None)
            if test_extractor.ffmpeg_path:
                return test_extractor.ffmpeg_path
            
            # FFmpeg not found — show dialog with options
            dialog = xbmcgui.Dialog()
            options = []
            option_actions = []
            
            # On Android, offer automatic download as first option
            if is_android():
                options.append(get_string(30873))  # "Download FFmpeg automatically"
                option_actions.append('download')
            
            options.append(get_string(30862))  # "Show installation instructions"
            option_actions.append('instructions')
            options.append(get_string(30863))  # "Browse for FFmpeg..."
            option_actions.append('browse')
            options.append(get_string(30864))  # "Try again"
            option_actions.append('retry')
            options.append(get_string(30865))  # "Cancel"
            option_actions.append('cancel')
            
            choice = dialog.select(get_string(30860), options)  # "FFmpeg not found"
            
            if choice < 0:
                return None
            
            action = option_actions[choice]
            
            if action == 'download':
                # Auto-download FFmpeg for Android
                pDialog = xbmcgui.DialogProgress()
                pDialog.create(get_string(30874))  # "Downloading FFmpeg for Android..."
                
                def progress_cb(binary_name):
                    pDialog.update(50 if binary_name == 'ffprobe' else 10,
                                   f"{get_string(30874)} {binary_name}...")
                
                ffmpeg_path = download_ffmpeg_android(progress_callback=progress_cb)
                pDialog.close()
                
                if ffmpeg_path:
                    # Test it
                    test = SE(ffmpeg_path)
                    if test.ffmpeg_path:
                        try:
                            from xbmcaddon import Addon
                            Addon().setSetting('ffmpeg_path', ffmpeg_path)
                        except:
                            pass
                        notify(get_string(30875))  # "FFmpeg downloaded successfully!"
                        return ffmpeg_path
                
                # Download failed
                dialog.ok(get_string(30860), get_string(30876))  # "Download failed..."
                continue
            
            elif action == 'instructions':
                # Show installation instructions
                dialog.textviewer(get_string(30860), get_string(30861))
                continue
            
            elif action == 'browse':
                # Browse for FFmpeg executable
                ffmpeg_file = dialog.browseSingle(
                    1,  # ShowAndGetFile
                    get_string(30866),  # "Select FFmpeg executable"
                    ''  # No mask - show all files
                )
                if ffmpeg_file:
                    # Test the selected path
                    test = SE(ffmpeg_file)
                    if test.ffmpeg_path:
                        # Save to settings for next time
                        try:
                            from xbmcaddon import Addon
                            Addon().setSetting('ffmpeg_path', ffmpeg_file)
                        except:
                            pass
                        notify(get_string(30867).format(ffmpeg_file))
                        return ffmpeg_file
                    else:
                        dialog.ok(get_string(30860), 
                                  get_string(30869).format(ffmpeg_file))
                continue
            elif action == 'retry':
                # Try again - loop
                configured_path = None
                continue
            else:
                # Cancel or back (-1)
                return None

    def _auto_fallback_if_needed(self):
        """Auto-fallback to Lingva if the selected service needs an API key that's missing.
        
        Returns:
            The actual service name to use (may differ from self.translation_service).
        """
        if self._service_needs_api_key() and not self._get_api_key_for_service():
            original = self.translation_service.replace('_', ' ').title()
            msg = get_string(30850).format(original)  # "No API key for {0} — using Lingva"
            log(msg, level=xbmc.LOGWARNING)
            notify(msg, icon=xbmcgui.NOTIFICATION_WARNING)
            return 'lingva'
        return self.translation_service
    
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
            # Get available embedded subtitles
            available_subs = self.get_available_subtitles()
            log(f"Available embedded subtitles: {available_subs}")
            log(f"Target language: {self.target_language}, Source language: {self.source_language}")
            log(f"ask_before_translate: {self.ask_before_translate}")
            
            # Check if target language is already available in embedded subtitles
            target_in_embedded = any(
                self._lang_match(sub.get('language', ''), self.target_language)
                for sub in available_subs
            )
            
            # Also check if target language exists as external subtitle
            target_external_path = self.find_external_subtitle_for_language(self.target_language)
            
            if target_in_embedded:
                log(f"Embedded subtitle already available in {self.target_language}, skipping translation")
                if self.show_notification:
                    notify(get_string(30719))  # "Subtitle already available in target language"
                return
            
            if target_external_path:
                log(f"External subtitle already available in {self.target_language}: {target_external_path}, loading it")
                if self.show_notification:
                    notify(get_string(30719))  # "Subtitle already available in target language"
                self.load_subtitle(target_external_path)
                return
            
            # Find embedded source subtitle
            source_sub = self.find_source_subtitle(available_subs)
            embedded_lang = source_sub.get('language', 'en') if source_sub else None
            log(f"Found embedded source subtitle: {source_sub is not None}, language: {embedded_lang}")
            
            # Look for external subtitle file (in source language)
            external_sub_path = self.find_external_subtitle(self.source_language)
            log(f"Found external subtitle: {external_sub_path}")
            
            # If external sub found, try to determine its language from filename
            if external_sub_path:
                ext_lang = self._parse_language_from_filename(os.path.basename(external_sub_path))
                if ext_lang:
                    log(f"External subtitle language from filename: {ext_lang}")
                else:
                    log(f"External subtitle has no language tag in filename")
            
            # Determine which source to use
            subtitle_source = None  # 'embedded', 'external', or path from browse
            subtitle_content = None
            
            if source_sub and external_sub_path:
                # Both sources available - ask user which to use
                log("Both embedded and external subtitles found, showing source selection dialog")
                choice = show_subtitle_source_dialog(
                    get_string(30840),  # "Select subtitle source"
                    embedded_lang=self.get_language_name(embedded_lang),
                    external_file=external_sub_path,
                    get_string_func=get_string
                )
                log(f"User selected: {choice}")
                
                if choice == 'embedded':
                    subtitle_source = 'embedded'
                elif choice == 'external':
                    subtitle_source = external_sub_path
                elif choice == 'browse':
                    browsed_path = browse_subtitle_file(get_string)
                    if browsed_path:
                        subtitle_source = browsed_path
                    else:
                        log("User cancelled file browse")
                        return
                else:
                    log("User cancelled source selection")
                    return
                    
            elif source_sub:
                # Only embedded available
                log(f"Only embedded subtitle available (language: {embedded_lang})")
                if self.ask_before_translate:
                    log("Showing translation confirmation dialog")
                    msg = get_string(30706).format(
                        self.get_language_name(self.target_language),
                        self.get_language_name(embedded_lang)
                    )
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
                    log("User confirmed translation")
                else:
                    log("Auto-translate enabled, skipping confirmation dialog")
                subtitle_source = 'embedded'
                
            elif external_sub_path:
                # Only external available
                log(f"Only external subtitle available: {external_sub_path}")
                if self.ask_before_translate:
                    log("Showing translation confirmation dialog")
                    filename = os.path.basename(external_sub_path)
                    # 30846: "Translate external subtitle ({0}) to {1}?"
                    msg = get_string(30846).format(filename, self.get_language_name(self.target_language))
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
                    log("User confirmed translation")
                else:
                    log("Auto-translate enabled, skipping confirmation dialog")
                subtitle_source = external_sub_path
                
            else:
                # No sources available - offer to browse
                log("No embedded or external subtitles found, showing browse dialog")
                choice = show_subtitle_source_dialog(
                    get_string(30840),  # "Select subtitle source"
                    embedded_lang=None,
                    external_file=None,
                    get_string_func=get_string
                )
                
                if choice == 'browse':
                    browsed_path = browse_subtitle_file(get_string)
                    if browsed_path:
                        subtitle_source = browsed_path
                    else:
                        log("User cancelled file browse")
                        return
                else:
                    log("No subtitle sources available")
                    xbmcgui.Dialog().ok(
                        get_addon_name(),
                        get_string(30703)  # No subtitles found
                    )
                    return
            
            # Perform translation based on selected source
            if subtitle_source == 'embedded':
                self.translate_subtitle(source_sub)
            else:
                # External file path
                self.translate_external_subtitle(subtitle_source)
            
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
    
    @staticmethod
    def _lang_match(lang_a, lang_b):
        """Match language codes flexibly: sv == sv_se == sv_SE, en == eng, etc."""
        a = lang_a.lower().replace('-', '_').split('_')[0][:3]
        b = lang_b.lower().replace('-', '_').split('_')[0][:3]
        # Handle 2-char vs 3-char ISO codes
        MAP = {'eng': 'en', 'swe': 'sv', 'nor': 'no', 'dan': 'da', 'fin': 'fi',
               'deu': 'de', 'ger': 'de', 'fra': 'fr', 'fre': 'fr', 'spa': 'es',
               'ita': 'it', 'por': 'pt', 'pol': 'pl', 'nld': 'nl', 'dut': 'nl',
               'rus': 'ru', 'ukr': 'uk', 'jpn': 'ja', 'zho': 'zh', 'chi': 'zh'}
        a = MAP.get(a, a)
        b = MAP.get(b, b)
        return a == b

    def find_source_subtitle(self, subtitles):
        """Find the best source subtitle for translation."""
        source_lang = self.source_language.lower()
        
        # First, try to find the specified source language
        if source_lang != 'auto':
            for sub in subtitles:
                if self._lang_match(sub.get('language', ''), source_lang):
                    return sub
        
        # Fallback: look for English
        for sub in subtitles:
            if self._lang_match(sub.get('language', ''), 'en'):
                return sub
        
        # Last resort: take the first subtitle
        if subtitles:
            return subtitles[0]
        
        return None
    
    def translate_subtitle(self, source_sub):
        """Translate the subtitle with progress tracking."""
        self.translation_in_progress = True
        progress = None
        was_playing = False
        
        try:
            get_debug_logger().info(f"Starting translation for: {self.current_file}", 'translation')
            get_debug_logger().debug(f"Source subtitle: {source_sub}", 'translation')
            
            # Check cache first
            cache_key = self.get_cache_key(source_sub)
            cached_path = self.get_cached_subtitle(cache_key)
            
            if cached_path and xbmcvfs.exists(cached_path):
                get_debug_logger().info(f"Cache hit: {cached_path}", 'cache')
                
                # Also save alongside video if enabled
                if self.save_alongside:
                    self._copy_to_alongside(cached_path)
                
                self.load_subtitle(cached_path)
                if self.show_notification:
                    notify(get_string(30705))  # Using cached translation
                return
            
            get_debug_logger().debug("Cache miss, starting translation", 'cache')
            
            # Check if FFmpeg is available BEFORE pausing playback or showing progress
            ffmpeg_path = self._ensure_ffmpeg_available(get_setting('ffmpeg_path'))
            if ffmpeg_path is None:
                log("User cancelled FFmpeg setup")
                return
            
            # Pause playback during translation
            if self.isPlaying():
                was_playing = True
                self.pause()
                log("Paused playback during translation")
                if self.show_notification:
                    notify(get_string(30717))  # "Pausing playback during translation..."
            
            # Initialize progress dialog
            progress = TranslationProgress(show_dialog=self.show_notification)
            progress.start(get_string(30700))  # "Translating subtitles..."
            
            # Extract subtitle from video
            progress.set_stage('extract', get_string(30707))  # "Extracting subtitles..."
            get_debug_logger().debug(f"Extracting subtitle index {source_sub.get('index', 0)}", 'ffmpeg')
            
            extractor = SubtitleExtractor(ffmpeg_path)
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
            progress.set_stage('parse', get_string(30708))  # "Parsing subtitle file..."
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
            
            # Auto-fallback if API key missing
            actual_service = self._auto_fallback_if_needed()
            translation_start_time = time.time()
            
            # Get translator
            # Show which service is being used
            service_display = actual_service.replace('_', ' ').title()
            progress.set_stage('translate', f"{get_string(30709)}\n🔗 {service_display}")  # "Connecting to translation service..."
            progress.set_service(service_display)
            get_debug_logger().debug(f"Using translation service: {actual_service}", 'api')
            
            translator = get_translator(
                actual_service,
                self.get_service_config() if actual_service == self.translation_service else self._get_fallback_config(actual_service)
            )
            
            # Translate in batches with progress
            translated_entries = []
            batch_size = self.batch_size
            total_batches = (len(entries) + batch_size - 1) // batch_size
            
            # Track success/failure
            successful_batches = 0
            failed_batches = 0
            max_consecutive_failures = 3  # Abort after 3 consecutive failures
            consecutive_failures = 0
            
            # Get fallback services
            fallback_services = []
            if get_setting_bool('enable_fallback'):
                fallback_str = get_setting('fallback_services')
                if fallback_str:
                    fallback_services = [s.strip() for s in fallback_str.split(',') if s.strip()]
            
            get_debug_logger().debug(f"Translating in {total_batches} batches of {batch_size}", 'translation')
            
            for batch_num, i in enumerate(range(0, len(entries), batch_size)):
                if progress.is_cancelled():
                    get_debug_logger().info("Translation cancelled by user", 'translation')
                    return
                
                batch = entries[i:i + batch_size]
                texts = [e['text'] for e in batch]
                
                # Update progress with percentage
                current_count = i + len(batch)
                percent = int((current_count / len(entries)) * 100)
                progress.update(
                    current_count,
                    f"{get_string(30710).format(batch_num + 1, total_batches)} ({percent}%)"
                )
                
                translated_texts = None
                last_error = None
                
                # Try primary translator
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
                    successful_batches += 1
                    consecutive_failures = 0
                    
                except Exception as api_error:
                    last_error = api_error
                    # Rate-limit log spam: only log first 3 primary failures, then every 50th
                    if not hasattr(self, '_primary_fail_count'):
                        self._primary_fail_count = 0
                    self._primary_fail_count += 1
                    if self._primary_fail_count <= 3:
                        get_debug_logger().error(f"Primary translator failed: {api_error}", 'api')
                        if self._primary_fail_count == 3:
                            get_debug_logger().error("Suppressing further primary translator errors (will log every 50th)", 'api')
                    elif self._primary_fail_count % 50 == 0:
                        get_debug_logger().error(f"Primary translator still failing ({self._primary_fail_count} times): {api_error}", 'api')
                    
                    # Try fallback services
                    for fallback_service in fallback_services:
                        if fallback_service == self.translation_service:
                            continue
                        try:
                            get_debug_logger().info(f"Trying fallback: {fallback_service}", 'api')
                            progress.update(current_count, f"Fallback: {fallback_service}...")
                            
                            fallback_config = {'timeout': get_setting_int('request_timeout')}
                            if fallback_service == 'lingva':
                                fallback_config['url'] = get_setting('lingva_url') or 'https://lingva.ml'
                            elif fallback_service == 'libretranslate':
                                fallback_config['url'] = get_setting('libretranslate_url') or 'https://translate.argosopentech.com'
                            
                            fallback_translator = get_translator(fallback_service, fallback_config)
                            translated_texts = fallback_translator.translate_batch(
                                texts,
                                self.source_language,
                                self.target_language
                            )
                            successful_batches += 1
                            consecutive_failures = 0
                            get_debug_logger().info(f"Fallback {fallback_service} succeeded", 'api')
                            break
                        except Exception as fallback_error:
                            # Rate-limit fallback error logging
                            if not hasattr(self, '_fallback_fail_counts'):
                                self._fallback_fail_counts = {}
                            key = fallback_service
                            self._fallback_fail_counts[key] = self._fallback_fail_counts.get(key, 0) + 1
                            fc = self._fallback_fail_counts[key]
                            if fc <= 3 or fc % 50 == 0:
                                get_debug_logger().error(f"Fallback {fallback_service} failed ({fc}x): {fallback_error}", 'api')
                            
                            # Exponential backoff on rate limit (429)
                            err_str = str(fallback_error)
                            if '429' in err_str or 'Too Many Requests' in err_str:
                                import time as _time
                                backoff = min(2 ** min(fc - 1, 5), 32)
                                if fc <= 3:
                                    get_debug_logger().info(f"Rate limited by {fallback_service}, backing off {backoff}s", 'api')
                                _time.sleep(backoff)
                            continue
                
                # If all translators failed for this batch
                if translated_texts is None:
                    failed_batches += 1
                    consecutive_failures += 1
                    
                    get_error_reporter().report_error('api', f"All translators failed for batch {batch_num + 1}", last_error, {
                        'service': self.translation_service,
                        'fallbacks_tried': fallback_services,
                        'batch_size': len(texts)
                    })
                    
                    # Check if we should abort
                    if consecutive_failures >= max_consecutive_failures:
                        raise Exception(f"Translation aborted: {consecutive_failures} consecutive failures. Check your translation service settings.")
                    
                    # Use original text only if we've had some successes (partial translation)
                    if successful_batches > 0:
                        progress.add_warning(f"Batch {batch_num + 1} failed, using original text")
                        translated_texts = texts
                    else:
                        # No successful batches yet - abort early
                        raise Exception(f"Translation service unavailable: {last_error}")
                
                for j, entry in enumerate(batch):
                    translated_entry = entry.copy()
                    if j < len(translated_texts):
                        translated_entry['text'] = translated_texts[j]
                    translated_entries.append(translated_entry)
                
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(entries):
                    xbmc.sleep(500)
            
            # Check if translation was mostly successful
            success_rate = successful_batches / total_batches if total_batches > 0 else 0
            if success_rate < 0.5:
                raise Exception(f"Translation failed: only {successful_batches}/{total_batches} batches translated successfully")
            
            # Verify that text actually changed (detect false "success" where original text was kept)
            unchanged_count = 0
            for orig, trans in zip(entries, translated_entries):
                if orig.get('text', '').strip() == trans.get('text', '').strip():
                    unchanged_count += 1
            unchanged_ratio = unchanged_count / len(entries) if entries else 0
            log(f"Translation check: {unchanged_count}/{len(entries)} unchanged ({unchanged_ratio:.0%})")
            # Log first 3 entries for debugging
            for idx in range(min(3, len(entries))):
                orig_text = entries[idx].get('text', '')[:60]
                trans_text = translated_entries[idx].get('text', '')[:60] if idx < len(translated_entries) else '?'
                log(f"  Sample {idx+1}: '{orig_text}' → '{trans_text}'")
            if unchanged_ratio > 0.95:
                raise Exception(
                    f"Translation failed: {unchanged_count}/{len(entries)} entries "
                    f"({unchanged_ratio:.0%}) were not translated. "
                    f"The translation service may be unreachable. "
                    f"Try a different service in settings."
                )
            
            # Format output (90%)
            progress.set_stage('format', f"{get_string(30708)} (90%)")  # Parsing/formatting
            get_debug_logger().debug(f"Generating {self.subtitle_format} output", 'format')
            
            # Determine service label early for disclaimer
            service_label = actual_service.replace('_', ' ').title()
            
            # Add disclaimer as first subtitle entries
            disclaimer_entries = self._make_disclaimer(service_label)
            # Shift existing indices
            num_disclaimer = len(disclaimer_entries)
            for entry in translated_entries:
                entry['index'] = entry.get('index', 0) + num_disclaimer
            for i, d in enumerate(disclaimer_entries):
                d['index'] = i + 1
            translated_entries = disclaimer_entries + translated_entries
            
            output_content = parser.generate(
                translated_entries,
                self.subtitle_format
            )
            
            # Save subtitle (95%)
            progress.set_stage('save', f"{get_string(30711)} (95%)")  # "Saving translated subtitles..."
            output_path = self.save_subtitle(output_content, cache_key)
            get_debug_logger().info(f"Saved subtitle to: {output_path}", 'save')
            
            # Load the translated subtitle
            self.load_subtitle(output_path)
            
            # Complete with service name and elapsed time
            elapsed_secs = time.time() - translation_start_time
            elapsed_str = self._format_elapsed(elapsed_secs)
            
            summary = progress.get_summary()
            get_debug_logger().info(f"Translation complete: {summary}", 'translation')
            completion_msg = get_string(30852).format(len(translated_entries), service_label, elapsed_str)
            progress.complete(True, completion_msg)
            
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
            
            # Resume playback if we paused it
            if was_playing:
                try:
                    # Check if player is paused using condition visibility
                    is_paused = xbmc.getCondVisibility('Player.Paused')
                    if is_paused:
                        self.pause()  # Toggle pause to resume
                        log("Resumed playback after translation")
                        if self.show_notification:
                            notify(get_string(30718))  # "Resuming playback"
                except Exception as e:
                    log(f"Could not resume playback: {e}", level=xbmc.LOGWARNING)
    
    def translate_external_subtitle(self, subtitle_path):
        """Translate an external subtitle file with progress tracking."""
        self.translation_in_progress = True
        progress = None
        was_playing = False
        
        try:
            get_debug_logger().info(f"Starting translation of external subtitle: {subtitle_path}", 'translation')
            
            # Generate cache key for external file
            cache_key = self.get_cache_key_external(subtitle_path)
            cached_path = self.get_cached_subtitle(cache_key)
            
            if cached_path and xbmcvfs.exists(cached_path):
                get_debug_logger().info(f"Cache hit: {cached_path}", 'cache')
                
                if self.save_alongside:
                    self._copy_to_alongside(cached_path)
                
                self.load_subtitle(cached_path)
                if self.show_notification:
                    notify(get_string(30705))  # Using cached translation
                return
            
            get_debug_logger().debug("Cache miss, starting translation", 'cache')
            
            # Pause playback during translation
            if self.isPlaying():
                was_playing = True
                self.pause()
                log("Paused playback during translation")
                if self.show_notification:
                    notify(get_string(30717))
            
            # Initialize progress dialog
            progress = TranslationProgress(show_dialog=self.show_notification)
            progress.start(get_string(30700))
            
            # Read external subtitle
            progress.set_stage('extract', get_string(30845))  # "Reading subtitle file..."
            subtitle_content = self.read_external_subtitle(subtitle_path)
            
            if not subtitle_content:
                error_msg = f"Failed to read external subtitle: {subtitle_path}"
                get_error_reporter().report_error('file', error_msg, context={
                    'file': subtitle_path
                })
                raise Exception(error_msg)
            
            get_debug_logger().debug(f"Read {len(subtitle_content)} bytes", 'file')
            
            # Parse subtitle
            progress.set_stage('parse', get_string(30708))
            parser = SubtitleParser()
            entries = parser.parse(subtitle_content)
            
            if not entries:
                error_msg = "No subtitle entries found in external file"
                get_error_reporter().report_error('parse', error_msg, context={
                    'content_length': len(subtitle_content),
                    'content_preview': subtitle_content[:500]
                })
                raise Exception(error_msg)
            
            get_debug_logger().info(f"Parsed {len(entries)} subtitle entries", 'parse')
            progress.total = len(entries)
            
            if progress.is_cancelled():
                get_debug_logger().info("Translation cancelled by user", 'translation')
                return
            
            # Auto-fallback if API key missing
            actual_service = self._auto_fallback_if_needed()
            translation_start_time = time.time()
            
            # Get translator
            progress.set_stage('translate', get_string(30709))
            get_debug_logger().debug(f"Using translation service: {actual_service}", 'api')
            
            translator = get_translator(
                actual_service,
                self.get_service_config() if actual_service == self.translation_service else self._get_fallback_config(actual_service)
            )
            
            # Translate in batches with progress
            translated_entries = []
            batch_size = self.batch_size
            total_batches = (len(entries) + batch_size - 1) // batch_size
            
            successful_batches = 0
            failed_batches = 0
            max_consecutive_failures = 3
            consecutive_failures = 0
            
            fallback_services = []
            if get_setting_bool('enable_fallback'):
                fallback_str = get_setting('fallback_services')
                if fallback_str:
                    fallback_services = [s.strip() for s in fallback_str.split(',') if s.strip()]
            
            get_debug_logger().debug(f"Translating in {total_batches} batches of {batch_size}", 'translation')
            
            for batch_num, i in enumerate(range(0, len(entries), batch_size)):
                if progress.is_cancelled():
                    get_debug_logger().info("Translation cancelled by user", 'translation')
                    return
                
                batch = entries[i:i + batch_size]
                texts = [e['text'] for e in batch]
                
                current_count = i + len(batch)
                percent = int((current_count / len(entries)) * 100)
                progress.update(
                    current_count,
                    f"{get_string(30710).format(batch_num + 1, total_batches)} ({percent}%)"
                )
                
                translated_texts = None
                last_error = None
                
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
                    successful_batches += 1
                    consecutive_failures = 0
                    
                except Exception as api_error:
                    last_error = api_error
                    get_debug_logger().error(f"Primary translator failed: {api_error}", 'api')
                    
                    for fallback_service in fallback_services:
                        if fallback_service == self.translation_service:
                            continue
                        try:
                            get_debug_logger().info(f"Trying fallback: {fallback_service}", 'api')
                            progress.update(current_count, f"Fallback: {fallback_service}...")
                            
                            fallback_config = {'timeout': get_setting_int('request_timeout')}
                            if fallback_service == 'lingva':
                                fallback_config['url'] = get_setting('lingva_url') or 'https://lingva.ml'
                            elif fallback_service == 'libretranslate':
                                fallback_config['url'] = get_setting('libretranslate_url') or 'https://translate.argosopentech.com'
                            
                            fallback_translator = get_translator(fallback_service, fallback_config)
                            translated_texts = fallback_translator.translate_batch(
                                texts,
                                self.source_language,
                                self.target_language
                            )
                            successful_batches += 1
                            consecutive_failures = 0
                            get_debug_logger().info(f"Fallback {fallback_service} succeeded", 'api')
                            break
                        except Exception as fallback_error:
                            if not hasattr(self, '_fallback_fail_counts2'):
                                self._fallback_fail_counts2 = {}
                            key = fallback_service
                            self._fallback_fail_counts2[key] = self._fallback_fail_counts2.get(key, 0) + 1
                            fc = self._fallback_fail_counts2[key]
                            if fc <= 3 or fc % 50 == 0:
                                get_debug_logger().error(f"Fallback {fallback_service} failed ({fc}x): {fallback_error}", 'api')
                            err_str = str(fallback_error)
                            if '429' in err_str or 'Too Many Requests' in err_str:
                                import time as _time
                                backoff = min(2 ** min(fc - 1, 5), 32)
                                if fc <= 3:
                                    get_debug_logger().info(f"Rate limited by {fallback_service}, backing off {backoff}s", 'api')
                                _time.sleep(backoff)
                            continue
                
                if translated_texts is None:
                    failed_batches += 1
                    consecutive_failures += 1
                    
                    get_error_reporter().report_error('api', f"All translators failed for batch {batch_num + 1}", last_error, {
                        'service': self.translation_service,
                        'fallbacks_tried': fallback_services,
                        'batch_size': len(texts)
                    })
                    
                    if consecutive_failures >= max_consecutive_failures:
                        raise Exception(f"Translation aborted: {consecutive_failures} consecutive failures.")
                    
                    if successful_batches > 0:
                        progress.add_warning(f"Batch {batch_num + 1} failed, using original text")
                        translated_texts = texts
                    else:
                        raise Exception(f"Translation service unavailable: {last_error}")
                
                for j, entry in enumerate(batch):
                    translated_entry = entry.copy()
                    if j < len(translated_texts):
                        translated_entry['text'] = translated_texts[j]
                    translated_entries.append(translated_entry)
                
                if i + batch_size < len(entries):
                    xbmc.sleep(500)
            
            success_rate = successful_batches / total_batches if total_batches > 0 else 0
            if success_rate < 0.5:
                raise Exception(f"Translation failed: only {successful_batches}/{total_batches} batches translated successfully")
            
            # Format output
            progress.set_stage('format', f"{get_string(30708)} (90%)")
            get_debug_logger().debug(f"Generating {self.subtitle_format} output", 'format')
            
            # Determine service label early for disclaimer
            service_label = actual_service.replace('_', ' ').title()
            
            # Add disclaimer as first subtitle entries
            disclaimer_entries = self._make_disclaimer(service_label)
            num_disclaimer = len(disclaimer_entries)
            for entry in translated_entries:
                entry['index'] = entry.get('index', 0) + num_disclaimer
            for i, d in enumerate(disclaimer_entries):
                d['index'] = i + 1
            translated_entries = disclaimer_entries + translated_entries
            
            output_content = parser.generate(
                translated_entries,
                self.subtitle_format
            )
            
            # Save subtitle
            progress.set_stage('save', f"{get_string(30711)} (95%)")
            output_path = self.save_subtitle(output_content, cache_key)
            get_debug_logger().info(f"Saved subtitle to: {output_path}", 'save')
            
            # Load the translated subtitle
            self.load_subtitle(output_path)
            
            # Complete with service name and elapsed time
            elapsed_secs = time.time() - translation_start_time
            elapsed_str = self._format_elapsed(elapsed_secs)
            
            summary = progress.get_summary()
            get_debug_logger().info(f"Translation complete: {summary}", 'translation')
            completion_msg = get_string(30852).format(len(translated_entries), service_label, elapsed_str)
            progress.complete(True, completion_msg)
            
        except Exception as e:
            get_debug_logger().error(f"Translation failed: {e}", 'translation')
            get_error_reporter().report_error('translation', f"Translation failed: {str(e)}", e, {
                'file': subtitle_path,
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
            
            if was_playing:
                try:
                    is_paused = xbmc.getCondVisibility('Player.Paused')
                    if is_paused:
                        self.pause()
                        log("Resumed playback after translation")
                        if self.show_notification:
                            notify(get_string(30718))
                except Exception as e:
                    log(f"Could not resume playback: {e}", level=xbmc.LOGWARNING)
    
    @staticmethod
    def _format_elapsed(seconds):
        """Format elapsed seconds as human-readable string (e.g. '1m 39s')."""
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        if minutes > 0:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"
    
    def _get_fallback_config(self, service):
        """Get config for a fallback service (e.g. lingva)."""
        config = {'timeout': get_setting_int('request_timeout')}
        if service == 'lingva':
            config['url'] = get_setting('lingva_url') or 'https://lingva.ml'
        elif service == 'libretranslate':
            config['url'] = get_setting('libretranslate_url') or 'https://translate.argosopentech.com'
        return config
    
    def get_cache_key_external(self, subtitle_path):
        """Generate a unique cache key for an external subtitle file."""
        key_data = f"ext|{subtitle_path}|{self.target_language}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
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
    
    def _normalize_path(self, path):
        """Normalize path separators for network paths (SMB uses forward slashes)."""
        if path and (path.startswith('smb://') or path.startswith('nfs://')):
            return path.replace('\\', '/')
        return path
    
    def _copy_to_alongside(self, source_path):
        """Copy subtitle file to alongside the video."""
        try:
            video_dir = os.path.dirname(self.current_file)
            video_name = os.path.splitext(os.path.basename(self.current_file))[0]
            ext = os.path.splitext(source_path)[1]  # Get extension from source
            alongside_path = self._normalize_path(os.path.join(
                video_dir,
                f"{video_name}.{self.target_language}{ext}"
            ))
            
            # Check if file already exists
            if xbmcvfs.exists(alongside_path):
                log(f"Subtitle already exists alongside video: {alongside_path}")
                return alongside_path
            
            # Read source and write to destination
            with xbmcvfs.File(source_path, 'r') as src:
                content = src.read()
            
            with xbmcvfs.File(alongside_path, 'w') as dst:
                dst.write(content)
            
            log(f"Copied subtitle alongside video: {alongside_path}")
            return alongside_path
        except Exception as e:
            log(f"Could not copy subtitle alongside video: {e}", level=xbmc.LOGWARNING)
            return None
    
    @staticmethod
    def _make_disclaimer(service_label):
        """Create disclaimer subtitle entries shown during the first 7 seconds.

        Follows broadcast subtitle standards:
        - Max 42 characters per line
        - Max 2 lines per subtitle event
        - Minimum 5/6 second duration per event
        Returns a list of entries (may be 1-2 events).
        """
        addon = get_addon()
        version = addon.getAddonInfo('version')
        # Line 1: max 42 chars — "Subtitle Translator v0.9.19" = 27 chars
        # Line 2: max 42 chars — "Service: Openai" fits easily
        line1 = f"Subtitle Translator v{version}"
        line2 = f"Service: {service_label}"
        return [
            {
                'index': 0,
                'start': 0,
                'end': 4000,
                'text': f"{line1}\n{line2}",
            },
            {
                'index': 0,
                'start': 4000,
                'end': 7000,
                'text': "github.com/yeager/\nkodi-subtitle-translator",
            },
        ]

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
            alongside_path = self._normalize_path(os.path.join(
                video_dir,
                f"{video_name}.{self.target_language}.{self.subtitle_format}"
            ))
            
            try:
                with xbmcvfs.File(alongside_path, 'w') as f:
                    f.write(content)
                output_path = alongside_path
                log(f"Saved subtitle alongside video: {alongside_path}")
            except Exception as e:
                log(f"Could not save alongside video: {e}", level=xbmc.LOGWARNING)
        
        return output_path
    
    def load_subtitle(self, path):
        """Load a subtitle file into the player and enable it."""
        self.setSubtitles(path)
        
        # Enable subtitle visibility and select the new subtitle
        xbmc.sleep(500)  # Give Kodi time to load the subtitle
        
        try:
            # Get available subtitles to find the index of the one we just added
            result = execute_jsonrpc('Player.GetProperties', {
                'playerid': 1,
                'properties': ['subtitles', 'currentsubtitle', 'subtitleenabled']
            })
            
            if result and 'result' in result:
                subtitles = result['result'].get('subtitles', [])
                
                # Find our subtitle (usually the last one added, or match by name)
                new_sub_index = len(subtitles) - 1 if subtitles else 0
                
                # Look for exact path match
                for i, sub in enumerate(subtitles):
                    if sub.get('name', '').endswith(os.path.basename(path)):
                        new_sub_index = i
                        break
                
                # Enable subtitles and select the new one
                execute_jsonrpc('Player.SetSubtitle', {
                    'playerid': 1,
                    'subtitle': new_sub_index,
                    'enable': True
                })
                log(f"Selected subtitle index {new_sub_index} and enabled display")
            else:
                # Fallback: just enable subtitles via built-in
                xbmc.executebuiltin('ActivateWindow(SubtitleSearch)')
                xbmc.sleep(100)
                xbmc.executebuiltin('Action(Close)')
                
        except Exception as e:
            log(f"Could not auto-select subtitle: {e}", level=xbmc.LOGWARNING)
        
        # Ensure subtitle visibility is on
        self.showSubtitles(True)
        log(f"Loaded and activated subtitle: {path}")
    
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
            config['api_key'] = get_setting('deepl_api_key')
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
    
    def _get_language_variants(self, lang_code):
        """Get common variations of a language code for matching."""
        if not lang_code:
            return []
        
        lang_lower = lang_code.lower()
        
        # Map of language codes to their common variants
        lang_variants = {
            'en': ['en', 'eng', 'english'],
            'eng': ['en', 'eng', 'english'],
            'sv': ['sv', 'swe', 'swedish'],
            'swe': ['sv', 'swe', 'swedish'],
            'no': ['no', 'nor', 'nob', 'norwegian'],
            'nor': ['no', 'nor', 'nob', 'norwegian'],
            'da': ['da', 'dan', 'danish'],
            'dan': ['da', 'dan', 'danish'],
            'fi': ['fi', 'fin', 'finnish'],
            'fin': ['fi', 'fin', 'finnish'],
            'de': ['de', 'ger', 'deu', 'german'],
            'ger': ['de', 'ger', 'deu', 'german'],
            'deu': ['de', 'ger', 'deu', 'german'],
            'fr': ['fr', 'fre', 'fra', 'french'],
            'fre': ['fr', 'fre', 'fra', 'french'],
            'fra': ['fr', 'fre', 'fra', 'french'],
            'es': ['es', 'spa', 'spanish'],
            'spa': ['es', 'spa', 'spanish'],
            'it': ['it', 'ita', 'italian'],
            'ita': ['it', 'ita', 'italian'],
            'pt': ['pt', 'por', 'portuguese'],
            'por': ['pt', 'por', 'portuguese'],
            'pl': ['pl', 'pol', 'polish'],
            'pol': ['pl', 'pol', 'polish'],
            'nl': ['nl', 'dut', 'nld', 'dutch'],
            'dut': ['nl', 'dut', 'nld', 'dutch'],
            'nld': ['nl', 'dut', 'nld', 'dutch'],
            'ru': ['ru', 'rus', 'russian'],
            'rus': ['ru', 'rus', 'russian'],
            'ja': ['ja', 'jpn', 'japanese'],
            'jpn': ['ja', 'jpn', 'japanese'],
            'zh': ['zh', 'chi', 'zho', 'chinese'],
            'chi': ['zh', 'chi', 'zho', 'chinese'],
            'zho': ['zh', 'chi', 'zho', 'chinese'],
            'ko': ['ko', 'kor', 'korean'],
            'kor': ['ko', 'kor', 'korean'],
            'ar': ['ar', 'ara', 'arabic'],
            'ara': ['ar', 'ara', 'arabic'],
            'tr': ['tr', 'tur', 'turkish'],
            'tur': ['tr', 'tur', 'turkish'],
        }
        
        variants = lang_variants.get(lang_lower, [lang_lower])
        return list(dict.fromkeys(variants))  # Deduplicate
    
    def _parse_language_from_filename(self, filename):
        """
        Parse language code from subtitle filename.
        
        Examples:
            'movie.en.srt' → 'en'
            'movie.eng.srt' → 'eng'
            'movie.swedish.srt' → 'swedish'
            'movie.srt' → None
        
        Returns:
            Language code string or None
        """
        name_without_ext = os.path.splitext(filename)[0]
        parts = name_without_ext.split('.')
        
        if len(parts) < 2:
            return None
        
        # The language code is typically the last part before the extension
        candidate = parts[-1].lower()
        
        # Check against known language codes/names
        known_codes = {
            'en', 'eng', 'english', 'sv', 'swe', 'swedish',
            'no', 'nor', 'nob', 'norwegian', 'da', 'dan', 'danish',
            'fi', 'fin', 'finnish', 'de', 'ger', 'deu', 'german',
            'fr', 'fre', 'fra', 'french', 'es', 'spa', 'spanish',
            'it', 'ita', 'italian', 'pt', 'por', 'portuguese',
            'pl', 'pol', 'polish', 'nl', 'dut', 'nld', 'dutch',
            'ru', 'rus', 'russian', 'uk', 'ukr', 'ukrainian',
            'ja', 'jpn', 'japanese', 'zh', 'chi', 'zho', 'chinese',
            'ko', 'kor', 'korean', 'ar', 'ara', 'arabic',
            'tr', 'tur', 'turkish', 'hi', 'hin', 'hindi',
            'th', 'tha', 'thai', 'vi', 'vie', 'vietnamese',
            'id', 'ind', 'indonesian', 'el', 'gre', 'ell', 'greek',
            'cs', 'cze', 'ces', 'czech', 'ro', 'rum', 'ron', 'romanian',
            'hu', 'hun', 'hungarian', 'he', 'heb', 'hebrew',
            'ms', 'may', 'msa', 'malay', 'fil', 'tl', 'tagalog',
            'ta', 'tam', 'tamil', 'te', 'tel', 'telugu',
        }
        
        if candidate in known_codes:
            return candidate
        
        return None
    
    def _list_external_subtitles(self):
        """
        List all external subtitle files for the current video.
        
        Returns:
            List of dicts: [{'path': str, 'language': str or None, 'filename': str}, ...]
        """
        if not self.current_file:
            return []
        
        video_dir = os.path.dirname(self.current_file)
        video_name = os.path.splitext(os.path.basename(self.current_file))[0]
        sub_extensions = ['.srt', '.ass', '.ssa', '.sub', '.vtt']
        results = []
        
        try:
            dirs, files = xbmcvfs.listdir(video_dir)
            
            for filename in files:
                name_lower = filename.lower()
                if not any(name_lower.endswith(ext) for ext in sub_extensions):
                    continue
                if not name_lower.startswith(video_name.lower()):
                    continue
                
                full_path = self._normalize_path(os.path.join(video_dir, filename))
                lang = self._parse_language_from_filename(filename)
                
                results.append({
                    'path': full_path,
                    'language': lang,
                    'filename': filename
                })
                log(f"Found external subtitle: {filename} (language: {lang})")
            
        except Exception as e:
            log(f"Error listing external subtitles: {e}", level=xbmc.LOGWARNING)
        
        return results
    
    def find_external_subtitle(self, source_lang=None):
        """
        Find external subtitle file for current video in the given language.
        
        Args:
            source_lang: Preferred source language code (e.g., 'en', 'eng')
        
        Returns:
            Path to external subtitle file, or None if not found
        """
        if not self.current_file:
            return None
        
        all_subs = self._list_external_subtitles()
        if not all_subs:
            return None
        
        # Build language variants to match
        lang_codes = self._get_language_variants(source_lang) if source_lang else ['en', 'eng', 'english']
        
        # First pass: find subtitle with matching language code
        for sub in all_subs:
            if sub['language'] and sub['language'].lower() in lang_codes:
                log(f"Found external subtitle with language '{sub['language']}': {sub['filename']}")
                return sub['path']
        
        # Second pass: return first subtitle without a language tag
        for sub in all_subs:
            if sub['language'] is None:
                log(f"Found external subtitle (no language tag): {sub['filename']}")
                return sub['path']
        
        # Last resort: return first subtitle
        if all_subs:
            log(f"Using first available external subtitle: {all_subs[0]['filename']}")
            return all_subs[0]['path']
        
        return None
    
    def find_external_subtitle_for_language(self, lang_code):
        """
        Check if an external subtitle exists for a specific language.
        
        Args:
            lang_code: Language code to check (e.g., 'sv', 'fr')
        
        Returns:
            Path to external subtitle file if found, or None
        """
        all_subs = self._list_external_subtitles()
        lang_variants = self._get_language_variants(lang_code)
        
        for sub in all_subs:
            if sub['language'] and sub['language'].lower() in lang_variants:
                log(f"Found external subtitle in target language '{sub['language']}': {sub['filename']}")
                return sub['path']
        
        return None
    
    def read_external_subtitle(self, subtitle_path):
        """
        Read content from an external subtitle file.
        
        Args:
            subtitle_path: Path to the subtitle file
        
        Returns:
            Subtitle content as string, or None on failure
        """
        try:
            log(f"Reading external subtitle: {subtitle_path}")
            
            # Try reading with Kodi's VFS (supports network paths)
            if xbmcvfs.exists(subtitle_path):
                with xbmcvfs.File(subtitle_path, 'r') as f:
                    content = f.read()
                
                if content:
                    # Handle bytes if needed
                    if isinstance(content, bytes):
                        # Try UTF-8 first, then fall back to latin-1
                        try:
                            content = content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                content = content.decode('utf-8-sig')  # BOM
                            except UnicodeDecodeError:
                                content = content.decode('latin-1')
                    
                    log(f"Successfully read {len(content)} bytes from external subtitle")
                    return content
            
            # Fallback: try direct file access (local files)
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                log(f"Read {len(content)} bytes using direct file access")
                return content
            
            log(f"External subtitle file not found: {subtitle_path}", level=xbmc.LOGERROR)
            return None
            
        except Exception as e:
            log(f"Error reading external subtitle: {e}", level=xbmc.LOGERROR)
            return None
    
    def get_language_name(self, code):
        """Get localized language name from code."""
        # Map language codes to string IDs (30800+)
        code_to_string_id = {
            'sv': 30800, 'swe': 30800,
            'en': 30801, 'eng': 30801,
            'no': 30802, 'nor': 30802, 'nob': 30802,
            'da': 30803, 'dan': 30803,
            'fi': 30804, 'fin': 30804,
            'de': 30805, 'ger': 30805, 'deu': 30805,
            'fr': 30806, 'fre': 30806, 'fra': 30806,
            'es': 30807, 'spa': 30807,
            'it': 30808, 'ita': 30808,
            'pt': 30809, 'por': 30809,
            'pl': 30810, 'pol': 30810,
            'nl': 30811, 'dut': 30811, 'nld': 30811,
            'ru': 30812, 'rus': 30812,
            'uk': 30813, 'ukr': 30813,
            'ja': 30814, 'jpn': 30814,
            'zh': 30815, 'chi': 30815, 'zho': 30815,
            'zh-TW': 30816,
            'ko': 30817, 'kor': 30817,
            'ar': 30818, 'ara': 30818,
            'tr': 30819, 'tur': 30819,
            'hi': 30820, 'hin': 30820,
            'th': 30821, 'tha': 30821,
            'vi': 30822, 'vie': 30822,
            'id': 30823, 'ind': 30823,
            'el': 30824, 'gre': 30824, 'ell': 30824,
            'cs': 30825, 'cze': 30825, 'ces': 30825,
            'ro': 30826, 'rum': 30826, 'ron': 30826,
            'hu': 30827, 'hun': 30827,
            'he': 30828, 'heb': 30828,
            'auto': 30829,
            'ms': 30830, 'may': 30830, 'msa': 30830,
            'fil': 30831, 'tl': 30831,
            'ta': 30832, 'tam': 30832,
            'te': 30833, 'tel': 30833,
        }
        
        # Normalize code to lowercase
        code_lower = code.lower() if code else ''
        
        string_id = code_to_string_id.get(code_lower)
        if string_id:
            return get_string(string_id)
        
        # Fallback to code itself
        return code


# Helper functions
def get_setting(key):
    """Get addon setting. Treats '-' as empty string (Kodi workaround)."""
    value = get_addon().getSetting(key)
    # Treat '-' as empty (workaround for Kodi settings v2 empty string issues)
    if value == '-':
        return ''
    return value

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
