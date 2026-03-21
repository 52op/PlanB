import hashlib
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app, url_for

from models import CoverFallbackCache, SystemSetting, db

ALLOWED_COVER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'}
DEFAULT_PEXELS_QUERY = 'nature'
DEFAULT_PEXELS_ORIENTATION = 'landscape'
DEFAULT_PEXELS_PER_PAGE = 6
DEFAULT_PEXELS_CACHE_HOURS = 24


def _parse_pexels_default_queries(value):
    raw_value = str(value or '').strip()
    if not raw_value:
        return [DEFAULT_PEXELS_QUERY]

    normalized = raw_value.replace('，', ',').replace(';', ',').replace('；', ',').replace('\n', ',')
    items = []
    for item in normalized.split(','):
        query = str(item or '').strip()
        if query and query not in items:
            items.append(query)
    return items or [DEFAULT_PEXELS_QUERY]


def _normalize_source_type(value):
    raw_value = str(value or '').strip().lower()
    return raw_value if raw_value in {'url', 'local_dir', 'pexels'} else 'url'


def _normalize_orientation(value):
    raw_value = str(value or '').strip().lower()
    return raw_value if raw_value in {'landscape', 'portrait', 'square'} else DEFAULT_PEXELS_ORIENTATION


def _parse_positive_int(value, default, minimum=1, maximum=None):
    try:
        parsed = int(str(value or '').strip())
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _coerce_tag_query(tags):
    if isinstance(tags, (list, tuple)):
        for tag in tags:
            tag_value = str(tag or '').strip()
            if tag_value:
                return tag_value
    tag_value = str(tags or '').strip()
    return tag_value


def _build_stable_seed(item):
    if not isinstance(item, dict):
        return 'cover-fallback'
    for key in ('slug', 'filename', 'url', 'title'):
        value = str(item.get(key) or '').strip()
        if value:
            return value
    return 'cover-fallback'


def build_stable_cover_index(seed, total):
    if total <= 0:
        return 0
    digest = hashlib.sha256(str(seed or 'cover-fallback').encode('utf-8')).hexdigest()
    return int(digest[:16], 16) % total


def get_cover_fallback_settings(site_settings=None):
    settings = dict(site_settings or {})
    source_type_setting = (
        settings.get('random_cover_source_type')
        if 'random_cover_source_type' in settings
        else SystemSetting.get('random_cover_source_type', 'url')
    )
    source_type = _normalize_source_type(source_type_setting)
    random_cover_api = str(
        settings.get('random_cover_api') if 'random_cover_api' in settings else SystemSetting.get('random_cover_api', '')
    ).strip()
    random_cover_local_dir = str(
        settings.get('random_cover_local_dir') if 'random_cover_local_dir' in settings else SystemSetting.get('random_cover_local_dir', '')
    ).strip()
    random_cover_pexels_api_key = str(
        settings.get('random_cover_pexels_api_key') if 'random_cover_pexels_api_key' in settings else SystemSetting.get('random_cover_pexels_api_key', '')
    ).strip()
    random_cover_pexels_default_query = str(
        settings.get('random_cover_pexels_default_query')
        if 'random_cover_pexels_default_query' in settings
        else SystemSetting.get('random_cover_pexels_default_query', DEFAULT_PEXELS_QUERY)
    ).strip() or DEFAULT_PEXELS_QUERY

    # 兼容旧版本：仅当数据库和传入上下文都没有来源类型时，才退回到 URL 模式。
    if not str(source_type_setting or '').strip() and random_cover_api:
        source_type = 'url'

    return {
        'random_cover_source_type': source_type,
        'random_cover_api': random_cover_api,
        'random_cover_local_dir': random_cover_local_dir,
        'random_cover_pexels_api_key': random_cover_pexels_api_key,
        'random_cover_pexels_default_query': random_cover_pexels_default_query,
        'random_cover_pexels_default_queries': _parse_pexels_default_queries(random_cover_pexels_default_query),
        'random_cover_pexels_orientation': _normalize_orientation(
            settings.get('random_cover_pexels_orientation')
            if 'random_cover_pexels_orientation' in settings
            else SystemSetting.get('random_cover_pexels_orientation', DEFAULT_PEXELS_ORIENTATION)
        ),
        'random_cover_pexels_per_page': _parse_positive_int(
            settings.get('random_cover_pexels_per_page')
            if 'random_cover_pexels_per_page' in settings
            else SystemSetting.get('random_cover_pexels_per_page', str(DEFAULT_PEXELS_PER_PAGE)),
            DEFAULT_PEXELS_PER_PAGE,
            minimum=1,
            maximum=20,
        ),
        'random_cover_pexels_cache_hours': _parse_positive_int(
            settings.get('random_cover_pexels_cache_hours')
            if 'random_cover_pexels_cache_hours' in settings
            else SystemSetting.get('random_cover_pexels_cache_hours', str(DEFAULT_PEXELS_CACHE_HOURS)),
            DEFAULT_PEXELS_CACHE_HOURS,
            minimum=1,
            maximum=168,
        ),
    }


