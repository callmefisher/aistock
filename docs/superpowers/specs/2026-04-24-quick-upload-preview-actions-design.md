# 快捷批量上传 · 预览页增强设计

**日期**：2026-04-24
**状态**：设计已确认，待用户 review

## 背景

当前 QuickUploadDialog 第 2 步预览页缺 3 个能力：

1. **无法移除单个待上传文件** — 选错后只能回第 1 步重选目录
2. **无法删除目标目录下的已有文件** — 有冲突时必须离开 Dialog 去别处删
3. **无法刷新目录** — 第 2 步期间外部改动（新增/删除/改内容）需退回第 1 步重选

导致：日常操作需要频繁"前进后退"或跳出 Dialog，摩擦大。

## 目标

在预览页新增 4 个操作，维持"一步可到"的流畅体验：

1. 移除单个待上传文件（纯前端）
2. 删除服务器上单个已有文件（`el-popconfirm` 轻量确认）
3. 清空某分组对应目录（`ElMessageBox` 正式确认 + 循环单删）
4. 重新读取目录（复用第 1 步目录选择器，用户再点一次同目录即可）

## 非目标

- 不做"跨目录整批清空"（只按预览页分组，各清各的）
- 不做"撤销删除/回收站"
- 不动后端：复用已有 `DELETE /workflows/step-files/` 和 `DELETE /workflows/public-files/`
- 不做后端路径白名单加固（本次零侵入，若需安全加固另开 spec）

## 架构决策

**方案**：全前端实现，循环调用现有单文件删除 API（方案 ①）。

**理由**：
- 10 文件规模的分组 0.3-0.5s 内完成，无需批量端点
- 零后端改动，符合项目"独立实现不侵入"方针
- 与现有单文件删行为一致，无新路径
- 删失败不回滚（文件删除天然不可逆），失败部分明确提示即可

## 交互设计

### 整体布局

```
┌──────────────────────────────────────────────────────────────┐
│ 第 2 步：预览与确认                        [🔄 重新读取目录]  │
├──────────────────────────────────────────────────────────────┤
│ ⚠ 工作流缺失检查：...（保持原逻辑）                          │
├──────────────────────────────────────────────────────────────┤
│ ▼ data/excel/2026-04-24/       8 个待上传 [🗑 清空本目录(3)]  │
│   待上传：                                                    │
│     1并购重组.xlsx     [将覆盖]        [✖ 移除]              │
│     5历史公告.xlsx     [新增]          [✖ 移除]              │
│   目录已有（3 个）：                                           │
│     1并购重组.xlsx     2026-04-23 10:12:30  [🗑 删除]         │
│     3国企名单.xlsx     2026-04-23 10:14:02  [🗑 删除]         │
│     ...                                                      │
│ ▶ data/excel/2026-04-24/百日新高/  2 个待上传 [🗑 清空本目录(1)]│
├──────────────────────────────────────────────────────────────┤
│                    [上一步]  [开始上传]                       │
└──────────────────────────────────────────────────────────────┘
```

### 4 个操作的 UX 细节

| 操作 | 位置 | 确认方式 | 成功反馈 |
|---|---|---|---|
| **移除单个待上传** | 待上传表格每行右侧 | 无（纯前端） | 行消失 |
| **删除单个已有** | 已有文件表格每行右侧 | `el-popconfirm` 就地小气泡 | 行消失 + `ElMessage.success` + 自动重扫目录 |
| **清空本目录** | 分组头部右侧 | `ElMessageBox.confirm` 正式确认，标题"确认清空"，内容"将删除目录 XXX 下的 N 个文件" | 列表空 + `ElMessage.success("已清空 N 个文件")` + 自动重扫 |
| **重新读取目录** | 第 2 步页面头部右上 | 无（直接弹系统目录选择器） | 选完同目录 → 自动重新生成 parsedRows / existingFilesMap |

### 覆盖状态联动

**重要**：删除/清空服务器已有文件 → 对应待上传文件标签从"将覆盖"自动变回"新增"。

