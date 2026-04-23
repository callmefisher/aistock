# 快捷批量上传 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作流页面顶部加「快捷批量上传」按钮，一键完成"选目录 → 按文件名路由到对应 workflow_type/子目录 → 上传 → 同步所有工作流日期 → 预勾选并弹出批量执行确认框"。

**Architecture:** 前端新增 `QuickUploadDialog.vue` 多步向导 + `quickUploadRules.js` 纯函数解析文件名；复用现有 `POST /workflows/upload-step-file/` 单文件上传接口（并发 4）；后端新增 `PUT /workflows/bulk-set-date` 批量同步日期；执行阶段复用现有 `handleBatchRun` 对话框。

**Tech Stack:** Vue 3 + Element Plus + Vitest（前端）；FastAPI + SQLAlchemy + pytest（后端）。

**Spec:** `docs/superpowers/specs/2026-04-23-quick-batch-upload-design.md`

---

## 文件结构

### 新建
- `frontend/src/utils/quickUploadRules.js`（~120 行）：纯函数 `resolveTarget(filename)`、`normalizeFilename(filename)`、`WORKFLOW_TYPE_FOR_PREFIX` 常量。
- `frontend/tests/unit/quickUploadRules.test.js`（~180 行）：单测。
- `frontend/src/components/QuickUploadDialog.vue`（~450 行）：多步对话框组件。
- `backend/tests/test_workflows_bulk_set_date.py`（~100 行）：后端单测。

### 修改
- `backend/api/workflows.py`：在 `POST /workflows/batch-run/` 后新增 `PUT /workflows/bulk-set-date` 端点（~40 行增量）。
- `frontend/src/views/Workflows.vue`：顶部新增按钮、引入 `QuickUploadDialog`、新增 `quickUploadVisible` 状态、新增 `openQuickUpload()`、`onQuickUploadFinish(dateStr)` 方法（~60 行增量）。

---

## Task 1: 前端 - 文件名解析规则（TDD）

**Files:**
- Create: `frontend/src/utils/quickUploadRules.js`
- Create: `frontend/tests/unit/quickUploadRules.test.js`

- [ ] **Step 1.1: 写失败测试**

创建 `frontend/tests/unit/quickUploadRules.test.js`：

