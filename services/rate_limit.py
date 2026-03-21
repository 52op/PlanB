"""
频率限制服务
默认使用数据库持久化，支持可选 Redis 后端。
"""
from datetime import datetime, timedelta
import time

from sqlalchemy import or_

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None


DEFAULT_DELAY_LEVELS = [
    (3, 30),
    (5, 300),
    (10, 1800),
]

DEFAULT_SEND_DELAY_LEVELS = [
    (5, 600),
    (10, 3600),
    (20, 86400),
]


def _safe_int(value, default, minimum=None):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        parsed = default
    if minimum is not None and parsed < minimum:
        return minimum
    return parsed


def _get_models():
    from models import RateLimitAttempt, SystemSetting, db

    return RateLimitAttempt, SystemSetting, db


def _get_setting(key, default=None):
    _, SystemSetting, _ = _get_models()
    return SystemSetting.get(key, default)


def _is_bucket_enabled(bucket_type):
    key_map = {
        'login': 'security_login_rate_limit_enabled',
        'verification': 'security_verification_rate_limit_enabled',
        'verification_send_ip': 'security_verification_send_rate_limit_enabled',
        'verification_send_email': 'security_verification_send_rate_limit_enabled',
    }
    setting_key = key_map.get(bucket_type)
    if not setting_key:
        return True
    return (_get_setting(setting_key, 'true') or 'true').strip().lower() != 'false'


def _load_delay_levels(bucket_type='login'):
    if bucket_type in {'verification_send_ip', 'verification_send_email'}:
        defaults = DEFAULT_SEND_DELAY_LEVELS
        attempts_keys = [
            'security_send_rate_limit_level1_attempts',
            'security_send_rate_limit_level2_attempts',
            'security_send_rate_limit_level3_attempts',
        ]
        seconds_keys = [
            'security_send_rate_limit_level1_seconds',
            'security_send_rate_limit_level2_seconds',
            'security_send_rate_limit_level3_seconds',
        ]
    else:
        defaults = DEFAULT_DELAY_LEVELS
        attempts_keys = [
            'security_rate_limit_level1_attempts',
            'security_rate_limit_level2_attempts',
            'security_rate_limit_level3_attempts',
        ]
        seconds_keys = [
            'security_rate_limit_level1_seconds',
            'security_rate_limit_level2_seconds',
            'security_rate_limit_level3_seconds',
        ]

    configured = [
        (
            _safe_int(_get_setting(attempts_keys[0], defaults[0][0]), defaults[0][0], minimum=1),
            _safe_int(_get_setting(seconds_keys[0], defaults[0][1]), defaults[0][1], minimum=0),
        ),
        (
            _safe_int(_get_setting(attempts_keys[1], defaults[1][0]), defaults[1][0], minimum=1),
            _safe_int(_get_setting(seconds_keys[1], defaults[1][1]), defaults[1][1], minimum=0),
        ),
        (
            _safe_int(_get_setting(attempts_keys[2], defaults[2][0]), defaults[2][0], minimum=1),
            _safe_int(_get_setting(seconds_keys[2], defaults[2][1]), defaults[2][1], minimum=0),
        ),
    ]
    return sorted(configured, key=lambda item: item[0])


def _get_record_ttl_seconds():
    return _safe_int(_get_setting('security_rate_limit_record_ttl_seconds', '7200'), 7200, minimum=300)


def _get_backend_preference():
    backend = (_get_setting('security_rate_limit_backend', 'database') or 'database').strip().lower()
    return 'redis' if backend == 'redis' else 'database'


def _get_redis_key_prefix():
    return ((_get_setting('security_redis_key_prefix', 'planning:rate-limit') or 'planning:rate-limit').strip() or 'planning:rate-limit')


def _create_redis_client(test_connection=False):
    redis_url = (_get_setting('security_redis_url', '') or '').strip()
    if not redis_url:
        return None, '未配置 Redis 连接地址'
    if redis_lib is None:
        return None, '未安装 redis Python 依赖'
    try:
        client = redis_lib.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        if test_connection:
            client.ping()
        return client, None
    except Exception as exc:
        return None, str(exc)


def _resolve_active_backend():
    preferred_backend = _get_backend_preference()
    if preferred_backend != 'redis':
        return 'database', None
    client, error_message = _create_redis_client(test_connection=False)
    if client is None:
        return 'database', error_message
    return 'redis', client


def _build_redis_key(bucket_type, scope_key):
    return f'{_get_redis_key_prefix()}:{bucket_type}:{scope_key}'


def _calculate_wait_seconds(failures, bucket_type='login'):
    wait_seconds = 0
    for threshold, delay in _load_delay_levels(bucket_type):
        if failures >= threshold:
            wait_seconds = delay
    return wait_seconds


