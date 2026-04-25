"""
数据库结构自动同步工具
自动对比 models.py 和现有数据库结构，生成并执行同步操作

使用方式:
    python db_sync.py              # 检查差异
    python db_sync.py --sync       # 自动同步
    python db_sync.py --dry-run    # 预览将要执行的 SQL
"""
import sys
import argparse
from sqlalchemy import inspect, MetaData, Table, Column
from sqlalchemy.schema import CreateTable, CreateIndex
from app import create_app
from models import db

def get_model_tables():
    """获取 models.py 中定义的所有表结构"""
    tables = {}
    for table_name, table in db.metadata.tables.items():
        tables[table_name] = {
            'columns': {col.name: col for col in table.columns},
            'indexes': table.indexes,
            'constraints': table.constraints
        }
    return tables

def get_database_tables(engine):
    """获取数据库中现有的表结构"""
    inspector = inspect(engine)
    tables = {}
    for table_name in inspector.get_table_names():
        columns = {}
        for col in inspector.get_columns(table_name):
            columns[col['name']] = col
        
        tables[table_name] = {
            'columns': columns,
            'indexes': inspector.get_indexes(table_name),
            'foreign_keys': inspector.get_foreign_keys(table_name)
        }
    return tables

def compare_structures(model_tables, db_tables):
    """对比模型和数据库结构，找出差异"""
    differences = {
        'missing_tables': [],      # 缺失的表
        'missing_columns': {},     # 缺失的列 {table: [columns]}
        'extra_tables': [],        # 多余的表（数据库有但模型没有）
        'extra_columns': {},       # 多余的列
        'type_mismatches': {}      # 类型不匹配的列
    }
    
    # 检查缺失的表
    for table_name in model_tables:
        if table_name not in db_tables:
            differences['missing_tables'].append(table_name)
    
    # 检查多余的表
    for table_name in db_tables:
        if table_name not in model_tables:
            differences['extra_tables'].append(table_name)
    
    # 检查列差异
    for table_name in model_tables:
        if table_name in db_tables:
            model_cols = model_tables[table_name]['columns']
            db_cols = db_tables[table_name]['columns']
            
            # 缺失的列
            missing = []
            for col_name, col_obj in model_cols.items():
                if col_name not in db_cols:
                    missing.append({
                        'name': col_name,
                        'type': str(col_obj.type),
                        'nullable': col_obj.nullable,
                        'default': col_obj.default,
                        'column_obj': col_obj
                    })
            if missing:
                differences['missing_columns'][table_name] = missing
            
            # 多余的列
            extra = []
            for col_name in db_cols:
                if col_name not in model_cols:
                    extra.append(col_name)
            if extra:
                differences['extra_columns'][table_name] = extra
    
    return differences

def generate_sync_sql(differences, dialect='sqlite'):
    """根据差异生成同步 SQL 语句"""
    sql_statements = []
    
    # 创建缺失的表
    for table_name in differences['missing_tables']:
        table = db.metadata.tables[table_name]
        create_stmt = str(CreateTable(table).compile(dialect=db.engine.dialect))
        sql_statements.append(f"-- 创建表: {table_name}")
        sql_statements.append(create_stmt + ";")
        sql_statements.append("")
    
    # 添加缺失的列
    for table_name, columns in differences['missing_columns'].items():
        for col_info in columns:
            col_name = col_info['name']
            col_type = col_info['type']
            nullable = "NULL" if col_info['nullable'] else "NOT NULL"
            
            # 处理默认值
            default_clause = ""
            if col_info['default'] is not None:
                default_val = col_info['default']
                if hasattr(default_val, 'arg'):
                    if isinstance(default_val.arg, bool):
                        default_clause = f" DEFAULT {1 if default_val.arg else 0}"
                    elif isinstance(default_val.arg, (int, float)):
                        default_clause = f" DEFAULT {default_val.arg}"
                    elif isinstance(default_val.arg, str):
                        default_clause = f" DEFAULT '{default_val.arg}'"
            
            sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default_clause};"
            sql_statements.append(f"-- 添加列: {table_name}.{col_name}")
            sql_statements.append(sql)
            sql_statements.append("")
    
    return sql_statements

