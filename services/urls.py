import re
from urllib.parse import urljoin, urlparse

from flask import request, url_for


_ABSOLUTE_URL_RE = re.compile(r'https?://[^\s"\'<>()]+', re.IGNORECASE)


def normalize_local_media_url(url):
    raw_value = str(url or '').strip()
    if not raw_value:
        return ''

    parsed = urlparse(raw_value)
    if parsed.scheme and parsed.netloc:
        if (parsed.path or '').startswith('/media/'):
            normalized = parsed.path or ''
            if parsed.query:
                normalized += f'?{parsed.query}'
            return normalized
        return raw_value

    if raw_value.startswith('media/'):
        return f'/{raw_value}'
    return raw_value


def normalize_local_media_references_in_text(text):
    raw_text = str(text or '')
    if not raw_text:
        return ''

    return _ABSOLUTE_URL_RE.sub(
        lambda match: normalize_local_media_url(match.group(0)),
        raw_text,
    )


def force_https_url(url):
    if url and request.headers.get('X-Forwarded-Proto') == 'https':
        return url.replace('http://', 'https://', 1)
    return url


def get_safe_redirect_target(target):
    candidate = target or ''
    if not candidate:
        return url_for('main.index')

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, candidate))
    if test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc:
        return test_url.path + (('?' + test_url.query) if test_url.query else '')
    return url_for('main.index')
