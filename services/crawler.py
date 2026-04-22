import mimetypes
import os
import re
import socket
from io import BytesIO
from ipaddress import ip_address
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import ssl
import certifi

from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown
from werkzeug.datastructures import FileStorage

from .media import upload_media_file
from .urls import force_https_url


DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
MAX_HTML_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 25 * 1024 * 1024

DATE_META_NAMES = (
    ('property', 'article:published_time'),
    ('property', 'og:published_time'),
    ('name', 'article:published_time'),
    ('name', 'publishdate'),
    ('name', 'pubdate'),
    ('name', 'date'),
    ('itemprop', 'datePublished'),
)
TITLE_META_NAMES = (
    ('property', 'og:title'),
    ('name', 'twitter:title'),
)
IMAGE_META_NAMES = (
    ('property', 'og:image'),
    ('name', 'twitter:image'),
)
TAG_META_NAMES = (
    ('property', 'article:tag'),
    ('name', 'keywords'),
)
CONTENT_SELECTORS = (
    'article',
    '[itemprop="articleBody"]',
    '.post-content',
    '.entry-content',
    '.article-content',
    '.article-body',
    '.post-body',
    '.single-content',
    '.markdown-body',
    '.doc-content',
    '.content-body',
    'main article',
    'main',
    '.content',
    '.post',
)
DROP_TAGS = (
    'script',
    'style',
    'noscript',
    'iframe',
    'form',
    'button',
    'input',
    'textarea',
    'select',
    'svg',
    'canvas',
    'video',
    'audio',
)
DROP_SELECTORS = (
    'header',
    'footer',
    'nav',
    'aside',
    '.sidebar',
    '.post-toc',
    '.toc',
    '.comment',
    '.comments',
    '.comment-list',
    '.advertisement',
    '.ads',
    '.share',
    '.social',
    '.recommend',
    '.related',
    '.breadcrumbs',
)


class CrawlError(Exception):
    """文章抓取失败。"""


def _is_ip_public(value):
    try:
        ip_obj = ip_address(value)
    except ValueError:
        return False

    return bool(getattr(ip_obj, 'is_global', False))


def _validate_public_url(raw_url):
    parsed = urlparse(str(raw_url or '').strip())
    if parsed.scheme not in {'http', 'https'}:
        raise CrawlError('仅支持 http 或 https 链接')

    hostname = (parsed.hostname or '').strip().lower()
    if not hostname:
        raise CrawlError('链接缺少可访问的主机名')

    blocked_hosts = {'localhost', '127.0.0.1', '::1'}
    if hostname in blocked_hosts:
        raise CrawlError('不允许抓取本机或内网地址')

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CrawlError('无法解析目标站点地址') from exc

    for _, _, _, _, sockaddr in addr_info:
        resolved_ip = sockaddr[0]
        if not _is_ip_public(resolved_ip):
            raise CrawlError('不允许抓取内网、保留地址或本机地址')

    return parsed.geturl()


def _read_limited(response, max_bytes):
    chunks = []
    total = 0
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise CrawlError('目标内容过大，暂不支持抓取')
        chunks.append(chunk)
    return b''.join(chunks)


def _fetch_bytes(url, max_bytes=MAX_HTML_BYTES, accept_html=False):
    safe_url = _validate_public_url(url)
    request = Request(safe_url, headers=DEFAULT_HEADERS)

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=15, context=ssl_context) as response:
            final_url = response.geturl()
            _validate_public_url(final_url)
            content_type = (response.headers.get_content_type() or '').lower()
            if accept_html and content_type and 'html' not in content_type:
                raise CrawlError('目标地址不是可解析的文章页面')
            content = _read_limited(response, max_bytes)
            return final_url, content, response.headers
    except CrawlError:
        raise
    except Exception as exc:
        raise CrawlError(f'抓取失败：{exc}') from exc


def _meta_content(soup, attr_name, attr_value):
    node = soup.find('meta', attrs={attr_name: attr_value})
    return (node.get('content') or '').strip() if node else ''


def _normalize_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _trim_site_suffix(value):
    text = _normalize_text(value)
    if not text:
        return ''

    for separator in (' | ', ' - ', ' — ', ' – '):
        if separator not in text:
            continue
        parts = [item.strip() for item in text.split(separator) if item.strip()]
        if len(parts) < 2:
            continue
        last_part = parts[-1]
        leading = separator.join(parts[:-1]).strip()
        if leading and len(last_part) <= 24 and len(leading) > len(last_part):
            return leading
    return text


