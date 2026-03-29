import math
import os
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import quote
from functools import lru_cache

import bleach
import markdown
import markdown.extensions.codehilite
import markdown.extensions.fenced_code
import yaml
from bleach.css_sanitizer import CSSSanitizer
from flask import abort
from flask_login import current_user
from pypinyin import Style, lazy_pinyin

from models import DirectoryConfig, DocumentViewStat
from .access import has_password_rule_access
from .paths import InvalidPathError, get_docs_root, normalize_relative_path, resolve_docs_path
from .permissions import check_permission, has_explicit_permission
from .urls import normalize_local_media_references_in_text, normalize_local_media_url


# 文件缓存：缓存文件的修改时间和解析结果
_FILE_CACHE = {}

def _get_file_mtime(filepath):
    """获取文件修改时间"""
    try:
        return os.path.getmtime(filepath)
    except (OSError, IOError):
        return 0


ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union({
    'p', 'pre', 'code', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'thead', 'tbody',
    'tr', 'th', 'td', 'blockquote', 'hr', 'br', 'span', 'div', 'img', 'ul', 'ol', 'li'
})
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
}
ALLOWED_PROTOCOLS = set(bleach.sanitizer.ALLOWED_PROTOCOLS).union({'data'})
CSS_SANITIZER = CSSSanitizer(allowed_css_properties=['width', 'height', 'max-width'])
FRONT_MATTER_BOUNDARY = '---'
WORD_RE = re.compile(r'\w+', re.UNICODE)
SLUG_BASE_MAX_LENGTH = 60
SLUG_MAX_LENGTH = 64


def _sanitize_html(html):
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=CSS_SANITIZER,
        strip=True,
    )


def _is_admin_user(user):
    return bool(getattr(user, 'is_authenticated', False) and getattr(user, 'role', '') == 'admin')


def _has_read_permission(path_value):
    return check_permission(current_user, path_value, 'read')


def _can_access_document_metadata(filename, metadata, user=None, allow_password_access=False):
    active_user = user or current_user
    if _is_admin_user(active_user):
        return True

    if not check_permission(active_user, filename, 'read'):
        return False

    password_rule_access = bool(allow_password_access and user is None and has_password_rule_access(filename))

    normalized_template = _normalize_template(metadata.get('template'))
    is_public = _normalize_bool(metadata.get('public'), default=False)
    if is_public:
        return True
    if password_rule_access:
        return True

    if normalized_template == 'post':
        return bool(getattr(active_user, 'is_authenticated', False))

    return has_explicit_permission(active_user, filename, 'read')


def _normalize_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off'}:
            return False
    return default


def _normalize_tags(value):
    if value is None:
        return []
    if isinstance(value, str):
        items = [item.strip() for item in value.split(',')]
    elif isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
    else:
        text = str(value).strip()
        items = [text] if text else []
    return [item for item in items if item]


def _normalize_template(value):
    template = str(value or 'doc').strip().lower()
    if template not in {'doc', 'post'}:
        return 'doc'
    return template


def _normalize_date_value(value):
    if value is None or value == '':
        return '', ''
    if isinstance(value, datetime):
        date_value = value.date()
        return date_value.isoformat(), date_value.strftime('%Y-%m-%d')
    if isinstance(value, date):
        return value.isoformat(), value.strftime('%Y-%m-%d')

    text = str(value).strip()
    if not text:
        return '', ''

    parsed = None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue

    if parsed is not None:
        date_value = parsed.date()
        return date_value.isoformat(), date_value.strftime('%Y-%m-%d')
    return text, text


def _split_front_matter(content):
    if not content.startswith(FRONT_MATTER_BOUNDARY):
        return {}, content

    lines = content.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_BOUNDARY:
        return {}, content

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_BOUNDARY:
            end_index = index
            break

    if end_index is None:
        return {}, content

    front_matter_text = '\n'.join(lines[1:end_index])
    body = '\n'.join(lines[end_index + 1:])
    if content.endswith('\n'):
        body += '\n'

    try:
        parsed = yaml.safe_load(front_matter_text) or {}
    except yaml.YAMLError:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, body


def _has_front_matter_block(content):
    text = str(content or '')
    if not text.startswith(FRONT_MATTER_BOUNDARY):
        return False

    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_BOUNDARY:
        return False

    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_BOUNDARY:
            return True
    return False


