import os
from app import create_app, db
from app.models import (
    User, Role, Permission, Department,
    Category, Product, Partner, Tag,
    Warehouse, Stock, InventoryLog,
    Order, OrderItem,
    Article, Attachment,
    AuditLog, AiChatLog
)

# 从环境变量获取配置模式
# 支持 FLASK_ENV (Railway) 或 FLASK_CONFIG
config_name = os.getenv('FLASK_ENV') or os.getenv('FLASK_CONFIG') or 'default'
if config_name == 'production':
    config_name = 'production'
elif config_name in ('development', 'dev'):
    config_name = 'development'
    
app = create_app(config_name)

@app.shell_context_processor
def make_shell_context():
    """
    配置 Flask Shell 上下文。
    允许在命令行中使用 'flask shell' 时自动导入 db 和 app。
    """
    return dict(
        db=db, 
        app=app,
        User=User,
        Role=Role,
        Permission=Permission,
        Department=Department,
        Category=Category,
        Product=Product,
        Partner=Partner,
        Tag=Tag,
        Warehouse=Warehouse,
        Stock=Stock,
        InventoryLog=InventoryLog,
        Order=Order,
        OrderItem=OrderItem,
        Article=Article,
        Attachment=Attachment,
        AuditLog=AuditLog,
        AiChatLog=AiChatLog,
    )

if __name__ == '__main__':
    print("-------------------------------------------------------")
    print("   NEXUS PRIME SYSTEM STARTUP SEQUENCE INITIATED       ")
    print("   Target: Localhost:5000                              ")
    print("-------------------------------------------------------")
    app.run(host='0.0.0.0', port=5000)