# -*- coding: utf-8 -*-
"""
Advanced Features for Subtitle Translator
"""

import json
import os
import re
import hashlib
import time
import threading
import queue
from datetime import datetime, timedelta
import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon


class GlossaryManager:
    """
    Custom glossary/terminology management.
    Allows users to define custom translations for specific terms.
    """
    
    def __init__(self, addon_data_path):
        self.glossary_path = os.path.join(addon_data_path, 'glossary.json')
        self.glossary = {}
        self.load()
    
    def load(self):
        """Load glossary from file."""
        if xbmcvfs.exists(self.glossary_path):
            try:
                with xbmcvfs.File(self.glossary_path, 'r') as f:
                    self.glossary = json.loads(f.read())
            except:
                self.glossary = {}
    
    def save(self):
        """Save glossary to file."""
        with xbmcvfs.File(self.glossary_path, 'w') as f:
            f.write(json.dumps(self.glossary, indent=2, ensure_ascii=False))
    
    def add_term(self, source_lang, target_lang, original, translation, case_sensitive=False):
        """Add a term to the glossary."""
        key = f"{source_lang}_{target_lang}"
        if key not in self.glossary:
            self.glossary[key] = []
        
        self.glossary[key].append({
            'original': original,
            'translation': translation,
            'case_sensitive': case_sensitive,
            'added': datetime.now().isoformat()
        })
        self.save()
    
    def remove_term(self, source_lang, target_lang, original):
        """Remove a term from the glossary."""
        key = f"{source_lang}_{target_lang}"
        if key in self.glossary:
            self.glossary[key] = [t for t in self.glossary[key] if t['original'] != original]
            self.save()
    
    def apply_glossary(self, text, source_lang, target_lang):
        """Apply glossary replacements to text."""
        key = f"{source_lang}_{target_lang}"
        if key not in self.glossary:
            return text
        
        for term in self.glossary[key]:
            if term['case_sensitive']:
                text = text.replace(term['original'], term['translation'])
            else:
                pattern = re.compile(re.escape(term['original']), re.IGNORECASE)
                text = pattern.sub(term['translation'], text)
        
        return text
    
    def get_glossary_prompt(self, source_lang, target_lang):
        """Get glossary as prompt text for AI translators."""
        key = f"{source_lang}_{target_lang}"
        if key not in self.glossary or not self.glossary[key]:
            return ""
        
        terms = []
        for term in self.glossary[key]:
            terms.append(f'"{term["original"]}" → "{term["translation"]}"')
        
        return f"\n\nCustom terminology (always use these translations):\n" + "\n".join(terms)


class TranslationProfiles:
    """
    Translation profiles for different content types.
    E.g., movies, anime, documentaries, kids content.
    """
    
    DEFAULT_PROFILES = {
        'default': {
            'name': 'Default',
            'formality': 'default',
            'preserve_honorifics': False,
            'censor_profanity': False,
            'simplify_language': False,
            'max_line_length': 42,
            'reading_speed': 21  # chars per second
        },
        'anime': {
            'name': 'Anime',
            'formality': 'less',
            'preserve_honorifics': True,  # Keep -san, -kun, etc.
            'censor_profanity': False,
            'simplify_language': False,
            'max_line_length': 42,
            'reading_speed': 21,
            'preserve_terms': ['senpai', 'sensei', 'kawaii', 'baka', 'nani']
        },
        'kids': {
            'name': 'Kids Content',
            'formality': 'less',
            'preserve_honorifics': False,
            'censor_profanity': True,
            'simplify_language': True,
            'max_line_length': 35,
            'reading_speed': 15  # Slower for children
        },
        'documentary': {
            'name': 'Documentary',
            'formality': 'more',
            'preserve_honorifics': False,
            'censor_profanity': False,
            'simplify_language': False,
            'max_line_length': 42,
            'reading_speed': 21
        },
        'formal': {
            'name': 'Formal/Business',
            'formality': 'more',
            'preserve_honorifics': False,
            'censor_profanity': True,
            'simplify_language': False,
            'max_line_length': 42,
            'reading_speed': 21
        }
    }
    
    def __init__(self, addon_data_path):
        self.profiles_path = os.path.join(addon_data_path, 'profiles.json')
        self.profiles = self.DEFAULT_PROFILES.copy()
        self.load()
    
    def load(self):
        """Load custom profiles from file."""
        if xbmcvfs.exists(self.profiles_path):
            try:
                with xbmcvfs.File(self.profiles_path, 'r') as f:
                    custom = json.loads(f.read())
                    self.profiles.update(custom)
            except:
                pass
    
    def save(self):
        """Save profiles to file."""
        # Only save non-default profiles
        custom = {k: v for k, v in self.profiles.items() if k not in self.DEFAULT_PROFILES}
        with xbmcvfs.File(self.profiles_path, 'w') as f:
            f.write(json.dumps(custom, indent=2))
    
    def get_profile(self, name):
        """Get a profile by name."""
        return self.profiles.get(name, self.profiles['default'])
    
    def create_profile(self, name, settings):
        """Create a new profile."""
        self.profiles[name] = settings
        self.save()
    
    def list_profiles(self):
        """List all available profiles."""
        return list(self.profiles.keys())