```js
import { describe, it, expect } from 'vitest'
import { resolveTarget, isAcceptableFile } from '@/utils/quickUploadRules'

describe('resolveTarget - 子目录关键字（优先级 1）', () => {
  it('含"百日新高" → 并购重组/match_high_price', () => {
    const r = resolveTarget('百日新高0422.xlsx')
    expect(r.status).toBe('resolved')
    expect(r.workflow_type).toBe('并购重组')
    expect(r.step_type).toBe('match_high_price')
    expect(r.sub_dir).toBe('百日新高')
  })

  it('含"20日均线" → match_ma20', () => {
    const r = resolveTarget('20日均线0422.xlsx')
    expect(r.step_type).toBe('match_ma20')
    expect(r.sub_dir).toBe('20日均线')
  })

  it('含"20日线"同义词 → match_ma20', () => {
    const r = resolveTarget('站上20日线0422.xlsx')
    expect(r.step_type).toBe('match_ma20')
  })

  it('含"国央企" → match_soe', () => {
    const r = resolveTarget('国央企0422.xlsx')
    expect(r.step_type).toBe('match_soe')
    expect(r.sub_dir).toBe('国企')
  })

  it('含"板块" → match_sector', () => {
    const r = resolveTarget('一级板块0422.xlsx')
    expect(r.step_type).toBe('match_sector')
    expect(r.sub_dir).toBe('一级板块')
  })

  it('"1百日新高0422" 关键字优先于数字前缀', () => {
    const r = resolveTarget('1百日新高0422.xlsx')
    expect(r.step_type).toBe('match_high_price')
    expect(r.workflow_type).toBe('并购重组')
  })
})

describe('resolveTarget - 数字前缀（优先级 2）', () => {
  const cases = [
    ['1并购重组0422.xlsx', '并购重组'],
    ['2股权转让0422.xlsx', '股权转让'],
    ['3增发实现0422.xlsx', '增发实现'],
    ['4申报并购重组0422.xlsx', '申报并购重组'],
    ['5质押中大盘0422.xlsx', '质押'],
    ['5质押小盘0422.xlsx', '质押'],
    ['6减持叠加质押和大宗交易0422.xlsx', '减持叠加质押和大宗交易'],
    ['8涨幅排名0422.xlsx', '涨幅排名'],
    ['9招投标0422.xlsx', '招投标'],
  ]
  cases.forEach(([name, wt]) => {
    it(`${name} → ${wt}`, () => {
      const r = resolveTarget(name)
      expect(r.status).toBe('resolved')
      expect(r.workflow_type).toBe(wt)
      expect(r.step_type).toBe('merge_excel')
      expect(r.sub_dir).toBeNull()
    })
  })
})

describe('resolveTarget - 未识别', () => {
  it('无数字前缀无关键字 → unresolved', () => {
    const r = resolveTarget('abc.xlsx')
    expect(r.status).toBe('unresolved')
  })

  it('0 或 7 开头 → unresolved', () => {
    expect(resolveTarget('0foo.xlsx').status).toBe('unresolved')
    expect(resolveTarget('7条件交集.xlsx').status).toBe('unresolved')
  })
})

describe('isAcceptableFile - 扩展名和隐藏文件过滤', () => {
  it('接受 .xlsx/.xls', () => {
    expect(isAcceptableFile('a.xlsx')).toBe(true)
    expect(isAcceptableFile('a.xls')).toBe(true)
  })

  it('拒绝非 Excel 扩展名', () => {
    expect(isAcceptableFile('a.txt')).toBe(false)
    expect(isAcceptableFile('a.csv')).toBe(false)
    expect(isAcceptableFile('readme')).toBe(false)
  })

  it('拒绝隐藏文件和 Office 锁文件', () => {
    expect(isAcceptableFile('.DS_Store')).toBe(false)
    expect(isAcceptableFile('.hidden.xlsx')).toBe(false)
    expect(isAcceptableFile('~$temp.xlsx')).toBe(false)
  })
})

describe('resolveTarget - 目标路径展示字符串', () => {
  it('1 开头 target_dir 相对路径', () => {
    const r = resolveTarget('1并购重组0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/2026-04-23/')
  })

  it('2 开头 target_dir', () => {
    const r = resolveTarget('2股权转让0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/股权转让/2026-04-23/')
  })

  it('子目录 target_dir', () => {
    const r = resolveTarget('百日新高0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/2026-04-23/百日新高/')
  })
})
```

- [ ] **Step 1.2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/quickUploadRules.test.js
```

Expected: 全部 FAIL，`Failed to resolve import "@/utils/quickUploadRules"`。

- [ ] **Step 1.3: 写实现**

创建 `frontend/src/utils/quickUploadRules.js`：

```js
const ACCEPT_EXTS = ['.xlsx', '.xls']

export function isAcceptableFile(filename) {
  if (!filename) return false
  if (filename.startsWith('.')) return false
  if (filename.startsWith('~$')) return false
  const lower = filename.toLowerCase()
  return ACCEPT_EXTS.some(ext => lower.endsWith(ext))
}

const SUBDIR_KEYWORDS = [
  { keywords: ['百日新高'], step_type: 'match_high_price', sub_dir: '百日新高' },
  { keywords: ['20日均线', '20日线'], step_type: 'match_ma20', sub_dir: '20日均线' },
  { keywords: ['国央企'], step_type: 'match_soe', sub_dir: '国企' },
  { keywords: ['板块'], step_type: 'match_sector', sub_dir: '一级板块' },
]

const PREFIX_TO_TYPE = {
  '1': '并购重组',
  '2': '股权转让',
  '3': '增发实现',
  '4': '申报并购重组',
  '5': '质押',
  '6': '减持叠加质押和大宗交易',
  '8': '涨幅排名',
  '9': '招投标',
}

const WORKFLOW_TYPE_TO_BASE = {
  '并购重组': '',
  '股权转让': '股权转让',
  '增发实现': '增发实现',
  '申报并购重组': '申报并购重组',
  '质押': '质押',
  '减持叠加质押和大宗交易': '减持叠加质押和大宗交易',
  '涨幅排名': '涨幅排名',
  '招投标': '招投标',
}

function stripExt(name) {
  const idx = name.lastIndexOf('.')
  return idx > 0 ? name.slice(0, idx) : name
}

function buildTargetDir(workflow_type, sub_dir, date_str) {
  const base = WORKFLOW_TYPE_TO_BASE[workflow_type]
  const d = date_str || '{date}'
  const parts = ['data/excel']
  if (base) parts.push(base)
  parts.push(d)
  if (sub_dir) parts.push(sub_dir)
  return parts.join('/') + '/'
}