def _estimate_reading_minutes(content):
    word_count = len(WORD_RE.findall(content or ''))
    if word_count <= 0:
        return 1
    return max(1, int(math.ceil(word_count / 200.0)))


def _format_category_name(category_path):
    if not category_path:
        return ''
    name = os.path.basename(category_path.rstrip('/'))
    return name.replace('-', ' ').replace('_', ' ').strip()


def _normalize_slug_source(value):
    text = str(value or '').strip().lower()
    normalized = unicodedata.normalize('NFKD', text)
    slug_source = ''.join(char for char in normalized if not unicodedata.combining(char))
    slug_source = '-'.join(
        token for token in lazy_pinyin(
            slug_source,
            style=Style.NORMAL,
            errors=lambda item: [item],
            neutral_tone_with_five=True,
        ) if str(token or '').strip()
    )
    slug = re.sub(r'[^\w\u4e00-\u9fff-]+', '-', slug_source, flags=re.UNICODE)
    return re.sub(r'-{2,}', '-', slug).strip('-_')


def _truncate_slug(slug, max_length=SLUG_BASE_MAX_LENGTH):
    normalized_slug = re.sub(r'-{2,}', '-', str(slug or '').strip('-_'))
    if not normalized_slug:
        return 'post'
    if max_length is None or max_length <= 0 or len(normalized_slug) <= max_length:
        return normalized_slug

    parts = [part for part in normalized_slug.split('-') if part]
    if not parts:
        return (normalized_slug[:max_length] or 'post').strip('-_') or 'post'

    truncated_parts = []
    current_length = 0
    for part in parts:
        separator_length = 1 if truncated_parts else 0
        next_length = current_length + separator_length + len(part)
        if next_length > max_length:
            break
        truncated_parts.append(part)
        current_length = next_length

    if truncated_parts:
        return '-'.join(truncated_parts)

    return (normalized_slug[:max_length] or 'post').strip('-_') or 'post'


def _slugify(value, max_length=SLUG_BASE_MAX_LENGTH):
    slug = _normalize_slug_source(value)
    slug = _truncate_slug(slug, max_length=max_length)
    return slug or 'post'


def _append_slug_suffix(base_slug, suffix, max_length=SLUG_MAX_LENGTH):
    suffix_text = f'-{suffix}'
    base_limit = max(1, max_length - len(suffix_text))
    limited_base = _truncate_slug(base_slug, max_length=base_limit) or 'post'
    return f'{limited_base}{suffix_text}'


def _build_markdown_url(filename):
    return '/docs/doc/{0}'.format(quote(filename.replace('\\', '/')))


def _find_post_slug_conflicts(slug, exclude_filename=''):
    normalized_slug = _slugify(slug)
    if not normalized_slug:
        return []

    normalized_exclude = ''
    if exclude_filename:
        try:
            normalized_exclude = normalize_relative_path(exclude_filename)
        except InvalidPathError:
            normalized_exclude = str(exclude_filename).replace('\\', '/').strip('/')

    conflicts = []
    for filename in _iter_markdown_filenames():
        try:
            normalized_filename = normalize_relative_path(filename)
        except InvalidPathError:
            normalized_filename = str(filename).replace('\\', '/').strip('/')

        if normalized_exclude and normalized_filename == normalized_exclude:
            continue

        payload = _parse_markdown_file(normalized_filename)
        if not payload:
            continue

        metadata = payload.get('metadata') or {}
        if _normalize_template(metadata.get('template')) != 'post':
            continue

        target_slug = str(metadata.get('slug') or '').strip().lower()
        if target_slug != normalized_slug:
            continue

        is_visible = _can_access_document_metadata(normalized_filename, metadata)
        conflicts.append({
            'filename': normalized_filename,
            'title': metadata.get('title') if is_visible else '其他文章',
            'public': bool(metadata.get('public')),
            'visible': bool(is_visible),
        })

    conflicts.sort(key=lambda item: item.get('filename') or '')
    return conflicts