class SubtitleTimingAdjuster:
    """
    Adjust subtitle timing for better readability.
    """
    
    def __init__(self, reading_speed=21, min_duration=1000, max_duration=7000):
        self.reading_speed = reading_speed  # Characters per second
        self.min_duration = min_duration  # Minimum display time in ms
        self.max_duration = max_duration  # Maximum display time in ms
        self.gap_threshold = 100  # Minimum gap between subtitles in ms
    
    def calculate_optimal_duration(self, text):
        """Calculate optimal display duration based on text length."""
        char_count = len(text.replace('\n', ''))
        optimal = (char_count / self.reading_speed) * 1000
        return max(self.min_duration, min(optimal, self.max_duration))
    
    def adjust_timing(self, entries):
        """Adjust timing for all subtitle entries."""
        adjusted = []
        
        for i, entry in enumerate(entries):
            new_entry = entry.copy()
            text = entry.get('text', '')
            
            # Calculate optimal duration
            optimal_duration = self.calculate_optimal_duration(text)
            current_duration = entry['end'] - entry['start']
            
            # Only extend if current duration is too short
            if current_duration < optimal_duration:
                new_end = entry['start'] + optimal_duration
                
                # Check if we overlap with next subtitle
                if i + 1 < len(entries):
                    next_start = entries[i + 1]['start']
                    max_end = next_start - self.gap_threshold
                    new_end = min(new_end, max_end)
                
                new_entry['end'] = max(new_end, entry['end'])
            
            adjusted.append(new_entry)
        
        return adjusted
    
    def sync_offset(self, entries, offset_ms):
        """Apply a time offset to all subtitles."""
        return [
            {**e, 'start': e['start'] + offset_ms, 'end': e['end'] + offset_ms}
            for e in entries
        ]
    
    def stretch_timing(self, entries, factor):
        """Stretch or compress subtitle timing by a factor."""
        if not entries:
            return entries
        
        base_time = entries[0]['start']
        return [
            {
                **e,
                'start': base_time + int((e['start'] - base_time) * factor),
                'end': base_time + int((e['end'] - base_time) * factor)
            }
            for e in entries
        ]