export function resolveTarget(filename, date_str = '{date}') {
  const base = stripExt(filename)

  // 优先级 1: 子目录关键字
  for (const { keywords, step_type, sub_dir } of SUBDIR_KEYWORDS) {
    if (keywords.some(k => base.includes(k))) {
      return {
        filename,
        workflow_type: '并购重组',
        step_type,
        sub_dir,
        target_dir: buildTargetDir('并购重组', sub_dir, date_str),
        status: 'resolved',
        reason: `命中关键字 "${keywords[0]}"`,
      }
    }
  }

  // 优先级 2: 数字前缀
  const first = base.charAt(0)
  if (PREFIX_TO_TYPE[first]) {
    const wt = PREFIX_TO_TYPE[first]
    return {
      filename,
      workflow_type: wt,
      step_type: 'merge_excel',
      sub_dir: null,
      target_dir: buildTargetDir(wt, null, date_str),
      status: 'resolved',
      reason: `首位数字 "${first}" → ${wt}`,
    }
  }

  return {
    filename,
    workflow_type: null,
    step_type: null,
    sub_dir: null,
    target_dir: '',
    status: 'unresolved',
    reason: '未匹配任何规则',
  }
}
```

- [ ] **Step 1.4: 运行测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/quickUploadRules.test.js
```

Expected: 全部 PASS（30+ 用例）。

- [ ] **Step 1.5: 提交**

```bash
cd /Users/xiayanji/qbox/aistock && \
git add frontend/src/utils/quickUploadRules.js frontend/tests/unit/quickUploadRules.test.js && \
git commit -m "$(cat <<'EOF'
feat(quick-upload): 文件名解析规则 resolveTarget

前端纯函数：按"子目录关键字优先、数字前缀次之"解析文件
落盘目标。配全量单测。
EOF
)"
```

---

## Task 2: 后端 - `PUT /workflows/bulk-set-date`（TDD）

**Files:**
- Create: `backend/tests/test_workflows_bulk_set_date.py`
- Modify: `backend/api/workflows.py`（在 `@router.post("/batch-run/")` 前后插入新端点）

- [ ] **Step 2.1: 写失败测试**

参考现有 `backend/tests/test_ranking_format.py` 模式，创建 `backend/tests/test_workflows_bulk_set_date.py`：

```python
"""测试 PUT /workflows/bulk-set-date 批量同步日期端点"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from main import app
from core.database import get_async_db
from models.models import Workflow


@pytest.mark.asyncio
async def test_bulk_set_date_updates_all_workflows(auth_client: AsyncClient, db_session):
    """正常：所有工作流的 date_str 和 steps[].config.date_str 同步更新"""
    wf1 = Workflow(
        name="测试并购1", workflow_type="并购重组", date_str="2026-04-20",
        steps=[
            {"type": "merge_excel", "config": {"date_str": "2026-04-20"}},
            {"type": "match_high_price", "config": {"date_str": "2026-04-20"}},
        ],
    )
    wf2 = Workflow(
        name="测试质押", workflow_type="质押", date_str="2026-04-20",
        steps=[{"type": "merge_excel", "config": {"date_str": "2026-04-20"}}],
    )
    db_session.add_all([wf1, wf2])
    await db_session.commit()

    resp = await auth_client.put("/api/workflows/bulk-set-date", json={"date_str": "2026-04-23"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["updated_count"] >= 2

    await db_session.refresh(wf1)
    await db_session.refresh(wf2)
    assert wf1.date_str == "2026-04-23"
    assert wf2.date_str == "2026-04-23"
    for step in wf1.steps:
        assert step["config"]["date_str"] == "2026-04-23"


@pytest.mark.asyncio
async def test_bulk_set_date_rejects_invalid_format(auth_client: AsyncClient):
    """日期格式非法 → 422"""
    for bad in ["2026/04/23", "26-4-23", "abc", "", None]:
        resp = await auth_client.put("/api/workflows/bulk-set-date", json={"date_str": bad})
        assert resp.status_code in (400, 422), f"{bad} 应被拒绝"


@pytest.mark.asyncio
async def test_bulk_set_date_requires_auth(client_no_auth: AsyncClient):
    """未登录 → 401"""
    resp = await client_no_auth.put("/api/workflows/bulk-set-date", json={"date_str": "2026-04-23"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bulk_set_date_empty_workflows(auth_client: AsyncClient, db_session):
    """无工作流 → updated_count=0，success=True"""
    await db_session.execute("DELETE FROM workflows")
    await db_session.commit()
    resp = await auth_client.put("/api/workflows/bulk-set-date", json={"date_str": "2026-04-23"})
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 0
```