def _normalize_date(value):
    text = _normalize_text(value)
    if not text:
        return ''

    match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', text)
    if match:
        return match.group(1)

    match = re.search(r'(\d{4}/\d{1,2}/\d{1,2})', text)
    if match:
        return match.group(1).replace('/', '-')

    match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2})', text)
    if match:
        return match.group(1).replace('.', '-')

    return ''


def _extract_title(soup):
    for attr_name, attr_value in TITLE_META_NAMES:
        value = _meta_content(soup, attr_name, attr_value)
        if value:
            return _trim_site_suffix(value)

    for selector in ('article h1', 'main h1', 'h1', '.post-title', '.entry-title', '.article-title'):
        node = soup.select_one(selector)
        if node:
            text = _normalize_text(node.get_text(' ', strip=True))
            if text:
                return text

    title_text = _trim_site_suffix(soup.title.string if soup.title and soup.title.string else '')
    if title_text:
        return title_text
    return ''


def _extract_date(soup):
    for attr_name, attr_value in DATE_META_NAMES:
        value = _normalize_date(_meta_content(soup, attr_name, attr_value))
        if value:
            return value

    time_node = soup.select_one('time[datetime], time[pubdate], time')
    if time_node:
        time_value = time_node.get('datetime') or time_node.get('content') or time_node.get_text(' ', strip=True)
        normalized = _normalize_date(time_value)
        if normalized:
            return normalized

    text = _normalize_text(soup.get_text(' ', strip=True))
    return _normalize_date(text[:1200])


def _extract_tags(soup):
    tags = []

    for attr_name, attr_value in TAG_META_NAMES:
        value = _meta_content(soup, attr_name, attr_value)
        if not value:
            continue
        if attr_value == 'keywords':
            tags.extend([item.strip() for item in re.split(r'[,，]', value) if item.strip()])
        else:
            tags.append(value)

    for node in soup.select('a[rel="tag"], .tags a, .post-tags a, .article-tags a, [data-tag]'):
        text = _normalize_text(node.get_text(' ', strip=True) or node.get('data-tag') or '')
        if text:
            tags.append(text)

    deduped = []
    seen = set()
    for item in tags:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
        if len(deduped) >= 8:
            break
    return deduped


def _normalize_dom_urls(soup, base_url):
    for node in soup.select('[src]'):
        raw_src = (node.get('src') or '').strip()
        if raw_src:
            node['src'] = urljoin(base_url, raw_src)

    for node in soup.select('[href]'):
        raw_href = (node.get('href') or '').strip()
        if raw_href:
            node['href'] = urljoin(base_url, raw_href)


def _extract_cover(soup, content_node):
    for attr_name, attr_value in IMAGE_META_NAMES:
        value = _meta_content(soup, attr_name, attr_value)
        if value:
            return value

    image_node = None
    if content_node:
        image_node = content_node.select_one('img[src]')
    if not image_node:
        image_node = soup.select_one('article img[src], main img[src], img[src]')

    if image_node:
        return (image_node.get('src') or '').strip()
    return ''


def _score_content_node(node):
    text = _normalize_text(node.get_text(' ', strip=True))
    if len(text) < 120:
        return 0

    paragraph_count = len(node.find_all('p'))
    image_count = len(node.find_all('img'))
    heading_count = len(node.find_all(re.compile(r'^h[1-6]$')))
    return len(text) + paragraph_count * 120 + image_count * 40 + heading_count * 25


def _pick_content_node(soup, title):
    candidates = []
    for selector in CONTENT_SELECTORS:
        for node in soup.select(selector):
            score = _score_content_node(node)
            if score:
                candidates.append((score, node))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    body = soup.body or soup
    if title:
        title_node = body.find(re.compile(r'^h[1-6]$'), string=re.compile(re.escape(title)))
        if title_node and title_node.parent:
            return title_node.parent
    return body


def _clean_content_node(node):
    if node is None:
        return None

    for tag_name in DROP_TAGS:
        for child in node.find_all(tag_name):
            child.decompose()

    for selector in DROP_SELECTORS:
        for child in node.select(selector):
            child.decompose()

    for child in node.select('[style*="display:none"], [hidden], .hidden, .sr-only, .visually-hidden'):
        child.decompose()

    return node


def _strip_leading_duplicate_title(markdown_text, title):
    lines = markdown_text.splitlines()
    if not lines or not title:
        return markdown_text

    normalized_title = _normalize_text(title).lower()
    first_line = _normalize_text(re.sub(r'^#+\s*', '', lines[0])).lower()
    if first_line == normalized_title:
        return '\n'.join(lines[1:]).lstrip()
    return markdown_text


