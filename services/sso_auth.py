"""
SSO 认证服务 — 验证 GoAuth 颁发的 RS256 JWT，并从数据库查找或创建对应用户。
仅在 config.yaml 中 auth_mode = "sso" 时被调用。
"""
import secrets
from typing import Optional

import jwt  # PyJWT
from cryptography.hazmat.primitives.serialization import load_pem_public_key


def load_rsa_public_key(pem_str: str):
    """从 PEM 字符串加载 RSA 公钥（支持 \\n 转义写法）"""
    pem_str = pem_str.replace('\\n', '\n')
    return load_pem_public_key(pem_str.encode())


def verify_sso_token(token: str, public_key, issuer: Optional[str] = None) -> Optional[dict]:
    """
    验证 GoAuth JWT（RS256），返回 payload 或 None。
    GoAuth payload 字段：user_id, username, email, role
    """
    try:
        kwargs: dict = {}
        if issuer:
            kwargs['issuer'] = issuer
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={'require': ['exp', 'sub']},
            **kwargs
        )
        return payload
    except Exception:
        return None


def get_sso_token_from_request(request, cookie_name: str = '_goauth_token') -> Optional[str]:
    """从请求 Cookie 或 Authorization 头提取 token"""
    # Bearer header 优先
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    # Cookie 备用
    return request.cookies.get(cookie_name)


def find_or_create_sso_user(payload: dict, db, User):
    """
    根据 GoAuth JWT payload 查找或创建本地用户。
    - 优先以 email 匹配
    - 若无 email，以 username 匹配
    - 若不存在，创建新用户（密码随机，不可用于本地登录）
    """
    email = (payload.get('email') or '').strip().lower() or None
    username = (payload.get('username') or str(payload.get('user_id', ''))).strip()
    role_raw = payload.get('role', 'user')
    # GoAuth role 映射到 planB role
    role = 'admin' if role_raw == 'admin' else 'regular'

    user = None
    if email:
        user = User.query.filter_by(email=email).first()
    if user is None and username:
        user = User.query.filter_by(username=username).first()

    if user is None:
        # 首次 SSO 登录：自动创建本地影子账户
        # 用户名冲突时加后缀
        base_username = username or (email.split('@')[0] if email else 'sso_user')
        final_username = base_username
        suffix = 1
        while User.query.filter_by(username=final_username).first():
            final_username = f'{base_username}_{suffix}'
            suffix += 1

        user = User(
            username=final_username,
            email=email,
            role=role,
            email_verified=True,
        )
        user.set_password(secrets.token_hex(32))  # 随机密码，不可本地登录
        db.session.add(user)
        db.session.commit()
    else:
        # 同步角色（GoAuth 是权威来源）
        changed = False
        if user.role != role:
            user.role = role
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if changed:
            db.session.commit()

    return user
