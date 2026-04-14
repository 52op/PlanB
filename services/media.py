import os
import re
import uuid
import logging
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.exceptions import NoCredentialsError
from flask import current_app, url_for
from werkzeug.utils import secure_filename

from models import Image, SystemSetting, db
from runtime_paths import get_data_subdir
from .paths import get_docs_root
from .urls import normalize_local_media_url

logger = logging.getLogger(__name__)


def _normalize_upload_subdir(value):
    raw_value = str(value or '').replace('\\', '/').strip().strip('/')
    if not raw_value:
        return ''
    return '/'.join([segment for segment in raw_value.split('/') if segment not in {'', '.', '..'}])


def _upload_to_local(file_storage, target_subdir=''):
    normalized_subdir = _normalize_upload_subdir(target_subdir)
    date_folder = datetime.now().strftime('%Y/%m')
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1]
    unique_filename = f'{uuid.uuid4()}{ext}'

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    base_upload_dir = current_app.config.get('UPLOADS_DIR') or get_data_subdir('uploads')
    relative_dir = normalized_subdir or date_folder
    upload_folder = os.path.join(base_upload_dir, relative_dir.replace('/', os.sep))
    os.makedirs(upload_folder, exist_ok=True)

    save_path = os.path.join(upload_folder, unique_filename)
    file_storage.save(save_path)

    relative_path = f'{relative_dir}/{unique_filename}'.replace('\\', '/')
    url = normalize_local_media_url(url_for('main.media_file', filename=relative_path))
    return {
        'filename': filename,
        'unique_filename': unique_filename,
        'storage_type': 'local',
        'path': relative_path,
        'url': url,
        'size': size,
    }


def _upload_to_s3(file_storage, target_subdir=''):
    try:
        from botocore.client import Config
    except ImportError as exc:
        raise Exception('Boto3 依赖未安装，请执行 `pip install boto3`。') from exc

    endpoint = SystemSetting.get('s3_endpoint')
    bucket = SystemSetting.get('s3_bucket')
    access_key = SystemSetting.get('s3_access_key')
    secret_key = SystemSetting.get('s3_secret_key')
    cdn_domain = SystemSetting.get('s3_cdn_domain')
    path_prefix = (SystemSetting.get('s3_path_prefix') or 'media').strip('/')
    use_path_style = SystemSetting.get('s3_path_style', 'false') == 'true'

    if not all([endpoint, bucket, access_key, secret_key]):
        raise Exception('S3 配置不完整。')

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path' if use_path_style else 'virtual'}),
    )

    normalized_subdir = _normalize_upload_subdir(target_subdir)
    date_folder = datetime.now().strftime('%Y/%m')
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1]
    unique_filename = f'{uuid.uuid4()}{ext}'
    relative_dir = normalized_subdir or date_folder
    s3_path = f'{path_prefix}/{relative_dir}/{unique_filename}'

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    try:
        s3_client.upload_fileobj(file_storage, bucket, s3_path)
    except NoCredentialsError as exc:
        raise Exception('S3 凭证无效。') from exc
    except Exception as exc:
        raise Exception(f'S3 上传失败: {exc}') from exc

    if cdn_domain:
        url = f"https://{cdn_domain.strip('/')}/{s3_path}"
    elif use_path_style:
        url = f"{(endpoint or '').strip('/')}/{bucket}/{s3_path}"
    else:
        parsed = urlparse(endpoint or '')
        url = urlunparse((parsed.scheme or 'https', f'{bucket}.{parsed.netloc}', s3_path, '', '', ''))

    return {
        'filename': filename,
        'unique_filename': unique_filename,
        'storage_type': 's3',
        'path': s3_path,
        'url': url,
        'size': size,
    }


def upload_media_file(file_storage, target_subdir=''):
    storage_type = SystemSetting.get('media_storage_type', 'local')
    upload_result = (
        _upload_to_s3(file_storage, target_subdir=target_subdir)
        if storage_type == 's3'
        else _upload_to_local(file_storage, target_subdir=target_subdir)
    )
    if upload_result['storage_type'] == 'local':
        upload_result['url'] = normalize_local_media_url(upload_result['url'])

    new_image = Image()
    new_image.filename = upload_result['filename']
    new_image.unique_filename = upload_result['unique_filename']
    new_image.storage_type = upload_result['storage_type']
    new_image.path = upload_result['path']
    new_image.url = upload_result['url']
    new_image.size = upload_result['size']
    db.session.add(new_image)
    db.session.commit()
    return upload_result['url']