- 实现：`refreshDirectoryListing(target_dir)` 的末尾调用 `recomputeOverwriteStatus(target_dir)`
- 范围：只重算当前 target_dir 对应的 parsedRows，不影响其它分组

### 禁用状态

上传进行中（第 3 步）时，所有新按钮置灰：

```js
const isUploading = computed(() => currentStep.value === 2)  // 对应"正在上传"步骤
```

并发保护：
- `deletingFiles: Set<path>` / `clearingDirs: Set<target_dir>` 标记进行中
- 按钮 `:loading` 绑定 `set.has(key)`
- 防重复点 + 防同目录并发清空

## 数据流

### 组件状态（新增）

```js
const dirInputRef = ref(null)          // 隐藏 input[webkitdirectory] 的 ref
const deletingFiles = ref(new Set())   // 正在删除的 file_path 集合
const clearingDirs = ref(new Set())    // 正在清空的 target_dir 集合
```

### 关键 methods

```js
// 1. 移除单个待上传（纯前端）
function removeParsedRow(row) {
  parsedRows.value = parsedRows.value.filter(r => r !== row)
  acceptedFiles.value = acceptedFiles.value.filter(f => f !== row._file)
}

// 2. 判定 public vs step 端点
function isPublicTarget(targetDir) {
  return targetDir.includes('/public/')
      || targetDir.endsWith('/public')
      || targetDir.includes('/2025public/')
      || targetDir.endsWith('/2025public')
}

// 3. 删除服务器单文件
async function deleteExistingFile(targetDir, filePath) {
  deletingFiles.value.add(filePath)
  try {
    const endpoint = isPublicTarget(targetDir) ? '/workflows/public-files/' : '/workflows/step-files/'
    const res = await api.delete(endpoint, { params: { file_path: filePath } })
    // 后端统一返 200 + {success, message}
    if (res?.success) {
      ElMessage.success('已删除')
    } else if (res?.message?.includes('不存在')) {
      ElMessage.info('文件已被删除')
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
    await refreshDirectoryListing(targetDir)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '网络异常')
  } finally {
    deletingFiles.value.delete(filePath)
  }
}

// 4. 清空分组目录（循环单删）
async function clearDirectory(targetDir) {
  const files = existingFilesMap.value[targetDir] || []
  if (files.length === 0) return
  await ElMessageBox.confirm(
    `将删除目录 ${targetDir} 下的 ${files.length} 个文件，是否继续？`,
    '确认清空',
    { confirmButtonText: '确认清空', cancelButtonText: '取消', type: 'warning' }
  )
  clearingDirs.value.add(targetDir)
  const endpoint = isPublicTarget(targetDir) ? '/workflows/public-files/' : '/workflows/step-files/'
  const failed = []
  try {
    for (const f of files) {
      try {
        const res = await api.delete(endpoint, { params: { file_path: f.path } })
        // 后端即便文件不存在也返 200 + success:false，不抛异常
        if (!res?.success && !res?.message?.includes('不存在')) {
          failed.push(f.filename)
        }
      } catch (e) {
        // 真网络异常才算失败
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
    clearingDirs.value.delete(targetDir)
  }
}

// 5. 重新读取目录（触发原生目录选择器）
function refreshFromDirectoryPicker() {
  if (!dirInputRef.value) return
  dirInputRef.value.value = ''   // 清空以确保同目录选择也触发 change
  dirInputRef.value.click()
}

function onDirectoryReselected(e) {
  const files = Array.from(e.target.files || []).filter(f =>
    f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
  )
  if (files.length === 0) {
    ElMessage.warning('未找到 Excel 文件')
    return
  }
  onFilesAccepted(files)   // 复用第 1 步现有处理函数
}

// 6. 重扫单目录已有文件
async function refreshDirectoryListing(targetDir) {
  const sample = parsedRows.value.find(r => r.target_dir === targetDir)
  if (!sample) return
  const endpoint = isPublicTarget(targetDir) ? '/workflows/public-files/' : '/workflows/step-files/'
  const params = {
    step_type: sample.step_type,
    date_str: sample.date_str,
    workflow_type: sample.workflow_type,
  }
  const res = await api.get(endpoint, { params })
  existingFilesMap.value = {
    ...existingFilesMap.value,
    [targetDir]: res.files || [],
  }
  recomputeOverwriteStatus(targetDir)
}

// 7. 重算覆盖状态（单目录范围）
function recomputeOverwriteStatus(targetDir) {
  const existingFilenames = new Set(
    (existingFilesMap.value[targetDir] || []).map(f => f.filename)
  )
  parsedRows.value = parsedRows.value.map(r => {
    if (r.target_dir !== targetDir) return r
    return { ...r, willOverwrite: existingFilenames.has(r.filename) }
  })
}
```