def _suggest_unique_post_slug(slug, exclude_filename=''):
    base_slug = _slugify(slug) or 'post'
    if not _find_post_slug_conflicts(base_slug, exclude_filename=exclude_filename):
        return base_slug

    suffix = 1
    while True:
        candidate = _append_slug_suffix(base_slug, suffix)
        if not _find_post_slug_conflicts(candidate, exclude_filename=exclude_filename):
            return candidate
        suffix += 1


def _ensure_unique_post_slug(slug, filename):
    normalized_slug = _slugify(slug) or 'post'
    conflicts = _find_post_slug_conflicts(normalized_slug, exclude_filename=filename)
    if conflicts:
        raise ValueError(f'Slug "{normalized_slug}" 已被其他文章使用，请修改后重试')
    return normalized_slug


def _normalize_metadata(filename, raw_metadata, raw_content):
    filename = normalize_relative_path(filename)
    directory = os.path.dirname(filename).replace('\\', '/')
    basename = os.path.basename(filename)
    slug = _slugify(os.path.splitext(basename)[0])
    date_value, date_display = _normalize_date_value(raw_metadata.get('date'))
    category = normalize_relative_path(raw_metadata.get('category') or directory)
    title = str(raw_metadata.get('title') or os.path.splitext(basename)[0].replace('-', ' ').replace('_', ' ').strip() or basename)
    summary = str(raw_metadata.get('summary') or '').strip()
    if not summary:
        plain_text = re.sub(r'[#>*`_\-]+', ' ', raw_content)
        plain_text = re.sub(r'!\[.*?\]\((.*?)\)', ' ', plain_text)
        plain_text = re.sub(r'<[^>]+>', ' ', plain_text)
        plain_text = re.sub(r'\s+', ' ', plain_text).strip()
        summary = plain_text[:120] + ('...' if len(plain_text) > 120 else '')
    metadata = {
        'title': title,
        'summary': summary,
        'tags': _normalize_tags(raw_metadata.get('tags')),
        'cover': normalize_local_media_url(str(raw_metadata.get('cover') or '').strip()),
        'template': _normalize_template(raw_metadata.get('template')),
        'public': _normalize_bool(raw_metadata.get('public'), default=False),
        'draft': _normalize_bool(raw_metadata.get('draft'), default=False),
        'date': date_value,
        'date_display': str(raw_metadata.get('date_display') or date_display).strip(),
        'updated': _normalize_date_value(raw_metadata.get('updated'))[0],
        'updated_display': _normalize_date_value(raw_metadata.get('updated'))[1],
        'category': category,
        'category_path': category,
        'category_name': str(raw_metadata.get('category_name') or _format_category_name(category)).strip(),
        'filename': filename,
        'slug': _slugify(raw_metadata.get('slug') or slug),
        'url': '',
        'reading_minutes': _estimate_reading_minutes(raw_content),
    }
    metadata['url'] = str(
        raw_metadata.get('url')
        or (
            f"/post/{quote(metadata['slug'])}"
            if metadata['template'] == 'post'
            else _build_markdown_url(filename)
        )
    ).strip()
    return metadata


def _render_markdown(content):
    md = markdown.Markdown(extensions=['fenced_code', 'codehilite', 'tables', 'toc'])
    html = _sanitize_html(md.convert(content))
    toc_html = _sanitize_html(getattr(md, 'toc', ''))
    return html, toc_html


def _attach_view_counts(items):
    if not items:
        return items
    filename_map = {item.get('filename'): item for item in items if item.get('filename')}
    if not filename_map:
        return items
    stats = DocumentViewStat.query.filter(DocumentViewStat.filename.in_(list(filename_map.keys()))).all()
    for stat in stats:
        target = filename_map.get(stat.filename)
        if target is not None:
            target['view_count'] = int(stat.view_count or 0)
    return items


def _iter_markdown_filenames():
    docs_root = get_docs_root()
    filenames = []
    for root, dirnames, files in os.walk(docs_root):
        dirnames.sort()
        files.sort()
        rel_dir = os.path.relpath(root, docs_root).replace('\\', '/')
        if rel_dir == '.':
            rel_dir = ''
        for filename in files:
            if not filename.lower().endswith('.md'):
                continue
            rel_path = os.path.join(rel_dir, filename).replace('\\', '/') if rel_dir else filename
            filenames.append(rel_path)
    filenames.sort()
    return filenames


