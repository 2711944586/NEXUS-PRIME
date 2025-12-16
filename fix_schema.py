import os
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def fix_auth_users_table():
    if not DATABASE_URL:
        print("❌ 错误：未设置 DATABASE_URL。请确保连接到 Railway。")
        return

    print("🔌 正在连接数据库...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 定义代码中存在但数据库可能缺失的列
        # 格式: (列名, 类型, 默认值/约束)
        missing_columns = [
            ("failed_login_attempts", "INTEGER", "DEFAULT 0"),
            ("locked_until", "TIMESTAMP WITHOUT TIME ZONE", "NULL"),
            ("last_password_change", "TIMESTAMP WITHOUT TIME ZONE", "DEFAULT CURRENT_TIMESTAMP"),
            ("is_active_user", "BOOLEAN", "DEFAULT TRUE"),
            ("department_name", "VARCHAR(100)", "NULL"), # 补全可能缺失的业务字段
            ("position", "VARCHAR(100)", "NULL"),
            ("bio", "TEXT", "NULL"),
            ("preferences", "JSON", "NULL"),
            ("is_admin", "BOOLEAN", "DEFAULT FALSE")
        ]

        print("🔍 正在检查并修复 auth_users 表结构...")

        for col, dtype, constraint in missing_columns:
            try:
                # 尝试添加列
                alter_query = f"ALTER TABLE auth_users ADD COLUMN {col} {dtype} {constraint};"
                cur.execute(alter_query)
                conn.commit()
                print(f"✅ 成功添加列: {col}")
            except psycopg2.errors.DuplicateColumn:
                # 如果列已存在，忽略错误
                conn.rollback()
                print(f"ℹ️  列已存在，跳过: {col}")
            except Exception as e:
                conn.rollback()
                print(f"⚠️ 添加列 {col} 失败: {e}")

        # 额外修复：确保 password_hash 足够长 (防止旧数据长度不够)
        try:
            cur.execute("ALTER TABLE auth_users ALTER COLUMN password_hash TYPE TEXT;")
            conn.commit()
            print("✅ 已将 password_hash 扩容为 TEXT 类型")
        except Exception as e:
            conn.rollback()
            print(f"ℹ️  password_hash 调整跳过: {e}")

        conn.close()
        print("\n🎉 数据库结构修复完成！")

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

if __name__ == "__main__":
    fix_auth_users_table()