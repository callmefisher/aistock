# 快捷批量上传 · 预览页增强 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 QuickUploadDialog 预览页新增 4 个操作（移除待上传 / 删除已有 / 清空目录 / 刷新目录），避免用户退回选择步骤或跳出 Dialog。

**Architecture:** 全前端实现，复用现有 `DELETE /workflows/step-files/` 和 `DELETE /workflows/public-files/`（统一返 `200 + {success, message}`）。改动集中在 `QuickUploadDialog.vue` 单文件；测试新增 `tests/unit/QuickUploadDialog.spec.js`。零后端改动。

**Tech Stack:** Vue 3 (script setup) + Element Plus + axios (`@/utils/api`) + Vitest + `@testing-library/vue`。

**Spec:** `docs/superpowers/specs/2026-04-24-quick-upload-preview-actions-design.md`

---

## 文件结构

**修改文件（唯一）：**
- `frontend/src/components/QuickUploadDialog.vue` — 组件本身（395 行已存在），新增 state + methods + 4 个模板块

**新增文件：**
- `frontend/tests/unit/QuickUploadDialog.spec.js` — Vitest 单测

**零后端改动；零其它前端文件改动**（含 `@/utils/api`、`quickUploadRules.js` 均不动）。

---

## 命名对齐（关键 · 以现有代码为准）

- 组件已有 `will_overwrite`（下划线）字段，**不是 camelCase**，保持
- `fileMap: Map<string, File>` 存 File 对象（名→File），**移除待上传时也要从 fileMap delete**
- `currentStep`: 0=选目录、1=预览、2=上传中、3=完成；**上传中判定用 `uploading.value` 或 `currentStep.value === 2`**
- 现有 list API 调用格式：`api.get('/workflows/step-files/', { params: { step_type, workflow_type, date_str } })` — 无 `target_dir` 参数
- 已有文件响应字段：`{ filename, path, size, modified_time }`

---

## Task 1: 新增 state + isPublicTarget 工具函数

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue` (`<script setup>` 段)

- [ ] **Step 1: 在现有 state 声明区追加 3 行 state**

找到组件 `<script setup>` 里 `const openedGroups = ref([])` 那块，在其下方追加：

```javascript
// 预览页操作：删除/清空/刷新 相关状态
const dirInputRef = ref(null)          // 隐藏 input[webkitdirectory] 的 ref
const deletingFiles = ref(new Set())   // 正在删除的 file.path 集合
const clearingDirs = ref(new Set())    // 正在清空的 target_dir 集合
```

- [ ] **Step 2: 在 methods 区（`onFilesPicked` 上方或下方空白处）添加 isPublicTarget 工具函数**

```javascript
// 判定 target_dir 是公共目录（走 public-files 端点）还是日期目录（走 step-files 端点）
// 路径含 /public/ 或以 /public 结尾，或含 /2025public/ 或以 /2025public 结尾 → public
function isPublicTarget(targetDir) {
  if (!targetDir) return false
  return targetDir.includes('/public/')
      || targetDir.endsWith('/public')
      || targetDir.includes('/2025public/')
      || targetDir.endsWith('/2025public')
}
```

- [ ] **Step 3: 在 `<script setup>` 底部（`defineExpose` 或 reset 函数附近）导出 `isPublicTarget` 供测试用**

如果组件已有 `defineExpose({...})`，在其中加 `isPublicTarget`；如果没有，新增：

```javascript
defineExpose({ isPublicTarget })
```

（若组件已有 `defineExpose`，把 `isPublicTarget` 合并进去，不要覆盖）

- [ ] **Step 4: Syntax check**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npm run build 2>&1 | tail -5
```
Expected: built successfully，无新错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue
git commit -m "feat(quick-upload): 新增 state + isPublicTarget 工具"
```

---

## Task 2: isPublicTarget 测试（纯函数单测）

**Files:**
- Create: `frontend/tests/unit/QuickUploadDialog.spec.js`

- [ ] **Step 1: 新建测试文件骨架**

```javascript
// frontend/tests/unit/QuickUploadDialog.spec.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/vue'
import { nextTick } from 'vue'

import QuickUploadDialog from '@/components/QuickUploadDialog.vue'
import api from '@/utils/api'

// Mock api: default return success; override per test
vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessageBox: {
      confirm: vi.fn().mockResolvedValue('confirm'),
    },
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  }
})

