# 🚀 NEXUS PRIME - 量子仓储管理系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green.svg" alt="Flask">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

一个现代化的企业级仓储管理系统，具有量子科技风格的用户界面。

---

## 📋 功能模块

- 🏠 **智能仪表盘** - 实时数据可视化
- 📦 **量子仓储** - 库存管理与调拨
- 🛒 **销售管理** - 订单处理与发票
- 📥 **采购管理** - 供应商与采购订单
- 💰 **财务中心** - 应收账款与信用管理
- 📊 **报表分析** - 多维度数据分析
- 🔔 **通知中心** - 智能预警与订阅
- 🤖 **AI 助手** - DeepSeek 智能分析
- ⚙️ **系统管理** - 团队、审计、设置

---

## 🔐 管理员账号

| 项目 | 值 |
|------|-----|
| **用户名** | Commander |
| **邮箱** | admin@nexus.com |
| **密码** | admin |

> ⚠️ **重要**: 首次登录后请立即修改默认密码！

普通用户默认密码: `password`

---

## 🛠️ 技术栈

### 后端
- Python 3.10+
- Flask 3.0
- SQLAlchemy 2.0
- Flask-Login / Flask-WTF
- Gunicorn (生产服务器)

### 前端
- Jinja2 模板
- Bootstrap 5
- ECharts 5 (图表)
- Font Awesome (图标)
- CSS3 变量 (主题切换)

### 数据库
- 开发环境: SQLite
- 生产环境: PostgreSQL

---

## 📦 本地安装

### 1. 克隆项目

```bash
git clone https://github.com/2711944586/NEXUS-PRIME.git
cd NEXUS-PRIME
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，设置必要的环境变量
```

### 5. 初始化数据库

```bash
# 执行数据库迁移
flask db upgrade

# 生成测试数据（包含管理员账号）
flask forge

# 可选：指定数据规模（默认10倍）
flask forge --scale 5
```

### 6. 运行应用

```bash
# 开发模式
flask run

# 或者
python run.py
```

访问 http://127.0.0.1:5000

---

## 🚀 Railway 部署

### 步骤 1: 创建项目

1. 登录 [Railway](https://railway.app)
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择 `NEXUS-PRIME` 仓库

### 步骤 2: 添加数据库

1. 在项目中点击 **+ New** → **Database** → **PostgreSQL**
2. Railway 会自动注入 `DATABASE_URL` 环境变量

### 步骤 3: 配置环境变量

在 **Variables** 中添加：

```env
FLASK_ENV=production
SECRET_KEY=<运行 python -c "import secrets; print(secrets.token_hex(32))" 生成>
DEEPSEEK_API_KEY=<你的DeepSeek API密钥，可选>
AI_FALLBACK=true
```

> 💡 **AI 功能说明**：
> - 如果有 DeepSeek API Key，填入 `DEEPSEEK_API_KEY` 即可使用 AI 助手
> - 如果没有，设置 `AI_FALLBACK=true` 使用本地回退模式
> - DeepSeek API 申请：https://platform.deepseek.com

### 步骤 4: 初始化数据库

部署完成后，在 Railway Shell 中运行：

```bash
flask db upgrade
flask forge --scale 5
```

### 步骤 5: 生成域名

在 **Settings** → **Networking** → **Generate Domain**

---

## 📁 项目结构

```
NEXUS-PRIME/
├── app/
│   ├── blueprints/      # 13个功能模块
│   │   ├── ai/          # AI 助手
│   │   ├── auth/        # 认证登录
│   │   ├── cms/         # 内容管理
│   │   ├── finance/     # 财务中心
│   │   ├── inventory/   # 库存管理
│   │   ├── main/        # 主页仪表盘
│   │   ├── notification/# 通知中心
│   │   ├── profile/     # 个人中心
│   │   ├── purchase/    # 采购管理
│   │   ├── reports/     # 报表分析
│   │   ├── sales/       # 销售管理
│   │   ├── stocktake/   # 盘点管理
│   │   └── system/      # 系统设置
│   ├── models/          # 数据模型 (37张表)
│   ├── services/        # 业务服务层
│   ├── templates/       # Jinja2 模板
│   ├── static/          # 静态资源
│   └── utils/           # 工具函数
├── migrations/          # 数据库迁移
├── config.py            # 配置文件
├── run.py              # 应用入口
├── requirements.txt     # Python 依赖
├── Procfile            # Railway 部署
└── railway.json        # Railway 配置
```

---

## 🔧 常用命令

```bash
# 查看数据库状态
flask status

# 生成测试数据
flask forge --scale 10

# 数据库迁移
flask db migrate -m "描述"
flask db upgrade

# 本地运行
flask run --debug
```

---

## 🌙 主题切换

系统支持 **暗色模式** 和 **亮色模式**，点击导航栏的主题图标即可切换。

---

## 📄 License

MIT License

---

## 👨‍💻 作者
庄颂

---

**🌟 如果这个项目对你有帮助，请给个 Star！**
