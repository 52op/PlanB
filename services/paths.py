import os

from flask import current_app

from models import SystemSetting


class InvalidPathError(ValueError):
    pass


def get_docs_root():
    docs_dir_name = SystemSetting.get('docs_dir', 'jobs')
    docs_root = os.path.abspath(os.path.join(current_app.root_path, docs_dir_name))
    os.makedirs(docs_root, exist_ok=True)
    return docs_root


def normalize_relative_path(path_value):
    raw_value = (path_value or '').replace('\\', '/').strip()
    if raw_value in ('', '.'):
        return ''
    normalized = os.path.normpath(raw_value).replace('\\', '/')
    if normalized.startswith('../') or normalized == '..' or os.path.isabs(raw_value):
        raise InvalidPathError('非法路径')
    if normalized == '.':
        return ''
    return normalized.lstrip('/')


def resolve_docs_path(relative_path='', allow_directory=False, create_directory=False):
    docs_root = get_docs_root()
    normalized = normalize_relative_path(relative_path)
    absolute_path = os.path.abspath(os.path.join(docs_root, normalized))

    if absolute_path != docs_root and not absolute_path.startswith(docs_root + os.sep):
        raise InvalidPathError('非法路径')

    if create_directory and allow_directory:
        os.makedirs(absolute_path, exist_ok=True)

    return docs_root, normalized, absolute_path