def _resolve_local_cover_directory(raw_dir):
    directory_value = str(raw_dir or '').strip()
    if not directory_value:
        return ''
    expanded_dir = os.path.expandvars(os.path.expanduser(directory_value))
    if not os.path.isabs(expanded_dir):
        expanded_dir = os.path.join(current_app.root_path, expanded_dir)
    absolute_dir = os.path.abspath(expanded_dir)
    return absolute_dir if os.path.isdir(absolute_dir) else ''


def get_local_cover_base_dir(site_settings=None):
    settings = get_cover_fallback_settings(site_settings)
    return _resolve_local_cover_directory(settings.get('random_cover_local_dir'))


def list_local_cover_files(local_dir):
    absolute_dir = _resolve_local_cover_directory(local_dir)
    if not absolute_dir:
        return []

    files = []
    for root, _, filenames in os.walk(absolute_dir):
        for filename in filenames:
            extension = os.path.splitext(filename)[1].lower()
            if extension not in ALLOWED_COVER_EXTENSIONS:
                continue
            absolute_path = os.path.join(root, filename)
            relative_path = os.path.relpath(absolute_path, absolute_dir).replace('\\', '/')
            files.append(relative_path)
    files.sort(key=lambda item: item.lower())
    return files


def _build_local_cover_url(relative_path):
    normalized_path = str(relative_path or '').replace('\\', '/').lstrip('/')
    if not normalized_path:
        return ''
    return url_for('main.local_cover_file', filename=normalized_path)


def _select_stable_candidate(candidates, seed):
    if not candidates:
        return ''
    return candidates[build_stable_cover_index(seed, len(candidates))]


def _get_cache_record(provider, cache_key):
    now = datetime.utcnow()
    record = CoverFallbackCache.query.filter_by(provider=provider, cache_key=cache_key).first()
    if not record:
        return None
    if record.expires_at <= now:
        db.session.delete(record)
        db.session.commit()
        return None
    return record


def _set_cache_record(provider, cache_key, payload, ttl_hours):
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    record = CoverFallbackCache.query.filter_by(provider=provider, cache_key=cache_key).first()
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    if record:
        record.payload = serialized_payload
        record.expires_at = expires_at
    else:
        record = CoverFallbackCache(
            provider=provider,
            cache_key=cache_key,
            payload=serialized_payload,
            expires_at=expires_at,
        )
        db.session.add(record)
    db.session.commit()


