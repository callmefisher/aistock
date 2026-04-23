# 快捷批量上传设计

日期: 2026-04-23
作者: brainstorming 共创
状态: Draft

## 目标

在"工作流"页面顶部新增一个「快捷批量上传」入口，一次性完成以下事情：

1. 选择本地一个目录（或多个文件），批量上传到正确的工作流子目录；
2. 根据文件名规则自动路由到对应 `workflow_type + 子目录`；
3. 上传完成后统一同步所有工作流的数据日期；
4. 自动预勾选所有可执行工作流，弹出并行执行确认框。

目的是把当前"分别去每个工作流逐个上传文件、逐个改日期、最后再点批量执行"的重复操作压缩到一个对话框里。

## 非目标

- 不做 WebSocket 流式上传；
- 不做上传历史/版本管理（当前系统本来就同名覆盖）；
- 不强制要求用户账号下每种 workflow_type 都已存在工作流（未建的类型允许落盘，但不执行）；
- 不自动创建缺失的工作流。

## 架构

```
Workflows.vue 顶部新按钮「快捷批量上传」
  → QuickUploadDialog.vue（新组件，多步向导）
      Step 1: 选目录或多文件 + 选 {date}（默认今天）
      Step 2: 解析预览（resolveTarget 纯函数）+ 列已有文件 + 同名高亮
      Step 3: 并发上传（复用 POST /workflows/upload-step-file/）
      Step 4: 批量同步 date_str（新增 PUT /workflows/bulk-set-date）
      Step 5: 关闭对话框，打开现有 batchRun 对话框，预勾选所有可执行工作流
```

## 组件清单

### 前端

| 文件 | 变更 | 预估行数 |
|---|---|---|
| `frontend/src/views/Workflows.vue` | 顶部加按钮；引入 `QuickUploadDialog`；新增 `openQuickUploadDialog()`、`onQuickUploadDone(date)` 注入日期并打开 batchRun | +60 |
| `frontend/src/components/QuickUploadDialog.vue` | 新建对话框组件 | ~450 |
| `frontend/src/utils/quickUploadRules.js` | 纯函数 `resolveTarget(filename)` | ~120 |
| `frontend/tests/quickUploadRules.spec.js` | 单测 | ~150 |

### 后端

| 文件 | 变更 | 预估行数 |
|---|---|---|
| `backend/api/workflows.py` | 新增 `PUT /workflows/bulk-set-date` 端点 | +40 |
| `backend/tests/test_workflows_bulk_set_date.py` | 新增单测 | ~80 |

### 复用

- `POST /workflows/upload-step-file/` （workflows.py:579）：不改。参数 `workflow_type + date_str + step_type + file`，按 path_resolver 落盘，同名覆盖。
- `GET /workflows/step-files/` （workflows.py:632）：不改。用来列目标目录下已有文件。
- `Workflows.vue` 现有 `openBatchRunDialog()` / `handleBatchRun()` / batch-status 轮询：不改，作为 Step 5 的交接点。

## 文件名解析规则（resolveTarget）

### 归一化

1. 取叶子文件名（忽略相对路径）；
2. 过滤扩展名非 `.xlsx/.xls/.csv`；
3. 过滤隐藏文件（`.` 开头）和 Office 锁文件（`~$` 开头）；
4. 去扩展名后再匹配。

### 匹配优先级（高 → 低）

**优先级 1：子目录关键字（大小写不敏感）**
| 关键字 | workflow_type | step_type | 最终落盘目录 |
|---|---|---|---|
| 包含"百日新高" | 并购重组 | match_high_price | `data/excel/{date}/百日新高/` |
| 包含"20日均线" 或 "20日线" | 并购重组 | match_ma20 | `data/excel/{date}/20日均线/` |
| 包含"国央企" | 并购重组 | match_soe | `data/excel/{date}/国企/` |
| 包含"板块" | 并购重组 | match_sector | `data/excel/{date}/一级板块/` |

