import os

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import SystemSetting, Image, User, db
from services import (
    InvalidPathError,
    check_permission,
    delete_media_file,
    force_https_url,
    get_all_images_with_status,
    get_local_images,
    normalize_relative_path,
    resolve_docs_path,
    sync_front_matter,
    update_all_image_references,
    upload_media_file,
)
from werkzeug.utils import secure_filename

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _ensure_markdown_filename(filename):
    safe_name = secure_filename((filename or '').strip())
    if not safe_name:
        raise ValueError('文件名不能为空')
    if not safe_name.lower().endswith('.md'):
        safe_name = f'{safe_name}.md'
    return safe_name


def _ensure_directory_name(name):
    safe_name = secure_filename((name or '').strip())
    if not safe_name:
        raise ValueError('目录名不能为空')
    return safe_name


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
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    return jsonify({'content': content})

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
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

    try:
        file_url = upload_media_file(file)
        corrected_url = force_https_url(file_url)
        return jsonify({'success': True, 'url': corrected_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

@api_bp.route('/images/all')
@login_required
def get_all_images():
    if current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403
    images = get_all_images_with_status()
    for image in images:
        image['url'] = force_https_url(image['url'])
    return jsonify({'images': images})

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
    image = Image.query.filter_by(unique_filename=unique_filename).first()

    if status == 'orphan':
        storage_type = SystemSetting.get('media_storage_type', 'local')
        image_path = None
        if storage_type == 'local':
            all_local_images = get_local_images()
            if unique_filename in all_local_images:
                image_path = all_local_images[unique_filename]['path']
            else:
                return jsonify({'error': 'Orphan file not found in local storage.'}), 404
        else: # s3
            image_path = unique_filename

        image_to_delete = Image()
        image_to_delete.storage_type = storage_type
        image_to_delete.path = image_path
        if not delete_media_file(image_to_delete):
            return jsonify({'error': 'Failed to delete orphan file from storage.'}), 500
    
    elif image:
        if image.is_referenced:
            return jsonify({'error': 'Image is in use and cannot be deleted.'}), 400
        
        if not delete_media_file(image):
            return jsonify({'error': 'Failed to delete file from storage.'}), 500
        
        db.session.delete(image)
        db.session.commit()

    else:
        return jsonify({'error': 'Image not found.'}), 404

    return jsonify({'success': True})