def _parse_markdown_file(filename):
    try:
        _, normalized_filename, filepath = resolve_docs_path(filename)
    except InvalidPathError:
        return None

    if not normalized_filename.endswith('.md'):
        return None
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return None

    # 检查缓存
    current_mtime = _get_file_mtime(filepath)
    cache_key = normalized_filename
    if cache_key in _FILE_CACHE:
        cached_mtime, cached_result = _FILE_CACHE[cache_key]
        if cached_mtime == current_mtime:
            # 缓存命中，直接返回
            return cached_result

    # 缓存未命中，读取并解析文件
    with open(filepath, 'r', encoding='utf-8') as file_obj:
        full_content = file_obj.read()

    raw_metadata, raw_content = _split_front_matter(full_content)
    raw_content = normalize_local_media_references_in_text(raw_content)
    metadata = _normalize_metadata(normalized_filename, raw_metadata, raw_content)
    html, toc_html = _render_markdown(raw_content)

    result = {
        'html': html,
        'toc': toc_html,
        'metadata': metadata,
        'raw_content': raw_content,
        'filename': normalized_filename,
        'has_front_matter': _has_front_matter_block(full_content),
    }

    # 存入缓存
    _FILE_CACHE[cache_key] = (current_mtime, result)

    return result


def _is_visible_post(metadata, include_private=False):
    if metadata.get('template') != 'post':
        return False
    if metadata.get('draft') and not _is_admin_user(current_user):
        return False
    if not include_private and not metadata.get('public') and not _is_admin_user(current_user):
        return False
    return True


def _extract_first_heading(content):
    match = re.search(r'^#\s+(.+)$', content or '', re.MULTILINE)
    return match.group(1).strip() if match else ''


def _extract_first_image(content):
    markdown_match = re.search(r'!\[[^\]]*\]\(([^)\s]+)', content or '')
    if markdown_match:
        return markdown_match.group(1).strip()
    html_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content or '', re.IGNORECASE)
    if html_match:
        return html_match.group(1).strip()
    return ''