class ProfanityFilter:
    """
    Filter or censor profanity in subtitles.
    """
    
    # Basic list - expand as needed
    PROFANITY_LISTS = {
        'en': ['fuck', 'shit', 'damn', 'ass', 'bitch', 'crap', 'bastard', 'hell'],
        'sv': ['fan', 'jävla', 'skit', 'helvete', 'förbannad'],
        'de': ['scheiße', 'verdammt', 'arsch', 'fick'],
        'fr': ['merde', 'putain', 'bordel', 'con'],
        'es': ['mierda', 'joder', 'coño', 'puta'],
    }
    
    def __init__(self, addon_data_path):
        self.custom_path = os.path.join(addon_data_path, 'profanity_filter.json')
        self.custom_words = {}
        self.replacement = '***'
        self.load()
    
    def load(self):
        """Load custom profanity list."""
        if xbmcvfs.exists(self.custom_path):
            try:
                with xbmcvfs.File(self.custom_path, 'r') as f:
                    self.custom_words = json.loads(f.read())
            except:
                pass
    
    def save(self):
        """Save custom profanity list."""
        with xbmcvfs.File(self.custom_path, 'w') as f:
            f.write(json.dumps(self.custom_words, indent=2))
    
    def add_word(self, language, word):
        """Add a word to the filter list."""
        if language not in self.custom_words:
            self.custom_words[language] = []
        if word.lower() not in self.custom_words[language]:
            self.custom_words[language].append(word.lower())
            self.save()
    
    def get_words(self, language):
        """Get all profanity words for a language."""
        words = self.PROFANITY_LISTS.get(language, []).copy()
        words.extend(self.custom_words.get(language, []))
        return words
    
    def filter_text(self, text, language):
        """Filter profanity from text."""
        words = self.get_words(language)
        
        for word in words:
            # Match whole words only, case-insensitive
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            text = pattern.sub(self.replacement, text)
        
        return text


class TranslationQueue:
    """
    Background translation queue for batch processing.
    """
    
    def __init__(self, addon_data_path, max_concurrent=2):
        self.queue_path = os.path.join(addon_data_path, 'translation_queue.json')
        self.queue = []
        self.processing = False
        self.max_concurrent = max_concurrent
        self._thread = None
        self._stop_event = threading.Event()
        self.load()
    
    def load(self):
        """Load queue from file."""
        if xbmcvfs.exists(self.queue_path):
            try:
                with xbmcvfs.File(self.queue_path, 'r') as f:
                    self.queue = json.loads(f.read())
            except:
                self.queue = []
    
    def save(self):
        """Save queue to file."""
        with xbmcvfs.File(self.queue_path, 'w') as f:
            f.write(json.dumps(self.queue, indent=2))
    
    def add(self, video_path, source_lang, target_lang, priority=5):
        """Add a video to the translation queue."""
        item = {
            'id': hashlib.md5(f"{video_path}{target_lang}".encode()).hexdigest()[:12],
            'video_path': video_path,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'priority': priority,
            'status': 'pending',
            'added': datetime.now().isoformat(),
            'attempts': 0,
            'error': None
        }
        
        # Check for duplicates
        if not any(q['id'] == item['id'] for q in self.queue):
            self.queue.append(item)
            self.queue.sort(key=lambda x: x['priority'])
            self.save()
            return item['id']
        return None
    
    def remove(self, item_id):
        """Remove an item from the queue."""
        self.queue = [q for q in self.queue if q['id'] != item_id]
        self.save()
    
    def get_status(self):
        """Get queue status summary."""
        return {
            'total': len(self.queue),
            'pending': len([q for q in self.queue if q['status'] == 'pending']),
            'processing': len([q for q in self.queue if q['status'] == 'processing']),
            'completed': len([q for q in self.queue if q['status'] == 'completed']),
            'failed': len([q for q in self.queue if q['status'] == 'failed'])
        }
    
    def get_next(self):
        """Get the next item to process."""
        for item in self.queue:
            if item['status'] == 'pending':
                return item
        return None
    
    def update_status(self, item_id, status, error=None):
        """Update item status."""
        for item in self.queue:
            if item['id'] == item_id:
                item['status'] = status
                item['error'] = error
                if status == 'processing':
                    item['attempts'] += 1
                break
        self.save()