describe('QuickUploadDialog · isPublicTarget', () => {
  let instance
  beforeEach(() => {
    // 通过 ref 拿 exposed methods
    const { container } = render(QuickUploadDialog, {
      props: { modelValue: true },
    })
    // Vue Test Utils 才能拿 expose；@testing-library 没直接暴露。
    // 替代方案：直接导入函数级单测（下文）。
  })
})
```

> ⚠️ @testing-library/vue 不直接暴露组件实例，纯函数单测推荐从组件中抽出到独立文件。**改方案**：Task 1 的 `isPublicTarget` 抽出到 `frontend/src/utils/quickUploadRules.js` 的末尾，测试直接 import。继续 Step 2。

- [ ] **Step 2: （修订）把 isPublicTarget 搬到 quickUploadRules.js 便于单测**

打开 `frontend/src/utils/quickUploadRules.js`，在文件底部新增并 export：

```javascript
// 判定 target_dir 是公共目录（走 public-files 端点）还是日期目录（走 step-files 端点）
export function isPublicTarget(targetDir) {
  if (!targetDir) return false
  return targetDir.includes('/public/')
      || targetDir.endsWith('/public')
      || targetDir.includes('/2025public/')
      || targetDir.endsWith('/2025public')
}
```

再在 QuickUploadDialog.vue 的 `<script setup>` 顶部 import 区改为：

```javascript
import { resolveTarget, isPublicTarget } from '@/utils/quickUploadRules'
```

并**删除** Task 1 Step 2 里在组件内定义的那份 `isPublicTarget`（避免重复）。`defineExpose` 里的也删掉（测试通过 import 验证，不需 expose）。

- [ ] **Step 3: 写 isPublicTarget 单测**

改写 `frontend/tests/unit/QuickUploadDialog.spec.js` 开头部分为：

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen, waitFor } from '@testing-library/vue'
import { nextTick } from 'vue'

import QuickUploadDialog from '@/components/QuickUploadDialog.vue'
import { isPublicTarget } from '@/utils/quickUploadRules'
import api from '@/utils/api'
import { ElMessageBox, ElMessage } from 'element-plus'

vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  }
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('isPublicTarget', () => {
  it.each([
    ['data/excel/2025public/', true],
    ['data/excel/2025public', true],
    ['data/excel/股权转让/public/', true],
    ['data/excel/股权转让/public', true],
    ['data/excel/质押/public/', true],
    ['data/excel/涨幅排名/2026-04-23/public/', true],
    ['data/excel/2026-04-24/', false],
    ['data/excel/2026-04-24/百日新高/', false],
    ['', false],
    [null, false],
    [undefined, false],
  ])('returns %s for %s', (dir, expected) => {
    expect(isPublicTarget(dir)).toBe(expected)
  })
})
```

- [ ] **Step 4: Run the test**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -20
```
Expected: 11 tests passed (it.each 展开 11 条).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/quickUploadRules.js frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): isPublicTarget 抽离到 quickUploadRules + 单测"
```

---

## Task 3: 移除待上传文件（removeParsedRow）

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`
- Modify: `frontend/tests/unit/QuickUploadDialog.spec.js`

- [ ] **Step 1: 在 QuickUploadDialog.vue methods 区新增 removeParsedRow**

找到 `async function loadExistingFiles()` 下方空白处，插入：

```javascript
// 预览页 · 移除单个待上传文件（纯前端，不调 API）
function removeParsedRow(row) {
  parsedRows.value = parsedRows.value.filter(r => r !== row)
  acceptedFiles.value = acceptedFiles.value.filter(f => leafName(f) !== row.filename)
  fileMap.delete(row.filename)
}
```

- [ ] **Step 2: 在预览页 `el-table` 中新增"操作"列**

找到 `el-collapse-item` 里的 `<el-table :data="g.rows" size="small">`（约第 45 行），在其最后一个 `<el-table-column>` 后添加：

```html
<el-table-column label="操作" width="80" align="center">
  <template #default="{ row }">
    <el-button size="small" type="danger" link :disabled="uploading"
      @click="removeParsedRow(row)">移除</el-button>
  </template>
</el-table-column>
```

- [ ] **Step 3: 单测**

在 `QuickUploadDialog.spec.js` 的 describe 块外追加一个辅助函数 + 测试：

```javascript
// 辅助：mock 成功的 loadExistingFiles 响应
function mockListEmpty() {
  api.get.mockResolvedValue({ files: [] })
}

// 辅助：构造一个 xlsx File 对象
function makeFile(name) {
  return new File([''], name, { type: 'application/vnd.ms-excel' })
}

