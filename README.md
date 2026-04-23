# 选股池自动化系统

一个基于Python + Vue3的选股池自动化生成系统，支持从多个需要登录验证的网站导出Excel数据，通过智能规则引擎处理数据，最终生成选股池。

## 🎯 核心功能

- **多源数据抓取**：支持从不同网站（东方财富、同花顺等）抓取数据
- **多种登录方式**：支持账号密码、验证码、二维码、Cookie等多种登录方式
- **智能规则引擎**：自然语言转Excel公式/筛选条件
- **灵活调度策略**：支持手动、定时、间隔等多种任务调度方式
- **多格式输出**：在线展示、Excel下载、邮件通知、历史记录
- **Docker部署**：一键启动，易于维护

## 🏗️ 技术架构

### 后端技术栈
- **框架**：FastAPI (异步高性能)
- **数据库**：MySQL 8.0
- **缓存**：Redis
- **Web自动化**：Selenium + Chrome
- **Excel处理**：Pandas + OpenPyXL
- **任务调度**：APScheduler
- **AI服务**：OpenAI API (可选)

### 前端技术栈
- **框架**：Vue 3
- **UI组件**：Element Plus
- **构建工具**：Vite

### 部署方案
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx

## 📦 项目结构

```
aistock/
├── backend/                 # 后端代码
│   ├── api/                # API路由
│   ├── models/             # 数据模型
│   ├── services/           # 业务逻辑
│   ├── core/               # 核心配置
│   ├── utils/              # 工具函数
│   ├── tests/              # 测试代码
│   ├── main.py             # 应用入口
│   ├── requirements.txt    # Python依赖
│   └── Dockerfile          # 后端Docker配置
├── frontend/               # 前端代码
│   ├── src/               # 源代码
│   ├── dist/              # 构建产物
│   └── package.json       # Node依赖
├── data/                   # 数据目录
│   ├── excel/             # Excel文件
│   ├── logs/              # 日志文件
│   └── cookies/           # Cookie存储
├── docker-compose.yml      # Docker编排配置
├── nginx.conf             # Nginx配置
├── init.sql               # 数据库初始化脚本
└── .env.example           # 环境变量示例

```

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ 内存

### 安装步骤

1. **克隆项目**
```bash
git clone git@github.com:callmefisher/aistock.git
cd aistock
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑.env文件，配置必要的参数
```

3. **启动服务**

   - **macOS**：双击 `mac.command`（首次被 Gatekeeper 拦截时右键→打开）
   - **Windows**：双击 `win.bat`
   - **Linux / 命令行**：
     ```bash
     ./deploy.sh smart-build && ./deploy.sh restart
     ```

4. **访问应用**

默认端口：
- 前端界面：http://localhost:7654
- API 文档：http://localhost:8000/docs
- API 地址：http://localhost:8000/api/v1

### 首次使用

1. 注册用户账号
2. 配置数据源（网站登录信息）
3. 创建筛选规则
4. 创建任务并执行
5. 查看和下载选股池结果

## 📖 使用指南

### 1. 数据源配置

支持的数据源类型：
- **Excel下载**：直接下载Excel文件
- **网页表格**：从网页表格提取数据
- **API接口**：调用API获取JSON数据

登录方式：
- **账号密码**：自动填写表单登录
- **验证码**：支持图形验证码识别
- **二维码**：扫码登录
- **Cookie**：使用已有Cookie登录

### 2. 规则配置

支持自然语言规则，例如：
- "筛选PE小于20且ROE大于15%的股票"
- "选择市值大于100亿的股票"
- "过滤掉ST股票"

系统会自动将自然语言转换为Excel公式和筛选条件。

### 3. 任务调度

支持多种调度方式：
- **手动执行**：立即执行一次
- **定时执行**：Cron表达式（如每天早上9点）
- **间隔执行**：固定时间间隔（如每小时）

### 4. 结果输出

- **在线查看**：Web界面直接查看选股池
- **Excel下载**：下载标准格式的Excel文件
- **邮件通知**：任务完成后发送邮件
- **历史记录**：保存所有历史执行记录

## 🔧 开发指南

### 后端开发

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
cd backend
pytest
```

## 📊 API文档

启动服务后访问：
- Swagger UI: http://localhost/docs
- ReDoc: http://localhost/redoc

主要API端点：
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/data-sources` - 获取数据源列表
- `POST /api/v1/rules` - 创建规则
- `POST /api/v1/tasks` - 创建任务
- `GET /api/v1/stock-pools` - 获取选股池列表

## 🔒 安全建议

1. **修改默认密码**：修改MySQL root密码和用户密码
2. **配置SECRET_KEY**：生成强随机密钥
3. **启用HTTPS**：生产环境建议配置SSL证书
4. **限制访问**：配置防火墙规则限制访问
5. **定期备份**：定期备份MySQL数据

## 🐛 故障排查

### 常见问题

1. **MySQL连接失败**
   - 检查MySQL容器是否启动
   - 验证数据库配置是否正确

2. **Selenium超时**
   - 增加超时时间
   - 检查网络连接
   - 查看Chrome浏览器日志

3. **Excel处理错误**
   - 检查Excel文件格式
   - 验证数据列名是否正确

### 查看日志

```bash
# 查看后端日志
docker-compose logs backend

# 查看所有服务日志
docker-compose logs
```

## 📝 更新日志

### v1.0.0 (2024-01-XX)
- 初始版本发布
- 支持多数据源抓取
- 实现智能规则引擎
- 完成Docker部署方案

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📧 联系方式

如有问题，请提交Issue或联系开发团队。