def _check_database_rate_limit(bucket_type, scope_key):
    RateLimitAttempt, _, _ = _get_models()
    record = RateLimitAttempt.query.filter_by(bucket_type=bucket_type, scope_key=scope_key).first()
    if not record:
        return True, 0, 0
    now = datetime.utcnow()
    blocked_until = record.blocked_until
    if blocked_until and blocked_until > now:
        wait_seconds = max(1, int((blocked_until - now).total_seconds()))
        return False, wait_seconds, record.failures or 0
    return True, 0, record.failures or 0


def _record_database_failure(bucket_type, scope_key):
    RateLimitAttempt, _, db = _get_models()
    now = datetime.utcnow()
    record = RateLimitAttempt.query.filter_by(bucket_type=bucket_type, scope_key=scope_key).first()
    if not record:
        record = RateLimitAttempt(bucket_type=bucket_type, scope_key=scope_key)
        db.session.add(record)
        record.failures = 0
    record.failures = (record.failures or 0) + 1
    record.last_attempt_at = now
    wait_seconds = _calculate_wait_seconds(record.failures, bucket_type)
    record.blocked_until = now + timedelta(seconds=wait_seconds) if wait_seconds > 0 else None
    db.session.commit()
    return wait_seconds, record.failures


def _record_database_success(bucket_type, scope_key):
    RateLimitAttempt, _, db = _get_models()
    record = RateLimitAttempt.query.filter_by(bucket_type=bucket_type, scope_key=scope_key).first()
    if record:
        db.session.delete(record)
        db.session.commit()


def _check_redis_rate_limit(bucket_type, scope_key, client):
    now = time.time()
    key = _build_redis_key(bucket_type, scope_key)
    record = client.hgetall(key)
    if not record:
        return True, 0, 0
    failures = _safe_int(record.get('failures', 0), 0, minimum=0)
    blocked_until = float(record.get('blocked_until', 0) or 0)
    if blocked_until > now:
        wait_seconds = max(1, int(blocked_until - now))
        return False, wait_seconds, failures
    return True, 0, failures


def _record_redis_failure(bucket_type, scope_key, client):
    now = time.time()
    key = _build_redis_key(bucket_type, scope_key)
    ttl_seconds = _get_record_ttl_seconds()
    record = client.hgetall(key)
    failures = _safe_int(record.get('failures', 0), 0, minimum=0) + 1
    wait_seconds = _calculate_wait_seconds(failures, bucket_type)
    blocked_until = now + wait_seconds if wait_seconds > 0 else 0
    client.hset(
        key,
        mapping={
            'failures': failures,
            'last_attempt': now,
            'blocked_until': blocked_until,
        },
    )
    client.expire(key, ttl_seconds)
    return wait_seconds, failures


def _record_redis_success(bucket_type, scope_key, client):
    key = _build_redis_key(bucket_type, scope_key)
    client.delete(key)


def _check_bucket_rate_limit(bucket_type, scope_key):
    if not _is_bucket_enabled(bucket_type):
        return True, 0, 0
    backend, backend_payload = _resolve_active_backend()
    if backend == 'redis':
        try:
            return _check_redis_rate_limit(bucket_type, scope_key, backend_payload)
        except Exception:
            return _check_database_rate_limit(bucket_type, scope_key)
    return _check_database_rate_limit(bucket_type, scope_key)


def _record_bucket_failure(bucket_type, scope_key):
    if not _is_bucket_enabled(bucket_type):
        return 0, 0
    backend, backend_payload = _resolve_active_backend()
    if backend == 'redis':
        try:
            return _record_redis_failure(bucket_type, scope_key, backend_payload)
        except Exception:
            return _record_database_failure(bucket_type, scope_key)
    return _record_database_failure(bucket_type, scope_key)


def _record_bucket_success(bucket_type, scope_key):
    if not _is_bucket_enabled(bucket_type):
        return
    backend, backend_payload = _resolve_active_backend()
    if backend == 'redis':
        try:
            _record_redis_success(bucket_type, scope_key, backend_payload)
            return
        except Exception:
            pass
    _record_database_success(bucket_type, scope_key)


def check_rate_limit(ip_address):
    """
    检查密码/全局密码登录是否被限制
    """
    return _check_bucket_rate_limit('login', ip_address)


def record_login_failure(ip_address):
    """
    记录登录失败
    """
    return _record_bucket_failure('login', ip_address)


def record_login_success(ip_address):
    """
    记录登录成功
    """
    _record_bucket_success('login', ip_address)


def build_verification_scope_key(ip_address, email, purpose='register'):
    """
    构造验证码校验限流范围键
    """
    normalized_ip = (ip_address or '0.0.0.0').strip() or '0.0.0.0'
    normalized_email = (email or '').strip().lower()
    normalized_purpose = (purpose or 'register').strip().lower() or 'register'
    return f'{normalized_ip}|{normalized_email}|{normalized_purpose}'