**优先级 2：首位数字前缀（未命中子目录关键字时）**
| 正则 | workflow_type | step_type | 最终落盘目录 |
|---|---|---|---|
| `^1` | 并购重组 | merge_excel | `data/excel/{date}/` |
| `^2` | 股权转让 | merge_excel | `data/excel/股权转让/{date}/` |
| `^3` | 增发实现 | merge_excel | `data/excel/增发实现/{date}/` |
| `^4` | 申报并购重组 | merge_excel | `data/excel/申报并购重组/{date}/` |
| `^5` | 质押 | merge_excel | `data/excel/质押/{date}/`（中大盘/小盘由后端 `_derive_pledge_source` 按文件名前缀自动判定，不在前端区分） |
| `^6` | 减持叠加质押和大宗交易 | merge_excel | `data/excel/减持叠加质押和大宗交易/{date}/` |
| `^8` | 涨幅排名 | merge_excel | `data/excel/涨幅排名/{date}/` |
| `^9` | 招投标 | merge_excel | `data/excel/招投标/{date}/` |

**未命中任何规则** → `unresolved`，进入预览页未识别区，软校验跳过，不阻断。

### resolveTarget 返回值

```ts
{
  filename: string,
  workflow_type: string | null,
  step_type: string | null,
  sub_dir: string | null,
  target_dir: string,          // 展示给用户的相对路径（data/excel/... 形式）
  status: 'resolved' | 'unresolved',
  reason: string,              // 未识别时写"未匹配任何规则"，识别时写命中的规则名
}
```

## UI 流程

### Step 1: 选文件

- `<input type="file" webkitdirectory multiple>`（现代浏览器都支持）+ 额外一个"选多个文件"入口；
- 日期选择器（el-date-picker，默认今天）；
- 下方实时显示"发现 N 个文件"。

### Step 2: 预览

分三区：
- ✅ **识别成功区**（按 workflow_type 分组折叠展示）：每行 `文件名 → 目标目录`；每组右侧展示"目标目录已有文件"列表（调 `GET /workflows/step-files/` 拉取）；同名文件行加 `⚠️ 将覆盖` 红标；
- ❌ **未识别区**：文件名 + 原因；这些文件不会上传；
- 📊 **统计条**：`识别 N / 未识别 K / 覆盖同名 X`；
- 主按钮："确认上传"（未识别不阻断）；次按钮："返回修改"。

### Step 3: 上传执行

- 并发度 4，使用 `Promise.allSettled`；
- 每文件进度条 + 全局进度统计；
- 失败项单列 + "重试失败项"按钮；
- 全部成功或用户显式跳过失败 → 进入 Step 4。

### Step 4: 同步日期

- 调 `PUT /workflows/bulk-set-date` body `{date_str}`；
- 成功：toast `已将 N 个工作流日期改为 YYYY-MM-DD`；失败：toast warning，但不阻断 Step 5；
- 自动进入 Step 5。

### Step 5: 触发执行

- 关闭当前对话框；
- 调用 `Workflows.vue` 的 `openBatchRunDialog()`，预勾选所有 `is_aggregation != True && is_export_only != True` 的工作流（聚合类和导出类用户需要手动加勾）；
- 用户在现有批量执行对话框里点"开始执行" → 走现有 `handleBatchRun` 流程。

## 后端 API 规格

### PUT /workflows/bulk-set-date

**请求**
```json
{ "date_str": "2026-04-23" }
```

**响应**
```json
{ "success": true, "updated_count": 12 }
```

**行为**
- 校验 `date_str` 格式为 `YYYY-MM-DD`，否则 422；
- 查询当前登录用户下所有 `Workflow` 记录；
- 对每条 workflow：
  - 更新 `Workflow.date_str = date_str`；
  - 遍历 `Workflow.steps`（JSON），每个 step 若有 `config.date_str` 字段，同步更新；
- DB 事务提交，失败则回滚并返回 500；
- 聚合类（条件交集、百日新高总趋势、导出20日均线趋势）一并更新，以保持联动。

