from urllib.parse import urljoin, urlparse

from flask import request, url_for


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