describe('QuickUploadDialog · removeParsedRow', () => {
  it('removes a parsed row without calling API', async () => {
    mockListEmpty()
    const wrapper = render(QuickUploadDialog, {
      props: { modelValue: true },
    })
    // 模拟选文件 → 进预览步骤需要触发 onFilesPicked + goPreview
    // 此处简化：通过 inject / 侧路径。建议在 QuickUploadDialog 上 defineExpose
    // parsedRows / removeParsedRow 便于测试。
    // （实现：Task 3 Step 4 里新增 expose）
  })
})
```

> ⚠️ 测试这个交互需要组件内部状态访问。继续 Step 4。

- [ ] **Step 4: 在组件底部 defineExpose 暴露测试接口**

找到 `<script setup>` 末尾，若无 `defineExpose` 就新增；若已有则合并：

```javascript
// 仅测试用：暴露内部状态/方法便于单测断言（非正式 API）
defineExpose({
  // state
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  // methods
  removeParsedRow,
})
```

若组件之前没用 `setup ref` 传父组件则不影响现有功能；`defineExpose` 是纯可选暴露。

- [ ] **Step 5: 改写 removeParsedRow 测试，用 ref 访问 exposed**

```javascript
import { ref, h } from 'vue'
import { mount } from '@vue/test-utils'

// ⚠️ 如果项目用 @testing-library/vue 不是 @vue/test-utils，需要先确认 package.json
// 本 plan 假设 @vue/test-utils 已装（Vitest 默认生态常见）。
// 如未装：`npm i -D @vue/test-utils` 后继续。

describe('QuickUploadDialog · removeParsedRow', () => {
  it('removes a parsed row and cleans fileMap', async () => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    const vm = wrapper.vm
    // 手工填充 parsedRows / acceptedFiles / fileMap
    const f1 = makeFile('a.xlsx')
    const f2 = makeFile('b.xlsx')
    vm.acceptedFiles.push(f1, f2)
    vm.fileMap.set('a.xlsx', f1)
    vm.fileMap.set('b.xlsx', f2)
    const row1 = { filename: 'a.xlsx', target_dir: 'data/excel/2026-04-24/', status: 'resolved' }
    const row2 = { filename: 'b.xlsx', target_dir: 'data/excel/2026-04-24/', status: 'resolved' }
    vm.parsedRows.push(row1, row2)

    vm.removeParsedRow(row1)
    await nextTick()

    expect(vm.parsedRows).toHaveLength(1)
    expect(vm.parsedRows[0]).toBe(row2)
    expect(vm.acceptedFiles).toHaveLength(1)
    expect(vm.acceptedFiles[0]).toBe(f2)
    expect(vm.fileMap.has('a.xlsx')).toBe(false)
    expect(vm.fileMap.has('b.xlsx')).toBe(true)
    expect(api.delete).not.toHaveBeenCalled()
  })
})
```

在测试文件顶部 import 追加：

```javascript
import { mount } from '@vue/test-utils'
```

先确认是否已装：

```bash
cd /Users/xiayanji/qbox/aistock/frontend && grep '"@vue/test-utils"' package.json
```

如未装：

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npm i -D @vue/test-utils
```

- [ ] **Step 6: Run**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -20
```
Expected: 12 tests passed (11 + 1)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js frontend/package.json frontend/package-lock.json
git commit -m "feat(quick-upload): 移除待上传文件按钮 + 单测"
```

---

