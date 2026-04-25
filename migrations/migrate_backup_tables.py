"""
数据库迁移脚本 - 添加备份功能相关表
运行方式: python migrations/migrate_backup_tables.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import inspect, text

def table_exists(table_name):
    """检查表是否存在"""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def migrate_backup_tables():
    """迁移备份相关表"""
    with app.app_context():
        print("开始数据库迁移...")
        
        # 检查并创建 backup_configs 表
        if not table_exists('backup_configs'):
            print("创建 backup_configs 表...")
            db.session.execute(text("""
                CREATE TABLE backup_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enabled BOOLEAN NOT NULL DEFAULT 0,
                    schedule_type VARCHAR(20) NOT NULL DEFAULT 'manual',
                    schedule_time VARCHAR(10),
                    schedule_interval INTEGER,
                    retention_days INTEGER NOT NULL DEFAULT 7,
                    retention_count INTEGER NOT NULL DEFAULT 10,
                    compress BOOLEAN NOT NULL DEFAULT 1,
                    encrypt BOOLEAN NOT NULL DEFAULT 0,
                    encryption_key VARCHAR(255),
                    storage_local BOOLEAN NOT NULL DEFAULT 1,
                    storage_ftp BOOLEAN NOT NULL DEFAULT 0,
                    ftp_host VARCHAR(255),
                    ftp_port INTEGER DEFAULT 21,
                    ftp_username VARCHAR(100),
                    ftp_password VARCHAR(255),
                    ftp_path VARCHAR(255) DEFAULT '/backups',
                    storage_email BOOLEAN NOT NULL DEFAULT 0,
                    email_to VARCHAR(255),
                    email_from VARCHAR(255),
                    email_smtp_host VARCHAR(255),
                    email_smtp_port INTEGER DEFAULT 587,
                    email_smtp_user VARCHAR(255),
                    email_smtp_password VARCHAR(255),
                    email_use_tls BOOLEAN NOT NULL DEFAULT 1,
                    storage_s3 BOOLEAN NOT NULL DEFAULT 0,
                    s3_bucket VARCHAR(255),
                    s3_region VARCHAR(50),
                    s3_access_key VARCHAR(255),
                    s3_secret_key VARCHAR(255),
                    s3_endpoint VARCHAR(255),
                    s3_path VARCHAR(255) DEFAULT 'backups/',
                    notification_enabled BOOLEAN NOT NULL DEFAULT 1,
                    notification_on_success BOOLEAN NOT NULL DEFAULT 0,
                    notification_on_failure BOOLEAN NOT NULL DEFAULT 1,
                    notification_email VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 插入默认配置
            db.session.execute(text("""
                INSERT INTO backup_configs (
                    enabled, schedule_type, retention_days, retention_count,
                    compress, encrypt, storage_local
                ) VALUES (0, 'manual', 7, 10, 1, 0, 1)
            """))
            print("✓ backup_configs 表创建成功")
        else:
            print("✓ backup_configs 表已存在")
        
        # 检查并创建 backup_jobs 表
        if not table_exists('backup_jobs'):
            print("创建 backup_jobs 表...")
            db.session.execute(text("""
                CREATE TABLE backup_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id VARCHAR(50) UNIQUE NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    trigger_type VARCHAR(20) NOT NULL DEFAULT 'manual',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    file_path VARCHAR(500),
                    file_size INTEGER,
                    compressed BOOLEAN DEFAULT 0,
                    encrypted BOOLEAN DEFAULT 0,
                    storage_locations TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("✓ backup_jobs 表创建成功")
        else:
            print("✓ backup_jobs 表已存在")
        
        # 检查并创建 backup_file_trackers 表
        if not table_exists('backup_file_trackers'):
            print("创建 backup_file_trackers 表...")
            db.session.execute(text("""
                CREATE TABLE backup_file_trackers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path VARCHAR(500) NOT NULL,
                    file_hash VARCHAR(64) NOT NULL,
                    file_size INTEGER NOT NULL,
                    last_modified TIMESTAMP NOT NULL,
                    last_backup_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (last_backup_id) REFERENCES backup_jobs(id)
                )
            """))
            
            # 创建索引
            db.session.execute(text("""
                CREATE INDEX idx_file_path ON backup_file_trackers(file_path)
            """))
            print("✓ backup_file_trackers 表创建成功")
        else:
            print("✓ backup_file_trackers 表已存在")
        
        db.session.commit()
        print("\n数据库迁移完成！")
        print("所有备份相关表已就绪，现有数据未受影响。")

if __name__ == '__main__':
    try:
        migrate_backup_tables()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