### 错误处理矩阵

**后端重要前提**：`DELETE /workflows/step-files/` 和 `DELETE /workflows/public-files/` 现有实现统一返 **HTTP 200 + `{success: bool, message: str}`**，不抛 4xx/5xx。判断删除成功看 `response.success`，不看 status code。

| 场景 | 后端返回 | 前端处理 |
|---|---|---|
| 删除成功 | `200 {success: true}` | `ElMessage.success` + 重扫 |
| 文件已被他人删 | `200 {success: false, message: "文件不存在"}` | `ElMessage.info('文件已被删除')` + 重扫 |
| 其它业务错误（权限/IO） | `200 {success: false, message: "删除失败: ..."}` | `ElMessage.error(message)` + 重扫 |
| 网络异常（axios 抛） | — | `ElMessage.error('网络异常')` + 不重扫 |
| 清空部分失败 | — | `ElMessage.warning` 统计 + 展示前 3 名（"文件不存在"不计入失败） |
| 用户取消目录选择 | — | 静默无反应 |

## 模板变更

集中在 `frontend/src/components/QuickUploadDialog.vue` 一个文件。

### 变更点

1. **头部加刷新按钮**（第 2 步顶部）：
```html
<div class="preview-header">
  <span class="step-title">第 2 步：预览与确认</span>
  <el-button size="small" :icon="RefreshRight" @click="refreshFromDirectoryPicker">
    重新读取目录
  </el-button>
</div>
```

2. **持久隐藏 input**（组件末尾）：
```html
<input ref="dirInputRef" type="file" webkitdirectory directory multiple
       style="display:none" @change="onDirectoryReselected" />
```

3. **分组头加"清空本目录"按钮**（`el-collapse-item` 的 `#title` 插槽）：
```html
<el-button size="small" type="danger" plain :icon="Delete"
  :loading="clearingDirs.has(group.target_dir)"
  :disabled="(existingFilesMap[group.target_dir] || []).length === 0 || isUploading"
  @click.stop="clearDirectory(group.target_dir)">
  清空本目录（{{ (existingFilesMap[group.target_dir] || []).length }}）
</el-button>
```

4. **待上传行加"移除"按钮**（待上传 `el-table` 末列）：
```html
<el-table-column label="操作" width="80" align="center">
  <template #default="{ row }">
    <el-button size="small" type="danger" link :disabled="isUploading"
      @click="removeParsedRow(row)">移除</el-button>
  </template>
</el-table-column>
```

5. **已有文件行加"删除"按钮**（已有文件 `el-table` 末列，已有列应含 `filename` / `modified_time` / `path`）：
```html
<el-table-column label="操作" width="80" align="center">
  <template #default="{ row }">
    <el-popconfirm :title="`确认删除 ${row.filename}？`"
      confirm-button-text="删除" cancel-button-text="取消"
      @confirm="deleteExistingFile(group.target_dir, row.path)">
      <template #reference>
        <el-button size="small" type="danger" link
          :loading="deletingFiles.has(row.path)"
          :disabled="isUploading">删除</el-button>
      </template>
    </el-popconfirm>
  </template>
</el-table-column>
```

