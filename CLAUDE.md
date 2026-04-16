# 选股池自动化系统

## 流程

设计 → 实施 → review(逻辑/边界/错误处理) → 测试 → `./deploy.sh build && ./deploy.sh restart` → 更新 codebase.md

- 需求不明确先澄清，不猜测编码
- >3 文件变更必须分解子任务
- Bug 修复遵循 TDD：写失败测试 → 修复 → 全部通过
- 用户纠正后在「经验教训」追加规则

## 经验教训

1. Excel 源文件可能有双行表头（第1行分组头，第2行实际列名）。`_merge_excel` 动态查找序号=1行，检测前一行是否含已知列名再决定是否重映射。禁止硬编码 iloc 分割。
2. 列名重映射仅在前一行含已知列名（证券代码/证券简称/最新公告日等）时触发，否则元数据值会被误当列名。
3. 双行表头子列名可能重复（如受让方/转让方各有"名称"列），重映射后必须去重列名（追加 `_1` 后缀），否则 `pd.concat` 报 Reindexing 错误。

## 命令

```bash
./deploy.sh build          # 构建镜像
./deploy.sh restart        # 重启服务
./deploy.sh ps             # 状态
./deploy.sh logs [service] # 日志
cd backend && python -m pytest tests/ -v  # 后端测试
cd frontend && npm test                   # 前端测试
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:7654 |
| API  | http://localhost:8000/docs |
| MySQL | localhost:3306 |
| Redis | localhost:6379 |

## 架构

```
Nginx(:7654) → Vue 3 SPA + /api/* proxy → FastAPI(:8000) → MySQL/Redis/FileStorage
```

## 目录

```
backend/
  main.py                        # FastAPI 入口
  core/config.py, database.py    # 配置(.env) + SQLAlchemy
  api/                           # 7 路由: auth, workflows, tasks, rules, data_sources, stock_pools, data_api
  models/models.py               # 8 ORM: User, Workflow, Rule, Task, ExecutionLog, StockPool, BatchExecution, DataSource
  services/workflow_executor.py  # 核心: 11 步骤类型 (merge/dedup/match_*/condition_intersection)
  services/path_resolver.py      # 按 workflow_type 动态路径
  services/rule_engine.py        # NL→Excel公式 (OpenAI+fallback)
  config/workflow_type_config.py # 工作流类型定义(7类型+条件交集)
  utils/stock_code_normalizer.py # 证券代码标准化
frontend/src/
  views/Workflows.vue            # 核心页面(~900行): 步骤构建/执行/批量/下载
  stores/auth.js                 # Pinia JWT 状态
  utils/api.js                   # Axios 拦截器
```

## 工作流

| 类型 | 上传目录 | 公共目录 |
|------|---------|---------|
| 并购重组 | `data/excel/{date}/` | `data/excel/2025public/` |
| 股权转让 | `data/excel/股权转让/{date}/` | `data/excel/股权转让/public/` |

步骤链: `merge_excel → smart_dedup → extract_columns → match_high_price → match_ma20 → match_soe → match_sector`

## 条件交集工作流

- **类型**: 条件交集，聚合类工作流，不处理自己的数据，从其他工作流的 DB 结果中读取
- **步骤**: 仅 `condition_intersection` 一个步骤
- **过滤条件**: 百日新高(默认)/20日均线/国企/一级板块，全局 AND/OR
- **输出**: 双 Sheet Excel (`7条件交集{date}.xlsx`)
  - Sheet1: 所有类型过滤后合并，列: 序号/证券代码/证券简称/最新公告日/百日新高/站上20日线/国央企/所属板块/资本运作行为
  - Sheet2: 交集选股池(xx年xx月选股池)，保存到 stock_pools 表
- **工作流顺序**: 默认 并购重组→股权转让→增发实现→申报并购重组→减持叠加质押和大宗交易→招投标，UI 可调
- **唯一性约束**: 同 workflow_type + 同 date_str 只允许一个工作流（全局生效）
- **列名映射**: 20日均线→站上20日线, 国企→国央企, 一级板块→所属板块（仅输出重命名，原始数据不动）

## 关键逻辑

- **merge_excel**: 公共文件 skiprows=1；非公共文件查找序号=1行开始，双行表头自动列名重映射
- **smart_dedup**: 按日期降序 + `drop_duplicates(subset=证券代码, keep=first)` 保留最新日期，过滤 .NQ
- **股权转让列映射**: 代码→证券代码, 名称→证券简称, 公告日期→最新公告日
- **证券代码匹配**: `normalize_stock_code()` 统一格式，`match_stock_code_flexible()` 跨格式比对
- **认证**: JWT HS256, 7天过期, localStorage 存储
- **环境变量**: `.env`(gitignored), 必需: MYSQL_*, SECRET_KEY; 可选: OPENAI_API_KEY, SMTP_*

## 数据目录

```
data/excel/
  2025public/    百日新高/    20日均线/    国企/    一级板块/
  {date}/        # 日上传 + 步骤输出(total_1.xlsx, deduped.xlsx, output_*.xlsx)
  股权转让/public/  股权转让/{date}/
```
