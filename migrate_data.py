"""
NEXUS PRIME 数据迁移工具
支持从 SQLite 导出数据到 CSV，以及从 CSV 导入到 PostgreSQL
"""
import os
import sqlite3
import csv
import io
import click
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH') or os.path.join(BASE_DIR, 'instance', 'nexus_prime.db')
POSTGRES_DB_URL = os.environ.get('DATABASE_URL')
EXPORT_DIR = os.path.join(BASE_DIR, 'data_export')

# 表导入顺序（按依赖关系排序，被依赖的表先导入）
TABLE_IMPORT_ORDER = [
    # 1. 基础表（无外键依赖）
    'alembic_version',
    'auth_roles',
    'auth_departments',
    'auth_permissions',
    'biz_categories',
    'biz_tags',
    'stock_warehouses',
    
    # 2. 用户表（依赖角色和部门）
    'auth_users',
    
    # 3. 业务伙伴表
    'biz_partners',
    
    # 4. 产品表（依赖分类和供应商）
    'biz_products',
    
    # 5. 多对多关联表
    'biz_product_tags',
    'roles_permissions',
    
    # 6. 库存相关
    'stock_quantities',
    'stock_logs',
    'stock_alerts',
    'stock_replenishment_suggestions',
    
    # 7. 交易相关
    'trade_orders',
    'trade_order_items',
    
    # 8. 采购相关
    'purchase_orders',
    'purchase_order_items',
    'purchase_price_history',
    'supplier_performance',
    
    # 9. 财务相关
    'finance_customer_credit',
    'finance_receivables',
    'finance_payments',
    'finance_statements',
    
    # 10. 盘点相关
    'stock_takes',
    'stock_take_items',
    'stock_take_history',
    
    # 11. 内容管理
    'cms_articles',
    'cms_attachments',
    
    # 12. 系统日志和通知
    'sys_audit_logs',
    'sys_notifications',
    'sys_ai_logs',
    'sys_ai_sessions',
    'sys_ai_messages',
    
    # 13. 报表相关
    'report_subscriptions',
    'generated_reports',
]


