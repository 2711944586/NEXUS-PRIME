import os
import sqlite3
import csv
import click
from dotenv import load_dotenv

load_dotenv()

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH') or os.path.join(BASE_DIR, 'instance', 'nexus_prime.db')
POSTGRES_DB_URL = os.environ.get('DATABASE_URL')
EXPORT_DIR = os.path.join(BASE_DIR, 'data_export')
# 首选导出顺序（若表存在则按此顺序导出）
TABLES_PREFERRED_ORDER = [
    'users', 'roles', 'permissions', 'departments',
    'categories', 'products', 'partners', 'tags',
    'warehouses', 'stock', 'inventory_logs',
    'orders', 'order_items',
    'articles', 'attachments',
    'audit_logs', 'ai_chat_logs'
]

# --- 导出功能 ---
def export_data_from_sqlite():
    """连接到 SQLite 并将每个存在的表导出为 CSV"""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"错误：找不到 SQLite 数据库文件于 '{SQLITE_DB_PATH}'")
        return

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    # 枚举数据库中实际存在的表
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        existing_tables = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"错误：无法读取 SQLite 表列表: {e}")
        conn.close()
        return

    # 按首选顺序导出已存在的表，然后导出剩余的表
    ordered_existing = [t for t in TABLES_PREFERRED_ORDER if t in existing_tables]
    remaining = sorted(set(existing_tables) - set(ordered_existing))
    export_tables = ordered_existing + remaining

    print(f"发现 {len(existing_tables)} 个表，将导出 {len(export_tables)} 个表。")

    for table_name in export_tables:
        print(f"正在导出表: {table_name}...")
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            headers = [description[0] for description in cursor.description]
        except sqlite3.Error as e:
            print(f"  -> 跳过表 '{table_name}': {e}")
            continue

        if not rows:
            print(f"  -> 表 '{table_name}' 为空，跳过。")
            continue

        file_path = os.path.join(EXPORT_DIR, f"{table_name}.csv")
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"  -> 成功导出到 {file_path}（{len(rows)} 行）")
        except OSError as e:
            print(f"  -> 写入文件失败 '{file_path}': {e}")

    conn.close()
    print("\n所有可用表已成功导出（如有错误已上方提示）。")

# --- 导入功能 (将在下一步实现) ---
def import_data_to_postgres(truncate=False, only_tables=None):
    """连接到 PostgreSQL 并从 CSV 导入数据。

    参数：
    - truncate: 在导入前清空表（推荐在新库上使用）。
    - only_tables: 仅导入指定的表名列表（来自 CSV 文件名）。
    """
    # 延迟导入 PostgreSQL 依赖，避免在仅导出时要求安装
    try:
        import psycopg2
        from psycopg2 import sql
    except Exception:
        print("错误：未安装 psycopg2，导入功能不可用。请先执行 `pip install -r requirements.txt`。")
        return

    if not POSTGRES_DB_URL:
        print("错误：未检测到环境变量 DATABASE_URL。请在本地 .env 中设置或在终端中导出该变量。")
        return

    # 收集待导入的 CSV 文件
    if not os.path.isdir(EXPORT_DIR):
        print(f"错误：未找到导出目录：{EXPORT_DIR}。请先执行导出。")
        return

    csv_files = [f for f in os.listdir(EXPORT_DIR) if f.endswith('.csv')]
    if only_tables:
        only_set = set(only_tables)
        csv_files = [f for f in csv_files if os.path.splitext(f)[0] in only_set]
        if not csv_files:
            print("提示：未匹配到指定的 CSV 文件。")
            return

    # 连接到 PostgreSQL
    print("正在连接到 PostgreSQL...")
    conn = psycopg2.connect(POSTGRES_DB_URL)
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()

    # 查询现有表（public 模式）
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public'
    """)
    pg_tables = {row[0] for row in cur.fetchall()}
    if not pg_tables:
        print("错误：目标数据库中未检测到任何表。请先运行迁移：`flask db upgrade`。")
        cur.close(); conn.close()
        return

    # 禁用外键/触发器以便批量导入
    cur.execute("SET session_replication_role = 'replica'")
    conn.commit()

    imported_counts = {}
    for fname in csv_files:
        table_name = os.path.splitext(fname)[0]
        file_path = os.path.join(EXPORT_DIR, fname)

        if table_name not in pg_tables:
            print(f"跳过：PostgreSQL 中不存在表 '{table_name}'。请确认迁移已创建该表。")
            continue

        # 读取 CSV 的表头，并与数据库列名求交集，避免不匹配的列导致失败
        with open(file_path, 'r', encoding='utf-8') as f:
            import csv as _csv
            reader = _csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                print(f"跳过：文件 '{fname}' 为空。")
                continue

        # 获取数据库列名
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table_name,)
        )
        db_columns = [row[0] for row in cur.fetchall()]
        insert_columns = [c for c in headers if c in db_columns]
        if not insert_columns:
            print(f"跳过：表 '{table_name}' 未找到匹配列，文件列：{headers}，库列：{db_columns}")
            continue

        try:
            if truncate:
                cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(table_name)))
                conn.commit()
                print(f"已清空表 '{table_name}'。")

            # 使用 COPY 导入，速度快且类型适配友好
            copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)")\
                .format(sql.Identifier(table_name), sql.SQL(',').join(map(sql.Identifier, insert_columns)))

            with open(file_path, 'r', encoding='utf-8') as f:
                cur.copy_expert(copy_sql.as_string(conn), f)
            conn.commit()

            # 记录导入行数（直接格式化表名，避免作为参数传入导致错误）
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}".format(table_name)))
            count = cur.fetchone()[0]
            imported_counts[table_name] = count

            # 若存在 id 序列，重置到最大值
            cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (f'public.{table_name}', 'id'))
            seq_row = cur.fetchone()
            if seq_row and seq_row[0]:
                seq_name = seq_row[0]
                cur.execute(sql.SQL("SELECT COALESCE(MAX(id), 1) FROM {}".format(table_name)))
                max_id = cur.fetchone()[0]
                cur.execute("SELECT setval(%s, %s, true)", (seq_name, max_id))
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"导入表 '{table_name}' 失败：{e}")
            continue

        print(f"  -> 表 '{table_name}' 导入完成。")

    # 恢复会话角色
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close(); conn.close()

    print("\n导入完成。已导入表及行数：")
    for t, n in imported_counts.items():
        print(f"- {t}: {n} 行")


# --- 命令行接口 ---
@click.group()
def cli():
    """一个用于在 SQLite 和 PostgreSQL 之间迁移数据的工具。"""
    pass

@cli.command()
def export():
    """从 SQLite 导出数据到 CSV 文件。"""
    print("--- 开始从 SQLite 导出数据 ---")
    export_data_from_sqlite()

@cli.command('import')
@click.option('--truncate', is_flag=True, help='导入前清空表并重置序列（适用于新库）。')
@click.option('--only', multiple=True, help='仅导入指定的表（可多次传入）。')
def import_data_command(truncate, only):
    """从 CSV 文件导入数据到 PostgreSQL。"""
    print("--- 开始向 PostgreSQL 导入数据 ---")
    import_data_to_postgres(truncate=truncate, only_tables=list(only) if only else None)

if __name__ == '__main__':
    cli()
