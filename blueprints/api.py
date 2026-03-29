import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session, url_for, current_app, Response
from flask_login import login_required, current_user
from models import SystemSetting, Image, ShareLink, User, db
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services import (
    CrawlError,
    InvalidPathError,
    build_share_session_key,
    build_share_title,
    check_permission,
    clear_file_cache,
    delete_media_file,
    extract_article_preview,
    fetch_remote_image,
    finalize_crawled_content,
    force_https_url,
    generate_share_token,
    get_all_images_with_status,
    get_public_post_documents,
    get_share_link_by_token,
    is_share_expired,
    get_local_images,
    normalize_local_media_references_in_text,
    normalize_local_media_url,
    normalize_relative_path,
    resolve_shared_path,
    resolve_docs_path,
    sync_front_matter,
    update_all_image_references,
    upload_media_file,
)
from services.docs import (
    SLUG_BASE_MAX_LENGTH,
    SLUG_MAX_LENGTH,
    _build_front_matter,
    _can_access_document_metadata,
    _find_post_slug_conflicts,
    _has_front_matter_block,
    _normalize_slug_source,
    _parse_markdown_file,
    _slugify,
    _split_front_matter,
    _suggest_unique_post_slug,
)
from werkzeug.utils import secure_filename

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _get_app_timezone():
    timezone_name = (current_app.config.get('APP_TIMEZONE') or 'Asia/Shanghai').strip() or 'Asia/Shanghai'
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), name=timezone_name)


def _serialize_utc_datetime(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def _ensure_markdown_filename(filename):
    """确保文件名安全且有.md后缀，支持中文"""
    name = (filename or '').strip()
    if not name:
        raise ValueError('文件名不能为空')
    
    # 移除危险字符，但保留中文、字母、数字、下划线、连字符、点号、空格
    import re
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    safe_name = safe_name.strip()
    
    if not safe_name:
        raise ValueError('文件名不能为空或只包含特殊字符')
    
    # 确保有.md后缀
    if not safe_name.lower().endswith('.md'):
        safe_name = f'{safe_name}.md'
    
    return safe_name


def _ensure_directory_name(name):
    """确保目录名安全，支持中文"""
    dir_name = (name or '').strip()
    if not dir_name:
        raise ValueError('目录名不能为空')
    
    # 移除危险字符，但保留中文、字母、数字、下划线、连字符、空格
    import re
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', dir_name)
    safe_name = safe_name.strip()
    
    if not safe_name:
        raise ValueError('目录名不能为空或只包含特殊字符')
    
    return safe_name


def _parse_share_expiry(raw_value):
    value = (raw_value or '').strip()
    if not value or value == 'never':
        return None

    shortcuts = {
        '1d': timedelta(days=1),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
    }
    if value in shortcuts:
        return datetime.utcnow() + shortcuts[value]

    app_timezone = _get_app_timezone()

    try:
        expires_at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('???????') from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=app_timezone)
    else:
        expires_at = expires_at.astimezone(app_timezone)

    expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    if expires_at <= datetime.utcnow():
        raise ValueError('???????????')
    return expires_at


def _build_share_response(share_link):
    is_expired = is_share_expired(share_link)
    return {
        'id': share_link.id,
        'token': share_link.token,
        'url': url_for('main.share_view', token=share_link.token, _external=True),
        'title': share_link.title,
        'target_type': share_link.target_type,
        'target_path': share_link.target_path,
        'allow_edit': bool(share_link.allow_edit),
        'requires_password': bool(share_link.is_password_protected),
        'expires_at': _serialize_utc_datetime(share_link.expires_at),
        'created_at': _serialize_utc_datetime(share_link.created_at),
        'updated_at': _serialize_utc_datetime(share_link.updated_at),
        'is_expired': is_expired,
        'is_active': not is_expired,
    }


def _get_share_for_api(token, require_edit=False, require_access=False):
    share_link = get_share_link_by_token(token)
    if not share_link:
        return None, jsonify({'error': '分享不存在'}), 404
    if is_share_expired(share_link):
        return None, jsonify({'error': '分享已过期'}), 410
    if require_edit and not share_link.allow_edit:
        return None, jsonify({'error': '当前分享未开启编辑权限'}), 403
    if require_access and share_link.is_password_protected and not session.get(build_share_session_key(share_link.token)):
        return None, jsonify({'error': '请先输入分享密码'}), 403
    return share_link, None, None