class SubtitleStatistics:
    """
    Track translation statistics and usage.
    """
    
    def __init__(self, addon_data_path):
        self.stats_path = os.path.join(addon_data_path, 'statistics.json')
        self.stats = {
            'total_translations': 0,
            'total_characters': 0,
            'total_subtitles': 0,
            'translations_by_service': {},
            'translations_by_language': {},
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'first_translation': None,
            'last_translation': None,
            'daily_stats': {}
        }
        self.load()
    
    def load(self):
        """Load statistics from file."""
        if xbmcvfs.exists(self.stats_path):
            try:
                with xbmcvfs.File(self.stats_path, 'r') as f:
                    self.stats = json.loads(f.read())
            except:
                pass
    
    def save(self):
        """Save statistics to file."""
        with xbmcvfs.File(self.stats_path, 'w') as f:
            f.write(json.dumps(self.stats, indent=2))
    
    def record_translation(self, service, target_lang, subtitle_count, char_count):
        """Record a successful translation."""
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        self.stats['total_translations'] += 1
        self.stats['total_characters'] += char_count
        self.stats['total_subtitles'] += subtitle_count
        
        # By service
        if service not in self.stats['translations_by_service']:
            self.stats['translations_by_service'][service] = 0
        self.stats['translations_by_service'][service] += 1
        
        # By language
        if target_lang not in self.stats['translations_by_language']:
            self.stats['translations_by_language'][target_lang] = 0
        self.stats['translations_by_language'][target_lang] += 1
        
        # Timestamps
        if not self.stats['first_translation']:
            self.stats['first_translation'] = now.isoformat()
        self.stats['last_translation'] = now.isoformat()
        
        # Daily stats
        if today not in self.stats['daily_stats']:
            self.stats['daily_stats'][today] = {'translations': 0, 'characters': 0}
        self.stats['daily_stats'][today]['translations'] += 1
        self.stats['daily_stats'][today]['characters'] += char_count
        
        self.save()
    
    def record_cache_hit(self):
        """Record a cache hit."""
        self.stats['cache_hits'] += 1
        self.save()
    
    def record_cache_miss(self):
        """Record a cache miss."""
        self.stats['cache_misses'] += 1
        self.save()
    
    def record_error(self):
        """Record a translation error."""
        self.stats['errors'] += 1
        self.save()
    
    def get_summary(self):
        """Get a human-readable summary."""
        cache_total = self.stats['cache_hits'] + self.stats['cache_misses']
        cache_rate = (self.stats['cache_hits'] / cache_total * 100) if cache_total > 0 else 0
        
        return {
            'total_translations': self.stats['total_translations'],
            'total_subtitles': self.stats['total_subtitles'],
            'total_characters': self.stats['total_characters'],
            'cache_hit_rate': f"{cache_rate:.1f}%",
            'most_used_service': max(self.stats['translations_by_service'].items(), 
                                     key=lambda x: x[1])[0] if self.stats['translations_by_service'] else 'N/A',
            'most_translated_language': max(self.stats['translations_by_language'].items(),
                                            key=lambda x: x[1])[0] if self.stats['translations_by_language'] else 'N/A'
        }


class ServiceFallbackChain:
    """
    Try multiple translation services in order if one fails.
    """
    
    def __init__(self, services_config):
        """
        services_config: List of (service_name, config) tuples in priority order
        """
        self.services = services_config
        self.failed_services = set()
        self.failure_timeout = 300  # 5 minutes before retrying failed service
        self.failure_times = {}
    
    def reset_failures(self):
        """Reset failed services list."""
        self.failed_services.clear()
        self.failure_times.clear()
    
    def mark_failed(self, service_name):
        """Mark a service as temporarily failed."""
        self.failed_services.add(service_name)
        self.failure_times[service_name] = time.time()
    
    def is_available(self, service_name):
        """Check if a service is available (not in cooldown)."""
        if service_name not in self.failed_services:
            return True
        
        # Check if cooldown has expired
        failure_time = self.failure_times.get(service_name, 0)
        if time.time() - failure_time > self.failure_timeout:
            self.failed_services.discard(service_name)
            return True
        
        return False
    
    def get_available_services(self):
        """Get list of currently available services."""
        return [s for s in self.services if self.is_available(s[0])]