def print_differences(differences):
    """打印差异报告"""
    print("\n" + "="*60)
    print("数据库结构差异报告")
    print("="*60 + "\n")
    
    has_diff = False
    
    if differences['missing_tables']:
        has_diff = True
        print(f"📋 缺失的表 ({len(differences['missing_tables'])} 个):")
        for table in differences['missing_tables']:
            print(f"   - {table}")
        print()
    
    if differences['missing_columns']:
        has_diff = True
        print(f"➕ 缺失的列:")
        for table, columns in differences['missing_columns'].items():
            print(f"   表 {table}:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"      - {col['name']} ({col['type']}) {nullable}")
        print()
    
    if differences['extra_tables']:
        has_diff = True
        print(f"⚠️  多余的表 ({len(differences['extra_tables'])} 个):")
        print("   (数据库中存在但 models.py 中未定义)")
        for table in differences['extra_tables']:
            print(f"   - {table}")
        print()
    
    if differences['extra_columns']:
        has_diff = True
        print(f"⚠️  多余的列:")
        print("   (数据库中存在但 models.py 中未定义)")
        for table, columns in differences['extra_columns'].items():
            print(f"   表 {table}:")
            for col in columns:
                print(f"      - {col}")
        print()
    
    if not has_diff:
        print("✅ 数据库结构与 models.py 完全一致，无需同步。\n")
        return False
    
    return True

def execute_sync(app, sql_statements):
    """执行同步 SQL"""
    if not sql_statements:
        print("✅ 无需执行任何操作。\n")
        return True
    
    print("\n" + "="*60)
    print("开始执行数据库同步")
    print("="*60 + "\n")
    
    with app.app_context():
        try:
            for i, sql in enumerate(sql_statements, 1):
                if sql.strip() and not sql.startswith('--'):
                    print(f"[{i}] 执行: {sql[:80]}...")
                    db.session.execute(db.text(sql))
            
            db.session.commit()
            print("\n✅ 数据库同步完成！\n")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ 同步失败: {e}\n")
            import traceback
            traceback.print_exc()
            return False

def main():
    parser = argparse.ArgumentParser(
        description='数据库结构自动同步工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python db_sync.py              # 检查差异
  python db_sync.py --sync       # 自动同步
  python db_sync.py --dry-run    # 预览 SQL（不执行）
        """
    )
    parser.add_argument('--sync', action='store_true', 
                       help='自动执行同步操作')
    parser.add_argument('--dry-run', action='store_true',
                       help='预览将要执行的 SQL（不实际执行）')
    
    args = parser.parse_args()
    
    print("\n🔍 正在分析数据库结构...\n")
    
    # 创建应用
    app = create_app()
    
    with app.app_context():
        # 获取模型和数据库结构
        model_tables = get_model_tables()
        db_tables = get_database_tables(db.engine)
        
        # 对比差异
        differences = compare_structures(model_tables, db_tables)
        
        # 打印差异报告
        has_diff = print_differences(differences)
        
        if not has_diff:
            return 0
        
        # 生成同步 SQL
        sql_statements = generate_sync_sql(differences)
        
        # 根据参数决定操作
        if args.dry_run or not args.sync:
            print("="*60)
            print("预览 SQL 语句" if args.dry_run else "建议执行的 SQL")
            print("="*60 + "\n")
            for sql in sql_statements:
                print(sql)
            
            if not args.sync:
                print("\n💡 提示: 使用 --sync 参数自动执行同步")
                print("       使用 --dry-run 仅预览 SQL\n")
            return 0
        
        # 执行同步
        if args.sync:
            confirm = input("\n⚠️  确定要执行数据库同步吗？建议先备份数据库。(yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("❌ 已取消同步操作。\n")
                return 1
            
            success = execute_sync(app, sql_statements)
            return 0 if success else 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