def _resolve_share_target_for_owner(target_type, target_path, allow_edit=False):
    if target_type == 'file':
        _, normalized_target_path, absolute_target_path = resolve_docs_path(target_path)
        if not os.path.isfile(absolute_target_path):
            return None, None, jsonify({'error': '目标文档不存在'}), 404
        if not check_permission(current_user, normalized_target_path, 'read'):
            return None, None, jsonify({'error': '没有该文档的分享权限'}), 403
        if allow_edit and not check_permission(current_user, normalized_target_path, 'edit'):
            return None, None, jsonify({'error': '没有该文档的编辑权限，无法创建可编辑分享'}), 403
    else:
        _, normalized_target_path, absolute_target_path = resolve_docs_path(target_path, allow_directory=True)
        if not os.path.isdir(absolute_target_path):
            return None, None, jsonify({'error': '目标目录不存在'}), 404
        if not check_permission(current_user, normalized_target_path, 'read'):
            return None, None, jsonify({'error': '没有该目录的分享权限'}), 403
        if allow_edit and not check_permission(current_user, normalized_target_path, 'edit'):
            return None, None, jsonify({'error': '没有该目录的编辑权限，无法创建可编辑分享'}), 403
    return normalized_target_path, absolute_target_path, None, None


def _get_owned_share_link(token):
    share_link = ShareLink.query.filter_by(token=(token or '').strip(), created_by_user_id=current_user.id).first()
    if not share_link:
        return None, jsonify({'error': '分享不存在或无权管理'}), 404
    return share_link, None


@api_bp.route('/users/suggest')
def suggest_users():
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'items': []})
    like_value = f'{query}%'
    users = User.query.filter(User.username.like(like_value)).order_by(User.username.asc()).limit(8).all()
    return jsonify({'items': [{'username': user.username, 'nickname': user.nickname or ''} for user in users]})

@api_bp.route('/get_raw')
def get_raw_markdown():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename missing'}), 400

    try:
        _, filename, filepath = resolve_docs_path(filename)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400
        
    if not check_permission(current_user, filename, 'read'):
        return jsonify({'error': 'Permission denied'}), 403
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    payload = _parse_markdown_file(filename)
    if not payload or not _can_access_document_metadata(filename, payload.get('metadata') or {}):
        return jsonify({'error': 'Permission denied'}), 403
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = normalize_local_media_references_in_text(f.read())
        
    return jsonify({'content': content})


@api_bp.route('/crawl/preview', methods=['POST'])
@login_required
def crawl_article_preview():
    data = request.get_json() or {}
    source_url = (data.get('url') or '').strip()
    filename = (data.get('filename') or '').strip()

    if not source_url:
        return jsonify({'error': '请输入要抓取的文章链接'}), 400

    normalized_filename = ''
    if filename:
        try:
            _, normalized_filename, _ = resolve_docs_path(filename)
        except InvalidPathError:
            return jsonify({'error': '目标文档路径无效'}), 400

        if not check_permission(current_user, normalized_filename, 'edit'):
            return jsonify({'error': '没有该文档的编辑权限'}), 403

    try:
        preview = extract_article_preview(source_url)
        return jsonify({
            'success': True,
            'filename': normalized_filename,
            'source_url': preview.get('source_url') or source_url,
            'title': preview.get('title') or '',
            'date': preview.get('date') or '',
            'tags': preview.get('tags') or [],
            'cover': force_https_url(preview.get('cover') or ''),
            'markdown': preview.get('markdown') or '',
        })
    except CrawlError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'抓取失败：{exc}'}), 500


@api_bp.route('/crawl/finalize', methods=['POST'])
@login_required
def finalize_crawled_article():
    data = request.get_json() or {}
    filename = (data.get('filename') or '').strip()
    markdown_text = data.get('markdown')
    image_mode = (data.get('image_mode') or 'remote').strip().lower()
    cover_url = (data.get('cover') or '').strip()

    if markdown_text is None:
        return jsonify({'error': '缺少要插入的正文内容'}), 400

    if image_mode not in {'remote', 'download_local'}:
        return jsonify({'error': '图片处理方式无效'}), 400

    if filename:
        try:
            _, filename, _ = resolve_docs_path(filename)
        except InvalidPathError:
            return jsonify({'error': '目标文档路径无效'}), 400

        if not check_permission(current_user, filename, 'edit'):
            return jsonify({'error': '没有该文档的编辑权限'}), 403

    try:
        result = finalize_crawled_content(
            markdown_text=str(markdown_text or ''),
            image_mode=image_mode,
            cover_url=cover_url,
        )
        update_all_image_references()
        return jsonify({
            'success': True,
            'markdown': result.get('markdown') or '',
            'cover': result.get('cover') or '',
            'warnings': result.get('warnings') or [],
        })
    except CrawlError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'处理失败：{exc}'}), 500


@api_bp.route('/crawl/image-proxy', methods=['GET'])
@login_required
def crawl_image_proxy():
    source_url = (request.args.get('url') or '').strip()
    if not source_url:
        return jsonify({'error': '缺少图片地址'}), 400

    try:
        _, content, headers = fetch_remote_image(source_url)
        content_type = headers.get_content_type() or 'image/jpeg'
        response = Response(content, mimetype=content_type)
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except CrawlError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'图片预览失败：{exc}'}), 500