**权限**: 需登录；只影响当前用户自己的 workflow。

## 错误处理与边界

| 场景 | 行为 |
|---|---|
| 空目录 | "未发现任何文件"，禁用"下一步" |
| 含非 Excel 文件 | 按扩展名过滤，不进未识别区 |
| 多个同规则文件（如两个 5 开头） | 全部落到质押目录，不改名 |
| 同一子目录多个文件 | 都进对应子目录，同名后者覆盖前者 |
| {date} 目录不存在 | 后端 upload API 自动 mkdir（path_resolver 已有） |
| 用户中途取消 | 已上传文件保留；日期未改；执行不触发 |
| 某 workflow_type 账号下无工作流 | 文件仍落盘；Step 5 预勾选列表无此项 |
| bulk-set-date 失败 | 上传不回滚；warning 提示手动改日期；仍进入 Step 5 |
| 上传部分失败 | 弹"重试失败项"；允许跳过继续 |

## 测试

### 前端（Vitest）

`frontend/tests/quickUploadRules.spec.js`：
- `1并购重组0422.xlsx` → 并购重组 / merge_excel
- `2股权转让0422.xlsx` → 股权转让
- `3增发实现0422.xlsx` → 增发实现
- `4申报并购重组0422.xlsx` → 申报并购重组
- `5质押中大盘0422.xlsx` → 质押
- `5质押小盘0422.xlsx` → 质押（同目录）
- `6减持叠加质押和大宗交易0422.xlsx` → 减持叠加质押和大宗交易
- `8涨幅排名0422.xlsx` → 涨幅排名
- `9招投标0422.xlsx` → 招投标
- `百日新高0422.xlsx` → match_high_price
- `20日均线0422.xlsx` → match_ma20
- `20日线0422.xlsx` → match_ma20（同义）
- `国央企0422.xlsx` → match_soe
- `一级板块0422.xlsx` → match_sector（因含"板块"）
- `1百日新高0422.xlsx` → match_high_price（关键字优先，覆盖数字前缀）
- `abc.xlsx` → unresolved
- `.DS_Store` / `~$temp.xlsx` → 被过滤，不返回
- `readme.txt` → 被过滤，不返回

### 后端（pytest）

`backend/tests/test_workflows_bulk_set_date.py`：
- 正常：多个工作流全部更新成功；
- 空日期 / 格式非法（`2026/04/23`、`26-4-23`）→ 422；
- 未登录 → 401；
- DB 异常（mock commit 抛异常）→ 500 + 回滚；
- 只影响自己账号的 workflow；
- 聚合类型也被更新。

### 手工 e2e

准备测试目录含以下文件：
```
1并购重组0423.xlsx
2股权转让0423.xlsx
5质押中大盘0423.xlsx
8涨幅排名0423.xlsx
百日新高0423.xlsx
国央企0423.xlsx
一级板块0423.xlsx
readme.txt
```

预期：
1. 预览页识别 7 个；readme.txt 被过滤不显示；
2. 4 个子目录文件分别进 `2026-04-23/百日新高`、`/国企`、`/一级板块`；
3. 其他 3 个进各自 workflow_type 目录；
4. 所有工作流 date_str 变为 2026-04-23；
5. 批量执行对话框弹出，除条件交集/百日新高总趋势外预勾选。

## 部署

无 schema 变更，无配置变更。按 `./deploy.sh build && ./deploy.sh restart` 重启。

## 风险

1. **批量改日期的影响面**：`PUT /workflows/bulk-set-date` 会改当前用户所有工作流的日期，包括本次没上传文件的。这是用户明确要求（"所有工作流"）。缓解：Step 4 toast 明确显示"已将 N 个工作流日期改为 XXX"，用户可感知。
2. **webkitdirectory 兼容**：现代浏览器均支持；不做额外降级；旧浏览器退化为"请用现代浏览器"提示。
3. **并发上传压力**：并发度 4 + 单文件 ≤ 几 MB，可控。