def _fetch_pexels_cover_candidates(query, settings):
    query_value = str(query or '').strip()
    api_key = str(settings.get('random_cover_pexels_api_key') or '').strip()
    if not query_value or not api_key:
        return []

    orientation = settings.get('random_cover_pexels_orientation') or DEFAULT_PEXELS_ORIENTATION
    per_page = settings.get('random_cover_pexels_per_page') or DEFAULT_PEXELS_PER_PAGE
    cache_hours = settings.get('random_cover_pexels_cache_hours') or DEFAULT_PEXELS_CACHE_HOURS
    cache_key_seed = f'{query_value}|{orientation}|{per_page}'
    cache_key = hashlib.sha256(cache_key_seed.encode('utf-8')).hexdigest()

    cached = _get_cache_record('pexels', cache_key)
    if cached:
        try:
            payload = json.loads(cached.payload)
            if isinstance(payload, list):
                return payload
        except (TypeError, ValueError):
            pass

    request_url = (
        'https://api.pexels.com/v1/search'
        f'?query={quote(query_value)}'
        f'&per_page={per_page}'
        f'&orientation={quote(str(orientation))}'
    )
    request_obj = Request(
        request_url,
        headers={
            'Authorization': api_key,
            'Accept': 'application/json',
            'User-Agent': 'planning-cover-fallback/1.0',
        },
    )

    try:
        with urlopen(request_obj, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        current_app.logger.warning('Pexels 封面拉取失败: %s', exc)
        return []

    photos = payload.get('photos') if isinstance(payload, dict) else []
    candidates = []
    for photo in photos or []:
        if not isinstance(photo, dict):
            continue
        src = photo.get('src') if isinstance(photo.get('src'), dict) else {}
        image_url = (
            src.get('landscape')
            or src.get('large')
            or src.get('large2x')
            or src.get('medium')
            or src.get('original')
            or ''
        )
        image_url = str(image_url or '').strip()
        if image_url:
            candidates.append(image_url)

    if candidates:
        _set_cache_record('pexels', cache_key, candidates, cache_hours)
    return candidates


def _resolve_local_dir_cover(item, settings):
    local_dir = settings.get('random_cover_local_dir')
    candidates = list_local_cover_files(local_dir)
    selected = _select_stable_candidate(candidates, _build_stable_seed(item))
    return _build_local_cover_url(selected) if selected else ''


def _resolve_pexels_cover(item, settings):
    query_value, _ = resolve_pexels_query(item, settings)
    candidates = _fetch_pexels_cover_candidates(query_value, settings)
    return _select_stable_candidate(candidates, f"{_build_stable_seed(item)}|{query_value}")


def resolve_pexels_query(item_metadata, settings=None):
    item = dict(item_metadata or {})
    resolved_settings = get_cover_fallback_settings(settings)
    tag_query = _coerce_tag_query(item.get('tags'))
    if tag_query:
        return tag_query, 'tag'

    default_queries = resolved_settings.get('random_cover_pexels_default_queries') or [DEFAULT_PEXELS_QUERY]
    seed = _build_stable_seed(item)
    selected_query = _select_stable_candidate(default_queries, f'{seed}|default-pexels-query')
    return selected_query or DEFAULT_PEXELS_QUERY, 'default'


def preview_cover_source(settings=None, sample_query=''):
    resolved_settings = get_cover_fallback_settings(settings)
    sample_query = str(sample_query or '').strip()
    sample_item = {
        'slug': 'admin-cover-preview',
        'filename': 'admin-cover-preview.md',
        'title': 'Admin Cover Preview',
        'tags': [sample_query] if sample_query else [],
        'cover': '',
    }
    source_type = resolved_settings.get('random_cover_source_type') or 'url'

    if source_type == 'url':
        selected_url = str(resolved_settings.get('random_cover_api') or '').strip()
        return {
            'source_type': 'url',
            'selected_url': selected_url,
            'candidates': [selected_url] if selected_url else [],
            'count': 1 if selected_url else 0,
            'message': '当前将直接使用远程封面地址作为兜底图。' if selected_url else '当前还没有填写可用的远程封面地址。',
        }

    if source_type == 'local_dir':
        base_dir = get_local_cover_base_dir(resolved_settings)
        local_files = list_local_cover_files(resolved_settings.get('random_cover_local_dir'))
        preview_files = local_files[:4]
        return {
            'source_type': 'local_dir',
            'selected_url': resolve_fallback_cover(sample_item, resolved_settings),
            'candidates': [_build_local_cover_url(path) for path in preview_files],
            'count': len(local_files),
            'directory': base_dir,
            'message': (
                '当前本地目录不存在或不可访问，请检查路径是否填写正确。'
                if not base_dir else
                f'检测到 {len(local_files)} 张可用图片，当前预览按稳定规则选中其中一张。'
                if local_files else
                '当前目录下没有找到可用图片，支持 jpg / jpeg / png / webp / gif / avif。'
            ),
        }

    query_value, query_source = resolve_pexels_query(sample_item, resolved_settings)
    candidates = _fetch_pexels_cover_candidates(query_value, resolved_settings)
    preview_candidates = candidates[:4]
    selected_url = _select_stable_candidate(candidates, f"{_build_stable_seed(sample_item)}|{query_value}") if candidates else ''
    query_label = '测试关键词' if sample_query else ('默认关键词池' if query_source == 'default' else '文章标签')
    return {
        'source_type': 'pexels',
        'selected_url': selected_url,
        'candidates': preview_candidates,
        'count': len(candidates),
        'query': query_value,
        'query_source': query_source,
        'message': (
            '当前还没有填写 Pexels API Key，无法拉取候选封面图。'
            if not str(resolved_settings.get('random_cover_pexels_api_key') or '').strip() else
            f'当前使用 {query_label} “{query_value}” 获取封面候选图。'
            if query_value else
            '当前没有可用的查询关键词。'
        ),
    }


def resolve_fallback_cover(item_metadata, site_settings=None):
    item = dict(item_metadata or {})
    raw_cover = str(item.get('cover') or '').strip()
    normalized_cover = raw_cover.lower()
    if normalized_cover == '__none__':
        return ''
    if raw_cover and normalized_cover not in {'none', 'false'}:
        return raw_cover

    settings = get_cover_fallback_settings(site_settings)
    source_type = settings.get('random_cover_source_type') or 'url'
    if source_type == 'local_dir':
        return _resolve_local_dir_cover(item, settings)
    if source_type == 'pexels':
        return _resolve_pexels_cover(item, settings)
    return str(settings.get('random_cover_api') or '').strip()
