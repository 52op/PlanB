import os
import re
import uuid
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.exceptions import NoCredentialsError
from flask import current_app, url_for
from werkzeug.utils import secure_filename

from models import Image, SystemSetting, db


def _upload_to_local(file_storage):
    date_folder = datetime.now().strftime('%Y/%m')
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1]
    unique_filename = f'{uuid.uuid4()}{ext}'

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', date_folder)
    os.makedirs(upload_folder, exist_ok=True)

    save_path = os.path.join(upload_folder, unique_filename)
    file_storage.save(save_path)

    url = url_for('main.media_file', filename=f'{date_folder}/{unique_filename}', _external=True)
    return {
        'filename': filename,
        'unique_filename': unique_filename,
        'storage_type': 'local',
        'path': os.path.join(date_folder, unique_filename).replace('\\', '/'),
        'url': url,
        'size': size,
    }


def _upload_to_s3(file_storage):
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

    date_folder = datetime.now().strftime('%Y/%m')
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1]
    unique_filename = f'{uuid.uuid4()}{ext}'
    s3_path = f'{path_prefix}/{date_folder}/{unique_filename}'

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


def upload_media_file(file_storage):
    storage_type = SystemSetting.get('media_storage_type', 'local')
    upload_result = _upload_to_s3(file_storage) if storage_type == 's3' else _upload_to_local(file_storage)

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
        file_path = os.path.join(current_app.root_path, 'static', 'uploads', image.path)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
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
        return False


def delete_media_file(image):
    return _delete_from_s3(image) if image.storage_type == 's3' else _delete_from_local(image)


def update_all_image_references():
    docs_dir_name = SystemSetting.get('docs_dir', 'jobs') or 'jobs'
    docs_root = os.path.abspath(os.path.join(current_app.root_path, docs_dir_name))
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
        
        # 匹配 Markdown 语法: ![...](url)
        markdown_urls = re.findall(r'!\[.*?\]\((.*?)\)', content)
        all_referenced_urls.update(markdown_urls)
        
        # 匹配 HTML img 标签: <img src="url" ...>
        html_urls = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\'][^>]*>', content)
        all_referenced_urls.update(html_urls)

    # 标准化URL以忽略协议差异（http vs https）
    def normalize_url(url):
        return url.replace('https://', 'http://')
    
    normalized_refs = {normalize_url(url) for url in all_referenced_urls}
    
    for image in Image.query.all():
        normalized_image_url = normalize_url(image.url)
        image.is_referenced = normalized_image_url in normalized_refs

    db.session.commit()


def get_all_images_with_status():
    db_images = {img.unique_filename: img for img in Image.query.all()}
    storage_images = _get_all_storage_images()
    combined_images = []

    for unique_filename, data in storage_images.items():
        if unique_filename in db_images:
            image = db_images.pop(unique_filename)
            combined_images.append({
                'filename': image.filename,
                'unique_filename': image.unique_filename,
                'url': image.url,
                'is_referenced': image.is_referenced,
                'status': 'synced',
            })
        else:
            combined_images.append({
                'filename': data['filename'],
                'unique_filename': unique_filename,
                'url': data['url'],
                'is_referenced': False,
                'status': 'orphan',
            })

    for unique_filename, image in db_images.items():
        combined_images.append({
            'filename': image.filename,
            'unique_filename': unique_filename,
            'url': '#',
            'is_referenced': image.is_referenced,
            'status': 'db_only',
        })

    return combined_images


def _get_all_storage_images():
    return _get_s3_images() if SystemSetting.get('media_storage_type', 'local') == 's3' else get_local_images()


def get_local_images():
    images = {}
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    if not os.path.exists(upload_folder):
        return images

    for root, _, files in os.walk(upload_folder):
        for filename in files:
            unique_filename = os.path.basename(filename)
            date_folder = os.path.relpath(root, upload_folder).replace('\\', '/')
            url = url_for('main.media_file', filename=f'{date_folder}/{unique_filename}', _external=True)
            images[unique_filename] = {
                'filename': filename,
                'url': url,
                'path': os.path.join(date_folder, unique_filename).replace('\\', '/'),
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
            }
    return images