## Task 4: refreshDirectoryListing + recomputeOverwriteStatus

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`

**说明**：现有 `groups` computed 里的 `will_overwrite` 是每次渲染自动计算的（基于 `existingFilesMap` 和 `resolvedRows`），所以**实际上不需要显式 recompute 函数**——修改 `existingFilesMap` 就会自动触发 computed 重算。这简化了实现。

但为了避免 Task 6/7 测试需要"验证 will_overwrite 更新"时的可读性，我们保留 `refreshDirectoryListing` 函数，且它完成后只需更新 `existingFilesMap.value` 即可。

- [ ] **Step 1: 新增 refreshDirectoryListing**

插到 `loadExistingFiles` 下方：

```javascript
// 重扫单个 target_dir 的已有文件（删除/清空成功后调用）
// 更新 existingFilesMap 后，groups computed 会自动重算 will_overwrite
async function refreshDirectoryListing(targetDir) {
  const sample = parsedRows.value.find(r => r.target_dir === targetDir)
  if (!sample) return
  const endpoint = isPublicTarget(targetDir)
    ? '/workflows/public-files/'
    : '/workflows/step-files/'
  try {
    const resp = await api.get(endpoint, {
      params: {
        step_type: sample.step_type,
        workflow_type: sample.workflow_type,
        date_str: dateStr.value,
      },
    })
    existingFilesMap.value = {
      ...existingFilesMap.value,
      [targetDir]: resp?.files || [],
    }
  } catch (e) {
    console.warn('refreshDirectoryListing failed', targetDir, e)
  }
}
```

- [ ] **Step 2: 把 `refreshDirectoryListing` 加到 defineExpose**

```javascript
defineExpose({
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  removeParsedRow, refreshDirectoryListing,
})
```

- [ ] **Step 3: 测试**

在 spec 追加：

```javascript
describe('QuickUploadDialog · refreshDirectoryListing', () => {
  it('calls step-files endpoint for non-public dir and updates map', async () => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'a.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
    api.get.mockResolvedValueOnce({
      files: [{ filename: 'old.xlsx', path: '/app/data/excel/2026-04-24/old.xlsx', modified_time: '2026-04-23 10:00' }],
    })

    await vm.refreshDirectoryListing('data/excel/2026-04-24/')

    expect(api.get).toHaveBeenCalledWith('/workflows/step-files/', {
      params: { step_type: 'merge_excel', workflow_type: '并购重组', date_str: expect.any(String) },
    })
    expect(vm.existingFilesMap['data/excel/2026-04-24/']).toHaveLength(1)
    expect(vm.existingFilesMap['data/excel/2026-04-24/'][0].filename).toBe('old.xlsx')
  })

  it('calls public-files endpoint for public dir', async () => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: '百日新高.xlsx',
      target_dir: 'data/excel/股权转让/public/',
      step_type: 'merge_excel',
      workflow_type: '股权转让',
      status: 'resolved',
    })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.refreshDirectoryListing('data/excel/股权转让/public/')

    expect(api.get).toHaveBeenCalledWith('/workflows/public-files/', expect.any(Object))
  })
})
```

- [ ] **Step 4: Run**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -15
```
Expected: 14 tests passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): refreshDirectoryListing 按 target_dir 重扫"
```

---

## Task 5: deleteExistingFile（单文件删 + 自动重扫）

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`

- [ ] **Step 1: 新增 deleteExistingFile**

```javascript
async function deleteExistingFile(targetDir, filePath) {
  deletingFiles.value.add(filePath)
  const endpoint = isPublicTarget(targetDir)
    ? '/workflows/public-files/'
    : '/workflows/step-files/'
  try {
    const res = await api.delete(endpoint, { params: { file_path: filePath } })
    if (res?.success) {
      ElMessage.success('已删除')
    } else if (res?.message?.includes('不存在')) {
      ElMessage.info('文件已被删除')
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
    await refreshDirectoryListing(targetDir)
  } catch (e) {
    ElMessage.error('网络异常')
  } finally {
    // 用 new Set 触发响应性（Set 的 delete 不会触发 Vue 追踪）
    const next = new Set(deletingFiles.value)
    next.delete(filePath)
    deletingFiles.value = next
  }
}
```

⚠️ 细节：`Set.delete()` 不会触发 Vue 3 的响应式更新。改为新建 Set 赋值。`add` 同理，但 Vue 3 + reactivity transforms **对 Set 的 add/delete 是能追踪的**（若 Set 在 `ref` 内）。保险起见用新建 Set。`add` 那行也改：

在 Task 1 的 state 声明保持 `ref(new Set())`。但 add/delete 时都应该：

```javascript
deletingFiles.value = new Set([...deletingFiles.value, filePath])  // add
// 或
const next = new Set(deletingFiles.value); next.delete(filePath); deletingFiles.value = next  // delete
```

**改进版**：封装为助手函数（放在 methods 区开头）：

```javascript
function addToSetRef(setRef, item) {
  setRef.value = new Set([...setRef.value, item])
}
function removeFromSetRef(setRef, item) {
  const next = new Set(setRef.value)
  next.delete(item)
  setRef.value = next
}
```

然后 deleteExistingFile 改为：

```javascript
async function deleteExistingFile(targetDir, filePath) {
  addToSetRef(deletingFiles, filePath)
  const endpoint = isPublicTarget(targetDir)
    ? '/workflows/public-files/'
    : '/workflows/step-files/'
  try {
    const res = await api.delete(endpoint, { params: { file_path: filePath } })
    if (res?.success) {
      ElMessage.success('已删除')
    } else if (res?.message?.includes('不存在')) {
      ElMessage.info('文件已被删除')
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
    await refreshDirectoryListing(targetDir)
  } catch (e) {
    ElMessage.error('网络异常')
  } finally {
    removeFromSetRef(deletingFiles, filePath)
  }
}
```