def _delete_from_local(image):
    try:
        base_upload_dir = current_app.config.get('UPLOADS_DIR') or get_data_subdir('uploads')
        file_path = os.path.join(base_upload_dir, image.path)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        logger.exception('删除本地媒体文件失败: image_id=%s path=%s', getattr(image, 'id', None), getattr(image, 'path', None))
        return False


def _delete_from_s3(image):
    try:
        from botocore.client import Config

        endpoint = SystemSetting.get('s3_endpoint')
        bucket = SystemSetting.get('s3_bucket')
        access_key = SystemSetting.get('s3_access_key')
        secret_key = SystemSetting.get('s3_secret_key')
        use_path_style = SystemSetting.get('s3_path_style', 'false') == 'true'

        if not all([endpoint, bucket, access_key, secret_key]):
            raise Exception('S3 configuration is incomplete.')

        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path' if use_path_style else 'virtual'}),
        )
        s3_client.delete_object(Bucket=bucket, Key=image.path)
        return True
    except Exception:
        logger.exception('删除 S3 媒体文件失败: image_id=%s path=%s', getattr(image, 'id', None), getattr(image, 'path', None))
        return False


def delete_media_file(image):
    return _delete_from_s3(image) if image.storage_type == 's3' else _delete_from_local(image)


def _normalize_reference_value(value):
    raw_value = str(value or '').strip()
    if not raw_value:
        return ''

    parsed = urlparse(raw_value)
    if parsed.scheme and parsed.netloc:
        path_with_query = parsed.path or ''
        if parsed.query:
            path_with_query += f'?{parsed.query}'
        if path_with_query.startswith('/media/'):
            return path_with_query
        normalized_absolute = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, '', parsed.query, ''))
        return normalized_absolute.replace('https://', 'http://')

    if raw_value.startswith('media/'):
        raw_value = f'/{raw_value}'
    return raw_value


def _image_reference_candidates(image_or_data):
    if not image_or_data:
        return []
    url_value = str(getattr(image_or_data, 'url', None) or (image_or_data.get('url') if isinstance(image_or_data, dict) else '') or '').strip()
    path_value = str(getattr(image_or_data, 'path', None) or (image_or_data.get('path') if isinstance(image_or_data, dict) else '') or '').strip()
    candidates = []
    normalized_url = _normalize_reference_value(url_value)
    if normalized_url:
        candidates.append(normalized_url)
    if path_value:
        normalized_media_path = _normalize_reference_value(f"/media/{path_value.lstrip('/')}")
        if normalized_media_path and normalized_media_path not in candidates:
            candidates.append(normalized_media_path)
    return candidates


def _extract_image_references(content):
    references = []
    markdown_urls = re.findall(r'!\[.*?\]\((.*?)\)', content or '')
    html_urls = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\'][^>]*>', content or '', re.IGNORECASE)
    for raw_value in markdown_urls + html_urls:
        normalized = _normalize_reference_value(raw_value)
        if normalized and normalized not in references:
            references.append(normalized)
    return references


def _build_document_usage_map():
    usage_map = {}
    docs_root = get_docs_root()
    if not os.path.exists(docs_root):
        return usage_map

    from .docs import _parse_markdown_file

    for root, _, files in os.walk(docs_root):
        for filename in files:
            if not filename.endswith('.md'):
                continue

            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, docs_root).replace('\\', '/')
            payload = _parse_markdown_file(relative_path)
            if not payload:
                continue

            metadata = payload.get('metadata') or {}
            raw_content = payload.get('raw_content') or ''
            document_url = str(metadata.get('url') or url_for('main.docs_doc', filename=relative_path)).strip()
            document_title = str(metadata.get('title') or os.path.splitext(filename)[0]).strip()
            usage_entry = {
                'label': '文章插图',
                'url': document_url,
                'title': document_title,
            }

            for reference in _extract_image_references(raw_content):
                usage_map.setdefault(reference, [])
                if not any(item.get('url') == usage_entry['url'] for item in usage_map[reference]):
                    usage_map[reference].append(dict(usage_entry))

    return usage_map


def _build_image_usage_items(image_or_data, site_logo, document_usage_map):
    usage_items = []
    normalized_site_logo = _normalize_reference_value(site_logo)
    candidates = _image_reference_candidates(image_or_data)

    if normalized_site_logo and normalized_site_logo in candidates:
        usage_items.append({'label': 'Logo 图片'})

    for candidate in candidates:
        for item in document_usage_map.get(candidate, []):
            if not any(
                existing.get('label') == item.get('label')
                and existing.get('url') == item.get('url')
                for existing in usage_items
            ):
                usage_items.append(dict(item))

    return usage_items