注：如项目没有现成的 `auth_client`/`db_session` fixture，先照抄 `backend/tests/conftest.py`（若存在）的形式；若缺失，写最小版 conftest（另起一个简单 pytest 兼容），但这类基础设施通常已存在，先尝试跑通。

- [ ] **Step 2.2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_workflows_bulk_set_date.py -v
```

Expected: FAIL（404 Not Found 或 URL 未注册）。

- [ ] **Step 2.3: 在后端新增端点**

编辑 `backend/api/workflows.py`，在 `@router.post("/batch-run/")`（~line 714）之前插入：

```python
import re as _re_date

class BulkSetDateRequest(BaseModel):
    date_str: str


@router.put("/bulk-set-date")
async def bulk_set_date(
    payload: BulkSetDateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """批量同步所有工作流的数据日期 (Workflow.date_str + steps[].config.date_str)"""
    date_str = (payload.date_str or "").strip()
    if not _re_date.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=422, detail="date_str 必须为 YYYY-MM-DD 格式")

    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    updated = 0

    for wf in workflows:
        changed = False
        if wf.date_str != date_str:
            wf.date_str = date_str
            changed = True

        steps = wf.steps or []
        new_steps = []
        steps_changed = False
        for s in steps:
            if isinstance(s, dict):
                s_copy = copy.deepcopy(s)
                cfg = s_copy.get("config") or {}
                if cfg.get("date_str") != date_str:
                    cfg["date_str"] = date_str
                    s_copy["config"] = cfg
                    steps_changed = True
                new_steps.append(s_copy)
            else:
                new_steps.append(s)
        if steps_changed:
            wf.steps = new_steps
            changed = True

        if changed:
            updated += 1

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[bulk-set-date] commit 失败: {e}")
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

    return {"success": True, "updated_count": updated}
```

注：顶部已 `import copy` 和 `import re`（第 10-11 行），这里别名 `_re_date` 避免与其他 re 使用混淆。若项目已有 `re` 引用，直接 `re.match` 即可，去掉 `_re_date` 别名。

- [ ] **Step 2.4: 运行测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_workflows_bulk_set_date.py -v
```

Expected: 4 用例全 PASS。

若 `auth_client` fixture 不存在导致 collection error：先用 `curl` 手工验证端点可用（已构建重启后）：

```bash
curl -X PUT http://localhost:8000/api/workflows/bulk-set-date \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"date_str":"2026-04-23"}'
```

Expected: `{"success": true, "updated_count": N}`。然后把 fixture 问题记为 TODO，后续补。

- [ ] **Step 2.5: 提交**

```bash
cd /Users/xiayanji/qbox/aistock && \
git add backend/api/workflows.py backend/tests/test_workflows_bulk_set_date.py && \
git commit -m "$(cat <<'EOF'
feat(api): 新增 PUT /workflows/bulk-set-date 批量同步日期

用于快捷批量上传功能：一次性把所有工作流的 Workflow.date_str
和 steps[].config.date_str 改为指定日期。
EOF
)"
```

---

## Task 3: 前端 - QuickUploadDialog 组件骨架

**Files:**
- Create: `frontend/src/components/QuickUploadDialog.vue`

- [ ] **Step 3.1: 创建组件骨架（空实现，不可用）**