def _normalize_markdown(markdown_text, title=''):
    text = str(markdown_text or '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = _strip_leading_duplicate_title(text.strip(), title)
    return text.strip()


def extract_article_preview(url):
    fetched_url, raw_html, _ = _fetch_bytes(url, max_bytes=MAX_HTML_BYTES, accept_html=True)
    soup = BeautifulSoup(raw_html, 'html.parser')
    _normalize_dom_urls(soup, fetched_url)

    title = _extract_title(soup)
    content_node = _pick_content_node(soup, title)
    if content_node is None:
        raise CrawlError('未能识别正文内容')

    content_node = _clean_content_node(content_node)
    cover = _extract_cover(soup, content_node)
    published_at = _extract_date(soup)
    tags = _extract_tags(soup)

    markdown = html_to_markdown(
        str(content_node),
        heading_style='ATX',
        bullets='-',
        strong_em_symbol='*',
        strip=['script', 'style'],
    )
    markdown = _normalize_markdown(markdown, title=title)
    if not markdown:
        raise CrawlError('未能提取到有效正文内容')

    return {
        'source_url': fetched_url,
        'title': title,
        'date': published_at,
        'tags': tags,
        'cover': cover,
        'markdown': markdown,
    }


def _iter_markdown_image_urls(markdown_text):
    markdown_pattern = re.compile(r'!\[[^\]]*]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)')
    html_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

    for match in markdown_pattern.finditer(markdown_text or ''):
        raw_value = match.group(1).strip()
        if ' "' in raw_value:
            raw_value = raw_value.split(' "', 1)[0].strip()
        yield raw_value

    for match in html_pattern.finditer(markdown_text or ''):
        yield match.group(1).strip()


def _replace_markdown_image_urls(markdown_text, replacements):
    if not replacements:
        return markdown_text

    def replace_markdown(match):
        raw_value = match.group(1).strip()
        suffix = ''
        if ' "' in raw_value:
            raw_value, suffix = raw_value.split(' "', 1)
            suffix = f' "{suffix}'
        replaced = replacements.get(raw_value.strip(), raw_value.strip())
        return match.group(0).replace(match.group(1), f'{replaced}{suffix}')

    def replace_html(match):
        url_value = match.group(1).strip()
        return match.group(0).replace(match.group(1), replacements.get(url_value, url_value))

    markdown_pattern = re.compile(r'!\[[^\]]*]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)')
    html_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

    content = markdown_pattern.sub(replace_markdown, markdown_text or '')
    return html_pattern.sub(replace_html, content)


def _guess_extension(url, headers):
    parsed = urlparse(url)
    _, ext = os.path.splitext(parsed.path or '')
    if ext and len(ext) <= 8:
        return ext.lower()

    content_type = (headers.get_content_type() or '').lower()
    guessed = mimetypes.guess_extension(content_type or '')
    if guessed:
        return guessed
    return '.jpg'


def _download_remote_image(url):
    fetched_url, content, headers = fetch_remote_image(url)
    content_type = (headers.get_content_type() or '').lower()
    if not content_type.startswith('image/'):
        raise CrawlError('目标资源不是图片')

    ext = _guess_extension(fetched_url, headers)
    filename = f'crawler{ext}'
    file_obj = BytesIO(content)
    storage = FileStorage(stream=file_obj, filename=filename, content_type=content_type)
    uploaded_url = upload_media_file(storage)
    return force_https_url(uploaded_url)


def fetch_remote_image(url):
    fetched_url, content, headers = _fetch_bytes(url, max_bytes=MAX_IMAGE_BYTES, accept_html=False)
    content_type = (headers.get_content_type() or '').lower()
    if not content_type.startswith('image/'):
        raise CrawlError('目标资源不是图片')
    return fetched_url, content, headers


def _unique_urls(urls):
    seen = set()
    for item in urls:
        normalized = str(item or '').strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        yield normalized


def finalize_crawled_content(markdown_text, image_mode='remote', cover_url=''):
    content = str(markdown_text or '')
    cover_value = str(cover_url or '').strip()
    warnings = []

    if image_mode != 'download_local':
        return {
            'markdown': content,
            'cover': cover_value,
            'warnings': warnings,
        }

    remote_urls = list(_unique_urls([*list(_iter_markdown_image_urls(content)), cover_value]))
    replacements = {}
    for remote_url in remote_urls:
        parsed = urlparse(remote_url)
        if parsed.scheme not in {'http', 'https'}:
            continue
        try:
            replacements[remote_url] = _download_remote_image(remote_url)
        except Exception as exc:
            warnings.append(f'图片下载失败，已保留原地址：{remote_url}（{exc}）')

    return {
        'markdown': _replace_markdown_image_urls(content, replacements),
        'cover': replacements.get(cover_value, cover_value),
        'warnings': warnings,
    }
