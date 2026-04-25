"""
数据库迁移工具
支持从 SQLite 迁移到 PostgreSQL、MySQL 等数据库

使用方式:
    python migrate_database.py \\
        --from sqlite:///data/app.db \\
        --to postgresql://user:pass@localhost/dbname
"""
import sys
import argparse
from sqlalchemy import create_engine, MetaData, Table, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

def get_all_tables(engine):
    """获取数据库中的所有表"""
    inspector = inspect(engine)
    return inspector.get_table_names()

def copy_table_data(source_engine, target_engine, table_name, batch_size=1000):
    """复制单个表的数据"""
    print(f"  正在迁移表: {table_name}")
    
    # 创建会话
    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)
    
    source_session = SourceSession()
    target_session = TargetSession()
    
    try:
        # 获取表结构
        metadata = MetaData()
        source_table = Table(table_name, metadata, autoload_with=source_engine)
        target_table = Table(table_name, metadata, autoload_with=target_engine)
        
        # 查询源表数据
        result = source_session.execute(source_table.select())
        rows = result.fetchall()
        
        if not rows:
            print(f"    ✓ {table_name}: 0 条记录（空表）")
            return 0
        
        # 批量插入目标表
        total_rows = len(rows)
        inserted = 0
        
        for i in range(0, total_rows, batch_size):
            batch = rows[i:i + batch_size]
            
            # 转换为字典列表
            data_dicts = []
            for row in batch:
                row_dict = {}
                for col in source_table.columns:
                    row_dict[col.name] = getattr(row, col.name)
                data_dicts.append(row_dict)
            
            # 插入数据
            target_session.execute(target_table.insert(), data_dicts)
            target_session.commit()
            
            inserted += len(batch)
            print(f"    进度: {inserted}/{total_rows} ({inserted*100//total_rows}%)")
        
        print(f"    ✓ {table_name}: {total_rows} 条记录迁移完成")
        return total_rows
        
    except Exception as e:
        target_session.rollback()
        print(f"    ✗ {table_name}: 迁移失败 - {e}")
        raise
    finally:
        source_session.close()
        target_session.close()

def migrate_database(source_uri, target_uri, skip_tables=None):
    """执行数据库迁移"""
    skip_tables = skip_tables or []
    
    print("\n" + "="*60)
    print("数据库迁移工具")
    print("="*60)
    print(f"\n源数据库: {source_uri}")
    print(f"目标数据库: {target_uri}\n")
    
    # 创建引擎
    print("正在连接数据库...")
    source_engine = create_engine(source_uri, poolclass=NullPool)
    target_engine = create_engine(target_uri, poolclass=NullPool)
    
    try:
        # 测试连接
        source_engine.connect()
        target_engine.connect()
        print("✓ 数据库连接成功\n")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}\n")
        return False
    
    # 获取所有表
    print("正在分析表结构...")
    tables = get_all_tables(source_engine)
    tables_to_migrate = [t for t in tables if t not in skip_tables]
    
    print(f"找到 {len(tables)} 个表")
    if skip_tables:
        print(f"跳过 {len(skip_tables)} 个表: {', '.join(skip_tables)}")
    print(f"将迁移 {len(tables_to_migrate)} 个表\n")
    
    # 创建目标数据库表结构
    print("正在创建目标数据库表结构...")
    try:
        # 使用 SQLAlchemy 的 MetaData 反射源数据库结构
        metadata = MetaData()
        metadata.reflect(bind=source_engine)
        
        # 在目标数据库中创建表
        metadata.create_all(target_engine)
        print("✓ 表结构创建完成\n")
    except Exception as e:
        print(f"✗ 表结构创建失败: {e}\n")
        return False
    
    # 迁移数据
    print("="*60)
    print("开始迁移数据")
    print("="*60 + "\n")
    
    total_records = 0
    failed_tables = []
    
    for table_name in tables_to_migrate:
        try:
            records = copy_table_data(source_engine, target_engine, table_name)
            total_records += records
        except Exception as e:
            failed_tables.append((table_name, str(e)))
            print(f"  警告: 表 {table_name} 迁移失败，继续下一个表...\n")
    
    # 输出结果
    print("\n" + "="*60)
    print("迁移完成")
    print("="*60)
    print(f"\n成功迁移: {len(tables_to_migrate) - len(failed_tables)}/{len(tables_to_migrate)} 个表")
    print(f"总记录数: {total_records} 条")
    
    if failed_tables:
        print(f"\n失败的表 ({len(failed_tables)} 个):")
        for table, error in failed_tables:
            print(f"  - {table}: {error}")
        return False
    else:
        print("\n✅ 所有数据迁移成功！")
        return True

def main():
    parser = argparse.ArgumentParser(
        description='数据库迁移工具 - 支持从 SQLite 迁移到其他数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # SQLite -> PostgreSQL
  python migrate_database.py \\
    --from sqlite:///data/app.db \\
    --to postgresql://user:pass@localhost/dbname
  
  # SQLite -> MySQL
  python migrate_database.py \\
    --from sqlite:///data/app.db \\
    --to mysql+pymysql://user:pass@localhost/dbname
  
  # 跳过某些表
  python migrate_database.py \\
    --from sqlite:///data/app.db \\
    --to postgresql://user:pass@localhost/dbname \\
    --skip-tables alembic_version,temp_table
        """
    )
    
    parser.add_argument('--from', dest='source', required=True,
                       help='源数据库连接字符串')
    parser.add_argument('--to', dest='target', required=True,
                       help='目标数据库连接字符串')
    parser.add_argument('--skip-tables', dest='skip_tables',
                       help='跳过的表名（逗号分隔）')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='跳过确认提示')
    
    args = parser.parse_args()
    
    # 解析跳过的表
    skip_tables = []
    if args.skip_tables:
        skip_tables = [t.strip() for t in args.skip_tables.split(',')]
    
    # 确认提示
    if not args.yes:
        print("\n⚠️  警告：数据库迁移操作")
        print(f"源数据库: {args.source}")
        print(f"目标数据库: {args.target}")
        print("\n建议:")
        print("1. 确保已备份源数据库")
        print("2. 确保目标数据库为空或可以覆盖")
        print("3. 确保网络连接稳定")
        
        confirm = input("\n确定要继续吗？(yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            print("已取消迁移。\n")
            return 1
    
    # 执行迁移
    try:
        success = migrate_database(args.source, args.target, skip_tables)
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  迁移被用户中断。")
        return 1
    except Exception as e:
        print(f"\n\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