```vue
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="快捷批量上传"
    width="70%"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-steps :active="currentStep" finish-status="success" simple style="margin-bottom: 20px">
      <el-step title="选择文件" />
      <el-step title="预览" />
      <el-step title="上传" />
      <el-step title="完成" />
    </el-steps>

    <!-- Step 1: 选文件 -->
    <div v-if="currentStep === 0">
      <el-form label-width="100px">
        <el-form-item label="数据日期">
          <el-date-picker v-model="dateStr" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="选择目录">
          <input ref="dirInput" type="file" webkitdirectory multiple @change="onFilesPicked" style="display:none" />
          <input ref="fileInput" type="file" multiple accept=".xlsx,.xls" @change="onFilesPicked" style="display:none" />
          <el-button @click="$refs.dirInput.click()">选择整个目录</el-button>
          <el-button @click="$refs.fileInput.click()">选择多个文件</el-button>
          <span style="margin-left: 12px" v-if="acceptedFiles.length">
            已选 {{ acceptedFiles.length }} 个 Excel 文件（过滤掉 {{ skippedCount }} 个非 Excel）
          </span>
        </el-form-item>
      </el-form>
    </div>

    <!-- Step 2: 预览 -->
    <div v-if="currentStep === 1">
      <div v-if="previewLoading">加载已有文件列表…</div>
      <div v-else>
        <el-alert
          :title="`识别 ${resolvedRows.length} 个 / 未识别 ${unresolvedRows.length} 个 / 将覆盖 ${overwriteCount} 个同名文件`"
          type="info" :closable="false" style="margin-bottom: 12px"
        />
        <el-collapse v-model="openedGroups">
          <el-collapse-item v-for="g in groups" :key="g.key" :name="g.key" :title="`${g.title}（${g.rows.length} 个文件）`">
            <el-table :data="g.rows" size="small">
              <el-table-column prop="filename" label="文件" />
              <el-table-column prop="target_dir" label="目标目录" />
              <el-table-column label="状态">
                <template #default="{ row }">
                  <el-tag v-if="row.will_overwrite" type="danger" size="small">⚠️ 将覆盖</el-tag>
                  <el-tag v-else type="success" size="small">新增</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="g.existingFiles?.length" style="margin-top: 8px; color: #909399; font-size: 12px">
              目录已有文件：{{ g.existingFiles.map(f => f.filename).join('、') }}
            </div>
          </el-collapse-item>
        </el-collapse>
        <el-divider v-if="unresolvedRows.length" />
        <div v-if="unresolvedRows.length">
          <el-alert title="以下文件未识别任何规则，将被跳过" type="warning" :closable="false" />
          <el-table :data="unresolvedRows" size="small" style="margin-top: 8px">
            <el-table-column prop="filename" label="文件" />
            <el-table-column prop="reason" label="原因" />
          </el-table>
        </div>
      </div>
    </div>

    <!-- Step 3: 上传 -->
    <div v-if="currentStep === 2">
      <el-progress :percentage="uploadPercent" :status="uploadStatus" />
      <p style="margin-top: 8px">
        成功 {{ uploadSuccess }} / 失败 {{ uploadFailed }} / 总共 {{ resolvedRows.length }}
      </p>
      <el-table v-if="failedUploads.length" :data="failedUploads" size="small">
        <el-table-column prop="filename" label="文件" />
        <el-table-column prop="error" label="错误" />
      </el-table>
    </div>

    <!-- Step 4: 完成 -->
    <div v-if="currentStep === 3">
      <el-result icon="success" title="上传完成" sub-title="即将打开批量执行对话框" />
    </div>

    <template #footer>
      <el-button v-if="currentStep > 0 && currentStep < 2" @click="currentStep--">上一步</el-button>
      <el-button v-if="currentStep === 0" type="primary" :disabled="!canGoPreview" @click="goPreview">下一步</el-button>
      <el-button v-if="currentStep === 1" type="primary" :disabled="!resolvedRows.length" @click="startUpload">确认上传</el-button>
      <el-button v-if="currentStep === 2 && failedUploads.length" @click="retryFailed">重试失败项</el-button>
      <el-button v-if="currentStep === 2 && !uploading" type="primary" @click="finishAndTriggerRun">完成并执行</el-button>
      <el-button @click="handleClose">取消</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { resolveTarget, isAcceptableFile } from '@/utils/quickUploadRules'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'finish'])

const currentStep = ref(0)
const dateStr = ref(new Date().toISOString().slice(0, 10))
const acceptedFiles = ref([])
const skippedCount = ref(0)
const parsedRows = ref([])
const existingFilesMap = ref({})
const previewLoading = ref(false)
const openedGroups = ref([])
const uploading = ref(false)
const uploadSuccess = ref(0)
const uploadFailed = ref(0)
const failedUploads = ref([])

const resolvedRows = computed(() => parsedRows.value.filter(r => r.status === 'resolved'))
const unresolvedRows = computed(() => parsedRows.value.filter(r => r.status === 'unresolved'))

const groups = computed(() => {
  const map = {}
  for (const r of resolvedRows.value) {
    const key = r.target_dir
    if (!map[key]) {
      map[key] = {
        key,
        title: `${r.workflow_type}${r.sub_dir ? ' / ' + r.sub_dir : ''} → ${r.target_dir}`,
        rows: [],
        existingFiles: existingFilesMap.value[key] || [],
      }
    }
    map[key].rows.push({
      ...r,
      will_overwrite: (existingFilesMap.value[key] || []).some(f => f.filename === r.filename),
    })
  }
  return Object.values(map)
})

const overwriteCount = computed(() =>
  groups.value.reduce((sum, g) => sum + g.rows.filter(r => r.will_overwrite).length, 0)
)

const canGoPreview = computed(() => acceptedFiles.value.length > 0 && dateStr.value)

const uploadPercent = computed(() => {
  if (!resolvedRows.value.length) return 0
  return Math.round(((uploadSuccess.value + uploadFailed.value) / resolvedRows.value.length) * 100)
})

const uploadStatus = computed(() => {
  if (uploadFailed.value > 0) return 'exception'
  if (uploadSuccess.value === resolvedRows.value.length) return 'success'
  return undefined
})

function onFilesPicked(e) {
  const all = Array.from(e.target.files || [])
  const accepted = all.filter(f => isAcceptableFile(f.name))
  acceptedFiles.value = accepted
  skippedCount.value = all.length - accepted.length
}

async function goPreview() {
  parsedRows.value = acceptedFiles.value.map(f => ({
    ...resolveTarget(f.name, dateStr.value),
    _file: f,
  }))
  previewLoading.value = true
  await loadExistingFiles()
  previewLoading.value = false
  openedGroups.value = groups.value.map(g => g.key)
  currentStep.value = 1
}

async function loadExistingFiles() {
  const dedup = {}
  for (const r of resolvedRows.value) {
    const key = `${r.workflow_type}|${r.step_type}|${dateStr.value}`
    if (!dedup[key]) {
      dedup[key] = { workflow_type: r.workflow_type, step_type: r.step_type, target_dir: r.target_dir }
    }
  }
  const map = {}
  for (const { workflow_type, step_type, target_dir } of Object.values(dedup)) {
    try {
      const resp = await api.get('/workflows/step-files/', {
        params: { step_type, workflow_type, date_str: dateStr.value }
      })
      map[target_dir] = resp?.files || []
    } catch (e) {
      console.warn('获取已有文件失败', target_dir, e)
      map[target_dir] = []
    }
  }
  existingFilesMap.value = map
}

async function startUpload(rowsToUpload = null) {
  const rows = rowsToUpload || resolvedRows.value
  currentStep.value = 2
  uploading.value = true
  uploadSuccess.value = rowsToUpload ? uploadSuccess.value : 0
  uploadFailed.value = rowsToUpload ? uploadFailed.value - rows.length : 0
  failedUploads.value = rowsToUpload ? failedUploads.value.filter(f => !rows.some(r => r.filename === f.filename)) : []

  const concurrency = 4
  const queue = [...rows]
  const workers = Array.from({ length: concurrency }, () => (async () => {
    while (queue.length) {
      const row = queue.shift()
      if (!row) break
      try {
        const fd = new FormData()
        fd.append('file', row._file)
        fd.append('workflow_id', '0')
        fd.append('step_index', '0')
        fd.append('step_type', row.step_type)
        fd.append('workflow_type', row.workflow_type)
        fd.append('date_str', dateStr.value)
        const resp = await api.post('/workflows/upload-step-file/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        if (resp?.success) {
          uploadSuccess.value++
        } else {
          uploadFailed.value++
          failedUploads.value.push({ filename: row.filename, error: resp?.message || '未知错误', _row: row })
        }
      } catch (err) {
        uploadFailed.value++
        failedUploads.value.push({ filename: row.filename, error: err.message || String(err), _row: row })
      }
    }
  })())
  await Promise.all(workers)
  uploading.value = false
}

async function retryFailed() {
  const rows = failedUploads.value.map(f => f._row)
  await startUpload(rows)
}

async function finishAndTriggerRun() {
  try {
    await api.put('/workflows/bulk-set-date', { date_str: dateStr.value })
    ElMessage.success(`已将所有工作流日期改为 ${dateStr.value}`)
  } catch (e) {
    ElMessage.warning('批量同步日期失败，请手动调整：' + (e.message || e))
  }
  currentStep.value = 3
  emit('finish', dateStr.value)
  setTimeout(() => emit('update:modelValue', false), 600)
}

function handleClose() {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (v) => {
  if (v) {
    currentStep.value = 0
    dateStr.value = new Date().toISOString().slice(0, 10)
    acceptedFiles.value = []
    skippedCount.value = 0
    parsedRows.value = []
    existingFilesMap.value = {}
    uploadSuccess.value = 0
    uploadFailed.value = 0
    failedUploads.value = []
  }
})
</script>
```