def check_verification_rate_limit(scope_key):
    """
    检查验证码输入是否被限制
    """
    return _check_bucket_rate_limit('verification', scope_key)


def record_verification_failure(scope_key):
    """
    记录验证码校验失败
    """
    return _record_bucket_failure('verification', scope_key)


def record_verification_success(scope_key):
    """
    记录验证码校验成功
    """
    _record_bucket_success('verification', scope_key)


def build_verification_send_scope_key(ip_address=None, email=None, purpose='register', scope_type='ip'):
    """
    构造验证码发送限流范围键
    """
    normalized_purpose = (purpose or 'register').strip().lower() or 'register'
    if scope_type == 'email':
        normalized_email = (email or '').strip().lower()
        return f'{normalized_email}|{normalized_purpose}'
    normalized_ip = (ip_address or '0.0.0.0').strip() or '0.0.0.0'
    return f'{normalized_ip}|{normalized_purpose}'


def check_verification_send_rate_limit(ip_address, email, purpose='register'):
    """
    检查验证码发送是否过于频繁
    """
    ip_scope_key = build_verification_send_scope_key(ip_address=ip_address, purpose=purpose, scope_type='ip')
    email_scope_key = build_verification_send_scope_key(email=email, purpose=purpose, scope_type='email')

    ip_allowed, ip_wait_seconds, ip_failure_count = _check_bucket_rate_limit('verification_send_ip', ip_scope_key)
    if not ip_allowed:
        return False, ip_wait_seconds, ip_failure_count, 'ip'

    email_allowed, email_wait_seconds, email_failure_count = _check_bucket_rate_limit('verification_send_email', email_scope_key)
    if not email_allowed:
        return False, email_wait_seconds, email_failure_count, 'email'

    return True, 0, max(ip_failure_count, email_failure_count), None


def record_verification_send_attempt(ip_address, email, purpose='register'):
    """
    记录一次验证码发送行为
    """
    ip_scope_key = build_verification_send_scope_key(ip_address=ip_address, purpose=purpose, scope_type='ip')
    email_scope_key = build_verification_send_scope_key(email=email, purpose=purpose, scope_type='email')
    ip_wait_seconds, ip_failure_count = _record_bucket_failure('verification_send_ip', ip_scope_key)
    email_wait_seconds, email_failure_count = _record_bucket_failure('verification_send_email', email_scope_key)
    return max(ip_wait_seconds, email_wait_seconds), max(ip_failure_count, email_failure_count)


def get_client_ip(request):
    """
    获取客户端真实 IP 地址
    """
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    if request.headers.get('CF-Connecting-IP'):
        return request.headers.get('CF-Connecting-IP')
    return request.remote_addr or '0.0.0.0'


def format_wait_time(seconds):
    """
    格式化等待时间为人类可读格式
    """
    if seconds < 60:
        return f'{seconds} 秒'
    if seconds < 3600:
        minutes = seconds // 60
        return f'{minutes} 分钟'
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if minutes > 0:
        return f'{hours} 小时 {minutes} 分钟'
    return f'{hours} 小时'


def get_rate_limit_backend_status():
    """
    返回后台安全设置页需要的限流状态信息
    """
    preferred_backend = _get_backend_preference()
    if preferred_backend == 'redis':
        client, error_message = _create_redis_client(test_connection=True)
        if client is not None:
            return {
                'preferred_backend': 'redis',
                'active_backend': 'redis',
                'redis_available': True,
                'message': 'Redis 连接正常，限流将优先写入 Redis。',
            }
        return {
            'preferred_backend': 'redis',
            'active_backend': 'database',
            'redis_available': False,
            'message': f'Redis 当前不可用，运行时会自动回退到数据库。原因：{error_message}',
        }
    return {
        'preferred_backend': 'database',
        'active_backend': 'database',
        'redis_available': redis_lib is not None,
        'message': '当前使用数据库持久化限流，支持多线程、多进程共享计数。',
    }


def cleanup_old_records(max_age_seconds=None):
    """
    清理过期的数据库限流记录
    """
    RateLimitAttempt, _, db = _get_models()
    ttl_seconds = _get_record_ttl_seconds() if max_age_seconds is None else max(300, int(max_age_seconds))
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=ttl_seconds)
    query = RateLimitAttempt.query.filter(
        RateLimitAttempt.last_attempt_at < cutoff,
        or_(RateLimitAttempt.blocked_until.is_(None), RateLimitAttempt.blocked_until < now),
    )
    deleted_count = query.count()
    if deleted_count:
        query.delete(synchronize_session=False)
        db.session.commit()
    return deleted_count
