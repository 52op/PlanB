import os
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from runtime_paths import get_change_password_signal_path, get_data_subdir

db = SQLAlchemy()

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key, default=None):
        setting = db.session.get(SystemSetting, key)
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = db.session.get(SystemSetting, key)
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
    can_manage = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('permissions', lazy=True))


class PasswordAccessRule(db.Model):
    __tablename__ = 'password_access_rules'
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(10), nullable=False, default='dir')  # dir / file
    target_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint('target_type', 'target_path', name='uq_password_access_rule_target'),
        db.Index('ix_password_access_rule_target', 'target_type', 'target_path'),
    )


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


class RateLimitAttempt(db.Model):
    __tablename__ = 'rate_limit_attempts'
    id = db.Column(db.Integer, primary_key=True)
    bucket_type = db.Column(db.String(32), nullable=False, index=True)
    scope_key = db.Column(db.String(512), nullable=False)
    failures = db.Column(db.Integer, nullable=False, default=0)
    last_attempt_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    blocked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint('bucket_type', 'scope_key', name='uq_rate_limit_bucket_scope'),
        db.Index('ix_rate_limit_bucket_scope', 'bucket_type', 'scope_key'),
    )


class CoverFallbackCache(db.Model):
    __tablename__ = 'cover_fallback_cache'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(32), nullable=False, index=True)
    cache_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    payload = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    approval_token = db.Column(db.String(64), nullable=True, unique=True)
    approval_token_expires_at = db.Column(db.DateTime, nullable=True)
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


class BackupConfig(db.Model):
    """备份配置表"""
    __tablename__ = 'backup_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 基本配置
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    storage_type = db.Column(db.String(200), nullable=False)  # JSON数组: ["ftp", "email", "s3"]
    schedule_type = db.Column(db.String(20), nullable=False)  # hourly, daily, weekly, cron, daily_interval, weekly_interval
    schedule_value = db.Column(db.String(100), nullable=True)  # cron表达式
    schedule_metadata = db.Column(db.Text, nullable=True)  # JSON格式的额外调度信息（如间隔天数、周数）
    retention_count = db.Column(db.Integer, default=10, nullable=False)
    
    # 备份模式
    backup_mode = db.Column(db.String(20), default='full', nullable=False)  # full, incremental
    
    # 加密配置
    encryption_enabled = db.Column(db.Boolean, default=False, nullable=False)
    encryption_key_hash = db.Column(db.String(255), nullable=True)  # 加密密钥的哈希
    
    # FTP配置
    ftp_host = db.Column(db.String(255), nullable=True)
    ftp_port = db.Column(db.Integer, default=21, nullable=True)
    ftp_username = db.Column(db.String(100), nullable=True)
    ftp_password = db.Column(db.String(255), nullable=True)
    ftp_path = db.Column(db.String(255), default='/', nullable=True)
    
    # 邮件配置
    email_recipient = db.Column(db.String(255), nullable=True)
    
    # S3配置
    s3_endpoint = db.Column(db.String(255), nullable=True)
    s3_bucket = db.Column(db.String(100), nullable=True)
    s3_access_key = db.Column(db.String(100), nullable=True)
    s3_secret_key = db.Column(db.String(255), nullable=True)
    s3_path_prefix = db.Column(db.String(255), default='backups/', nullable=True)
    s3_region = db.Column(db.String(50), nullable=True)
    
    # 通知配置
    notification_enabled = db.Column(db.Boolean, default=True, nullable=False)
    notification_email = db.Column(db.String(255), nullable=True)
    
    # 存储监控
    storage_warning_threshold_mb = db.Column(db.Integer, default=1024, nullable=False)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())