- [ ] **Step 2: 在 defineExpose 加 deleteExistingFile**

```javascript
defineExpose({
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  removeParsedRow, refreshDirectoryListing, deleteExistingFile,
})
```

- [ ] **Step 3: 测试（4 个场景）**

spec 追加：

```javascript
describe('QuickUploadDialog · deleteExistingFile', () => {
  let vm
  beforeEach(() => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'a.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
  })

  it('success: ElMessage.success + refresh', async () => {
    api.delete.mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })  // refresh response

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/app/data/excel/2026-04-24/a.xlsx')

    expect(api.delete).toHaveBeenCalledWith('/workflows/step-files/', {
      params: { file_path: '/app/data/excel/2026-04-24/a.xlsx' },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(api.get).toHaveBeenCalled()
  })

  it('file already gone: ElMessage.info + refresh', async () => {
    api.delete.mockResolvedValueOnce({ success: false, message: '文件不存在' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.info).toHaveBeenCalledWith('文件已被删除')
    expect(api.get).toHaveBeenCalled()
  })

  it('business error: ElMessage.error + refresh', async () => {
    api.delete.mockResolvedValueOnce({ success: false, message: '删除失败: Permission denied' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败: Permission denied')
    expect(api.get).toHaveBeenCalled()
  })

  it('network error: ElMessage.error + NO refresh', async () => {
    api.delete.mockRejectedValueOnce(new Error('Network down'))

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
    expect(api.get).not.toHaveBeenCalled()
  })

  it('routes public endpoint when target dir is public', async () => {
    vm.parsedRows.push({
      filename: 'b.xlsx',
      target_dir: 'data/excel/股权转让/public/',
      step_type: 'merge_excel',
      workflow_type: '股权转让',
      status: 'resolved',
    })
    api.delete.mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/股权转让/public/', '/p/b.xlsx')

    expect(api.delete).toHaveBeenCalledWith('/workflows/public-files/', expect.any(Object))
  })
})
```

- [ ] **Step 4: Run**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -15
```
Expected: 19 tests passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): deleteExistingFile + addToSetRef helper"
```

---