def _build_front_matter(raw_metadata, body_content, filename):
    file_slug = _slugify(os.path.splitext(os.path.basename(filename))[0])
    heading_title = _extract_first_heading(body_content)
    summary = str(raw_metadata.get('summary') or '').strip()
    if not summary:
        plain_text = re.sub(r'[#>*`_\-]+', ' ', body_content)
        plain_text = re.sub(r'!\[.*?\]\((.*?)\)', ' ', plain_text)
        plain_text = re.sub(r'<[^>]+>', ' ', plain_text)
        plain_text = re.sub(r'\s+', ' ', plain_text).strip()
        summary = plain_text[:140] + ('...' if len(plain_text) > 140 else '')

    metadata = dict(raw_metadata)
    metadata['title'] = str(raw_metadata.get('title') or heading_title or file_slug.replace('-', ' ').replace('_', ' ')).strip()
    metadata['summary'] = summary
    
    # 保留原始的 cover 值
    # 支持 'none' 或 'false' 或 '__NONE__' 表示明确不要封面
    if 'cover' in raw_metadata:
        cover_value = str(raw_metadata.get('cover') or '').strip().lower()
        if cover_value in ('none', 'false', '__none__', ''):
            # 用户明确不要封面，使用特殊标记 __NONE__（不会被 yaml.safe_dump 过滤）
            metadata['cover'] = '__NONE__'
        else:
            # 用户设置了具体的封面 URL
            metadata['cover'] = normalize_local_media_url(str(raw_metadata.get('cover')).strip())
    else:
        # cover 字段不存在，尝试自动提取
        metadata['cover'] = normalize_local_media_url(str(_extract_first_image(body_content) or '').strip())
    
    metadata['slug'] = _slugify(raw_metadata.get('slug') or file_slug)
    metadata['updated'] = datetime.now().strftime('%Y-%m-%d')
    
    # 保留原始的 template 值，如果存在的话
    if 'template' in raw_metadata and raw_metadata['template']:
        metadata['template'] = _normalize_template(raw_metadata.get('template'))
    elif 'template' not in metadata:
        metadata['template'] = 'doc'
    
    # 保留原始的 public 值，如果存在的话
    if 'public' in raw_metadata:
        metadata['public'] = _normalize_bool(raw_metadata.get('public'), default=False)
    elif 'public' not in metadata:
        metadata['public'] = False
    
    # 保留原始的 draft 值
    if 'draft' in raw_metadata:
        metadata['draft'] = _normalize_bool(raw_metadata.get('draft'), default=False)
    elif 'draft' not in metadata:
        metadata['draft'] = False
    
    # 保留原始的 date 值，如果存在的话
    if 'date' in raw_metadata and raw_metadata['date']:
        metadata['date'] = raw_metadata['date']
    elif raw_metadata.get('date') in (None, '') and metadata.get('template') == 'post':
        metadata['date'] = datetime.now().strftime('%Y-%m-%d')

    if metadata.get('template') == 'post':
        metadata['slug'] = _ensure_unique_post_slug(metadata.get('slug') or file_slug, filename)

    ordered = [
        ('title', metadata.get('title')),
        ('date', metadata.get('date')),
        ('updated', metadata.get('updated')),
        ('summary', metadata.get('summary')),
        ('tags', _normalize_tags(metadata.get('tags'))),
        ('cover', metadata.get('cover')),
        ('template', metadata.get('template')),
        ('public', metadata.get('public')),
        ('draft', metadata.get('draft')),
        ('slug', metadata.get('slug')),
    ]

    front_matter = yaml.safe_dump({key: value for key, value in ordered if value not in (None, '', [])}, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{front_matter}\n---\n\n{body_content.lstrip()}"


def sync_front_matter(content, filename, ensure_front_matter=False):
    raw_metadata, body_content = _split_front_matter(content)
    has_front_matter = bool(raw_metadata) or content.startswith(FRONT_MATTER_BOUNDARY)
    if not has_front_matter and not ensure_front_matter:
        return content
    return _build_front_matter(raw_metadata, body_content, filename)


def _sort_posts(posts):
    return sorted(
        posts,
        key=lambda item: (
            item.get('date') or '',
            item.get('filename') or '',
        ),
        reverse=True,
    )


def get_markdown_files():
    docs_root = get_docs_root()

    def build_tree(current_rel_path=''):
        tree = []
        current_dir = docs_root if not current_rel_path else resolve_docs_path(current_rel_path, allow_directory=True)[2]
        items = sorted(os.listdir(current_dir))

        for item in items:
            item_path = os.path.join(current_dir, item)
            item_rel_path = os.path.join(current_rel_path, item).replace('\\', '/') if current_rel_path else item

            if os.path.isdir(item_path):
                if not _has_read_permission(item_rel_path):
                    continue
                children = build_tree(item_rel_path)
                if not children and not check_permission(current_user, item_rel_path, 'upload'):
                    continue
                tree.append({
                    'type': 'dir',
                    'name': item,
                    'path': item_rel_path,
                    'children': children,
                })
            elif os.path.isfile(item_path) and item.lower().endswith('.md'):
                if not _has_read_permission(item_rel_path):
                    continue
                payload = _parse_markdown_file(item_rel_path)
                if not payload:
                    continue
                if not _can_access_document_metadata(item_rel_path, payload.get('metadata') or {}, allow_password_access=True):
                    continue
                tree.append({
                    'type': 'file',
                    'name': item,
                    'path': item_rel_path,
                })
        return tree

    return build_tree()


def get_flat_files_list(tree):
    flat_list = []
    for node in tree:
        if node['type'] == 'file':
            flat_list.append(node['path'])
        elif node['type'] == 'dir':
            flat_list.extend(get_flat_files_list(node['children']))
    return flat_list


def get_default_file_for_dir(docs_root, relative_dir_path=''):
    del docs_root
    relative_dir_path = normalize_relative_path(relative_dir_path)
    _, relative_dir_path, abs_dir_path = resolve_docs_path(relative_dir_path, allow_directory=True)

    if not os.path.exists(abs_dir_path) or not os.path.isdir(abs_dir_path):
        return None
    if relative_dir_path and not _has_read_permission(relative_dir_path):
        return None

    dir_config = DirectoryConfig.query.filter_by(dir_path=relative_dir_path or '/').first()
    md_files = [
        filename for filename in os.listdir(abs_dir_path)
        if os.path.isfile(os.path.join(abs_dir_path, filename)) and filename.lower().endswith('.md')
    ]
    md_files = [
        filename for filename in md_files
        if _has_read_permission(os.path.join(relative_dir_path, filename).replace('\\', '/').lstrip('/'))
    ]
    visible_md_files = []
    for filename in md_files:
        relative_filename = os.path.join(relative_dir_path, filename).replace('\\', '/').lstrip('/')
        payload = _parse_markdown_file(relative_filename)
        if not payload:
            continue
        if not _can_access_document_metadata(relative_filename, payload.get('metadata') or {}, allow_password_access=True):
            continue
        visible_md_files.append(filename)
    md_files = visible_md_files
    if not md_files:
        return None

    if dir_config:
        if dir_config.default_open_file and dir_config.default_open_file in md_files:
            return os.path.join(relative_dir_path, dir_config.default_open_file).replace('\\', '/').lstrip('/')

        sort_rule = dir_config.sort_rule or 'asc'
        md_files.sort(reverse=(sort_rule == 'desc'))
        return os.path.join(relative_dir_path, md_files[0]).replace('\\', '/').lstrip('/')

    lower_files = {filename.lower(): filename for filename in md_files}
    if 'readme.md' in lower_files:
        return os.path.join(relative_dir_path, lower_files['readme.md']).replace('\\', '/').lstrip('/')
    if 'index.md' in lower_files:
        return os.path.join(relative_dir_path, lower_files['index.md']).replace('\\', '/').lstrip('/')

    md_files.sort()
    return os.path.join(relative_dir_path, md_files[0]).replace('\\', '/').lstrip('/')


def read_markdown_file(filename):
    payload = get_document_payload(filename)
    if payload is None:
        return None, None
    return payload['html'], payload['toc']


def get_document_payload(filename, allow_password_access=False):
    try:
        normalized_filename = normalize_relative_path(filename)
    except InvalidPathError:
        return None

    if not normalized_filename.endswith('.md'):
        return None
    if not _has_read_permission(normalized_filename):
        abort(403)

    payload = _parse_markdown_file(normalized_filename)
    if payload is None:
        return None
    if not _can_access_document_metadata(
        normalized_filename,
        payload.get('metadata') or {},
        allow_password_access=allow_password_access,
    ):
        abort(403)
    return payload


def get_posts(limit=None, category_path='', include_private=False):
    try:
        normalized_category = normalize_relative_path(category_path)
    except InvalidPathError:
        return []

    posts = []
    prefix = normalized_category.rstrip('/')
    for filename in _iter_markdown_filenames():
        if prefix and not (filename == prefix or filename.startswith(prefix + '/')):
            continue
        if not _has_read_permission(filename):
            continue
        payload = _parse_markdown_file(filename)
        if not payload:
            continue
        metadata = payload['metadata']
        if not _is_visible_post(metadata, include_private=include_private):
            continue
        posts.append(dict(metadata))

    posts = _sort_posts(posts)
    posts = _attach_view_counts(posts)
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None
        if limit is not None and limit >= 0:
            posts = posts[:limit]
    return posts


def get_public_post_documents():
    items = []
    filenames = []

    for filename in _iter_markdown_filenames():
        if not _has_read_permission(filename):
            continue

        payload = _parse_markdown_file(filename)
        if not payload:
            continue
        if not payload.get('has_front_matter'):
            continue

        metadata = payload.get('metadata') or {}
        if metadata.get('draft'):
            continue

        item = dict(metadata)
        item['path'] = filename
        item['doc_url'] = _build_markdown_url(filename)
        item['has_front_matter'] = True
        item['is_blog_visible'] = item.get('template') == 'post'
        item['can_edit'] = bool(check_permission(current_user, filename, 'edit'))
        item['timeline_date'] = item.get('updated') or item.get('date') or ''
        item['timeline_display'] = item.get('updated_display') or item.get('date_display') or '未设置日期'
        items.append(item)
        filenames.append(filename)

    if filenames:
        filename_map = {item.get('filename') or item.get('path'): item for item in items}
        stats = DocumentViewStat.query.filter(DocumentViewStat.filename.in_(filenames)).all()
        for stat in stats:
            target = filename_map.get(stat.filename)
            if target is not None:
                target['view_count'] = int(stat.view_count or 0)

    return _sort_posts(items)


def get_directory_articles(dirname='', include_private=False):
    try:
        normalized_dirname = normalize_relative_path(dirname)
    except InvalidPathError:
        return []

    posts = []
    prefix = normalized_dirname.rstrip('/')
    for filename in _iter_markdown_filenames():
        parent_dir = os.path.dirname(filename).replace('\\', '/')
        in_directory = parent_dir == prefix
        if prefix == '' and parent_dir != '':
            in_directory = False
        if not in_directory:
            continue
        if not _has_read_permission(filename):
            continue
        payload = _parse_markdown_file(filename)
        if not payload:
            continue
        metadata = payload['metadata']
        if not _is_visible_post(metadata, include_private=include_private):
            continue
        posts.append(dict(metadata))

    return _attach_view_counts(_sort_posts(posts))


def get_tag_posts(tag_name, include_private=False):
    target_tag = str(tag_name or '').strip().lower()
    if not target_tag:
        return []

    posts = []
    for post in get_posts(include_private=include_private):
        tags = [str(tag).strip().lower() for tag in post.get('tags', [])]
        if target_tag in tags:
            posts.append(post)
    return _attach_view_counts(_sort_posts(posts))


def get_all_tags(include_private=False):
    tag_map = {}
    posts = get_posts(include_private=include_private)

    for post in posts:
        latest_post = {
            'title': post.get('title') or '未命名文章',
            'url': post.get('url') or '',
            'date': post.get('date') or '',
            'date_display': post.get('date_display') or '',
            'updated': post.get('updated') or '',
            'updated_display': post.get('updated_display') or '',
            'summary': post.get('summary') or '',
            'cover': post.get('cover') or '',
        }

        for raw_tag in post.get('tags', []):
            normalized = str(raw_tag).strip()
            if not normalized:
                continue

            key = normalized.lower()
            entry = tag_map.setdefault(key, {
                'name': normalized,
                'count': 0,
                'latest_post': None,
            })
            entry['count'] += 1
            if entry['latest_post'] is None:
                entry['latest_post'] = dict(latest_post)

    tags = sorted(tag_map.values(), key=lambda item: (-item['count'], item['name'].lower()))
    if not tags:
        return []

    counts = [int(item.get('count') or 0) for item in tags]
    max_count = max(counts)
    min_count = min(counts)

    for index, entry in enumerate(tags, start=1):
        count = int(entry.get('count') or 0)
        if max_count == min_count:
            weight_ratio = 1.0
        else:
            weight_ratio = (count - min_count) / float(max_count - min_count)

        heat_level = min(5, max(1, int(round(weight_ratio * 4)) + 1))
        if heat_level >= 5:
            heat_label = '高热标签'
        elif heat_level == 4:
            heat_label = '热门标签'
        elif heat_level == 3:
            heat_label = '持续活跃'
        elif heat_level == 2:
            heat_label = '稳定更新'
        else:
            heat_label = '小众主题'

        entry['rank'] = index
        entry['weight_ratio'] = round(weight_ratio, 3)
        entry['heat_level'] = heat_level
        entry['font_scale'] = round(0.96 + weight_ratio * 0.42, 3)
        entry['heat_label'] = heat_label
        entry['description'] = f'已关联 {count} 篇文章'

    return tags


def get_archive_groups(include_private=False):
    groups = {}
    for post in get_posts(include_private=include_private):
        key = post.get('date', '')[:7] if post.get('date') else '未设置日期'
        if not key:
            key = '未设置日期'
        groups.setdefault(key, []).append(post)

    archive_groups = []
    for label, posts in sorted(groups.items(), key=lambda item: item[0], reverse=True):
        sorted_posts = _sort_posts(posts)
        year = ''
        month = ''
        month_label = label
        if re.match(r'^\d{4}-\d{2}$', label):
            year, month = label.split('-', 1)
            month_label = f'{int(month)} 月'

        archive_groups.append({
            'label': label,
            'posts': sorted_posts,
            'count': len(sorted_posts),
            'year': year,
            'month': month,
            'month_label': month_label,
            'range_label': f'{year} 年 {int(month)} 月' if year and month else label,
            'anchor': f"archive-{label.replace(' ', '-')}",
            'latest_post': sorted_posts[0] if sorted_posts else None,
        })

    return archive_groups


def get_adjacent_posts(filename, include_private=False):
    normalized_filename = normalize_relative_path(filename)
    posts = get_posts(include_private=include_private)
    current_index = -1

    for index, post in enumerate(posts):
        if post.get('filename') == normalized_filename:
            current_index = index
            break

    if current_index == -1:
        return None, None

    previous_post = posts[current_index - 1] if current_index > 0 else None
    next_post = posts[current_index + 1] if current_index < len(posts) - 1 else None
    return previous_post, next_post


def get_post_by_slug(slug, include_private=False):
    target_slug = str(slug or '').strip().lower()
    if not target_slug:
        return None

    hidden_match = None
    for filename in _iter_markdown_filenames():
        payload = _parse_markdown_file(filename)
        if not payload:
            continue
        metadata = payload['metadata']
        if str(metadata.get('slug') or '').strip().lower() != target_slug:
            continue
        if _is_visible_post(metadata, include_private=include_private):
            return payload
        if hidden_match is None:
            hidden_match = payload
    if include_private:
        return hidden_match
    return None


def get_public_post_tree(include_private=False):
    tree = []
    lookup = {}

    def ensure_dir(path_value):
        normalized = path_value.strip('/').replace('\\', '/')
        if not normalized:
            return tree
        if normalized in lookup:
            return lookup[normalized]['children']

        parent_path = os.path.dirname(normalized).replace('\\', '/')
        name = os.path.basename(normalized)
        children = ensure_dir(parent_path)
        node = {'type': 'dir', 'name': name, 'path': normalized, 'url': f"/category/{quote(normalized)}", 'children': []}
        children.append(node)
        lookup[normalized] = node
        return node['children']

    for post in get_posts(include_private=include_private):
        parent_dir = (post.get('category') or '').strip('/').replace('\\', '/')
        children = ensure_dir(parent_dir)
        children.append({
            'type': 'file',
            'name': post.get('title') or os.path.basename(post.get('filename', '')),
            'path': post.get('filename'),
            'url': post.get('url'),
        })

    return tree


def paginate_posts(items, page=1, per_page=10):
    total = len(items)
    per_page = max(1, int(per_page or 10))
    total_pages = max(1, int(math.ceil(total / float(per_page)))) if total else 1
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
    }