- [ ] **Step 3.2: 提交骨架**

```bash
cd /Users/xiayanji/qbox/aistock && \
git add frontend/src/components/QuickUploadDialog.vue && \
git commit -m "feat(quick-upload): QuickUploadDialog 组件（多步向导）"
```

---

## Task 4: 前端 - Workflows.vue 接入

**Files:**
- Modify: `frontend/src/views/Workflows.vue`

- [ ] **Step 4.1: 在模板顶部按钮栏加入口**

找到 `<el-button type="warning" @click="handleBatchRun"`（line 8 附近），在该行之前加一个按钮：

```html
<el-button type="primary" @click="openQuickUpload" style="margin-right: 8px">快捷批量上传</el-button>
```

- [ ] **Step 4.2: 引入组件并在模板底部挂载**

在 `<script setup>` 区域（约 line 2000+）顶部 `import` 区追加：

```js
import QuickUploadDialog from '@/components/QuickUploadDialog.vue'
```

在脚本里新增状态和方法（放在 `handleBatchRun` 之前）：

```js
const quickUploadVisible = ref(false)

const openQuickUpload = () => {
  quickUploadVisible.value = true
}

const onQuickUploadFinish = async (dateStr) => {
  // 1. 重新拉取工作流列表（日期已批量同步）
  await loadWorkflows()
  // 2. 预勾选所有可执行工作流（排除聚合类和导出类）
  selectedWorkflows.value = workflows.value.filter(w => {
    const agg = w.workflow_type === '条件交集' ||
                w.workflow_type === '百日新高总趋势' ||
                w.workflow_type === '导出20日均线趋势'
    return !agg
  })
  // 3. 触发现有批量执行确认对话框
  await handleBatchRun()
}
```

