import os
import secrets
import sys
import yaml
from flask import Flask, request
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, init_db, User
from runtime_paths import (
    get_config_path,
    get_data_dir,
    get_data_subdir,
    normalize_database_uri,
)

def _coerce_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return default


def _build_default_config():
    return {
        'port': 5000,
        'debug': False if getattr(sys, 'frozen', False) else True,
        'database_path': '',
        'secret_key': secrets.token_hex(32),
        'timezone': 'Asia/Shanghai',
        'cookie_secure': False,
    }


def _save_config(config_path, config):
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def _request_is_secure():
    forwarded_proto = str(request.headers.get('X-Forwarded-Proto') or '').strip().lower()
    if forwarded_proto:
        return forwarded_proto == 'https'
    return bool(request.is_secure)


def _is_local_host(host_value):
    host = str(host_value or '').strip().lower()
    if not host:
        return False
    if ':' in host:
        host = host.split(':', 1)[0]
    return host in {'127.0.0.1', 'localhost', '::1'}


def load_config():
    config_path = get_config_path()
    default_config = _build_default_config()
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f) or {}
        config = dict(default_config)
        config.update(loaded)
        should_persist = False
        if 'secret_key' not in loaded or not str(loaded.get('secret_key') or '').strip():
            config['secret_key'] = secrets.token_hex(32)
            should_persist = True
        if 'debug' not in loaded:
            should_persist = True
        if should_persist:
            _save_config(config_path, config)
    else:
        config = dict(default_config)
        _save_config(config_path, config)
    return config