@api_bp.route('/save', methods=['POST'])
@login_required
def save_markdown():
    data = request.get_json() or {}
    filename = data.get('filename')
    content = data.get('content')
    ensure_front_matter = bool(data.get('ensure_front_matter'))
    
    if not filename or content is None:
        return jsonify({'error': 'Invalid arguments'}), 400

    try:
        _, filename, filepath = resolve_docs_path(filename)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400
        
    if not check_permission(current_user, filename, 'edit'):
        return jsonify({'error': 'Permission denied: no edit access for this directory'}), 403
    
    try:
        content = sync_front_matter(content, filename, ensure_front_matter=ensure_front_matter)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        update_all_image_references()
        return jsonify({'success': True, 'content': content})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/front-matter/slug-check', methods=['GET'])
@login_required
def check_front_matter_slug():
    raw_slug = request.args.get('slug', '')
    filename = request.args.get('filename', '')
    template = (request.args.get('template', 'post') or 'post').strip().lower()

    normalized_filename = ''
    if filename:
        try:
            _, normalized_filename, _ = resolve_docs_path(filename)
        except InvalidPathError:
            return jsonify({'error': '目标文档路径无效'}), 400

        if not check_permission(current_user, normalized_filename, 'edit'):
            return jsonify({'error': '没有该文档的编辑权限'}), 403

    raw_normalized_slug = _normalize_slug_source(raw_slug)
    normalized_slug = _slugify(raw_slug)
    was_truncated = bool(raw_normalized_slug and normalized_slug != raw_normalized_slug)
    if template != 'post':
        return jsonify({
            'success': True,
            'slug': normalized_slug,
            'available': True,
            'conflicts': [],
            'suggested_slug': normalized_slug,
            'was_truncated': was_truncated,
            'slug_base_max_length': SLUG_BASE_MAX_LENGTH,
            'slug_max_length': SLUG_MAX_LENGTH,
            'message': '当前模板不是文章，slug 暂不参与博客路由唯一性校验',
        })

    conflicts = _find_post_slug_conflicts(normalized_slug, exclude_filename=normalized_filename)
    suggested_slug = _suggest_unique_post_slug(normalized_slug or 'post', exclude_filename=normalized_filename)
    return jsonify({
        'success': True,
        'slug': normalized_slug,
        'available': len(conflicts) == 0,
        'conflicts': conflicts,
        'suggested_slug': suggested_slug,
        'was_truncated': was_truncated,
        'slug_base_max_length': SLUG_BASE_MAX_LENGTH,
        'slug_max_length': SLUG_MAX_LENGTH,
        'message': '' if not conflicts else '当前 slug 已被其他博客文章占用',
    })


@api_bp.route('/public-posts', methods=['GET'])
@login_required
def list_public_posts():
    items = get_public_post_documents()
    return jsonify({
        'success': True,
        'items': [
            {
                'filename': item.get('filename') or item.get('path') or '',
                'path': item.get('path') or item.get('filename') or '',
                'title': item.get('title') or '未命名文档',
                'summary': item.get('summary') or '',
                'category_name': item.get('category_name') or '',
                'category_path': item.get('category_path') or '',
                'date': item.get('date') or '',
                'date_display': item.get('date_display') or '',
                'updated': item.get('updated') or '',
                'updated_display': item.get('updated_display') or '',
                'timeline_date': item.get('timeline_date') or '',
                'timeline_display': item.get('timeline_display') or '',
                'doc_url': item.get('doc_url') or '',
                'post_url': (url_for('main.post_detail', slug=item.get('slug')) if item.get('template') == 'post' and item.get('slug') else ''),
                'slug': item.get('slug') or '',
                'view_count': int(item.get('view_count') or 0),
                'can_edit': bool(item.get('can_edit')),
                'public': bool(item.get('public')),
                'template': item.get('template') or 'doc',
                'is_blog_visible': bool(item.get('is_blog_visible')),
                'has_front_matter': bool(item.get('has_front_matter')),
            }
            for item in items
        ],
    })