## 零侵入原则

- **后端**：零修改
- **前端**：仅 `QuickUploadDialog.vue` 单文件变更
- **现有函数**（`onFilesAccepted`, `parseFiles` 等）：不动，全部复用
- **现有样式 / 布局**：不动，只新增按钮元素

## 测试策略

### 前端单测

文件：`frontend/tests/unit/QuickUploadDialog.spec.js`（如项目未启用 Vue Test Utils 则以手工 checklist 验证）

| 测试点 | 场景 |
|---|---|
| `test_remove_parsed_row` | 点"移除" → `parsedRows` / `acceptedFiles` 对应项消失，不调任何 API |
| `test_is_public_target_routing` | 纯函数：`/public/`、`/public`、`2025public/`、`股权转让/public` 都返回 true |
| `test_delete_existing_routes_step` | target_dir `data/excel/2026-04-24/` → 调 `/workflows/step-files/` |
| `test_delete_existing_routes_public` | target_dir `data/excel/股权转让/public/` → 调 `/workflows/public-files/` |
| `test_delete_success_refreshes_listing` | mock `{success: true}` → 自动调 `GET /step-files/`，`existingFilesMap` 更新 |
| `test_delete_file_not_found_shows_info_and_refreshes` | mock `{success: false, message: "文件不存在"}` → `ElMessage.info` + 自动重扫 |
| `test_delete_business_error_shows_error_and_refreshes` | mock `{success: false, message: "删除失败: Permission denied"}` → `ElMessage.error` + 重扫 |
| `test_delete_network_failure_no_refresh` | axios 抛异常 → `ElMessage.error('网络异常')` + 不重扫 |
| `test_recompute_overwrite_after_delete` | 删除原已有文件 → 对应待上传行 `willOverwrite` 从 true 变 false |
| `test_clear_dir_confirms_and_loops` | 清空按钮 → `ElMessageBox` 显示 "将删除 N 个文件" → 确认后循环 N 次 DELETE |
| `test_clear_dir_partial_failure` | 10 个文件 3 个 `{success: false}` 且 message 不含"不存在" → `ElMessage.warning`，展示前 3 名 |
| `test_clear_dir_all_not_found_succeeds` | 10 个全 `{success: false, message: "文件不存在"}` → 视为成功，`ElMessage.success` |
| `test_refresh_button_triggers_input_click` | 点刷新 → `dirInputRef.value.click()` 被调用 |
| `test_refresh_reselect_rebuilds_preview` | mock `input.change` 含新文件 → `onFilesAccepted` 被调用 → `parsedRows` / `existingFilesMap` 重建 |
| `test_uploading_disables_buttons` | `currentStep = 2` → 所有删除/移除/刷新按钮 `disabled=true` |

### 手工验收 checklist

1. 打开快捷批量上传 → 选目录 → 第 2 步预览
2. 点某行"移除" → 行消失，不弹网络请求
3. 点某已有文件"删除"气泡 → 确认 → 行消失 + 列表立即刷新
4. 点"清空本目录" → 弹正式确认框显示 "将删除 N 个文件" → 确认 → 清空 + 列表刷新 + 原"将覆盖"标签变"新增"
5. 本地文件系统改一个文件 / 加删一个 → 点"重新读取目录" → 选同目录 → 新数据呈现
6. 启动上传后所有删除/移除/刷新按钮置灰
7. 手动把某已有文件在外部删掉 → 然后点删除 → 提示"文件已被删除"且列表自动刷新

## 经验教训预期

- 若 `dirInputRef.value.value = ''` 在 Safari 下仍不触发 change，改用 `input.remove() + 重挂` 兜底
- `el-popconfirm` + `el-button :loading` 联用时，loading 状态在 popconfirm 确认前不显示（确认后才显示）是预期行为
- `existingFilesMap` 更新必须用新对象赋值 `existingFilesMap.value = {...existingFilesMap.value, [k]: v}`，直接赋 `[k]` 会失去响应性（与现有代码约定一致）