## Task 6: clearDirectory（循环清空 + 确认框）

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`

- [ ] **Step 1: 新增 clearDirectory**

```javascript
async function clearDirectory(targetDir) {
  const files = existingFilesMap.value[targetDir] || []
  if (files.length === 0) return
  try {
    await ElMessageBox.confirm(
      `将删除目录 ${targetDir} 下的 ${files.length} 个文件，是否继续？`,
      '确认清空',
      { confirmButtonText: '确认清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return  // 用户取消
  }
  addToSetRef(clearingDirs, targetDir)
  const endpoint = isPublicTarget(targetDir)
    ? '/workflows/public-files/'
    : '/workflows/step-files/'
  const failed = []
  try {
    for (const f of files) {
      try {
        const res = await api.delete(endpoint, { params: { file_path: f.path } })
        if (!res?.success && !res?.message?.includes('不存在')) {
          failed.push(f.filename)
        }
      } catch {
        failed.push(f.filename)
      }
    }
    if (failed.length === 0) {
      ElMessage.success(`已清空 ${files.length} 个文件`)
    } else {
      ElMessage.warning(`清空完成，${failed.length} 个失败：${failed.slice(0, 3).join(', ')}`)
    }
    await refreshDirectoryListing(targetDir)
  } finally {
    removeFromSetRef(clearingDirs, targetDir)
  }
}
```

- [ ] **Step 2: 确保 ElMessageBox 已导入**

顶部 import 检查，若无则追加：

```javascript
import { ElMessage, ElMessageBox } from 'element-plus'
```

- [ ] **Step 3: 在 defineExpose 加 clearDirectory**

```javascript
defineExpose({
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  removeParsedRow, refreshDirectoryListing, deleteExistingFile, clearDirectory,
})
```

- [ ] **Step 4: 测试（4 个场景）**

```javascript
describe('QuickUploadDialog · clearDirectory', () => {
  let vm
  beforeEach(() => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'new.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'a.xlsx', path: '/p/a.xlsx' },
      { filename: 'b.xlsx', path: '/p/b.xlsx' },
      { filename: 'c.xlsx', path: '/p/c.xlsx' },
    ]
  })

  it('confirm + all success → ElMessage.success', async () => {
    api.delete
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    const callArgs = ElMessageBox.confirm.mock.calls[0]
    expect(callArgs[0]).toContain('3 个文件')
    expect(api.delete).toHaveBeenCalledTimes(3)
    expect(ElMessage.success).toHaveBeenCalledWith('已清空 3 个文件')
  })

  it('partial failure → warning with top 3', async () => {
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'a.xlsx', path: '/p/a.xlsx' },
      { filename: 'b.xlsx', path: '/p/b.xlsx' },
      { filename: 'c.xlsx', path: '/p/c.xlsx' },
      { filename: 'd.xlsx', path: '/p/d.xlsx' },
      { filename: 'e.xlsx', path: '/p/e.xlsx' },
    ]
    api.delete
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessage.warning).toHaveBeenCalled()
    const msg = ElMessage.warning.mock.calls[0][0]
    expect(msg).toContain('4 个失败')
    expect(msg).toContain('b.xlsx')
    expect(msg).toContain('c.xlsx')
    expect(msg).toContain('d.xlsx')
    expect(msg).not.toContain('e.xlsx')  // only top 3
  })

  it('all 文件不存在 → success (counts as gone)', async () => {
    api.delete
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessage.success).toHaveBeenCalledWith('已清空 3 个文件')
  })

  it('user cancels confirm → no api call', async () => {
    ElMessageBox.confirm.mockRejectedValueOnce('cancel')

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(api.delete).not.toHaveBeenCalled()
  })

  it('empty dir → no-op', async () => {
    vm.existingFilesMap['data/excel/2026-04-24/'] = []

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(api.delete).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 5: Run**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -15
```
Expected: 24 tests passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): clearDirectory 循环清空 + 部分失败"
```

---

## Task 7: 刷新按钮（refreshFromDirectoryPicker）

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`

- [ ] **Step 1: 新增 refreshFromDirectoryPicker 和 onDirectoryReselected**

```javascript
function refreshFromDirectoryPicker() {
  if (!dirInputRef.value) return
  dirInputRef.value.value = ''
  dirInputRef.value.click()
}

function onDirectoryReselected(e) {
  // 复用第 1 步的 onFilesPicked 逻辑，然后自动进预览
  const all = Array.from(e.target.files || [])
  const visible = all.filter(f => !isSilentlyIgnored(leafName(f)))
  const accepted = visible.filter(f => isAcceptableFile(leafName(f)))
  if (accepted.length === 0) {
    ElMessage.warning('未找到 Excel 文件')
    return
  }
  acceptedFiles.value = accepted
  skippedCount.value = visible.length - accepted.length
  // 重新生成 parsedRows + existingFilesMap
  goPreview()
}
```

⚠️ `isSilentlyIgnored` 和 `isAcceptableFile` 必须是当前文件里已有的工具函数。如果它们在 `quickUploadRules.js` 或 component 内，检查 import，必要时补。

- [ ] **Step 2: 在第 2 步页面头部新增刷新按钮**

找到 `<template>` 里"第 2 步：预览"的区块（大致在 collapse 之前），加：

```html
<!-- 在第 2 步内容区域最顶部，em-form 或标题之后 -->
<div class="preview-toolbar" style="margin-bottom: 12px; display:flex; justify-content: space-between; align-items: center;">
  <span>第 2 步：预览与确认</span>
  <el-button size="small" :icon="RefreshRight" @click="refreshFromDirectoryPicker" :disabled="uploading">
    重新读取目录
  </el-button>
</div>
```

若原本在 `<el-step>` 里用了其它结构，就在预览区 div 的顶部加这个 toolbar div，不要改既有结构。

`RefreshRight` icon import 追加到顶部：

```javascript
import { RefreshRight } from '@element-plus/icons-vue'
```

若已有则跳过。

- [ ] **Step 3: 在组件模板末尾（外层 `</el-dialog>` 内）加持久隐藏 input**

```html
<input
  ref="dirInputRef"
  type="file"
  webkitdirectory
  directory
  multiple
  style="display: none"
  @change="onDirectoryReselected"
/>
```

放在 dialog 内即可，确保卸载时一起卸载。

- [ ] **Step 4: 在 defineExpose 加 refreshFromDirectoryPicker**

```javascript
defineExpose({
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  removeParsedRow, refreshDirectoryListing, deleteExistingFile, clearDirectory,
  refreshFromDirectoryPicker,
})
```

- [ ] **Step 5: 测试**

```javascript
describe('QuickUploadDialog · refreshFromDirectoryPicker', () => {
  it('clicks the hidden input', () => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    const vm = wrapper.vm
    const clickSpy = vi.fn()
    // mock the ref
    vm.dirInputRef = null  // not accessible directly; test via DOM
    // Fallback approach: find the <input type="file" webkitdirectory> in DOM
    const input = wrapper.find('input[type="file"][webkitdirectory]')
    expect(input.exists()).toBe(true)
    input.element.click = clickSpy
    vm.refreshFromDirectoryPicker()
    expect(clickSpy).toHaveBeenCalled()
  })
})
```

注意：`dirInputRef` 通过 template ref 绑定，测试里无法直接 mock ref，改测 DOM。上面用 `wrapper.find`。

- [ ] **Step 6: Run**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -15
```
Expected: 25 tests passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): 重新读取目录按钮 + 隐藏 input"
```

---

## Task 8: 模板整合 · 每分组 "清空本目录" 按钮 + 已有文件列表删除按钮

**Files:**
- Modify: `frontend/src/components/QuickUploadDialog.vue`

- [ ] **Step 1: 分组头加"清空本目录"按钮**

找到 `<el-collapse-item ...>`（第 44 行附近），把 title 改为自定义插槽：

原来：
```html
<el-collapse-item v-for="g in groups" :key="g.key" :name="g.key" :title="`${g.title}（${g.rows.length} 个文件）`">
```

改为：
```html
<el-collapse-item v-for="g in groups" :key="g.key" :name="g.key">
  <template #title>
    <div style="display:flex; justify-content:space-between; align-items:center; width:100%; padding-right:16px;">
      <span>{{ g.title }}（{{ g.rows.length }} 个待上传）</span>
      <el-button
        size="small" type="danger" plain
        :icon="Delete"
        :loading="clearingDirs.has(g.key)"
        :disabled="(existingFilesMap[g.key] || []).length === 0 || uploading"
        @click.stop="clearDirectory(g.key)"
      >
        清空本目录（{{ (existingFilesMap[g.key] || []).length }}）
      </el-button>
    </div>
  </template>
  <!-- 原有 el-table 内容保持 -->
