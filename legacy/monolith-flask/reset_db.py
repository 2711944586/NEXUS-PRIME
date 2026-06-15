import os
from app import create_app, db
# 显式导入所有模型，确保 SQLAlchemy 能找到它们
from app.models import auth, biz, content, finance, notification, purchase, stock, stocktake, sys as sys_model, trade

from dotenv import load_dotenv

load_dotenv()

# 获取数据库连接
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("❌ 错误：未设置 DATABASE_URL。请确保配置了 Railway 连接串。")
    exit(1)

app = create_app('production')

with app.app_context():
    print(f"🔌 正在连接数据库: {db_url.split('@')[-1]}") # 打印部分信息以确认
    print("⚠️  警告：这将删除该数据库中的所有表和数据！")
    
    confirm = input("❓ 确认要重置吗？(输入 yes 继续): ")
    if confirm.lower() != 'yes':
        print("已取消。")
        exit()

    try:
        # 1. 删除所有表 (Drop All)
        print("🗑️  正在删除旧表...")
        # 暂时禁用外键检查以避免删除顺序问题 (针对 Postgres)
        db.session.execute(db.text("DROP SCHEMA public CASCADE;"))
        db.session.execute(db.text("CREATE SCHEMA public;"))
        db.session.execute(db.text("GRANT ALL ON SCHEMA public TO postgres;"))
        db.session.execute(db.text("GRANT ALL ON SCHEMA public TO public;"))
        db.session.commit()
        print("✅ 旧表已全部清除。")

        # 2. 重新创建表 (Create All)
        print("🏗️  正在根据最新代码创建新表...")
        db.create_all()
        print("✅ 新表结构创建成功！")
        
        print("\n🎉 数据库重置完成。现在请运行 migrate_data.py 导入数据。")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        print("提示：如果因连接占满失败，请尝试在 Railway 控制台重启一下 PostgreSQL 服务后再试。")