def _build_search_snippet(raw_content, keyword):
    content = re.sub(r'^---[\s\S]*?---\s*', '', raw_content or '', flags=re.MULTILINE)
    content = re.sub(r'!\[[^\]]*\]\((.*?)\)', ' ', content)
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'\s+', ' ', content).strip()
    if not content:
        return ''

    lowered = content.lower()
    target = keyword.lower()
    index = lowered.find(target)
    if index == -1:
        return content[:140] + ('...' if len(content) > 140 else '')

    start = max(0, index - 48)
    end = min(len(content), index + len(target) + 92)
    snippet = content[start:end].strip()
    if start > 0:
        snippet = '...' + snippet
    if end < len(content):
        snippet = snippet + '...'
    return snippet


def search_posts(query, include_private=False):
    keyword = str(query or '').strip().lower()
    if not keyword:
        return []

    results = []
    for filename in _iter_markdown_filenames():
        payload = _parse_markdown_file(filename)
        if not payload:
            continue
        metadata = payload['metadata']
        if not _is_visible_post(metadata, include_private=include_private):
            continue

        haystack = ' '.join([
            str(metadata.get('title') or ''),
            str(metadata.get('summary') or ''),
            ' '.join(metadata.get('tags') or []),
            str(payload.get('raw_content') or ''),
        ]).lower()
        if keyword in haystack:
            item = dict(metadata)
            item['search_snippet'] = _build_search_snippet(payload.get('raw_content') or '', keyword)
            results.append(item)

    return _attach_view_counts(_sort_posts(results))


def clear_file_cache(filename=None):
    """清除文件缓存

    Args:
        filename: 要清除的文件名，如果为 None 则清除所有缓存
    """
    global _FILE_CACHE
    if filename is None:
        _FILE_CACHE.clear()
    elif filename in _FILE_CACHE:
        del _FILE_CACHE[filename]