class BackupJob(db.Model):
    """备份任务记录表"""
    __tablename__ = 'backup_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 任务信息
    trigger_type = db.Column(db.String(20), nullable=False)  # auto, manual
    status = db.Column(db.String(20), nullable=False)  # running, success, failed
    backup_mode = db.Column(db.String(20), nullable=False)  # full, incremental
    
    # 备份文件信息
    filename = db.Column(db.String(255), nullable=True)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)
    file_hash = db.Column(db.String(64), nullable=True)  # SHA256
    storage_type = db.Column(db.String(20), nullable=True)
    storage_path = db.Column(db.String(500), nullable=True)
    
    # 备份内容统计
    db_size_bytes = db.Column(db.BigInteger, nullable=True)
    uploads_count = db.Column(db.Integer, nullable=True)
    uploads_size_bytes = db.Column(db.BigInteger, nullable=True)
    docs_count = db.Column(db.Integer, nullable=True)
    docs_size_bytes = db.Column(db.BigInteger, nullable=True)
    
    # 加密信息
    is_encrypted = db.Column(db.Boolean, default=False, nullable=False)
    
    # 增量备份信息
    base_backup_id = db.Column(db.Integer, db.ForeignKey('backup_jobs.id'), nullable=True)
    
    # 时间信息
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    
    # 错误信息
    error_message = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 关系
    base_backup = db.relationship('BackupJob', remote_side=[id], backref='incremental_backups')