class ContextualTranslator:
    """
    Provide context to translators for better quality.
    Sends surrounding subtitles for context-aware translation.
    """
    
    def __init__(self, context_window=3):
        self.context_window = context_window  # Number of subtitles before/after
    
    def prepare_with_context(self, entries, index):
        """Prepare a subtitle entry with surrounding context."""
        start_idx = max(0, index - self.context_window)
        end_idx = min(len(entries), index + self.context_window + 1)
        
        context_entries = entries[start_idx:end_idx]
        target_position = index - start_idx
        
        return {
            'context': context_entries,
            'target_index': target_position,
            'target_entry': entries[index]
        }
    
    def build_context_prompt(self, context_data, source_lang, target_lang):
        """Build a prompt with context for AI translators."""
        context = context_data['context']
        target_idx = context_data['target_index']
        
        lines = []
        for i, entry in enumerate(context):
            prefix = ">>> " if i == target_idx else "    "
            lines.append(f"{prefix}[{i+1}] {entry['text']}")
        
        prompt = f"""Translate the marked subtitle (>>>) from {source_lang} to {target_lang}.
Consider the surrounding context for accurate translation.

Context:
{chr(10).join(lines)}

Only output the translation for the marked line, nothing else."""
        
        return prompt


class SDHProcessor:
    """
    Process Subtitles for the Deaf and Hard-of-hearing (SDH).
    Handle speaker labels, sound descriptions, etc.
    """
    
    # Patterns for SDH elements
    SPEAKER_PATTERN = re.compile(r'^([A-Z][A-Z\s]+):\s*')
    SOUND_PATTERN = re.compile(r'\[([^\]]+)\]|\(([^\)]+)\)')
    MUSIC_PATTERN = re.compile(r'♪.*?♪|♫.*?♫', re.DOTALL)
    
    def __init__(self):
        self.preserve_speaker_labels = True
        self.preserve_sound_descriptions = True
        self.translate_sound_descriptions = True
    
    def extract_sdh_elements(self, text):
        """Extract SDH elements from text."""
        elements = {
            'speaker': None,
            'sounds': [],
            'music': [],
            'clean_text': text
        }
        
        # Extract speaker
        speaker_match = self.SPEAKER_PATTERN.match(text)
        if speaker_match:
            elements['speaker'] = speaker_match.group(1)
            elements['clean_text'] = text[speaker_match.end():]
        
        # Extract sounds
        elements['sounds'] = self.SOUND_PATTERN.findall(elements['clean_text'])
        elements['clean_text'] = self.SOUND_PATTERN.sub('', elements['clean_text'])
        
        # Extract music
        elements['music'] = self.MUSIC_PATTERN.findall(elements['clean_text'])
        elements['clean_text'] = self.MUSIC_PATTERN.sub('', elements['clean_text'])
        
        elements['clean_text'] = elements['clean_text'].strip()
        
        return elements
    
    def reconstruct_sdh(self, translated_text, original_elements, translated_sounds=None):
        """Reconstruct SDH subtitle with translated content."""
        result = translated_text
        
        # Add back speaker label
        if original_elements['speaker'] and self.preserve_speaker_labels:
            result = f"{original_elements['speaker']}: {result}"
        
        # Add back sound descriptions
        if self.preserve_sound_descriptions:
            for sound_tuple in original_elements['sounds']:
                sound = sound_tuple[0] or sound_tuple[1]
                if sound:
                    if translated_sounds and sound in translated_sounds:
                        sound = translated_sounds[sound]
                    result = f"{result} [{sound}]"
        
        # Add back music notation
        for music in original_elements['music']:
            result = f"{result} {music}"
        
        return result


class MultiLanguageGenerator:
    """
    Generate subtitles for multiple target languages simultaneously.
    """
    
    def __init__(self, translator_factory):
        self.translator_factory = translator_factory
    
    def translate_to_multiple(self, entries, source_lang, target_languages, service_config):
        """Translate to multiple languages."""
        results = {}
        
        for target_lang in target_languages:
            translator = self.translator_factory(service_config)
            try:
                translated = []
                for entry in entries:
                    trans_text = translator.translate(entry['text'], source_lang, target_lang)
                    translated.append({**entry, 'text': trans_text})
                results[target_lang] = {'success': True, 'entries': translated}
            except Exception as e:
                results[target_lang] = {'success': False, 'error': str(e)}
        
        return results


