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
