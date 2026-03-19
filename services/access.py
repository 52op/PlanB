from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app, redirect, request, url_for
from flask_login import current_user

from models import SystemSetting


COOKIE_NAME = 'global_access'
COOKIE_PURPOSE = 'global-access'
COOKIE_MAX_AGE = 12 * 60 * 60


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


def check_global_access():
    access_mode = SystemSetting.get('access_mode', 'open')

    if access_mode == 'password_only':
        global_pwd = SystemSetting.get('global_password', '')
        if global_pwd and not current_user.is_authenticated and not has_valid_global_access_cookie():
            return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path, from_docs=1))

    if access_mode == 'group_only' and not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.full_path if request.query_string else request.path, from_docs=1))

    return None