class SubtitleLineBreaker:
    """
    Intelligently break long subtitle lines for better readability.
    """
    
    def __init__(self, max_line_length=42, max_lines=2):
        self.max_line_length = max_line_length
        self.max_lines = max_lines
        # Words that shouldn't start a new line
        self.no_break_before = {'and', 'or', 'but', 'the', 'a', 'an', 'to', 'of', 'in', 'on', 'for'}
    
    def break_lines(self, text):
        """Break text into properly formatted subtitle lines."""
        # Remove existing line breaks
        text = ' '.join(text.split())
        
        if len(text) <= self.max_line_length:
            return text
        
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            # Check if adding this word exceeds the limit
            if current_length + word_length + (1 if current_line else 0) > self.max_line_length:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    # Word itself is too long, force it
                    lines.append(word)
                    current_length = 0
            else:
                current_line.append(word)
                current_length += word_length + (1 if len(current_line) > 1 else 0)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Respect max_lines limit
        if len(lines) > self.max_lines:
            lines = lines[:self.max_lines]
            lines[-1] += '...'
        
        return '\n'.join(lines)
    
    def process_entries(self, entries):
        """Process all subtitle entries."""
        return [{**e, 'text': self.break_lines(e['text'])} for e in entries]


class RateLimiter:
    """
    Intelligent rate limiting for translation APIs.
    """
    
    def __init__(self, addon_data_path):
        self.limits_path = os.path.join(addon_data_path, 'rate_limits.json')
        self.limits = {}
        self.usage = {}
        self.load()
        
        # Default limits per service (requests per period)
        self.default_limits = {
            'mymemory': {'requests': 1000, 'period': 86400, 'chars': 10000},  # Per day
            'libretranslate': {'requests': 100, 'period': 60, 'chars': None},  # Per minute
            'deepl_free': {'requests': None, 'period': None, 'chars': 500000},  # Per month
            'lingva': {'requests': 50, 'period': 60, 'chars': None},
        }
    
    def load(self):
        """Load rate limit state."""
        if xbmcvfs.exists(self.limits_path):
            try:
                with xbmcvfs.File(self.limits_path, 'r') as f:
                    data = json.loads(f.read())
                    self.limits = data.get('limits', {})
                    self.usage = data.get('usage', {})
            except:
                pass
    
    def save(self):
        """Save rate limit state."""
        with xbmcvfs.File(self.limits_path, 'w') as f:
            f.write(json.dumps({'limits': self.limits, 'usage': self.usage}, indent=2))
    
    def can_request(self, service, char_count=0):
        """Check if a request is allowed within rate limits."""
        limits = self.limits.get(service, self.default_limits.get(service, {}))
        if not limits:
            return True
        
        now = time.time()
        
        if service not in self.usage:
            self.usage[service] = {'requests': 0, 'chars': 0, 'period_start': now}
        
        usage = self.usage[service]
        
        # Reset if period has passed
        period = limits.get('period', 86400)
        if now - usage['period_start'] > period:
            usage['requests'] = 0
            usage['chars'] = 0
            usage['period_start'] = now
        
        # Check request limit
        if limits.get('requests') and usage['requests'] >= limits['requests']:
            return False
        
        # Check character limit
        if limits.get('chars') and usage['chars'] + char_count > limits['chars']:
            return False
        
        return True
    
    def record_request(self, service, char_count=0):
        """Record a request for rate limiting."""
        if service not in self.usage:
            self.usage[service] = {'requests': 0, 'chars': 0, 'period_start': time.time()}
        
        self.usage[service]['requests'] += 1
        self.usage[service]['chars'] += char_count
        self.save()
    
    def get_wait_time(self, service):
        """Get seconds to wait before next request is allowed."""
        limits = self.limits.get(service, self.default_limits.get(service, {}))
        if not limits:
            return 0
        
        usage = self.usage.get(service)
        if not usage:
            return 0
        
        period = limits.get('period', 86400)
        elapsed = time.time() - usage['period_start']
        
        if elapsed >= period:
            return 0
        
        if limits.get('requests') and usage['requests'] >= limits['requests']:
            return period - elapsed
        
        return 0


