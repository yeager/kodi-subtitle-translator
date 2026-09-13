"""Remove credentials and NUL bytes before writing diagnostics."""
import re
import xbmc

_CREDENTIALS = re.compile(r'(?i)([a-z][a-z0-9+.-]*://)[^/\s]*@')
_QUERY_SECRET = re.compile(r'(?i)([?&](?:api[_-]?key|key|token|access_token|password|auth|signature)=)[^&#\s]*')
_SECRET_KEYS = {'api_key', 'key', 'token', 'access_token', 'password', 'authorization', 'x-api-key'}


def redact(value):
    if isinstance(value, dict):
        return {key: '[redacted]' if str(key).lower() in _SECRET_KEYS else redact(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = value.replace('\x00', '')
        value = _CREDENTIALS.sub(r'\1[redacted]@', value)
        return _QUERY_SECRET.sub(r'\1[redacted]', value)
    return value


def log(message, level=xbmc.LOGINFO):
    xbmc.log(redact(str(message)), level)
