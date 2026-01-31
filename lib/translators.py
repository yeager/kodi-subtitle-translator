# -*- coding: utf-8 -*-
"""
Translation Services - Support for multiple translation APIs.
"""

import json
import urllib.request
import urllib.parse
import xbmc


def get_translator(service_name, config):
    """
    Get a translator instance for the specified service.
    
    Args:
        service_name: Name of the translation service
        config: Service configuration dict
    
    Returns:
        Translator instance
    """
    translators = {
        'deepl': DeepLTranslator,
        'deepl_free': DeepLTranslator,
        'libretranslate': LibreTranslateTranslator,
        'mymemory': MyMemoryTranslator,
        'google': GoogleTranslator,
        'microsoft': MicrosoftTranslator,
        'lingva': LingvaTranslator,
        'openai': OpenAITranslator,
        'anthropic': AnthropicTranslator,
        'argos': ArgosTranslator,
    }
    
    translator_class = translators.get(service_name, LibreTranslateTranslator)
    return translator_class(config)


class BaseTranslator:
    """Base class for translation services."""
    
    def __init__(self, config):
        self.config = config
        self.timeout = config.get('timeout', 30)
    
    def translate(self, text, source_lang, target_lang):
        """Translate a single text string."""
        raise NotImplementedError
    
    def translate_batch(self, texts, source_lang, target_lang):
        """
        Translate multiple texts.
        Default implementation translates one by one.
        """
        return [self.translate(text, source_lang, target_lang) for text in texts]
    
    def _request(self, url, data=None, headers=None, method='POST'):
        """Make HTTP request."""
        if headers is None:
            headers = {}
        
        if data and isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif data and isinstance(data, str):
            data = data.encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            self._log(f"Request error: {e}", xbmc.LOGERROR)
            raise
    
    def _log(self, message, level=xbmc.LOGINFO):
        """Log message."""
        xbmc.log(f"[Translator] {message}", level)


class DeepLTranslator(BaseTranslator):
    """DeepL Translation API."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.formality = config.get('formality', 'default')
        self.is_free = config.get('free', False)
        
        if self.is_free:
            self.base_url = 'https://api-free.deepl.com/v2'
        else:
            self.base_url = 'https://api.deepl.com/v2'
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using DeepL."""
        if not self.api_key:
            raise ValueError("DeepL API key required")
        
        result = self.translate_batch([text], source_lang, target_lang)
        return result[0] if result else text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts in one request."""
        if not self.api_key:
            raise ValueError("DeepL API key required")
        
        # Map language codes
        target = self._map_language(target_lang)
        source = self._map_language(source_lang) if source_lang != 'auto' else None
        
        data = {
            'text': texts,
            'target_lang': target
        }
        
        if source:
            data['source_lang'] = source
        
        if self.formality != 'default' and target in ['DE', 'FR', 'IT', 'ES', 'NL', 'PL', 'PT-PT', 'PT-BR', 'RU']:
            data['formality'] = self.formality
        
        headers = {
            'Authorization': f'DeepL-Auth-Key {self.api_key}'
        }
        
        try:
            response = self._request(f'{self.base_url}/translate', data, headers)
            return [t['text'] for t in response.get('translations', [])]
        except Exception as e:
            self._log(f"DeepL error: {e}", xbmc.LOGERROR)
            return texts
    
    def _map_language(self, lang):
        """Map language code to DeepL format."""
        mapping = {
            'en': 'EN', 'sv': 'SV', 'de': 'DE', 'fr': 'FR',
            'es': 'ES', 'it': 'IT', 'nl': 'NL', 'pl': 'PL',
            'pt': 'PT-PT', 'ru': 'RU', 'ja': 'JA', 'zh': 'ZH',
            'da': 'DA', 'fi': 'FI', 'no': 'NB', 'ko': 'KO'
        }
        return mapping.get(lang.lower(), lang.upper())


class LibreTranslateTranslator(BaseTranslator):
    """LibreTranslate API (self-hosted or public instances)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.get('url', 'https://libretranslate.com').rstrip('/')
        self.api_key = config.get('api_key', '')
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using LibreTranslate."""
        data = {
            'q': text,
            'source': source_lang if source_lang != 'auto' else 'auto',
            'target': target_lang,
            'format': 'text'
        }
        
        if self.api_key:
            data['api_key'] = self.api_key
        
        try:
            response = self._request(f'{self.base_url}/translate', data)
            return response.get('translatedText', text)
        except Exception as e:
            self._log(f"LibreTranslate error: {e}", xbmc.LOGERROR)
            return text


class MyMemoryTranslator(BaseTranslator):
    """MyMemory Translation API (free, rate-limited)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = 'https://api.mymemory.translated.net'
        self.email = config.get('email', '')  # Optional, increases rate limit
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using MyMemory."""
        lang_pair = f'{source_lang}|{target_lang}'
        
        params = {
            'q': text,
            'langpair': lang_pair
        }
        
        if self.email:
            params['de'] = self.email
        
        url = f'{self.base_url}/get?{urllib.parse.urlencode(params)}'
        
        try:
            response = self._request(url, method='GET')
            return response.get('responseData', {}).get('translatedText', text)
        except Exception as e:
            self._log(f"MyMemory error: {e}", xbmc.LOGERROR)
            return text


class GoogleTranslator(BaseTranslator):
    """Google Cloud Translation API."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.base_url = 'https://translation.googleapis.com/language/translate/v2'
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using Google Cloud Translation."""
        if not self.api_key:
            raise ValueError("Google API key required")
        
        result = self.translate_batch([text], source_lang, target_lang)
        return result[0] if result else text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts."""
        if not self.api_key:
            raise ValueError("Google API key required")
        
        data = {
            'q': texts,
            'target': target_lang,
            'format': 'text',
            'key': self.api_key
        }
        
        if source_lang != 'auto':
            data['source'] = source_lang
        
        try:
            response = self._request(self.base_url, data)
            translations = response.get('data', {}).get('translations', [])
            return [t.get('translatedText', texts[i]) for i, t in enumerate(translations)]
        except Exception as e:
            self._log(f"Google Translate error: {e}", xbmc.LOGERROR)
            return texts