def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)  # type: ignore[assignment]

    config = load_config()
    data_dir = get_data_dir()
    uploads_dir = get_data_subdir('uploads')
    get_data_subdir('jobs')
    get_data_subdir('covers')
    
    app.config['APP_CONFIG'] = config
    app.config['APP_TIMEZONE'] = config.get('timezone', 'Asia/Shanghai')
    app.config['DATA_DIR'] = data_dir
    app.config['UPLOADS_DIR'] = uploads_dir
    if config.get('force_https_for_external_urls', False):
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_uri(config.get('database_path'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    debug_enabled = _coerce_bool(config.get('debug', True), default=True)
    cookie_secure_enabled = _coerce_bool(config.get('cookie_secure', False), default=False)
    secret_key = os.environ.get('PLANNING_SECRET_KEY') or config.get('secret_key')
    if not secret_key:
        if debug_enabled:
            secret_key = secrets.token_hex(32)
        else:
            raise RuntimeError('生产环境必须配置 secret_key 或 PLANNING_SECRET_KEY')
    app.config['SECRET_KEY'] = secret_key
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600 * 4  # 4小时，平衡安全性和用户体验
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = cookie_secure_enabled
    app.config['REMEMBER_COOKIE_SECURE'] = cookie_secure_enabled
    app.config['COOKIE_SECURE_WARNING_PRINTED'] = False

    # 初始化数据库
    init_db(app)
    CSRFProtect(app)

    # 初始化登录管理器
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore[assignment]

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def warn_insecure_cookie_usage():
        if not app.config.get('SESSION_COOKIE_SECURE'):
            return None
        if app.config.get('COOKIE_SECURE_WARNING_PRINTED'):
            return None
        if _request_is_secure():
            return None
        if _is_local_host(request.host):
            return None
        app.config['COOKIE_SECURE_WARNING_PRINTED'] = True
        print(
            "[planning] WARNING: Detected HTTP access from a non-local address "
            f"({request.host}). cookie_secure=true may prevent session cookies "
            "from being sent, which can cause login/CSRF failures. If you are "
            "using LAN HTTP access, set cookie_secure: false in data/config.yaml "
            "or switch the site to HTTPS."
        )
        return None
    
    # IP 访问控制中间件
    @app.before_request
    def check_ip_access():
        from services.ip_access_control import ip_access_control_middleware
        return ip_access_control_middleware()

    # 注册蓝图
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # 初始化备份调度器
    from services.backup_scheduler import BackupScheduler
    backup_scheduler = BackupScheduler(app)
    backup_scheduler.start()
    app.config['BACKUP_SCHEDULER'] = backup_scheduler

    return app, config

if __name__ == '__main__':
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='Planning 文档&博客系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python app.py                         # 正常启动应用
  python app.py --update-db             # 检查并同步数据库结构
  python app.py --update-db --yes       # 自动同步（不询问确认）
  python app.py --disable-ip-control    # 禁用 IP 访问控制（紧急恢复）
        """
    )
    parser.add_argument('--update-db', action='store_true',
                       help='检查并同步数据库结构（对比 models.py 和现有数据库）')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='自动确认所有操作（与 --update-db 配合使用）')
    parser.add_argument('--disable-ip-control', action='store_true',
                       help='禁用 IP 访问控制（白名单、黑名单、共享密钥），用于紧急恢复访问')
    
    args = parser.parse_args()
    
    # 如果指定了 --disable-ip-control，禁用 IP 访问控制
    if args.disable_ip_control:
        print("\n⚠️  紧急恢复模式：正在禁用 IP 访问控制...\n")
        app, config = create_app()
        
        with app.app_context():
            from models import SystemSetting
            
            # 禁用所有 IP 访问控制
            SystemSetting.set('security_ip_whitelist_enabled', 'false')
            SystemSetting.set('security_ip_blacklist_enabled', 'false')
            SystemSetting.set('security_shared_secret_enabled', 'false')
            
            print("✓ 已禁用 IP 白名单")
            print("✓ 已禁用 IP 黑名单")
            print("✓ 已禁用共享密钥验证")
            print("\n✅ IP 访问控制已全部禁用，现在可以正常访问系统了。")
            print("   请访问 /admin/security 重新配置访问控制。\n")
        
        sys.exit(0)
    
    # 如果指定了 --update-db，执行数据库同步
    if args.update_db:
        from db_sync import (
            get_model_tables, 
            get_database_tables, 
            compare_structures,
            print_differences,
            generate_sync_sql,
            execute_sync
        )
        
        print("\n🔍 正在分析数据库结构...\n")
        app, config = create_app()
        
        with app.app_context():
            # 获取模型和数据库结构
            model_tables = get_model_tables()
            db_tables = get_database_tables(db.engine)
            
            # 对比差异
            differences = compare_structures(model_tables, db_tables)
            
            # 打印差异报告
            has_diff = print_differences(differences)
            
            if not has_diff:
                sys.exit(0)
            
            # 生成同步 SQL
            sql_statements = generate_sync_sql(differences)
            
            # 预览 SQL
            print("="*60)
            print("将要执行的 SQL 语句")
            print("="*60 + "\n")
            for sql in sql_statements:
                print(sql)
            
            # 确认执行
            if not args.yes:
                confirm = input("\n⚠️  确定要执行数据库同步吗？建议先备份数据库。(yes/no): ")
                if confirm.lower() not in ['yes', 'y']:
                    print("❌ 已取消同步操作。\n")
                    sys.exit(1)
            
            # 执行同步
            success = execute_sync(app, sql_statements)
            sys.exit(0 if success else 1)
    
    # 正常启动应用
    app, config = create_app()
    port = config.get('port', 5000)
    debug_enabled = _coerce_bool(config.get('debug', True), default=True)

    print(f"准备启动planning文档&博客系统")
    if app.config.get('SESSION_COOKIE_SECURE'):
        print(
            "[planning] 启用了 cookie_secure=true。如果你通过普通的 HTTP 访问该网站，"
            "例如使用局域网地址 http://192.168.x.x，"
            "登录和 CSRF 验证可能会失败。请使用 HTTPS 或在 data/config.yaml 中设置 "
            "cookie_secure: false。"
        )
    else:
        print(
            "[planning] 当前使用 cookie_secure=false，适合本机或局域网 HTTP 访问。"
            "如果你后续启用对外 HTTPS/SSL，请记得在 data/config.yaml 中改为 "
            "cookie_secure: true，以保护登录会话 Cookie。"
        )
    if debug_enabled:
        # 开发模式：使用 Flask 自带服务器
        print(f"[开发模式] 启动 Flask 开发服务器: http://0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        # 生产模式：使用 Waitress
        try:
            from waitress import serve
            print(f"[生产模式] 启动 Waitress 服务器: http://0.0.0.0:{port}")
            print(f"线程数: 4, 连接队列: 16")
            serve(app, host='0.0.0.0', port=port, threads=4, channel_timeout=60)
        except ImportError:
            print("[警告] 未安装 waitress，回退到 Flask 开发服务器")
            print("请运行: pip install waitress")
            app.run(host='0.0.0.0', port=port, debug=False)