def update_all_image_references():
    docs_root = get_docs_root()
    all_md_files = []
    for root, _, files in os.walk(docs_root):
        for filename in files:
            if filename.endswith('.md'):
                all_md_files.append(os.path.join(root, filename))

    all_referenced_urls = set()
    for md_file in all_md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as file_obj:
                content = file_obj.read()
        except OSError:
            continue
        
        all_referenced_urls.update(_extract_image_references(content))

    site_logo = str(SystemSetting.get('site_logo', '') or '').strip()
    if site_logo:
        all_referenced_urls.add(_normalize_reference_value(site_logo))

    normalized_refs = {url for url in all_referenced_urls if str(url or '').strip()}
    
    for image in Image.query.all():
        local_media_path = f"/media/{str(image.path or '').lstrip('/')}" if image.path else ''
        image.is_referenced = any(
            candidate and candidate in normalized_refs
            for candidate in (
                _normalize_reference_value(image.url),
                _normalize_reference_value(local_media_path),
            )
        )

    db.session.commit()


def get_all_images_with_status():
    db_images = {img.unique_filename: img for img in Image.query.all()}
    storage_images = _get_all_storage_images()
    combined_images = []
    site_logo = str(SystemSetting.get('site_logo', '') or '').strip()
    document_usage_map = _build_document_usage_map()

    for unique_filename, data in storage_images.items():
        if unique_filename in db_images:
            image = db_images.pop(unique_filename)
            display_url = (
                normalize_local_media_url(f"/media/{str(image.path or '').lstrip('/')}")
                if image.storage_type == 'local' and image.path
                else image.url
            )
            usage_items = _build_image_usage_items(image, site_logo, document_usage_map)
            combined_images.append({
                'filename': image.filename,
                'unique_filename': image.unique_filename,
                'display_name': image.unique_filename,
                'url': display_url,
                'is_referenced': image.is_referenced,
                'usage_items': usage_items,
                'usage_labels': [item.get('label') for item in usage_items],
                'status': 'synced',
                'created_at': _serialize_image_datetime(image.created_at) or data.get('created_at'),
            })
        else:
            usage_items = _build_image_usage_items(data, site_logo, document_usage_map)
            combined_images.append({
                'filename': data['filename'],
                'unique_filename': unique_filename,
                'display_name': unique_filename,
                'url': data['url'],
                'is_referenced': bool(usage_items),
                'usage_items': usage_items,
                'usage_labels': [item.get('label') for item in usage_items],
                'status': 'orphan',
                'created_at': data.get('created_at'),
            })

    for unique_filename, image in db_images.items():
        usage_items = _build_image_usage_items(image, site_logo, document_usage_map)
        combined_images.append({
            'filename': image.filename,
            'unique_filename': unique_filename,
            'display_name': unique_filename,
            'url': '#',
            'is_referenced': image.is_referenced,
            'usage_items': usage_items,
            'usage_labels': [item.get('label') for item in usage_items],
            'status': 'db_only',
            'created_at': _serialize_image_datetime(image.created_at),
        })

    return combined_images


def _get_all_storage_images():
    return _get_s3_images() if SystemSetting.get('media_storage_type', 'local') == 's3' else get_local_images()


def get_local_images():
    images = {}
    upload_folder = current_app.config.get('UPLOADS_DIR') or get_data_subdir('uploads')
    if not os.path.exists(upload_folder):
        return images

    for root, _, files in os.walk(upload_folder):
        for filename in files:
            unique_filename = os.path.basename(filename)
            date_folder = os.path.relpath(root, upload_folder).replace('\\', '/')
            file_path = os.path.join(root, filename)
            url = normalize_local_media_url(url_for('main.media_file', filename=f'{date_folder}/{unique_filename}'))
            images[unique_filename] = {
                'filename': filename,
                'url': url,
                'path': os.path.join(date_folder, unique_filename).replace('\\', '/'),
                'created_at': _serialize_timestamp(os.path.getmtime(file_path)),
            }
    return images


def _get_s3_images():
    images = {}
    endpoint = SystemSetting.get('s3_endpoint')
    bucket = SystemSetting.get('s3_bucket')
    access_key = SystemSetting.get('s3_access_key')
    secret_key = SystemSetting.get('s3_secret_key')

    if not all([endpoint, bucket, access_key, secret_key]):
        return images

    s3_client = boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            key = obj['Key']
            unique_filename = os.path.basename(key)
            images[unique_filename] = {
                'filename': unique_filename,
                'url': s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=3600),
                'created_at': _serialize_image_datetime(obj.get('LastModified')),
            }
    return images


def _serialize_image_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _serialize_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).isoformat()
    except (TypeError, ValueError, OSError):
        return None