```

记得闭合 `</el-collapse-item>`。

import `Delete` icon（顶部 import 如果没有就加）：

```javascript
import { Delete, RefreshRight } from '@element-plus/icons-vue'
```

- [ ] **Step 2: 在分组内容里显示已有文件列表 + 删除按钮**

找到 collapse-item 内 `<el-table :data="g.rows" ...>` 的后面（关闭 `</el-table>` 之后、`</el-collapse-item>` 之前），新增：

```html
<!-- 目录已有文件（可删除） -->
<div v-if="(existingFilesMap[g.key] || []).length > 0" style="margin-top:12px;">
  <div style="font-size:13px;color:#909399;margin-bottom:6px;">
    目录已有（{{ (existingFilesMap[g.key] || []).length }} 个）：
  </div>
  <el-table :data="existingFilesMap[g.key] || []" size="small">
    <el-table-column prop="filename" label="文件名" />
    <el-table-column prop="modified_time" label="修改时间" width="170" />
    <el-table-column label="操作" width="80" align="center">
      <template #default="{ row }">
        <el-popconfirm
          :title="`确认删除 ${row.filename}？`"
          confirm-button-text="删除"
          cancel-button-text="取消"
          @confirm="deleteExistingFile(g.key, row.path)"
        >
          <template #reference>
            <el-button size="small" type="danger" link
              :loading="deletingFiles.has(row.path)"
              :disabled="uploading">删除</el-button>
          </template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</div>
```

- [ ] **Step 3: Build check**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npm run build 2>&1 | tail -10
```
Expected: built successfully, no new errors referring to QuickUploadDialog.

- [ ] **Step 4: DOM 结构 smoke test**