class MicrosoftTranslator(BaseTranslator):
    """Microsoft Azure Translator API."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.region = config.get('region', 'westeurope')
        self.base_url = 'https://api.cognitive.microsofttranslator.com/translate'
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using Microsoft Translator."""
        if not self.api_key:
            raise ValueError("Microsoft API key required")
        
        result = self.translate_batch([text], source_lang, target_lang)
        return result[0] if result else text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts."""
        if not self.api_key:
            raise ValueError("Microsoft API key required")
        
        params = {
            'api-version': '3.0',
            'to': target_lang
        }
        
        if source_lang != 'auto':
            params['from'] = source_lang
        
        url = f'{self.base_url}?{urllib.parse.urlencode(params)}'
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Ocp-Apim-Subscription-Region': self.region
        }
        
        data = [{'Text': text} for text in texts]
        
        try:
            response = self._request(url, data, headers)
            return [r['translations'][0]['text'] for r in response]
        except Exception as e:
            self._log(f"Microsoft Translator error: {e}", xbmc.LOGERROR)
            return texts


class LingvaTranslator(BaseTranslator):
    """Lingva Translate (free, open-source Google Translate frontend)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.get('url', 'https://lingva.ml').rstrip('/')
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using Lingva."""
        source = source_lang if source_lang != 'auto' else 'auto'
        
        # URL encode the text
        encoded_text = urllib.parse.quote(text)
        url = f'{self.base_url}/api/v1/{source}/{target_lang}/{encoded_text}'
        
        try:
            response = self._request(url, method='GET')
            return response.get('translation', text)
        except Exception as e:
            self._log(f"Lingva error: {e}", xbmc.LOGERROR)
            return text


class OpenAITranslator(BaseTranslator):
    """OpenAI GPT Translation (high-quality, context-aware)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'gpt-4o-mini')
        self.base_url = config.get('base_url', 'https://api.openai.com/v1').rstrip('/')
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using OpenAI GPT."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        result = self.translate_batch([text], source_lang, target_lang)
        return result[0] if result else text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts using OpenAI."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        target_name = self._get_language_name(target_lang)
        source_name = self._get_language_name(source_lang) if source_lang != 'auto' else 'the source language'
        
        # Combine texts for efficient translation
        combined = '\n---SUBTITLE_BREAK---\n'.join(texts)
        
        system_prompt = f"""You are a professional subtitle translator. Translate the following subtitles from {source_name} to {target_name}.

Rules:
- Preserve the exact number of subtitle entries (separated by ---SUBTITLE_BREAK---)
- Keep translations natural and colloquial, suitable for subtitles
- Maintain the same tone and style as the original
- Keep translations concise (subtitles have limited space)
- Do not add explanations or notes
- Only output the translations, nothing else"""
        
        data = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': combined}
            ],
            'temperature': 0.3
        }
        
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        try:
            response = self._request(f'{self.base_url}/chat/completions', data, headers)
            translated = response['choices'][0]['message']['content']
            return translated.split('\n---SUBTITLE_BREAK---\n')
        except Exception as e:
            self._log(f"OpenAI error: {e}", xbmc.LOGERROR)
            return texts
    
    def _get_language_name(self, code):
        """Get full language name from code."""
        names = {
            'sv': 'Swedish', 'en': 'English', 'de': 'German', 'fr': 'French',
            'es': 'Spanish', 'it': 'Italian', 'no': 'Norwegian', 'da': 'Danish',
            'fi': 'Finnish', 'nl': 'Dutch', 'pl': 'Polish', 'pt': 'Portuguese',
            'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese', 'ko': 'Korean',
            'ar': 'Arabic', 'tr': 'Turkish', 'hi': 'Hindi', 'uk': 'Ukrainian'
        }
        return names.get(code, code)