class BackupFileTracker(db.Model):
    """文件变更追踪表 - 用于增量备份"""
    __tablename__ = 'backup_file_trackers'
    
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(500), nullable=False, unique=True, index=True)
    file_type = db.Column(db.String(20), nullable=False)  # database, upload, document
    last_modified = db.Column(db.DateTime, nullable=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)  # SHA256
    last_backup_id = db.Column(db.Integer, db.ForeignKey('backup_jobs.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())


def _ensure_column(app, table_name, column_name, column_sql):
    inspector = db.inspect(db.engine)
    column_names = {column['name'] for column in inspector.get_columns(table_name)}
    if column_name in column_names:
        return
    with db.engine.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}')


def _generate_admin_password():
    return os.environ.get('PLANNING_ADMIN_INITIAL_PASSWORD') or secrets.token_urlsafe(12)


def _ensure_admin_account():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        return admin, False

    initial_password = _generate_admin_password()
    admin = User()
    admin.username = 'admin'
    admin.role = 'admin'
    admin.set_password(initial_password)
    db.session.add(admin)
    db.session.commit()
    print(f"[planning] 已初始化 admin 账号，请尽快修改密码。初始密码: {initial_password}")
    return admin, True


def _handle_admin_password_reset_signal():
    signal_path = get_change_password_signal_path()
    if not os.path.exists(signal_path):
        return

    admin, _ = _ensure_admin_account()
    next_password = _generate_admin_password()
    admin.role = 'admin'
    admin.set_password(next_password)
    db.session.commit()
    print(f"[planning] 检测到 .changepassword，admin 密码已重置。新密码: {next_password}")

    try:
        os.remove(signal_path)
        print("[planning] 已处理并删除 .changepassword 标记文件。")
    except OSError as exc:
        print(f"[planning] 警告：无法删除 .changepassword 文件，请手动删除。原因: {exc}")


def _ensure_backup_config():
    """
    确保备份功能的初始化配置
    注意：表结构由 db.create_all() 或 --update-db 自动创建
    这个函数只负责：
    1. 插入默认配置数据（如果不存在）
    2. 创建必要的目录
    """
    try:
        # 插入默认配置（如果不存在）
        if BackupConfig.query.first() is None:
            print("[planning] 初始化备份默认配置...")
            default_config = BackupConfig(
                enabled=False,
                storage_type='[]',  # 空的 JSON 数组
                schedule_type='manual',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                notification_enabled=True,
                storage_warning_threshold_mb=1024
            )
            db.session.add(default_config)
            db.session.commit()
            print("[planning] ✓ 备份默认配置已创建")
        
        # 确保备份目录存在
        backup_dir = get_data_subdir('backups')
        os.makedirs(backup_dir, exist_ok=True)
        
    except Exception as e:
        # 如果表还不存在（比如首次运行且未执行 --update-db），静默跳过
        # 下次启动或执行 --update-db 后会自动创建
        if 'no such table' in str(e).lower():
            pass  # 表还不存在，等待 db.create_all() 或 --update-db 创建
        else:
            print(f"[planning] 警告：初始化备份配置失败: {e}")



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
        _ensure_column(app, 'comments', 'approval_token_expires_at', 'DATETIME')
        _ensure_column(app, 'permission_rules', 'can_manage', 'BOOLEAN NOT NULL DEFAULT 0')
        
        # 确保上传目录存在
        uploads_dir = app.config.get('UPLOADS_DIR') or get_data_subdir('uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        os.makedirs(get_data_subdir('jobs'), exist_ok=True)
        os.makedirs(get_data_subdir('covers'), exist_ok=True)

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
        if SystemSetting.get('random_cover_source_type') is None:
            SystemSetting.set('random_cover_source_type', 'url')
        if SystemSetting.get('random_cover_local_dir') is None:
            SystemSetting.set('random_cover_local_dir', 'covers')
        if SystemSetting.get('random_cover_pexels_api_key') is None:
            SystemSetting.set('random_cover_pexels_api_key', '')
        if SystemSetting.get('random_cover_pexels_default_query') is None:
            SystemSetting.set('random_cover_pexels_default_query', 'nature')
        if SystemSetting.get('random_cover_pexels_orientation') is None:
            SystemSetting.set('random_cover_pexels_orientation', 'landscape')
        if SystemSetting.get('random_cover_pexels_per_page') is None:
            SystemSetting.set('random_cover_pexels_per_page', '6')
        if SystemSetting.get('random_cover_pexels_cache_hours') is None:
            SystemSetting.set('random_cover_pexels_cache_hours', '24')
        if SystemSetting.get('security_rate_limit_backend') is None:
            SystemSetting.set('security_rate_limit_backend', 'database')
        if SystemSetting.get('security_redis_url') is None:
            SystemSetting.set('security_redis_url', '')
        if SystemSetting.get('security_redis_key_prefix') is None:
            SystemSetting.set('security_redis_key_prefix', 'planning:rate-limit')
        if SystemSetting.get('security_login_rate_limit_enabled') is None:
            SystemSetting.set('security_login_rate_limit_enabled', 'true')
        if SystemSetting.get('security_verification_rate_limit_enabled') is None:
            SystemSetting.set('security_verification_rate_limit_enabled', 'true')
        if SystemSetting.get('security_verification_send_rate_limit_enabled') is None:
            SystemSetting.set('security_verification_send_rate_limit_enabled', 'true')
        if SystemSetting.get('security_rate_limit_level1_attempts') is None:
            SystemSetting.set('security_rate_limit_level1_attempts', '3')
        if SystemSetting.get('security_rate_limit_level1_seconds') is None:
            SystemSetting.set('security_rate_limit_level1_seconds', '30')
        if SystemSetting.get('security_rate_limit_level2_attempts') is None:
            SystemSetting.set('security_rate_limit_level2_attempts', '5')
        if SystemSetting.get('security_rate_limit_level2_seconds') is None:
            SystemSetting.set('security_rate_limit_level2_seconds', '300')
        if SystemSetting.get('security_rate_limit_level3_attempts') is None:
            SystemSetting.set('security_rate_limit_level3_attempts', '10')
        if SystemSetting.get('security_rate_limit_level3_seconds') is None:
            SystemSetting.set('security_rate_limit_level3_seconds', '1800')
        if SystemSetting.get('security_send_rate_limit_level1_attempts') is None:
            SystemSetting.set('security_send_rate_limit_level1_attempts', '5')
        if SystemSetting.get('security_send_rate_limit_level1_seconds') is None:
            SystemSetting.set('security_send_rate_limit_level1_seconds', '600')
        if SystemSetting.get('security_send_rate_limit_level2_attempts') is None:
            SystemSetting.set('security_send_rate_limit_level2_attempts', '10')
        if SystemSetting.get('security_send_rate_limit_level2_seconds') is None:
            SystemSetting.set('security_send_rate_limit_level2_seconds', '3600')
        if SystemSetting.get('security_send_rate_limit_level3_attempts') is None:
            SystemSetting.set('security_send_rate_limit_level3_attempts', '20')
        if SystemSetting.get('security_send_rate_limit_level3_seconds') is None:
            SystemSetting.set('security_send_rate_limit_level3_seconds', '86400')
        if SystemSetting.get('security_rate_limit_record_ttl_seconds') is None:
            SystemSetting.set('security_rate_limit_record_ttl_seconds', '7200')

        # 建立默认管理员，并支持通过 .changepassword 文件强制重置密码
        _ensure_admin_account()
        _handle_admin_password_reset_signal()
        
        # 初始化备份功能的默认配置
        _ensure_backup_config()
