# 选股池自动化系统

基于 Python + Vue3 的选股池自动化系统：每天将带编号的 Excel 数据表（1~20 号表，如并购重组、股权转让、质押等）通过 Web 界面快捷上传，由后端工作流引擎自动完成合并、去重、列提取与跨表匹配（百日新高/20日均线/国央企/板块），产出条件交集选股池和各类趋势汇总表。

## 🎯 核心功能

- **工作流引擎**：20+ 种工作流类型、21 种步骤类型（合并/去重/列提取/四类跨表匹配/条件交集/趋势导出/周报月报汇总等）
- **1~20 号表体系**：事件表（并购重组/股权转让/增发实现/申报并购重组/质押/减持/招投标）+ 聚合表（条件交集/AI筛选汇总/周报）+ 趋势表
- **快捷批量上传**：按文件名前缀和关键字自动路由到目标目录
- **一键批量执行**：普通工作流先行，聚合类按依赖链串行执行
- **板块信号榜**：基于涨幅排名的持续强势榜/低位反转榜（加权评分）
- **结果落库 + Excel 输出**：`workflow_results` 表存全量数据，同时输出带图表的 xlsx

各表号的权威对照见 `docs/table-registry.md`，架构模式与新表 checklist 见 `docs/architecture-patterns.md`。

## 🏗️ 技术架构

`Nginx(:7654) → Vue 3 SPA + /api/* → FastAPI(:8000) → MySQL 8.0 / Redis / FileStorage(data/excel/)`

- **后端**：FastAPI(异步) + SQLAlchemy + Pandas + OpenPyXL + APScheduler
- **前端**：Vue 3 + Element Plus + Pinia + ECharts + Vite
- **部署**：Docker Compose 四容器（mysql/redis/backend/frontend）

## 📦 项目结构

```
aistock/
├── backend/
│   ├── api/            # 路由（workflows.py 最核心）
│   ├── services/       # 工作流引擎与各表实现
│   ├── config/         # workflow_type_config.py（类型总注册表）
│   ├── models/         # 数据模型
│   ├── utils/          # 股票代码规范化、北京时区
│   └── tests/          # pytest（test_weekly_workflows.py 等）
├── frontend/src/
│   ├── views/          # Workflows.vue（核心页面）
│   ├── components/     # QuickUploadDialog.vue（快捷上传）
│   └── utils/          # quickUploadRules.js（上传路由规则）
├── data/excel/         # 全部输入输出 Excel
├── docs/               # table-registry.md / architecture-patterns.md / 研报模版
├── CLAUDE.md           # AI 会话入口文档（含需求路由表）
└── deploy.sh           # 部署与运维脚本
```

## 🚀 快速开始

### 前置要求

- Docker 20.10+、Docker Compose 2.0+

### 安装步骤

1. **克隆项目**

```bash
git clone git@github.com:callmefisher/aistock.git
cd aistock
```

2. **配置环境变量**

```bash
cp .env.example .env
# 必需 MYSQL_*/SECRET_KEY；可选 OPENAI_API_KEY/SMTP_*
```

3. **启动服务**

- **macOS**：双击 `mac.command`（首次被 Gatekeeper 拦截时右键→打开）
- **Windows**：双击 `win.bat`
- **Linux / 命令行**：`./deploy.sh up`

4. **访问应用**

- 前端界面：http://localhost:7654
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 📖 使用指南

1. 注册账号（管理员可用 `./deploy.sh promote-admin <用户名>` 提升）
2. 在工作流页面用**快捷上传**批量上传当日导出的编号表（自动按文件名路由）
3. 单个执行或**一键批量执行**工作流（聚合类自动按依赖链排序）
4. 查看/下载各号表输出与条件交集选股池
5. 板块信号榜可在 API `GET /api/v1/sector-signal` 查看（前端页面待建）

## 🔧 运维

```bash
./deploy.sh ps                     # 服务状态
./deploy.sh logs [服务]            # 查看日志
./deploy.sh smart-build            # 智能构建（指纹未变则跳过）
./deploy.sh cleanup                # 清理悬空镜像与旧构建缓存
./deploy.sh deep-cleanup           # 深度清理（慎用）
./deploy.sh backup-db [输出文件]    # 备份数据库
./deploy.sh restore-db <文件> --yes # 从 SQL 恢复（灾难恢复）
./deploy.sh init-db                # 初始化数据库表
./deploy.sh exec mysql mysql -uroot-proot_password  # 进容器执行命令
```

日常开发迭代：`./deploy.sh smart-build && ./deploy.sh restart`（见 `.rules/project_rules.md`，禁止用 docker-compose up --no-deps 替代）。

数据持久化：宿主机 `./data/`（excel/logs）+ Docker 卷（mysql_data/redis_data）。

## 💻 开发指南

```bash
# 后端
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
# 前端
cd frontend && npm install && npm run dev
# 测试
cd backend && python -m pytest tests/ -v
cd frontend && npm test
```

开发约定与需求路由见 `CLAUDE.md`；新增/修改工作流类型的 6 处必改点见 `docs/architecture-patterns.md`。

## 🔒 安全建议

1. 修改 MySQL 默认密码和 SECRET_KEY
2. 生产环境配置 SSL/防火墙
3. 定期 `./deploy.sh backup-db`

## 🐛 故障排查

1. **MySQL 连接失败**：`./deploy.sh ps` 看容器状态，`./deploy.sh logs mysql` 看日志
2. **Excel 处理错误**：核对文件名前缀与目标目录（`quickUploadRules.js`）、列名映射
3. **端口被占用**：`lsof -i :8000` 查占用；deploy.sh 自动检测并切换备用端口

## 📄 许可证

MIT License