class AnthropicTranslator(BaseTranslator):
    """Anthropic Claude Translation (high-quality, context-aware)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'claude-3-haiku-20240307')
        self.base_url = 'https://api.anthropic.com/v1'
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using Claude."""
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        
        result = self.translate_batch([text], source_lang, target_lang)
        return result[0] if result else text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts using Claude."""
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        
        target_name = self._get_language_name(target_lang)
        source_name = self._get_language_name(source_lang) if source_lang != 'auto' else 'the source language'
        
        combined = '\n---SUBTITLE_BREAK---\n'.join(texts)
        
        system_prompt = f"""You are a professional subtitle translator. Translate subtitles from {source_name} to {target_name}.

Rules:
- Preserve the exact number of subtitle entries (separated by ---SUBTITLE_BREAK---)
- Keep translations natural and colloquial
- Maintain tone and style
- Keep translations concise for subtitle format
- Output only translations, no explanations"""
        
        data = {
            'model': self.model,
            'max_tokens': 4096,
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': combined}
            ]
        }
        
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01'
        }
        
        try:
            response = self._request(f'{self.base_url}/messages', data, headers)
            translated = response['content'][0]['text']
            return translated.split('\n---SUBTITLE_BREAK---\n')
        except Exception as e:
            self._log(f"Anthropic error: {e}", xbmc.LOGERROR)
            return texts
    
    def _get_language_name(self, code):
        """Get full language name from code."""
        names = {
            'sv': 'Swedish', 'en': 'English', 'de': 'German', 'fr': 'French',
            'es': 'Spanish', 'it': 'Italian', 'no': 'Norwegian', 'da': 'Danish',
            'fi': 'Finnish', 'nl': 'Dutch', 'pl': 'Polish', 'pt': 'Portuguese',
            'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese', 'ko': 'Korean',
            'ar': 'Arabic', 'tr': 'Turkish', 'hi': 'Hindi', 'uk': 'Ukrainian'
        }
        return names.get(code, code)


class ArgosTranslator(BaseTranslator):
    """Argos Translate (offline, local translation using neural models)."""
    
    def __init__(self, config):
        super().__init__(config)
        self.package_path = config.get('package_path', '')
        self._argos_available = None
    
    def _check_argos(self):
        """Check if Argos Translate is available."""
        if self._argos_available is not None:
            return self._argos_available
        
        try:
            import argostranslate.package
            import argostranslate.translate
            self._argos_available = True
        except ImportError:
            self._argos_available = False
            self._log("Argos Translate not installed. Install with: pip install argostranslate", xbmc.LOGERROR)
        
        return self._argos_available
    
    def translate(self, text, source_lang, target_lang):
        """Translate text using Argos Translate (offline)."""
        if not self._check_argos():
            return text
        
        try:
            import argostranslate.translate
            
            # Get installed languages
            installed_languages = argostranslate.translate.get_installed_languages()
            source_l = next((l for l in installed_languages if l.code == source_lang), None)
            target_l = next((l for l in installed_languages if l.code == target_lang), None)
            
            if not source_l or not target_l:
                self._log(f"Language pair {source_lang}->{target_lang} not installed", xbmc.LOGERROR)
                return text
            
            translation = source_l.get_translation(target_l)
            if translation:
                return translation.translate(text)
            else:
                self._log(f"No translation available for {source_lang}->{target_lang}", xbmc.LOGERROR)
                return text
                
        except Exception as e:
            self._log(f"Argos error: {e}", xbmc.LOGERROR)
            return text
    
    def translate_batch(self, texts, source_lang, target_lang):
        """Translate multiple texts using Argos."""
        return [self.translate(text, source_lang, target_lang) for text in texts]
