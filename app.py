import os
import secrets
import yaml
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from models import db, init_db, User

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        config = {
            'port': 5000,
            'debug': True,
            'database_path': 'sqlite:///app.db'
        }
    return config

def create_app():
    app = Flask(__name__)

    config = load_config()
    
    app.config['APP_CONFIG'] = config
    if config.get('force_https_for_external_urls', False):
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database_path', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    debug_enabled = bool(config.get('debug', True))
    secret_key = os.environ.get('PLANNING_SECRET_KEY') or config.get('secret_key')
    if not secret_key:
        if debug_enabled:
            secret_key = secrets.token_hex(32)
        else:
            raise RuntimeError('生产环境必须配置 secret_key 或 PLANNING_SECRET_KEY')
    app.config['SECRET_KEY'] = secret_key
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    if not debug_enabled:
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True

    # 初始化数据库
    init_db(app)
    CSRFProtect(app)

    # 初始化登录管理器
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore[assignment]

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 注册蓝图
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    return app, config

if __name__ == '__main__':
    app, config = create_app()
    port = config.get('port', 5000)
    debug_enabled = config.get('debug', True)

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