def get_sqlite_tables():
    """获取 SQLite 数据库中的所有表"""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ SQLite 数据库不存在: {SQLITE_DB_PATH}")
        return []
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def export_sqlite_to_csv():
    """从 SQLite 导出所有表到 CSV"""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ SQLite 数据库不存在: {SQLITE_DB_PATH}")
        return
    
    # 创建导出目录
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"📦 发现 {len(tables)} 个表，开始导出...")
    
    for table in tables:
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            if not rows:
                print(f"⚪ 表 '{table}' 为空，跳过")
                continue
            
            # 获取列名
            columns = [description[0] for description in cursor.description]
            
            # 写入 CSV
            csv_path = os.path.join(EXPORT_DIR, f"{table}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow(row)
            
            print(f"✅ 表 '{table}' 导出成功 ({len(rows)} 行)")
        except Exception as e:
            print(f"❌ 表 '{table}' 导出失败: {e}")
    
    conn.close()
    print(f"\n🎉 导出完成！文件保存在: {EXPORT_DIR}")


def import_data_to_postgres(truncate=False, only_tables=None):
    """从 CSV 导入数据到 PostgreSQL"""
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        print("❌ 错误：未安装 psycopg2。请运行 `pip install psycopg2-binary`")
        return

    if not POSTGRES_DB_URL:
        print("❌ 错误：未设置 DATABASE_URL。请检查环境变量。")
        return

    if not os.path.isdir(EXPORT_DIR):
        print(f"❌ 错误：未找到导出目录 {EXPORT_DIR}")
        return

    # 获取 CSV 文件列表
    csv_files = [f for f in os.listdir(EXPORT_DIR) if f.endswith('.csv')]
    if only_tables:
        csv_files = [f for f in csv_files if f.replace('.csv', '') in only_tables]
    
    if not csv_files:
        print("⚠️  没有找到需要导入的 CSV 文件。")
        return

    print(f"🔌 正在连接 PostgreSQL... (准备导入 {len(csv_files)} 个表)")
    
    # 修复 Railway PostgreSQL URL
    db_url = POSTGRES_DB_URL
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 预处理：修复数据库结构
    print("🔧 正在预检并修复数据库结构...")
    structure_fixes = [
        ("ALTER TABLE auth_users ALTER COLUMN password_hash TYPE TEXT;", "auth_users.password_hash 已扩容"),
        ("ALTER TABLE cms_articles ALTER COLUMN content TYPE TEXT;", "cms_articles.content 已扩容"),
        ("ALTER TABLE sys_ai_logs ALTER COLUMN prompt TYPE TEXT;", "sys_ai_logs.prompt 已扩容"),
        ("ALTER TABLE sys_ai_logs ALTER COLUMN response TYPE TEXT;", "sys_ai_logs.response 已扩容"),
        ("ALTER TABLE sys_ai_messages ALTER COLUMN content TYPE TEXT;", "sys_ai_messages.content 已扩容"),
        ("ALTER TABLE sys_audit_logs ALTER COLUMN details TYPE TEXT;", "sys_audit_logs.details 已扩容"),
    ]
    
    for fix_sql, msg in structure_fixes:
        try:
            cur.execute(fix_sql)
            conn.commit()
            print(f"  ✅ {msg}")
        except Exception:
            conn.rollback()

    # 获取数据库当前的列结构和数据类型
    cur.execute("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
    """)
    db_schema = {}
    db_column_types = {}
    for t, c, dtype in cur.fetchall():
        db_schema.setdefault(t, set()).add(c)
        db_column_types[(t, c)] = dtype

    # 开启"极速模式"（暂时禁用外键检查）
    cur.execute("SET session_replication_role = 'replica';")
    conn.commit()

    success_count = 0
    failed_tables = []
    
    # 按顺序导入
    ordered_files = []
    for table in TABLE_IMPORT_ORDER:
        fname = f"{table}.csv"
        if fname in csv_files:
            ordered_files.append(fname)
            csv_files.remove(fname)
    # 添加剩余的文件
    ordered_files.extend(csv_files)
    
    try:
        for fname in ordered_files:
            table_name = fname.replace('.csv', '')
            
            # 检查表是否存在
            if table_name not in db_schema:
                print(f"⚪ 跳过：数据库中不存在表 '{table_name}'")
                continue

            # 读取 CSV 表头
            file_path = os.path.join(EXPORT_DIR, fname)
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    csv_headers = next(reader)
                except StopIteration:
                    print(f"⚪ 跳过：文件 '{fname}' 为空")
                    continue
            
            # 计算公共列
            valid_cols = [c for c in csv_headers if c in db_schema[table_name]]
            
            if not valid_cols:
                print(f"❌ 错误：表 '{table_name}' 没有匹配的列，无法导入。")
                failed_tables.append(table_name)
                continue

            # 获取布尔类型的列
            bool_cols = set()
            for col in valid_cols:
                dtype = db_column_types.get((table_name, col), '')
                if dtype == 'boolean':
                    bool_cols.add(col)

            # 准备内存数据流（清洗数据）
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=valid_cols, extrasaction='ignore')
            writer.writeheader()

            with open(file_path, 'r', encoding='utf-8') as f:
                dict_reader = csv.DictReader(f)
                row_count = 0
                for row in dict_reader:
                    # 清洗数据
                    cleaned_row = {}
                    for col in valid_cols:
                        val = row.get(col, '')
                        # 处理空字符串为 NULL
                        if val == '' or val is None:
                            cleaned_row[col] = ''
                        # 只对布尔类型列进行布尔值转换
                        elif col in bool_cols:
                            if val in ('True', 'true', '1'):
                                cleaned_row[col] = 'true'
                            elif val in ('False', 'false', '0'):
                                cleaned_row[col] = 'false'
                            else:
                                cleaned_row[col] = val
                        else:
                            cleaned_row[col] = val
                    writer.writerow(cleaned_row)
                    row_count += 1
            
            output.seek(0)
            if row_count == 0:
                print(f"⚪ 表 '{table_name}' 无数据。")
                continue

            # 清空旧数据 (如果需要)
            if truncate:
                try:
                    cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(table_name)))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    cur.execute("SET session_replication_role = 'replica';")

            # 执行 COPY 导入
            try:
                columns_sql = sql.SQL(',').join(map(sql.Identifier, valid_cols))
                copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')").format(
                    sql.Identifier(table_name), columns_sql
                )
                cur.copy_expert(copy_sql, output)
                
                # 修复 ID 序列
                if 'id' in valid_cols:
                    try:
                        cur.execute(sql.SQL(
                            "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {}), 1));"
                        ).format(sql.Identifier(table_name)), [table_name])
                    except:
                        pass

                conn.commit()
                print(f"✅ 表 '{table_name}' 导入成功 ({row_count} 行)")
                success_count += 1
            except Exception as e:
                conn.rollback()
                cur.execute("SET session_replication_role = 'replica';")
                print(f"❌ 表 '{table_name}' 导入失败: {e}")
                failed_tables.append(table_name)

    finally:
        # 恢复外键检查
        cur.execute("SET session_replication_role = 'origin';")
        conn.commit()
        conn.close()
        
        print(f"\n🎉 任务结束。成功导入 {success_count} 个表。")
        if failed_tables:
            print(f"⚠️  失败的表: {', '.join(failed_tables)}")
        
        print(f"\n🎉 任务结束。成功导入 {success_count} 个表。")
        if failed_tables:
            print(f"⚠️  失败的表: {', '.join(failed_tables)}")


def verify_import():
    """验证导入结果"""
    try:
        import psycopg2
    except ImportError:
        print("❌ 错误：未安装 psycopg2")
        return

    if not POSTGRES_DB_URL:
        print("❌ 错误：未设置 DATABASE_URL")
        return

    db_url = POSTGRES_DB_URL
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    print("📊 PostgreSQL 数据库统计:")
    print("-" * 50)
    
    # 获取所有表及其行数
    cur.execute("""
        SELECT schemaname, relname, n_live_tup 
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public'
        ORDER BY relname;
    """)
    
    total_rows = 0
    for schema, table, rows in cur.fetchall():
        print(f"  {table}: {rows} 行")
        total_rows += rows
    
    print("-" * 50)
    print(f"  总计: {total_rows} 行")
    
    conn.close()


# --- 命令行接口 ---
@click.group()
def cli():
    """NEXUS PRIME 数据迁移工具"""
    pass


@cli.command()
def export():
    """从 SQLite 导出数据到 CSV"""
    export_sqlite_to_csv()


@cli.command('import')
@click.option('--truncate', is_flag=True, help='导入前清空表')
@click.option('--only', multiple=True, help='仅导入指定表')
def import_cmd(truncate, only):
    """从 CSV 导入数据到 PostgreSQL"""
    import_data_to_postgres(truncate, list(only) if only else None)


@cli.command()
def verify():
    """验证 PostgreSQL 数据库状态"""
    verify_import()


@cli.command()
def tables():
    """列出 SQLite 数据库中的所有表"""
    tables = get_sqlite_tables()
    if tables:
        print(f"📋 SQLite 数据库中的表 ({len(tables)} 个):")
        for t in sorted(tables):
            print(f"  - {t}")
    else:
        print("❌ 无法获取表列表")


@cli.command()
def compare():
    """对比本地 CSV 和云端 PostgreSQL 数据"""
    try:
        import psycopg2
    except ImportError:
        print("❌ 错误：未安装 psycopg2")
        return

    if not POSTGRES_DB_URL:
        print("❌ 错误：未设置 DATABASE_URL")
        return

    if not os.path.isdir(EXPORT_DIR):
        print(f"❌ 错误：未找到导出目录 {EXPORT_DIR}")
        return

    db_url = POSTGRES_DB_URL
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    print("📊 本地 CSV vs 云端 PostgreSQL 数据对比:")
    print("-" * 60)
    print(f"{'表名':<30} {'本地CSV':<10} {'云端PG':<10} {'状态':<10}")
    print("-" * 60)

    # 获取云端表行数
    cur.execute("""
        SELECT relname, n_live_tup 
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public';
    """)
    pg_counts = {row[0]: row[1] for row in cur.fetchall()}

    # 获取本地 CSV 行数
    csv_files = [f for f in os.listdir(EXPORT_DIR) if f.endswith('.csv')]
    
    missing_in_pg = []
    missing_in_csv = []
    mismatch = []
    
    for fname in sorted(csv_files):
        table_name = fname.replace('.csv', '')
        
        # 计算 CSV 行数
        csv_count = 0
        try:
            with open(os.path.join(EXPORT_DIR, fname), 'r', encoding='utf-8') as f:
                csv_count = sum(1 for _ in f) - 1  # 减去表头
                if csv_count < 0:
                    csv_count = 0
        except:
            csv_count = -1
        
        pg_count = pg_counts.get(table_name, -1)
        
        if pg_count == -1:
            status = "❌ 表不存在"
            missing_in_pg.append(table_name)
        elif csv_count == pg_count:
            status = "✅ 一致"
        elif csv_count > pg_count:
            status = f"⚠️ 差 {csv_count - pg_count}"
            mismatch.append((table_name, csv_count, pg_count))
        else:
            status = f"📈 多 {pg_count - csv_count}"
        
        print(f"{table_name:<30} {csv_count:<10} {pg_count:<10} {status}")
    
    # 检查云端有但本地没有的表
    csv_tables = {f.replace('.csv', '') for f in csv_files}
    for pg_table in pg_counts:
        if pg_table not in csv_tables:
            missing_in_csv.append(pg_table)
    
    print("-" * 60)
    
    if mismatch:
        print(f"\n⚠️  数据不一致的表 ({len(mismatch)} 个):")
        for t, local, remote in mismatch:
            print(f"  - {t}: 本地 {local} 行, 云端 {remote} 行 (差 {local - remote} 行)")
        print("\n💡 建议: 运行 `python migrate_data.py import --truncate` 重新导入")
    
    if missing_in_pg:
        print(f"\n❌ 云端缺失的表 ({len(missing_in_pg)} 个):")
        for t in missing_in_pg:
            print(f"  - {t}")
        print("\n💡 建议: 检查数据库迁移是否完成 (flask db upgrade)")
    
    if missing_in_csv:
        print(f"\nℹ️  云端独有的表 ({len(missing_in_csv)} 个):")
        for t in missing_in_csv:
            print(f"  - {t}")
    
    if not mismatch and not missing_in_pg:
        print("\n🎉 所有数据已同步！")
    
    conn.close()


@cli.command()
@click.option('--table', '-t', required=True, help='要检查的表名')
def check_table(table):
    """检查指定表的详细信息"""
    try:
        import psycopg2
    except ImportError:
        print("❌ 错误：未安装 psycopg2")
        return

    if not POSTGRES_DB_URL:
        print("❌ 错误：未设置 DATABASE_URL")
        return

    db_url = POSTGRES_DB_URL
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    print(f"📋 表 '{table}' 详细信息:")
    print("-" * 50)
    
    # 获取表结构
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
    """, [table])
    
    columns = cur.fetchall()
    if not columns:
        print(f"❌ 表 '{table}' 不存在")
        conn.close()
        return
    
    print("列结构:")
    for col_name, data_type, nullable, default in columns:
        null_str = "NULL" if nullable == 'YES' else "NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  {col_name}: {data_type} {null_str}{default_str}")
    
    # 获取行数
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"\n行数: {count}")
    
    # 显示前5行数据
    if count > 0:
        cur.execute(f"SELECT * FROM {table} LIMIT 5")
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        
        print(f"\n前 {min(5, count)} 行数据:")
        print(f"  {col_names}")
        for row in rows:
            print(f"  {row}")
    
    conn.close()


if __name__ == '__main__':
    cli()