模板底部（在其他对话框附近，如 `</el-dialog>` 尾部或 `</template>` 前）加挂载点：

```html
<QuickUploadDialog v-model="quickUploadVisible" @finish="onQuickUploadFinish" />
```

注：
- `loadWorkflows` 是现有加载方法名；若实际名称不同（可能是 `fetchWorkflows` 或 `getWorkflows`），在文件中搜一下 `api.get('/workflows/')` 或 `workflows.value =` 所在函数，用该名。
- `selectedWorkflows.value` 是 ref；若实际是 `const { selectedWorkflows } = ...` 形式需按项目写法调整。
- `handleBatchRun` 已含 `ElMessageBox.confirm` 确认框，不需额外弹窗。

- [ ] **Step 4.3: 构建前端并手工验证**

```bash
cd /Users/xiayanji/qbox/aistock && ./deploy.sh build && ./deploy.sh restart
```

浏览器打开 http://localhost:7654 → 登录 → 工作流页面：
- [ ] 顶部看到"快捷批量上传"按钮
- [ ] 点击弹出对话框
- [ ] 关闭对话框无报错

- [ ] **Step 4.4: 提交**

```bash
cd /Users/xiayanji/qbox/aistock && \
git add frontend/src/views/Workflows.vue && \
git commit -m "feat(quick-upload): 在工作流页面接入 QuickUploadDialog 入口"
```

---

## Task 5: 手工端到端测试

**Files:** 无需改动，仅测试。

- [ ] **Step 5.1: 准备测试目录**

```bash
mkdir -p /tmp/quick-upload-test && cd /tmp/quick-upload-test
# 从生产目录拷贝几个示例文件（改名以覆盖各前缀）
cp /Users/xiayanji/qbox/aistock/data/excel/2026-04-22/*.xlsx ./ 2>/dev/null || true
ls -la
# 手工准备覆盖以下前缀/关键字的文件（可以直接复制现有 .xlsx 重命名）：
#   1并购重组0423.xlsx
#   2股权转让0423.xlsx
#   5质押中大盘0423.xlsx
#   8涨幅排名0423.xlsx
#   百日新高0423.xlsx
#   国央企0423.xlsx
#   一级板块0423.xlsx
#   20日均线0423.xlsx
#   readme.txt   （应被过滤）
#   abc.xlsx     （应进未识别区）
```

- [ ] **Step 5.2: 执行 e2e 流程并验证**

