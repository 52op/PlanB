"""
频率限制服务
用于防止暴力破解和频繁请求攻击
"""
import time
from collections import defaultdict
from threading import Lock

# 内存存储：{ip: {'failures': count, 'last_attempt': timestamp, 'blocked_until': timestamp}}
_login_attempts = defaultdict(lambda: {'failures': 0, 'last_attempt': 0, 'blocked_until': 0})
_lock = Lock()

# 配置
MAX_ATTEMPTS_BEFORE_DELAY = 3  # 3次失败后开始延迟
DELAY_LEVELS = [
    (3, 30),      # 3-5次失败：等待30秒
    (5, 300),     # 5-10次失败：等待5分钟
    (10, 1800),   # 10次以上：等待30分钟
]


def check_rate_limit(ip_address):
    """
    检查 IP 是否被限制
    
    Args:
        ip_address: 客户端 IP 地址
        
    Returns:
        tuple: (is_allowed, wait_seconds, failure_count)
            - is_allowed: 是否允许尝试
            - wait_seconds: 需要等待的秒数（0表示可以立即尝试）
            - failure_count: 当前失败次数
    """
    with _lock:
        now = time.time()
        record = _login_attempts[ip_address]
        
        # 检查是否在封禁期内
        if record['blocked_until'] > now:
            wait_seconds = int(record['blocked_until'] - now)
            return False, wait_seconds, record['failures']
        
        # 已过封禁期，允许尝试
        return True, 0, record['failures']


def record_login_failure(ip_address):
    """
    记录登录失败
    
    Args:
        ip_address: 客户端 IP 地址
        
    Returns:
        tuple: (wait_seconds, failure_count)
            - wait_seconds: 下次尝试需要等待的秒数
            - failure_count: 当前失败次数
    """
    with _lock:
        now = time.time()
        record = _login_attempts[ip_address]
        
        # 增加失败次数
        record['failures'] += 1
        record['last_attempt'] = now
        
        # 计算封禁时间
        failures = record['failures']
        wait_seconds = 0
        
        for threshold, delay in DELAY_LEVELS:
            if failures >= threshold:
                wait_seconds = delay
        
        if wait_seconds > 0:
            record['blocked_until'] = now + wait_seconds
        
        return wait_seconds, failures


def record_login_success(ip_address):
    """
    记录登录成功，清除该 IP 的失败记录
    
    Args:
        ip_address: 客户端 IP 地址
    """
    with _lock:
        if ip_address in _login_attempts:
            del _login_attempts[ip_address]


def get_client_ip(request):
    """
    获取客户端真实 IP 地址
    优先从代理头获取，兜底使用 remote_addr
    
    Args:
        request: Flask request 对象
        
    Returns:
        str: 客户端 IP 地址
    """
    # 尝试从常见的代理头获取真实 IP
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For 可能包含多个 IP，取第一个
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    elif request.headers.get('CF-Connecting-IP'):  # Cloudflare
        return request.headers.get('CF-Connecting-IP')
    else:
        return request.remote_addr or '0.0.0.0'


def format_wait_time(seconds):
    """
    格式化等待时间为人类可读格式
    
    Args:
        seconds: 等待秒数
        
    Returns:
        str: 格式化的时间字符串
    """
    if seconds < 60:
        return f'{seconds} 秒'
    elif seconds < 3600:
        minutes = seconds // 60
        return f'{minutes} 分钟'
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f'{hours} 小时 {minutes} 分钟'
        return f'{hours} 小时'


def cleanup_old_records(max_age_seconds=7200):
    """
    清理过期的记录（可选，用于定期清理内存）
    建议在后台任务中定期调用
    
    Args:
        max_age_seconds: 记录最大保留时间（默认2小时）
    """
    with _lock:
        now = time.time()
        expired_ips = []
        
        for ip, record in _login_attempts.items():
            # 如果记录已经很久没有活动，且不在封禁期内
            if (now - record['last_attempt'] > max_age_seconds and 
                record['blocked_until'] < now):
                expired_ips.append(ip)
        
        for ip in expired_ips:
            del _login_attempts[ip]
        
        return len(expired_ips)