class ProxyManager:
    """
    Manage HTTP/SOCKS proxy configuration for API requests.
    """
    
    def __init__(self, addon_data_path):
        self.config_path = os.path.join(addon_data_path, 'proxy.json')
        self.config = {
            'enabled': False,
            'type': 'http',  # http, https, socks4, socks5
            'host': '',
            'port': 8080,
            'username': '',
            'password': '',
            'bypass': []  # Hosts to bypass proxy
        }
        self.load()
    
    def load(self):
        """Load proxy configuration."""
        if xbmcvfs.exists(self.config_path):
            try:
                with xbmcvfs.File(self.config_path, 'r') as f:
                    self.config.update(json.loads(f.read()))
            except:
                pass
    
    def save(self):
        """Save proxy configuration."""
        with xbmcvfs.File(self.config_path, 'w') as f:
            f.write(json.dumps(self.config, indent=2))
    
    def get_proxy_url(self):
        """Get proxy URL for requests."""
        if not self.config['enabled']:
            return None
        
        auth = ''
        if self.config['username']:
            auth = f"{self.config['username']}:{self.config['password']}@"
        
        return f"{self.config['type']}://{auth}{self.config['host']}:{self.config['port']}"
    
    def get_proxy_dict(self):
        """Get proxy dictionary for requests library."""
        url = self.get_proxy_url()
        if not url:
            return {}
        
        return {
            'http': url,
            'https': url
        }


class ExportManager:
    """
    Export translated subtitles in various formats.
    """
    
    FORMATS = ['srt', 'ass', 'vtt', 'json', 'txt']
    
    def __init__(self, addon_data_path):
        self.export_path = os.path.join(addon_data_path, 'exports')
        if not xbmcvfs.exists(self.export_path):
            xbmcvfs.mkdirs(self.export_path)
    
    def export(self, entries, video_name, target_lang, format='srt'):
        """Export subtitles to file."""
        filename = f"{video_name}.{target_lang}.{format}"
        filepath = os.path.join(self.export_path, filename)
        
        if format == 'srt':
            content = self._to_srt(entries)
        elif format == 'ass':
            content = self._to_ass(entries)
        elif format == 'vtt':
            content = self._to_vtt(entries)
        elif format == 'json':
            content = json.dumps(entries, indent=2, ensure_ascii=False)
        elif format == 'txt':
            content = '\n\n'.join(e['text'] for e in entries)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        with xbmcvfs.File(filepath, 'w') as f:
            f.write(content)
        
        return filepath
    
    def _format_time_srt(self, ms):
        """Format milliseconds to SRT time format."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
    
    def _format_time_vtt(self, ms):
        """Format milliseconds to VTT time format."""
        return self._format_time_srt(ms).replace(',', '.')
    
    def _to_srt(self, entries):
        """Convert entries to SRT format."""
        lines = []
        for i, entry in enumerate(entries, 1):
            lines.append(str(i))
            lines.append(f"{self._format_time_srt(entry['start'])} --> {self._format_time_srt(entry['end'])}")
            lines.append(entry['text'])
            lines.append('')
        return '\n'.join(lines)
    
    def _to_vtt(self, entries):
        """Convert entries to WebVTT format."""
        lines = ['WEBVTT', '']
        for i, entry in enumerate(entries, 1):
            lines.append(str(i))
            lines.append(f"{self._format_time_vtt(entry['start'])} --> {self._format_time_vtt(entry['end'])}")
            lines.append(entry['text'])
            lines.append('')
        return '\n'.join(lines)
    
    def _to_ass(self, entries):
        """Convert entries to ASS format."""
        header = """[Script Info]
Title: Translated Subtitles
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        
        for entry in entries:
            start = self._format_time_ass(entry['start'])
            end = self._format_time_ass(entry['end'])
            text = entry['text'].replace('\n', '\\N')
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        
        return '\n'.join(lines)
    
    def _format_time_ass(self, ms):
        """Format milliseconds to ASS time format."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        centis = (ms % 1000) // 10
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"