浏览器操作：
- [ ] 点击"快捷批量上传" → 对话框弹出
- [ ] 日期选 2026-04-23，点"选择整个目录"选 /tmp/quick-upload-test
- [ ] 显示"已选 8 个 Excel 文件（过滤掉 1 个非 Excel）"（readme.txt 被过滤）
- [ ] 点"下一步" → 预览页显示：
  - 识别 8 个 / 未识别 1 个（abc.xlsx）
  - 分组显示：并购重组、股权转让、质押、涨幅排名、各子目录
- [ ] 点"确认上传" → 上传进度条走到 100%，成功 8 失败 0
- [ ] 点"完成并执行" → toast "已将所有工作流日期改为 2026-04-23"
- [ ] 对话框关闭，自动弹出批量执行确认框（`ElMessageBox.confirm` "确定并行执行 N 个工作流?"）
- [ ] 确认执行后，批量执行抽屉打开并轮询状态

验证文件落盘：
```bash
ls /Users/xiayanji/qbox/aistock/data/excel/2026-04-23/       # 应有 1并购重组0423.xlsx
ls /Users/xiayanji/qbox/aistock/data/excel/股权转让/2026-04-23/
ls /Users/xiayanji/qbox/aistock/data/excel/质押/2026-04-23/
ls /Users/xiayanji/qbox/aistock/data/excel/涨幅排名/2026-04-23/
ls /Users/xiayanji/qbox/aistock/data/excel/2026-04-23/百日新高/
ls /Users/xiayanji/qbox/aistock/data/excel/2026-04-23/国企/
ls /Users/xiayanji/qbox/aistock/data/excel/2026-04-23/一级板块/
ls /Users/xiayanji/qbox/aistock/data/excel/2026-04-23/20日均线/
```

验证 DB：
```bash
docker exec -it $(docker ps --filter name=mysql -q) mysql -uroot -p$(grep MYSQL_ROOT_PASSWORD /Users/xiayanji/qbox/aistock/.env | cut -d= -f2) -e \
  "SELECT id, name, workflow_type, date_str FROM aistock.workflows LIMIT 30"
# 所有行的 date_str 都应为 2026-04-23
```

- [ ] **Step 5.3: 覆盖场景测试**

- [ ] 重新上传一次相同文件 → 预览里所有行显示"⚠️ 将覆盖"；确认后直接覆盖成功。
- [ ] 选个含未知文件的目录 → 识别成功区 + 未识别区都有展示。
- [ ] 选空目录 → "已选 0 个"，"下一步"按钮禁用。
- [ ] 上传中断网（关后端 `./deploy.sh stop`）→ 失败项列在失败区，"重试失败项"可重试。

---

## Task 6: 更新 CLAUDE.md 经验教训

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 6.1: 追加经验教训**

在 `## 经验教训` 列表末尾（当前最高是 9）追加：

```markdown
10. 快捷批量上传（前端）：`resolveTarget(filename)` 匹配优先级为"子目录关键字 > 数字前缀"。含"百日新高/20日均线/国央企/板块"的文件都归并购重组的子目录（即 `data/excel/{date}/百日新高/` 等），不管数字前缀。未识别文件软校验跳过，不阻断。`POST /workflows/upload-step-file/` 的 `workflow_id` 允许传 `0`，仅按 `workflow_type + date_str` 落盘。
11. 批量同步日期接口 `PUT /workflows/bulk-set-date`：同时更新 `Workflow.date_str` 和每个 step 的 `config.date_str`（后者通过 `copy.deepcopy` 避免 SQLAlchemy JSON in-place 修改失效）。
```

- [ ] **Step 6.2: 提交**

```bash
cd /Users/xiayanji/qbox/aistock && \
git add CLAUDE.md && \
git commit -m "docs: 快捷批量上传经验教训"
```

---

## 自审结果

1. **Spec 覆盖**：每个 Spec 小节都有 task 对应。
   - 文件名规则 → Task 1
   - 后端 bulk-set-date → Task 2
   - QuickUploadDialog → Task 3
   - Workflows.vue 接入 → Task 4
   - e2e 验证 → Task 5
   - 文档 → Task 6
2. **无占位符**：所有代码块完整，无 TODO/TBD。
3. **类型一致**：
   - `resolveTarget` 返回 `{filename, workflow_type, step_type, sub_dir, target_dir, status, reason}` 在 Task 1 定义并在 Task 3 使用一致。
   - `bulk-set-date` 返回 `{success, updated_count}` 在 Task 2 定义并在 Task 3 `finishAndTriggerRun` 消费。
   - `handleBatchRun` 名称与 Workflows.vue:2419 一致。
