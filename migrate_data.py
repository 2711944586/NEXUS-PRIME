import os
import sqlite3
import csv
import io
import click
from dotenv import load_dotenv

load_dotenv()

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH') or os.path.join(BASE_DIR, 'instance', 'nexus_prime.db')
POSTGRES_DB_URL = os.environ.get('DATABASE_URL')
EXPORT_DIR = os.path.join(BASE_DIR, 'data_export')

# --- 导出功能 ---
def export_data_from_sqlite():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"错误：找不到 SQLite 数据库文件于 '{SQLITE_DB_PATH}'")
        return
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing_tables = [row[0] for row in cursor.fetchall()]

    print(f"发现 {len(existing_tables)} 个表，开始导出...")
    for table_name in existing_tables:
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            if not rows: continue
            
            headers = [d[0] for d in cursor.description]
            file_path = os.path.join(EXPORT_DIR, f"{table_name}.csv")
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"  -> 已导出: {table_name}")
        except Exception as e:
            print(f"  -> 导出失败 {table_name}: {e}")
    conn.close()

# --- 导入功能 (增强版) ---
def import_data_to_postgres(truncate=False, only_tables=None):
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        print("错误：请运行 `pip install psycopg2-binary`")
        return
    
    if not POSTGRES_DB_URL:
        print("错误：未设置 DATABASE_URL")
        return

    csv_files = [f for f in os.listdir(EXPORT_DIR) if f.endswith('.csv')]
    if only_tables:
        csv_files = [f for f in csv_files if f.replace('.csv', '') in only_tables]

    print("正在连接 PostgreSQL...")
    conn = psycopg2.connect(POSTGRES_DB_URL)
    cur = conn.cursor()

    # 1. 获取目标数据库结构
    cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")
    db_schema = {}
    for t, c in cur.fetchall():
        db_schema.setdefault(t, set()).add(c)

    # 2. 暂时禁用外键检查 (关键步骤)
    cur.execute("SET session_replication_role = 'replica';")
    
    try:
        for fname in csv_files:
            table_name = fname.replace('.csv', '')
            if table_name not in db_schema:
                print(f"跳过：数据库缺表 '{table_name}'")
                continue

            # 读取 CSV 头
            file_path = os.path.join(EXPORT_DIR, fname)
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                csv_headers = next(reader, None)
            
            if not csv_headers: continue

            # 3. 计算公共列 (防止 CSV 有多余列导致报错)
            valid_cols = [c for c in csv_headers if c in db_schema[table_name]]
            if not valid_cols:
                print(f"跳过：表 '{table_name}' 无匹配列")
                continue

            if truncate:
                try:
                    cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(table_name)))
                except:
                    conn.rollback()
                    cur.execute("SET session_replication_role = 'replica';")

            # 4. 构建清洗后的数据流
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=valid_cols, extrasaction='ignore')
            writer.writeheader() # COPY 需要 header
            
            with open(file_path, 'r', encoding='utf-8') as f:
                dict_reader = csv.DictReader(f)
                for row in dict_reader:
                    writer.writerow(row)
            output.seek(0)

            try:
                # 5. 执行导入
                columns_sql = sql.SQL(',').join(map(sql.Identifier, valid_cols))
                copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
                    sql.Identifier(table_name), columns_sql
                )
                cur.copy_expert(copy_sql, output)
                conn.commit() # 及时提交
                
                # 重置 ID 序列
                if 'id' in valid_cols:
                    cur.execute("SET session_replication_role = 'replica';") # 重新确保模式
                    try:
                        seq_query = sql.SQL("SELECT setval(pg_get_serial_sequence('{}', 'id'), (SELECT MAX(id) FROM {}));").format(
                            sql.SQL(table_name), sql.Identifier(table_name))
                        cur.execute(seq_query)
                        conn.commit()
                    except:
                        conn.rollback() # 忽略无序列表的错误
                
                print(f"  -> 表 '{table_name}' 导入成功")
            except Exception as e:
                conn.rollback()
                print(f"  -> 表 '{table_name}' 导入失败: {e}")
            
            # 始终保持 replica 模式直到最后
            cur.execute("SET session_replication_role = 'replica';")

    finally:
        # 恢复外键检查
        cur.execute("SET session_replication_role = 'origin';")
        conn.commit()
        conn.close()
        print("\n操作结束。")

@click.group()
def cli(): pass

@cli.command()
def export(): export_data_from_sqlite()

@cli.command('import')
@click.option('--truncate', is_flag=True)
@click.option('--only', multiple=True)
def import_cmd(truncate, only):
    import_data_to_postgres(truncate, list(only) if only else None)

if __name__ == '__main__': cli()