```javascript
describe('QuickUploadDialog · template integration', () => {
  it('renders clear/delete buttons per group', async () => {
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: { stubs: { teleport: true } },
    })
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'new.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      sub_dir: null,
      status: 'resolved',
    })
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'old.xlsx', path: '/p/old.xlsx', modified_time: '2026-04-23 10:00' },
    ]
    vm.currentStep = 1  // preview step
    await nextTick()
    // 清空按钮
    expect(wrapper.text()).toContain('清空本目录')
    // 已有文件节目
    expect(wrapper.text()).toContain('old.xlsx')
    // 移除按钮
    expect(wrapper.text()).toContain('移除')
  })
})
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vitest run tests/unit/QuickUploadDialog.spec.js 2>&1 | tail -15
```
Expected: 26 tests passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/QuickUploadDialog.vue frontend/tests/unit/QuickUploadDialog.spec.js
git commit -m "feat(quick-upload): 分组清空按钮 + 已有文件删除按钮"
```

---

## Task 9: 部署 + 手工验收

**Files:** 无代码改动

- [ ] **Step 1: build + restart**

```bash
cd /Users/xiayanji/qbox/aistock && ./deploy.sh build && ./deploy.sh restart
```

- [ ] **Step 2: 手工验收 checklist**（打开 http://localhost:7654）

1. 登录 → 工作流页面 → 点「快捷批量上传」打开 Dialog
2. 第 1 步选个目录（比如 `data/excel/2026-04-24`）→ 下一步
3. 预览页确认：
   - 每个分组头部右侧有"清空本目录（N）"按钮
   - 每个待上传文件行右侧有"移除"按钮
   - 每个分组下方有"目录已有（N 个）"列表 + 每行"删除"按钮
   - 头部右上角有"重新读取目录"按钮
4. 点某"移除" → 该文件行消失，不发网络请求（F12 Network）
5. 点某已有文件"删除" → 气泡确认 → 确认 → 行消失 + 成功 Toast + 列表自动刷新
6. 点某分组"清空本目录" → 弹正式确认框"将删除 N 个文件" → 确认 → Toast 成功 N 个
7. 本地在那个目录里新增一个 xlsx → 回浏览器点"重新读取目录" → 选同目录 → 预览页多出新行
8. 点"开始上传" → 上传过程中所有删除/移除/刷新按钮置灰

- [ ] **Step 3: 若发现异常，按 CLAUDE.md 经验教训追加规则**

---

## 自审记录

**Spec 覆盖检查**（对照 `docs/superpowers/specs/2026-04-24-quick-upload-preview-actions-design.md`）：

- 4 个新操作：移除 (Task 3) / 删除单文件 (Task 5) / 清空目录 (Task 6) / 刷新 (Task 7) ✓
- `isPublicTarget` 判定：Task 1/2 ✓
- 覆盖状态联动（删除后"将覆盖"变"新增"）：依赖现有 `groups` computed 自动重算，Task 4 的 `existingFilesMap` 更新会触发，文档说明 ✓
- 禁用状态：每个按钮 `:disabled="uploading"`，Task 3/7/8 均已加 ✓
- 并发保护：`addToSetRef/removeFromSetRef` + loading 绑定 Task 5/6 ✓
- 错误处理矩阵：success/文件不存在/业务错/网络异常/部分失败/取消，Task 5/6 全覆盖 ✓
- 模板变更：头部刷新按钮 (Task 7) / 分组清空 (Task 8) / 待上传移除 (Task 3) / 已有删除 (Task 8) ✓
- 测试：11 (isPublicTarget) + 1 (remove) + 2 (refresh) + 5 (delete) + 5 (clear) + 1 (refresh button) + 1 (template) = **26 tests** ✓

**类型一致性检查**：
- `will_overwrite`（下划线）统一使用 ✓
- `target_dir`（下划线）统一 ✓
- `deletingFiles` / `clearingDirs` 都用 Set<string> ✓
- `addToSetRef` / `removeFromSetRef` Task 5 定义，Task 6 使用，同名 ✓

**Placeholder 扫描**：无 TBD/TODO，每个步骤都有完整代码。

**关键非显而易见的决策**（供实施者注意）：
- `will_overwrite` 不需要单独 recompute 函数 — 现有 `groups` computed 会自动从 `existingFilesMap` 推算（源码第 164 行）
- `addToSetRef/removeFromSetRef` 必须用新 Set 赋值（Vue 3 对 Set.add/delete 的响应式追踪不完美）
- `defineExpose` 只为测试服务，不是正式 API，production 代码不调用
- Task 2 的关键转折：`isPublicTarget` 抽到 `quickUploadRules.js`，否则无法在 @testing-library/vue 里做纯函数单测

---

## 执行方式

**Plan 完成，文件保存至 `docs/superpowers/plans/2026-04-24-quick-upload-preview-actions-plan.md`。**

两种执行方式：

1. **Subagent 驱动（推荐）** — 每任务独立 subagent + 两阶段审查
2. **内联执行** — 本会话执行 + checkpoint 批量审查

请选择。
