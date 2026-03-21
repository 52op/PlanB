import os
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key, default=None):
        setting = SystemSetting.query.get(key)
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = SystemSetting.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = SystemSetting()
            setting.key = key
            setting.value = value
            db.session.add(setting)
        db.session.commit()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nickname = db.Column(db.String(80), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='regular') # admin, regular, guest
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    can_comment = db.Column(db.Boolean, nullable=False, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class DirectoryConfig(db.Model):
    __tablename__ = 'directory_configs'
    id = db.Column(db.Integer, primary_key=True)
    dir_path = db.Column(db.String(255), unique=True, nullable=False) # e.g., '/' or 'tech/'
    default_open_file = db.Column(db.String(255), nullable=True) # e.g., 'intro.md'
    sort_rule = db.Column(db.String(50), nullable=True, default='asc') # asc, desc, manual

class PermissionRule(db.Model):
    __tablename__ = 'permission_rules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dir_path = db.Column(db.String(255), nullable=False) # '*' meaning all, or specific path
    can_read = db.Column(db.Boolean, default=True)
    can_edit = db.Column(db.Boolean, default=False)
    can_upload = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('permissions', lazy=True))

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    unique_filename = db.Column(db.String(255), unique=True, nullable=False)
    storage_type = db.Column(db.String(50), nullable=False, default='local') # local or s3
    path = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_referenced = db.Column(db.Boolean, default=False)


class DocumentViewStat(db.Model):
    __tablename__ = 'document_view_stats'
    filename = db.Column(db.String(255), primary_key=True)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())


class ShareLink(db.Model):
    __tablename__ = 'share_links'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    target_type = db.Column(db.String(10), nullable=False)  # file / dir
    target_path = db.Column(db.String(255), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    allow_edit = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    created_by = db.relationship('User', backref=db.backref('share_links', lazy=True))

    def set_password(self, password):
        password_value = (password or '').strip()
        self.password_hash = generate_password_hash(password_value) if password_value else None

    def check_password(self, password):
        if not self.password_hash:
            return True
        return check_password_hash(self.password_hash, (password or '').strip())

    @property
    def is_password_protected(self):
        return bool(self.password_hash)


class EmailVerificationCode(db.Model):
    __tablename__ = 'email_verification_codes'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    code = db.Column(db.String(12), nullable=False)
    purpose = db.Column(db.String(32), nullable=False, default='register')
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    approval_token = db.Column(db.String(64), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    target = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


def _ensure_column(app, table_name, column_name, column_sql):
    inspector = db.inspect(db.engine)
    column_names = {column['name'] for column in inspector.get_columns(table_name)}
    if column_name in column_names:
        return
    with db.engine.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}')

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _ensure_column(app, 'users', 'email', 'VARCHAR(255)')
        _ensure_column(app, 'users', 'email_verified', 'BOOLEAN NOT NULL DEFAULT 0')
        _ensure_column(app, 'users', 'nickname', 'VARCHAR(80)')
        _ensure_column(app, 'users', 'avatar_url', 'VARCHAR(255)')
        _ensure_column(app, 'users', 'can_comment', 'BOOLEAN NOT NULL DEFAULT 1')
        _ensure_column(app, 'comments', 'approval_token', 'VARCHAR(64)')
        
        # 确保上传目录存在
        uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

        # 初始化默认设置
        if SystemSetting.get('docs_dir') is None:
            SystemSetting.set('docs_dir', 'jobs')
        
        if SystemSetting.get('access_mode') is None:
            SystemSetting.set('access_mode', 'open') # open, group_only, password_only
            
        if SystemSetting.get('global_password') is None:
            SystemSetting.set('global_password', '')
        if SystemSetting.get('comments_enabled') is None:
            SystemSetting.set('comments_enabled', 'true')
        if SystemSetting.get('comments_require_approval') is None:
            SystemSetting.set('comments_require_approval', 'true')
        if SystemSetting.get('smtp_host') is None:
            SystemSetting.set('smtp_host', '')
        if SystemSetting.get('smtp_port') is None:
            SystemSetting.set('smtp_port', '465')
        if SystemSetting.get('smtp_username') is None:
            SystemSetting.set('smtp_username', '')
        if SystemSetting.get('smtp_password') is None:
            SystemSetting.set('smtp_password', '')
        if SystemSetting.get('smtp_use_ssl') is None:
            SystemSetting.set('smtp_use_ssl', 'true')
        if SystemSetting.get('smtp_sender') is None:
            SystemSetting.set('smtp_sender', '')

        # Theme settings
        if SystemSetting.get('default_theme_color') is None:
            SystemSetting.set('default_theme_color', 'blue')
        if SystemSetting.get('default_theme_mode') is None:
            SystemSetting.set('default_theme_mode', 'light')
        if SystemSetting.get('allow_user_theme_override') is None:
            SystemSetting.set('allow_user_theme_override', 'true')

        # Site mode settings
        if SystemSetting.get('site_mode') is None:
            SystemSetting.set('site_mode', 'blog')
        if SystemSetting.get('blog_enabled') is None:
            SystemSetting.set('blog_enabled', 'true')
        if SystemSetting.get('show_docs_entry_in_blog') is None:
            SystemSetting.set('show_docs_entry_in_blog', 'true')
        if SystemSetting.get('blog_theme') is None:
            SystemSetting.set('blog_theme', 'default')
        if SystemSetting.get('site_logo') is None:
            SystemSetting.set('site_logo', '')
        if SystemSetting.get('random_cover_api') is None:
            SystemSetting.set('random_cover_api', '')

        # 建立默认管理员
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            initial_password = os.environ.get('PLANNING_ADMIN_INITIAL_PASSWORD') or secrets.token_urlsafe(12)
            admin = User()
            admin.username = 'admin'
            admin.role = 'admin'
            admin.set_password(initial_password)
            db.session.add(admin)
            db.session.commit()
            print(f"[planning] 已初始化 admin 账号，请尽快修改密码。初始密码: {initial_password}")
