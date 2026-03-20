import os
import secrets
from datetime import datetime

from models import ShareLink
from .paths import InvalidPathError, normalize_relative_path, resolve_docs_path


def build_share_session_key(token):
    return f'share_access:{token}'


def generate_share_token():
    return secrets.token_urlsafe(18)


def get_share_link_by_token(token):
    return ShareLink.query.filter_by(token=(token or '').strip()).first()


def is_share_expired(share_link, now=None):
    if not share_link or share_link.expires_at is None:
        return False
    current_time = now or datetime.utcnow()
    return share_link.expires_at <= current_time


def resolve_shared_path(share_link, relative_path=''):
    if share_link is None:
        raise InvalidPathError('分享不存在')

    if share_link.target_type not in {'file', 'dir'}:
        raise InvalidPathError('无效的分享类型')

    if share_link.target_type == 'file':
        if relative_path:
            raise InvalidPathError('文件分享不支持子路径')
        _, normalized_path, absolute_path = resolve_docs_path(share_link.target_path)
        return normalized_path, absolute_path, ''

    requested_relative = normalize_relative_path(relative_path)
    base_dir = (share_link.target_path or '').strip('/')
    if requested_relative:
        combined_path = f'{base_dir}/{requested_relative}' if base_dir else requested_relative
    else:
        combined_path = base_dir

    _, normalized_path, absolute_path = resolve_docs_path(combined_path, allow_directory=True)
    if base_dir and normalized_path != base_dir and not normalized_path.startswith(base_dir + '/'):
        raise InvalidPathError('超出分享目录范围')
    return normalized_path, absolute_path, requested_relative


def build_share_title(target_type, target_path, explicit_title=''):
    title = (explicit_title or '').strip()
    if title:
        return title

    normalized_path = (target_path or '').replace('\\', '/').strip('/')
    if not normalized_path:
        return '根目录'

    name = os.path.basename(normalized_path)
    if target_type == 'file':
        return os.path.splitext(name)[0] or normalized_path
    return name or normalized_path