@api_bp.route('/public-posts/toggle', methods=['POST'])
@login_required
def toggle_public_post():
    data = request.get_json() or {}
    filename = data.get('filename', '')
    is_public = data.get('public')
    show_in_blog = data.get('show_in_blog')

    try:
        _, filename, filepath = resolve_docs_path(filename)
    except InvalidPathError:
        return jsonify({'error': '目标文档路径无效'}), 400

    if not check_permission(current_user, filename, 'edit'):
        return jsonify({'error': '没有该文档的编辑权限'}), 403

    if not os.path.isfile(filepath):
        return jsonify({'error': '目标文档不存在'}), 404

    try:
        with open(filepath, 'r', encoding='utf-8') as file_obj:
            content = file_obj.read()

        raw_metadata, body_content = _split_front_matter(content)
        raw_metadata = dict(raw_metadata or {})
        if is_public is not None:
            raw_metadata['public'] = bool(is_public)
        elif 'public' not in raw_metadata:
            raw_metadata['public'] = False

        if show_in_blog is not None:
            raw_metadata['template'] = 'post' if bool(show_in_blog) else 'doc'
        elif not raw_metadata.get('template'):
            raw_metadata['template'] = 'post'

        final_content = _build_front_matter(raw_metadata, body_content, filename)
        with open(filepath, 'w', encoding='utf-8') as file_obj:
            file_obj.write(final_content)

        clear_file_cache(filename)
        update_all_image_references()
        return jsonify({
            'success': True,
            'filename': filename,
            'public': bool(raw_metadata.get('public')),
            'template': raw_metadata.get('template') or 'doc',
            'is_blog_visible': (raw_metadata.get('template') or 'doc') == 'post',
            'post_url': (
                url_for('main.post_detail', slug=raw_metadata.get('slug'))
                if (raw_metadata.get('template') or 'doc') == 'post' and raw_metadata.get('slug')
                else ''
            ),
        })
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/public-posts/remove-front-matter', methods=['POST'])
@login_required
def remove_public_post_front_matter():
    data = request.get_json() or {}
    filename = data.get('filename', '')

    try:
        _, filename, filepath = resolve_docs_path(filename)
    except InvalidPathError:
        return jsonify({'error': '目标文档路径无效'}), 400

    if not check_permission(current_user, filename, 'edit'):
        return jsonify({'error': '没有该文档的编辑权限'}), 403

    if not os.path.isfile(filepath):
        return jsonify({'error': '目标文档不存在'}), 404

    try:
        with open(filepath, 'r', encoding='utf-8') as file_obj:
            content = file_obj.read()

        if not _has_front_matter_block(content):
            return jsonify({'error': '该文档没有可移除的头部信息'}), 400

        _, body_content = _split_front_matter(content)
        normalized_body = body_content.lstrip('\n')
        final_content = normalized_body if normalized_body else ''

        with open(filepath, 'w', encoding='utf-8') as file_obj:
            file_obj.write(final_content)

        clear_file_cache(filename)
        update_all_image_references()
        return jsonify({
            'success': True,
            'filename': filename,
        })
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@api_bp.route('/media_upload', methods=['POST'])
@login_required
def media_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # 权限检查 (简单检查用户是否有任何目录的上传权限)
    if not check_permission(current_user, '', 'upload') and current_user.role != 'admin':
        return jsonify({'error': 'Permission denied: you do not have upload rights.'}), 403
        
    # 文件大小限制
    max_size_value = SystemSetting.get('media_max_size_mb', 50)
    max_size_mb = int(max_size_value if max_size_value is not None else 50)
    if len(file.read()) > max_size_mb * 1024 * 1024:
        return jsonify({'error': f'File exceeds the maximum size of {max_size_mb}MB'}), 413
    file.seek(0) # 重置文件指针

    upload_purpose = (request.form.get('upload_purpose') or '').strip().lower()
    target_subdir = ''
    if upload_purpose == 'site_logo':
        if current_user.role != 'admin':
            return jsonify({'error': 'Permission denied: admin only.'}), 403
        target_subdir = 'logo'

    try:
        file_url = upload_media_file(file, target_subdir=target_subdir)
        corrected_url = force_https_url(file_url)
        return jsonify({'success': True, 'url': corrected_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/settings/site-logo', methods=['POST'])
@login_required
def update_site_logo_setting():
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403

    site_logo = normalize_local_media_url((request.form.get('site_logo') or '').strip())
    SystemSetting.set('site_logo', site_logo)
    update_all_image_references()
    return jsonify({
        'success': True,
        'site_logo': site_logo,
        'site_logo_url': force_https_url(site_logo) if site_logo else '',
    })


@api_bp.route('/upload', methods=['POST'])
@login_required
def upload_markdown():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if not (file.filename or '').endswith('.md'):
        return jsonify({'error': 'Only .md files are allowed'}), 400
        
    # 获取目标文件夹路径
    target_dir = request.form.get('target_dir', '')
    try:
        target_dir = normalize_relative_path(target_dir)
        _, target_dir, abs_target_dir = resolve_docs_path(target_dir, allow_directory=True, create_directory=True)
    except InvalidPathError:
        return jsonify({'error': 'Invalid target directory'}), 400
    
    if not check_permission(current_user, target_dir, 'upload'):
        return jsonify({'error': 'Permission denied: no upload access for this directory'}), 403

    safe_filename = secure_filename(file.filename or '')
    if not safe_filename.endswith('.md'):
        return jsonify({'error': 'Invalid filename'}), 400

    save_path = os.path.join(abs_target_dir, safe_filename)
    
    try:
        file.save(save_path)
        saved_path = safe_filename if not target_dir else f"{target_dir}/{safe_filename}"
        return jsonify({'success': True, 'path': saved_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/documents/create', methods=['POST'])
@login_required
def create_markdown_document():
    data = request.get_json() or {}
    target_dir = data.get('target_dir', '')
    filename = data.get('filename', '')

    try:
        target_dir = normalize_relative_path(target_dir)
        _, target_dir, abs_target_dir = resolve_docs_path(target_dir, allow_directory=True, create_directory=True)
        safe_filename = _ensure_markdown_filename(filename)
    except InvalidPathError:
        return jsonify({'error': 'Invalid target directory'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if not check_permission(current_user, target_dir, 'upload'):
        return jsonify({'error': 'Permission denied: no upload access for this directory'}), 403

    file_path = os.path.join(abs_target_dir, safe_filename)
    if os.path.exists(file_path):
        return jsonify({'error': '文件已存在'}), 400

    relative_path = safe_filename if not target_dir else f'{target_dir}/{safe_filename}'
    initial_content = sync_front_matter('', relative_path, ensure_front_matter=True)

    with open(file_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(initial_content)

    return jsonify({'success': True, 'path': relative_path})


@api_bp.route('/documents/rename', methods=['POST'])
@login_required
def rename_markdown_document():
    data = request.get_json() or {}
    source_path = data.get('source_path', '')
    new_name = data.get('new_name', '')

    try:
        _, source_path, abs_source_path = resolve_docs_path(source_path)
        safe_filename = _ensure_markdown_filename(new_name)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    source_dir = os.path.dirname(source_path).replace('\\', '/')
    if not check_permission(current_user, source_path, 'edit'):
        return jsonify({'error': 'Permission denied: no edit access for this file'}), 403

    if not os.path.isfile(abs_source_path):
        return jsonify({'error': 'File not found'}), 404

    target_path = safe_filename if not source_dir else f'{source_dir}/{safe_filename}'
    _, target_path, abs_target_path = resolve_docs_path(target_path)
    if os.path.exists(abs_target_path):
        return jsonify({'error': '目标文件已存在'}), 400

    os.rename(abs_source_path, abs_target_path)
    return jsonify({'success': True, 'path': target_path})


@api_bp.route('/documents/delete', methods=['DELETE'])
@login_required
def delete_markdown_document():
    data = request.get_json(silent=True) or {}
    filename = data.get('filename') or request.args.get('filename', '')

    try:
        _, filename, abs_file_path = resolve_docs_path(filename)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400

    if not check_permission(current_user, filename, 'delete'):
        return jsonify({'error': 'Permission denied: no delete access for this file'}), 403

    if not os.path.isfile(abs_file_path):
        return jsonify({'error': 'File not found'}), 404

    os.remove(abs_file_path)
    update_all_image_references()
    return jsonify({'success': True})


@api_bp.route('/directories/create', methods=['POST'])
@login_required
def create_directory():
    data = request.get_json() or {}
    parent_dir = data.get('parent_dir', '')
    name = data.get('name', '')

    try:
        parent_dir = normalize_relative_path(parent_dir)
        safe_name = _ensure_directory_name(name)
        _, parent_dir, abs_parent_dir = resolve_docs_path(parent_dir, allow_directory=True, create_directory=True)
    except InvalidPathError:
        return jsonify({'error': 'Invalid parent directory'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    target_dir = safe_name if not parent_dir else f'{parent_dir}/{safe_name}'
    _, target_dir, abs_target_dir = resolve_docs_path(target_dir, allow_directory=True)

    if not check_permission(current_user, parent_dir, 'upload'):
        return jsonify({'error': 'Permission denied: no upload access for this directory'}), 403
    if os.path.exists(abs_target_dir):
        return jsonify({'error': '目录已存在'}), 400

    os.makedirs(abs_target_dir, exist_ok=False)
    return jsonify({'success': True, 'path': target_dir})


@api_bp.route('/directories/rename', methods=['POST'])
@login_required
def rename_directory():
    data = request.get_json() or {}
    source_path = data.get('source_path', '')
    new_name = data.get('new_name', '')

    try:
        _, source_path, abs_source_dir = resolve_docs_path(source_path, allow_directory=True)
        safe_name = _ensure_directory_name(new_name)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if not source_path:
        return jsonify({'error': '根目录不允许重命名'}), 400

    parent_dir = os.path.dirname(source_path).replace('\\', '/')
    target_path = safe_name if not parent_dir else f'{parent_dir}/{safe_name}'
    _, target_path, abs_target_dir = resolve_docs_path(target_path, allow_directory=True)

    if not check_permission(current_user, source_path, 'edit'):
        return jsonify({'error': 'Permission denied: no edit access for this directory'}), 403
    if not os.path.isdir(abs_source_dir):
        return jsonify({'error': 'Directory not found'}), 404
    if os.path.exists(abs_target_dir):
        return jsonify({'error': '目标目录已存在'}), 400

    os.rename(abs_source_dir, abs_target_dir)
    return jsonify({'success': True, 'path': target_path})


@api_bp.route('/directories/delete', methods=['DELETE'])
@login_required
def delete_directory():
    data = request.get_json(silent=True) or {}
    dirname = data.get('dirname') or request.args.get('dirname', '')

    try:
        _, dirname, abs_dir_path = resolve_docs_path(dirname, allow_directory=True)
    except InvalidPathError:
        return jsonify({'error': 'Invalid path'}), 400

    if not dirname:
        return jsonify({'error': '根目录不允许删除'}), 400
    if not check_permission(current_user, dirname, 'delete'):
        return jsonify({'error': 'Permission denied: no delete access for this directory'}), 403
    if not os.path.isdir(abs_dir_path):
        return jsonify({'error': 'Directory not found'}), 404
    if os.listdir(abs_dir_path):
        return jsonify({'error': '目录不为空，请先清理其中的文档'}), 400

    os.rmdir(abs_dir_path)
    return jsonify({'success': True})


@api_bp.route('/shares', methods=['POST'])
@login_required
def create_share():
    data = request.get_json() or {}
    target_type = (data.get('target_type') or '').strip().lower()
    target_path = data.get('target_path', '')
    target_name = data.get('target_name', '')
    password = (data.get('password') or '').strip()
    allow_edit = bool(data.get('allow_edit'))

    if target_type not in {'file', 'dir'}:
        return jsonify({'error': '分享目标类型无效'}), 400

    try:
        expires_at = _parse_share_expiry(data.get('expires_at'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        if target_type == 'file':
            _, normalized_target_path, absolute_target_path = resolve_docs_path(target_path)
            if not os.path.isfile(absolute_target_path):
                return jsonify({'error': '目标文档不存在'}), 404
            if not check_permission(current_user, normalized_target_path, 'read'):
                return jsonify({'error': '没有该文档的分享权限'}), 403
            if allow_edit and not check_permission(current_user, normalized_target_path, 'edit'):
                return jsonify({'error': '没有该文档的编辑权限，无法创建可编辑分享'}), 403
        else:
            _, normalized_target_path, absolute_target_path = resolve_docs_path(target_path, allow_directory=True)
            if not os.path.isdir(absolute_target_path):
                return jsonify({'error': '目标目录不存在'}), 404
            if not check_permission(current_user, normalized_target_path, 'read'):
                return jsonify({'error': '没有该目录的分享权限'}), 403
            if allow_edit and not check_permission(current_user, normalized_target_path, 'edit'):
                return jsonify({'error': '没有该目录的编辑权限，无法创建可编辑分享'}), 403
    except InvalidPathError:
        return jsonify({'error': '目标路径无效'}), 400

    share_link = ShareLink()
    share_link.target_type = target_type
    share_link.target_path = normalized_target_path
    share_link.title = build_share_title(target_type, normalized_target_path, target_name)
    share_link.allow_edit = allow_edit
    share_link.expires_at = expires_at
    share_link.created_by_user_id = current_user.id
    share_link.set_password(password)

    for _ in range(8):
        token = generate_share_token()
        if not ShareLink.query.filter_by(token=token).first():
            share_link.token = token
            break
    if not share_link.token:
        return jsonify({'error': '生成分享链接失败，请稍后重试'}), 500

    db.session.add(share_link)
    db.session.commit()

    if not share_link.is_password_protected:
        session[build_share_session_key(share_link.token)] = True

    return jsonify({'success': True, 'share': _build_share_response(share_link)})


@api_bp.route('/shares', methods=['GET'])
@login_required
def list_shares():
    scope = (request.args.get('scope') or 'current').strip().lower()
    target_type = (request.args.get('target_type') or '').strip().lower()
    target_path = request.args.get('target_path', '')

    if scope not in {'current', 'all'}:
        return jsonify({'error': '分享范围无效'}), 400

    query = ShareLink.query.filter_by(created_by_user_id=current_user.id)

    if scope == 'current' and target_type not in {'file', 'dir'}:
        return jsonify({'error': '分享目标类型无效'}), 400

    try:
            normalized_target_path, _, error_response, status_code = _resolve_share_target_for_owner(
                target_type,
                target_path,
                allow_edit=False,
            )
            if error_response is not None:
                return error_response, status_code
    except InvalidPathError:
        return jsonify({'error': '目标路径无效'}), 400

    share_links = (
        ShareLink.query
        .filter_by(
            created_by_user_id=current_user.id,
            target_type=target_type,
            target_path=normalized_target_path,
        )
        .order_by(ShareLink.created_at.desc(), ShareLink.id.desc())
        .all()
    )
    return jsonify({
        'success': True,
        'items': [_build_share_response(share_link) for share_link in share_links],
    })


@api_bp.route('/shares/<string:token>', methods=['PATCH'])
@login_required
def update_share(token):
    share_link, error_response = _get_owned_share_link(token)
    if error_response is not None:
        return error_response

    data = request.get_json() or {}
    allow_edit = bool(data.get('allow_edit', share_link.allow_edit))

    try:
        _, _, target_error, target_status = _resolve_share_target_for_owner(
            share_link.target_type,
            share_link.target_path,
            allow_edit=allow_edit,
        )
        if target_error is not None:
            return target_error, target_status
    except InvalidPathError:
        return jsonify({'error': '分享目标路径无效'}), 400

    if 'active' in data:
        if bool(data.get('active')):
            share_link.expires_at = None
        else:
            share_link.expires_at = datetime.utcnow() - timedelta(seconds=1)
    elif 'expires_at' in data:
        try:
            share_link.expires_at = _parse_share_expiry(data.get('expires_at'))
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

    share_link.allow_edit = allow_edit

    password_mode = (data.get('password_mode') or 'keep').strip().lower()
    if password_mode == 'clear':
        share_link.set_password('')
    elif password_mode == 'set':
        password = (data.get('password') or '').strip()
        if not password:
            return jsonify({'error': '请先填写新的分享密码'}), 400
        share_link.set_password(password)
    elif password_mode != 'keep':
        return jsonify({'error': '密码操作类型无效'}), 400

    db.session.commit()

    if not share_link.is_password_protected:
        session[build_share_session_key(share_link.token)] = True
    else:
        session.pop(build_share_session_key(share_link.token), None)

    return jsonify({'success': True, 'share': _build_share_response(share_link)})


@api_bp.route('/shares/mine', methods=['GET'])
@login_required
def list_my_shares():
    share_links = (
        ShareLink.query
        .filter_by(created_by_user_id=current_user.id)
        .order_by(ShareLink.created_at.desc(), ShareLink.id.desc())
        .all()
    )
    return jsonify({
        'success': True,
        'scope': 'all',
        'items': [_build_share_response(share_link) for share_link in share_links],
    })


@api_bp.route('/shares/<string:token>', methods=['DELETE'])
@login_required
def delete_share_link(token):
    share_link, error_response = _get_owned_share_link(token)
    if error_response is not None:
        return error_response

    session.pop(build_share_session_key(share_link.token), None)
    db.session.delete(share_link)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/shares/<string:token>/raw')
def get_share_raw(token):
    share_link, error_response, status_code = _get_share_for_api(token, require_edit=True, require_access=True)
    if error_response is not None:
        return error_response, status_code

    target_relative_path = request.args.get('path', '')
    try:
        normalized_target_path, absolute_target_path, _ = resolve_shared_path(share_link, target_relative_path)
    except InvalidPathError:
        return jsonify({'error': '分享路径无效'}), 400

    if not normalized_target_path.endswith('.md') or not os.path.isfile(absolute_target_path):
        return jsonify({'error': '目标文档不存在'}), 404

    with open(absolute_target_path, 'r', encoding='utf-8') as file_obj:
        content = file_obj.read()
    return jsonify({'success': True, 'content': content, 'path': normalized_target_path})


@api_bp.route('/shares/<string:token>/save', methods=['POST'])
def save_shared_document(token):
    share_link, error_response, status_code = _get_share_for_api(token, require_edit=True, require_access=True)
    if error_response is not None:
        return error_response, status_code

    data = request.get_json() or {}
    target_relative_path = data.get('path', '')
    content = data.get('content')
    ensure_front_matter = bool(data.get('ensure_front_matter'))

    if content is None:
        return jsonify({'error': '缺少文档内容'}), 400

    try:
        normalized_target_path, absolute_target_path, _ = resolve_shared_path(share_link, target_relative_path)
    except InvalidPathError:
        return jsonify({'error': '分享路径无效'}), 400

    if not normalized_target_path.endswith('.md') or not os.path.isfile(absolute_target_path):
        return jsonify({'error': '目标文档不存在'}), 404

    try:
        final_content = sync_front_matter(content, normalized_target_path, ensure_front_matter=ensure_front_matter)
        with open(absolute_target_path, 'w', encoding='utf-8') as file_obj:
            file_obj.write(final_content)
        update_all_image_references()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    return jsonify({'success': True, 'content': final_content})

@api_bp.route('/images/all')
@login_required
def get_all_images():
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403
    images = get_all_images_with_status()
    for image in images:
        image['url'] = force_https_url(image['url'])
    return jsonify({'images': images})


def _delete_image_by_unique_filename(unique_filename, status_hint=''):
    normalized_status = (status_hint or '').strip()
    image = Image.query.filter_by(unique_filename=unique_filename).first()

    if normalized_status == 'orphan':
        storage_type = SystemSetting.get('media_storage_type', 'local')
        image_path = None
        if storage_type == 'local':
            all_local_images = get_local_images()
            if unique_filename in all_local_images:
                image_path = all_local_images[unique_filename]['path']
            else:
                return False, 'Orphan file not found in local storage.'
        else:
            image_path = unique_filename

        image_to_delete = Image()
        image_to_delete.storage_type = storage_type
        image_to_delete.path = image_path
        if not delete_media_file(image_to_delete):
            return False, 'Failed to delete orphan file from storage.'
        return True, None

    if not image:
        return False, 'Image not found.'

    if image.is_referenced:
        return False, 'Image is in use and cannot be deleted.'

    if normalized_status == 'db_only' or str(image.url or '').strip() == '#':
        db.session.delete(image)
        db.session.commit()
        return True, None

    if not delete_media_file(image):
        return False, 'Failed to delete file from storage.'

    db.session.delete(image)
    db.session.commit()
    return True, None

@api_bp.route('/images/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403

    image = Image.query.get_or_404(image_id)
    
    if image.is_referenced:
        return jsonify({'error': 'Image is currently in use and cannot be deleted.'}), 400

    if not delete_media_file(image):
        return jsonify({'error': 'Failed to delete file from storage.'}), 500
    
    db.session.delete(image)
    db.session.commit()
    
    return jsonify({'success': True})

@api_bp.route('/images/delete/<string:unique_filename>', methods=['DELETE'])
@login_required
def delete_image_by_filename(unique_filename):
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403

    status = request.args.get('status')
    success, error = _delete_image_by_unique_filename(unique_filename, status)
    if not success:
        status_code = 404 if error == 'Image not found.' or error == 'Orphan file not found in local storage.' else 400
        return jsonify({'error': error}), status_code

    return jsonify({'success': True})


@api_bp.route('/images/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_images():
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403

    payload = request.get_json(silent=True) or {}
    raw_items = payload.get('items')
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({'error': 'No images selected.'}), 400

    results = []
    success_count = 0
    failure_count = 0

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        unique_filename = str(item.get('unique_filename') or '').strip()
        status = str(item.get('status') or '').strip()
        if not unique_filename:
            continue

        success, error = _delete_image_by_unique_filename(unique_filename, status)
        if success:
            success_count += 1
        else:
            failure_count += 1
        results.append({
            'unique_filename': unique_filename,
            'success': success,
            'error': error,
        })

    if not results:
        return jsonify({'error': 'No valid images selected.'}), 400

    return jsonify({
        'success': failure_count == 0,
        'success_count': success_count,
        'failure_count': failure_count,
        'results': results,
    })


@api_bp.route('/search-docs', methods=['GET'])
def search_docs():
    """文档搜索API - 返回JSON格式的搜索结果"""
    from services import check_global_access
    
    # 检查全局访问权限
    access_redirect = check_global_access()
    if access_redirect:
        return jsonify({'success': False, 'error': '无权限访问'}), 403
    
    query = (request.args.get('q') or '').strip()
    
    if not query:
        return jsonify({'success': True, 'results': []})
    
    try:
        from services.docs import _iter_markdown_filenames, _parse_markdown_file
        import re
        
        results = []
        query_lower = query.lower()
        
        # 搜索所有markdown文件
        for filename in _iter_markdown_filenames():
            # 检查权限
            if not check_permission(current_user, filename, 'read'):
                continue
            
            # 解析文件
            payload = _parse_markdown_file(filename)
            if not payload:
                continue
            
            metadata = payload.get('metadata', {})
            if not _can_access_document_metadata(filename, metadata, allow_password_access=True):
                continue
            raw_content = payload.get('raw_content', '')
            
            # 搜索标题、内容
            title = metadata.get('title', '')
            searchable_text = f"{title} {raw_content}".lower()
            
            if query_lower in searchable_text:
                # 生成搜索摘要
                content = re.sub(r'^---[\s\S]*?---\s*', '', raw_content or '', flags=re.MULTILINE)
                content = re.sub(r'!\[[^\]]*\]\((.*?)\)', ' ', content)
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                # 查找关键词位置
                index = content.lower().find(query_lower)
                if index == -1:
                    snippet = content[:200] + ('...' if len(content) > 200 else '')
                else:
                    start = max(0, index - 80)
                    end = min(len(content), index + len(query) + 120)
                    snippet = content[start:end].strip()
                    if start > 0:
                        snippet = '...' + snippet
                    if end < len(content):
                        snippet = snippet + '...'
                
                from flask import url_for
                results.append({
                    'filename': filename,
                    'title': title or filename,
                    'snippet': snippet,
                    'url': url_for('main.docs_doc', filename=filename)
                })
        
        # 限制返回结果数量
        results = results[:50]
        
        return jsonify({'success': True, 'results': results, 'total': len(results)})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
