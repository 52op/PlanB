"""
数据库自动迁移模块
在应用启动时自动检查并创建缺失的表
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect

def auto_migrate_tables(app, db):
    """
    自动检查并创建缺失的表
    
    使用方式：
    from db_auto_migrate import auto_migrate_tables
    auto_migrate_tables(app, db)
    """
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # 获取所有模型定义的表
        model_tables = set()
        for model in db.Model.registry._class_registry.values():
            if hasattr(model, '__tablename__'):
                model_tables.add(model.__tablename__)
        
        # 找出缺失的表
        missing_tables = model_tables - set(existing_tables)
        
        if missing_tables:
            print(f"检测到缺失的表: {', '.join(missing_tables)}")
            print("正在创建...")
            
            # 只创建缺失的表，不影响现有表
            db.create_all()
            
            print("✓ 数据库表创建完成")
            
            # 如果是首次创建 backup_configs，插入默认配置
            if 'backup_configs' in missing_tables:
                from models import BackupConfig
                if BackupConfig.query.first() is None:
                    default_config = BackupConfig(
                        enabled=False,
                        schedule_type='manual',
                        retention_days=7,
                        retention_count=10,
                        compress=True,
                        encrypt=False,
                        storage_local=True
                    )
                    db.session.add(default_config)
                    db.session.commit()
                    print("✓ 已插入默认备份配置")
        else:
            print("✓ 数据库表结构已是最新")

def check_and_add_columns(app, db):
    """
    检查并添加缺失的列（用于表结构升级）
    
    示例：如果需要给现有表添加新列
    """
    with app.app_context():
        inspector = inspect(db.engine)
        
        # 示例：检查 users 表是否有 avatar_url 列
        # columns = [col['name'] for col in inspector.get_columns('users')]
        # if 'avatar_url' not in columns:
        #     db.session.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255)"))
        #     db.session.commit()
        #     print("✓ 已添加 avatar_url 列")
        
        pass
