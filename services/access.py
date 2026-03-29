from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app, redirect, request, url_for
from flask_login import current_user

from models import PasswordAccessRule, SystemSetting
from .paths import InvalidPathError, normalize_relative_path


COOKIE_NAME = 'global_access'
COOKIE_PURPOSE = 'global-access'
COOKIE_MAX_AGE = 12 * 60 * 60


def normalize_password_access_target(target_type, target_path):
    normalized_type = str(target_type or 'dir').strip().lower()
    if normalized_type not in {'dir', 'file'}:
        raise ValueError('访问密码规则类型无效')

    raw_path = str(target_path or '').strip().replace('\\', '/')
    if normalized_type == 'dir':
        if raw_path in {'', '/'}:
            return normalized_type, ''
        raw_path = raw_path.rstrip('/')
    try:
        normalized_path = normalize_relative_path(raw_path)
    except InvalidPathError as exc:
        raise ValueError('访问密码规则路径无效') from exc

    if normalized_type == 'file' and not normalized_path.lower().endswith('.md'):
        raise ValueError('访问密码规则文件必须是 Markdown 文档')

    return normalized_type, normalized_path


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='planning-global-access')


def issue_global_access_cookie(response):
    token = str(_get_serializer().dumps({'purpose': COOKIE_PURPOSE}))
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
        samesite=current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax'),
    )
    return response


def has_valid_global_access_cookie():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False

    try:
        data = _get_serializer().loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False

    return data.get('purpose') == COOKIE_PURPOSE


def is_password_visitor_session():
    if getattr(current_user, 'is_authenticated', False):
        return False
    if SystemSetting.get('access_mode', 'open') != 'password_only':
        return False
    global_pwd = SystemSetting.get('global_password', '')
    if not global_pwd:
        return False
    return has_valid_global_access_cookie()


def has_password_rule_access(target_path):
    if not is_password_visitor_session():
        return False

    try:
        normalized_target = normalize_relative_path(target_path)
    except InvalidPathError:
        return False

    for rule in PasswordAccessRule.query.order_by(PasswordAccessRule.target_type.asc(), PasswordAccessRule.target_path.asc()).all():
        rule_path = str(rule.target_path or '').strip().replace('\\', '/').strip('/')
        if rule.target_type == 'file':
            if normalized_target == rule_path:
                return True
            continue

        if not rule_path:
            return True
        if normalized_target == rule_path or normalized_target.startswith(f'{rule_path}/'):
            return True
    return False


def check_global_access():
    access_mode = SystemSetting.get('access_mode', 'open')

    if access_mode == 'password_only':
        global_pwd = SystemSetting.get('global_password', '')
        if global_pwd and not current_user.is_authenticated and not has_valid_global_access_cookie():
            return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path, from_docs=1))

    if access_mode == 'group_only' and not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path, from_docs=1))

    return None
