import os
import sys
from pathlib import Path


def ensure_directory(path):
    absolute_path = os.path.abspath(str(path))
    os.makedirs(absolute_path, exist_ok=True)
    return absolute_path


def get_runtime_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    custom_dir = os.environ.get('PLANNING_DATA_DIR')
    if custom_dir:
        expanded_dir = os.path.expandvars(os.path.expanduser(custom_dir))
        return ensure_directory(expanded_dir)
    return ensure_directory(os.path.join(get_runtime_base_dir(), 'data'))


def get_data_subdir(name):
    normalized_name = str(name or '').strip().strip('/\\')
    if not normalized_name:
        return get_data_dir()
    return ensure_directory(os.path.join(get_data_dir(), normalized_name))


def resolve_data_path(path_value, default_subdir=''):
    raw_value = str(path_value or '').strip()
    if not raw_value:
        return get_data_subdir(default_subdir) if default_subdir else get_data_dir()

    expanded_value = os.path.expandvars(os.path.expanduser(raw_value))
    if os.path.isabs(expanded_value):
        return os.path.abspath(expanded_value)

    return os.path.abspath(os.path.join(get_data_dir(), expanded_value))


def get_config_path():
    return os.path.join(get_data_dir(), 'config.yaml')


def get_default_database_path():
    return os.path.join(get_data_dir(), 'app.db')


def build_sqlite_uri(path):
    return f"sqlite:///{Path(path).resolve().as_posix()}"


def normalize_database_uri(uri):
    raw_uri = str(uri or '').strip()
    if not raw_uri:
        return build_sqlite_uri(get_default_database_path())

    if raw_uri.startswith('sqlite:///'):
        sqlite_path = raw_uri[len('sqlite:///'):]
        expanded_path = os.path.expandvars(os.path.expanduser(sqlite_path))
        if not os.path.isabs(expanded_path):
            expanded_path = os.path.join(get_data_dir(), expanded_path)
        return build_sqlite_uri(expanded_path)

    return raw_uri
