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
        <el-form-item label="选择文件">
          <input ref="dirInput" type="file" webkitdirectory multiple @change="onFilesPicked" style="display:none" />
          <input ref="fileInput" type="file" multiple accept=".xlsx,.xls" @change="onFilesPicked" style="display:none" />
          <el-button type="primary" @click="$refs.fileInput.click()">选择多个文件</el-button>
          <el-button @click="$refs.dirInput.click()">选择整个目录</el-button>
          <span style="margin-left: 12px" v-if="acceptedFiles.length">
            已选 {{ acceptedFiles.length }} 个 Excel 文件（过滤掉 {{ skippedCount }} 个非 Excel）
          </span>
          <div style="font-size:12px;color:#909399;margin-top:6px;">
            提示：选择整个目录时浏览器会弹"上传此目录下所有文件"的确认提示（安全机制，无法消除）；
            用"选择多个文件"（Cmd/Ctrl+A 全选）可绕过该弹窗。
          </div>
        </el-form-item>
      </el-form>
    </div>

    <!-- Step 2: 预览 -->
    <div v-if="currentStep === 1">
      <div v-if="previewLoading">加载已有文件列表…</div>
      <div v-else>
        <div class="preview-toolbar" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span>第 2 步：预览与确认</span>
          <el-button size="small" :icon="RefreshRight" @click="refreshFromDirectoryPicker" :disabled="uploading">
            重新读取目录
          </el-button>
        </div>
        <el-alert
          :title="`识别 ${resolvedRows.length} 个 / 未识别 ${unresolvedRows.length} 个 / 将覆盖 ${overwriteCount} 个同名文件${totalMissing ? ' / 缺失 ' + totalMissing + ' 类' : ''}`"
          :type="totalMissing ? 'warning' : 'info'" :closable="false" style="margin-bottom: 12px"
        />
        <el-collapse v-model="openedGroups">
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
            <el-table :data="g.rows" size="default">
              <el-table-column prop="filename" label="文件" />
              <el-table-column prop="target_dir" label="目标目录" />
              <el-table-column label="状态" width="120">
                <template #default="scope">
                  <el-tag v-if="scope?.row?.will_overwrite" type="danger">将覆盖</el-tag>
                  <el-tag v-else type="success">新增</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="scope">
                  <el-button type="danger" link :disabled="uploading"
                    @click="removeParsedRow(scope?.row)">移除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <!-- 目录已有文件（可删除） -->
            <div v-if="(existingFilesMap[g.key] || []).length > 0" style="margin-top:12px;">
              <div style="font-size:14px;color:#909399;margin-bottom:6px;">
                目录已有（{{ (existingFilesMap[g.key] || []).length }} 个）：
              </div>
              <el-table :data="existingFilesMap[g.key] || []" size="default">
                <el-table-column prop="filename" label="文件名" />
                <el-table-column prop="modified_time" label="修改时间" width="170" />
                <el-table-column label="操作" width="80" align="center">
                  <template #default="scope">
                    <el-popconfirm
                      :title="`确认删除 ${scope?.row?.filename}？`"
                      confirm-button-text="删除"
                      cancel-button-text="取消"
                      @confirm="deleteExistingFile(g.key, scope?.row?.path)"
                    >
                      <template #reference>
                        <el-button type="danger" link
                          :loading="deletingFiles.has(scope?.row?.path)"
                          :disabled="uploading">删除</el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
        <el-divider v-if="missingWorkflowTypes.length || missingPublicSubdirs.length" />
        <div v-if="missingWorkflowTypes.length || missingPublicSubdirs.length">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>缺失检查（仅警告，可继续上传）</template>
            <div style="font-size: 13px; margin-top: 6px">
              <div v-if="missingWorkflowTypes.length">
                <strong>未收到文件的工作流（{{ missingWorkflowTypes.length }} 个）：</strong>
                {{ missingWorkflowTypes.join('、') }}
              </div>
              <div v-if="missingPublicSubdirs.length" style="margin-top: 4px">
                <strong>未收到文件的公共数据（{{ missingPublicSubdirs.length }} 个）：</strong>
                {{ missingPublicSubdirs.join('、') }}
                <span style="color: #909399">（所有工作流共享，缺失时执行会自动从历史日期复制，但当日数据不是最新的）</span>
              </div>
            </div>
          </el-alert>
        </div>
        <el-divider v-if="publicSubdirsWithExisting.length" />
        <div v-if="publicSubdirsWithExisting.length">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>公共子目录已存在旧文件（仅警告，可继续上传）</template>
            <div style="font-size: 13px; margin-top: 6px">
              <div v-for="item in publicSubdirsWithExisting" :key="item.target_dir">
                <strong>{{ item.sub_dir }}</strong>
                （{{ item.count }} 个旧文件）
                <span style="color: #909399">→ {{ item.target_dir }}</span>
              </div>
              <div style="color: #909399; margin-top: 4px">
                提示：同目录下多份历史文件可能导致匹配读到错误数据，建议点上方分组内的「清空本目录」按钮清理后再上传。
              </div>
            </div>
          </el-alert>
        </div>
        <el-divider v-if="pledgeGroupIssue" />
        <div v-if="pledgeGroupIssue">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>质押目录需上传 2 个文件（中大盘 + 小盘）</template>
            <div style="font-size: 13px; margin-top: 6px">
              <div>当前待上传：<strong>{{ pledgeGroupIssue.total }}</strong> 个</div>
              <div v-if="pledgeGroupIssue.missing.length">
                缺少文件名包含：
                <strong>{{ pledgeGroupIssue.missing.join('、') }}</strong>
              </div>
              <div v-if="pledgeGroupIssue.total > 2" style="color: #909399">
                提示：超过 2 个可能夹带了历史遗留文件或重名变体，请核对。
              </div>
            </div>
          </el-alert>
        </div>
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
      <el-button v-if="currentStep === 1" type="primary" :disabled="!resolvedRows.length" @click="() => startUpload()">确认上传</el-button>
      <el-button v-if="currentStep === 2 && failedUploads.length && !uploading" @click="retryFailed">重试失败项</el-button>
      <el-button v-if="currentStep === 2 && !uploading" type="primary" @click="finishAndTriggerRun">完成并执行</el-button>
      <el-button @click="handleClose">取消</el-button>
    </template>
  </el-dialog>

  <input
    ref="dirInputRef"
    type="file"
    webkitdirectory
    directory
    multiple
    style="display: none"
    @change="onDirectoryReselected"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, RefreshRight } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { resolveTarget, isAcceptableFile, isSilentlyIgnored, isPublicTarget } from '@/utils/quickUploadRules'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'finish'])

function todayLocal() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
}

const currentStep = ref(0)
const dateStr = ref(todayLocal())
const acceptedFiles = ref([])
const skippedCount = ref(0)
const parsedRows = ref([])
const existingFilesMap = ref({})
const previewLoading = ref(false)
const openedGroups = ref([])
// 预览页操作：删除/清空/刷新 相关状态
const dirInputRef = ref(null)          // 隐藏 input[webkitdirectory] 的 ref
const deletingFiles = ref(new Set())   // 正在删除的 file.path 集合
const clearingDirs = ref(new Set())    // 正在清空的 target_dir 集合
const uploading = ref(false)
const uploadSuccess = ref(0)
const uploadFailed = ref(0)
const failedUploads = ref([])
const batchSize = ref(0)
const doneInBatch = ref(0)

// File objects kept outside reactive state (Vue shouldn't track File internals)
const fileMap = new Map()  // filename → File

const resolvedRows = computed(() => parsedRows.value.filter(r => r.status === 'resolved'))
const unresolvedRows = computed(() => parsedRows.value.filter(r => r.status === 'unresolved'))

// 预览阶段无条件触发这两个 step_type 的 /step-files/ 查询，
// 让后端 ensure_match_source_files 跑一次，从最近历史日期复制老文件到当日目录
// （国企/一级板块 auto_copy=True，用户没选这两类文件时也要复制）。
const ALWAYS_PREVIEW_STEPS = [
  { workflow_type: '并购重组', step_type: 'match_soe', sub_dir: '国企' },
  { workflow_type: '并购重组', step_type: 'match_sector', sub_dir: '一级板块' },
]
const FORCED_SUBDIR_GROUPS = ALWAYS_PREVIEW_STEPS
// groups computed 补显时用：sub_dir → 后端返回的真实 target_dir
const forcedSubdirTargetMap = ref({})

// 分组展示顺序：主工作流按数字前缀 1→9，之后是 4 个公共子目录
const GROUP_ORDER = [
  '并购重组',        // 1
  '股权转让',        // 2
  '增发实现',        // 3
  '申报并购重组',    // 4
  '质押',            // 5
  '减持叠加质押和大宗交易', // 6
  '涨幅排名',        // 8
  '招投标',          // 9
]
const SUBDIR_ORDER = ['百日新高', '20日均线', '国企', '一级板块']

function groupSortKey(g) {
  // 公共子目录：SUBDIR_ORDER 里的索引 + 偏移到主工作流之后
  if (g.sub_dir) {
    const idx = SUBDIR_ORDER.indexOf(g.sub_dir)
    return (idx === -1 ? 99 : idx) + 1000
  }
  const idx = GROUP_ORDER.indexOf(g.workflow_type)
  return idx === -1 ? 500 : idx
}

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
        workflow_type: r.workflow_type,
        sub_dir: r.sub_dir || null,
      }
    }
    map[key].rows.push({
      ...r,
      will_overwrite: (existingFilesMap.value[key] || []).some(f => f.filename === r.filename),
    })
  }
  // 强制补显：国企/一级板块即便用户没选文件，也要把"目录已有"（含历史复制）渲染成分组
  for (const { sub_dir } of FORCED_SUBDIR_GROUPS) {
    const dir = forcedSubdirTargetMap.value[sub_dir]
    if (!dir || map[dir]) continue
    if ((existingFilesMap.value[dir] || []).length === 0) continue
    map[dir] = {
      key: dir,
      title: `并购重组 / ${sub_dir} → ${dir}（仅历史复制，无新上传）`,
      rows: [],
      existingFiles: existingFilesMap.value[dir],
      workflow_type: '并购重组',
      sub_dir,
    }
  }
  return Object.values(map).sort((a, b) => groupSortKey(a) - groupSortKey(b))
})

const overwriteCount = computed(() =>
  groups.value.reduce((sum, g) => sum + g.rows.filter(r => r.will_overwrite).length, 0)
)

// 除聚合/导出类之外应该有文件上传的工作流类型（即"主流程"工作流）
const REQUIRED_WORKFLOW_TYPES = [
  '并购重组', '股权转让', '增发实现', '申报并购重组',
  '质押', '减持叠加质押和大宗交易', '涨幅排名', '招投标'
]
// 公共匹配源（并购重组子目录，所有工作流执行时都会读）
const REQUIRED_PUBLIC_SUBDIRS = ['百日新高', '20日均线', '国企', '一级板块']

const missingWorkflowTypes = computed(() => {
  // 只统计非子目录文件对应的 workflow_type（子目录文件的 workflow_type 固定是"并购重组"，
  // 会把"并购重组"类算作已上传——这里过滤掉 sub_dir 不为空的行）
  const uploaded = new Set(
    resolvedRows.value
      .filter(r => !r.sub_dir)
      .map(r => r.workflow_type)
      .filter(Boolean)
  )
  return REQUIRED_WORKFLOW_TYPES.filter(t => !uploaded.has(t))
})

const missingPublicSubdirs = computed(() => {
  const uploadedSubdirs = new Set(
    resolvedRows.value.map(r => r.sub_dir).filter(Boolean)
  )
  return REQUIRED_PUBLIC_SUBDIRS.filter(s => !uploadedSubdirs.has(s))
})

const totalMissing = computed(
  () => missingWorkflowTypes.value.length + missingPublicSubdirs.value.length
)

// 公共子目录若已有旧文件，在下方统一告警（同目录下多份历史文件会污染匹配）
const publicSubdirsWithExisting = computed(() => {
  const out = []
  const seen = new Set()
  for (const r of resolvedRows.value) {
    if (!r.sub_dir) continue
    if (!REQUIRED_PUBLIC_SUBDIRS.includes(r.sub_dir)) continue
    if (seen.has(r.target_dir)) continue
    seen.add(r.target_dir)
    const count = (existingFilesMap.value[r.target_dir] || []).length
    if (count > 0) out.push({ sub_dir: r.sub_dir, target_dir: r.target_dir, count })
  }
  return out
})

// 质押组：待上传须 2 个且包含"中大盘"+"小盘"；组为 0 时交给"缺失工作流"告警，不重复提示
const pledgeGroupIssue = computed(() => {
  const rows = resolvedRows.value.filter(r => r.workflow_type === '质押' && !r.sub_dir)
  const total = rows.length
  if (total === 0) return null
  const hasLarge = rows.some(r => r.filename.includes('中大盘'))
  const hasSmall = rows.some(r => r.filename.includes('小盘'))
  const missing = []
  if (!hasLarge) missing.push('中大盘')
  if (!hasSmall) missing.push('小盘')
  if (total === 2 && missing.length === 0) return null
  return { total, hasLarge, hasSmall, missing }
})

const canGoPreview = computed(() => acceptedFiles.value.length > 0 && dateStr.value)

const uploadPercent = computed(() => {
  if (!batchSize.value) return 0
  return Math.min(100, Math.round(doneInBatch.value / batchSize.value * 100))
})

const uploadStatus = computed(() => {
  if (uploadFailed.value > 0) return 'exception'
  if (resolvedRows.value.length > 0 && uploadSuccess.value === resolvedRows.value.length) return 'success'
  return undefined
})

// Safari 的 webkitdirectory 模式下 file.name 会带相对路径（"0422/foo.xlsx"），
// Chrome/Firefox 下只有 file.webkitRelativePath 带路径、file.name 仍是叶子名。
// 统一用 name 的最后一段作为"叶子文件名"，供解析/分组/上传 filename 使用。
function leafName(file) {
  const raw = file.name || ''
  return raw.split(/[\\/]/).pop()
}

function onFilesPicked(e) {
  const all = Array.from(e.target.files || [])
  // Drop hidden/OS/Office-lock files first — they never count as "非 Excel"
  const visible = all.filter(f => !isSilentlyIgnored(leafName(f)))
  const accepted = visible.filter(f => isAcceptableFile(leafName(f)))
  acceptedFiles.value = accepted
  skippedCount.value = visible.length - accepted.length
}

async function goPreview() {
  fileMap.clear()
  parsedRows.value = acceptedFiles.value.map(f => {
    const name = leafName(f)
    fileMap.set(name, f)
    return { ...resolveTarget(name, dateStr.value) }
  })
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
      dedup[key] = { workflow_type: r.workflow_type, step_type: r.step_type, target_dir: r.target_dir, sub_dir: null }
    }
  }
  // 强制补加：无论用户是否选了这些子目录文件，都查一次让后端触发 ensure_match_source_files
  for (const { workflow_type, step_type, sub_dir } of ALWAYS_PREVIEW_STEPS) {
    const key = `${workflow_type}|${step_type}|${dateStr.value}`
    if (!dedup[key]) {
      dedup[key] = { workflow_type, step_type, target_dir: null, sub_dir }
    }
  }
  const map = {}
  const subdirMap = {}
  for (const { workflow_type, step_type, target_dir, sub_dir } of Object.values(dedup)) {
    try {
      const resp = await api.get('/workflows/step-files/', {
        params: { step_type, workflow_type, date_str: dateStr.value }
      })
      // 后端 /step-files/ 返回里含 directory 字段，forced 项没预设 target_dir 时用它回填
      const actualDir = target_dir || resp?.directory
      if (actualDir) {
        map[actualDir] = resp?.files || []
        if (sub_dir) subdirMap[sub_dir] = actualDir
      }
    } catch (e) {
      console.warn('获取已有文件失败', target_dir || step_type, e)
      if (target_dir) map[target_dir] = []
    }
  }
  existingFilesMap.value = map
  forcedSubdirTargetMap.value = subdirMap
}

// Set ref 响应式更新助手（Vue 3 对 Set.add/delete 的追踪不完美，新建 Set 更稳）
function addToSetRef(setRef, item) {
  setRef.value = new Set([...setRef.value, item])
}
function removeFromSetRef(setRef, item) {
  const next = new Set(setRef.value)
  next.delete(item)
  setRef.value = next
}

// 预览页 · 移除单个待上传文件（纯前端，不调 API）
// row 可能来自 groups computed（里面是展开后的新对象），不能用引用匹配，
// 改用 filename 在 parsedRows / acceptedFiles 里定位真身
function removeParsedRow(row) {
  if (!row || !row.filename) return
  const name = row.filename
  const pi = parsedRows.value.findIndex(r => r.filename === name)
  if (pi !== -1) parsedRows.value.splice(pi, 1)
  const fi = acceptedFiles.value.findIndex(f => leafName(f) === name)
  if (fi !== -1) acceptedFiles.value.splice(fi, 1)
  fileMap.delete(name)
}

// 重扫单个 target_dir 的已有文件（删除/清空成功后调用）
// 更新 existingFilesMap 后，groups computed 会自动重算 will_overwrite
async function refreshDirectoryListing(targetDir) {
  // 样本查找：优先用 parsedRows（用户已选文件对应的 row）；
  // 对强制补显的国企/一级板块目录（parsedRows 里没有）用 forcedSubdirTargetMap 反查。
  let sample = parsedRows.value.find(r => r.target_dir === targetDir)
  if (!sample) {
    for (const { workflow_type, step_type, sub_dir } of FORCED_SUBDIR_GROUPS) {
      if (forcedSubdirTargetMap.value[sub_dir] === targetDir) {
        sample = { workflow_type, step_type }
        break
      }
    }
  }
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

function refreshFromDirectoryPicker() {
  if (!dirInputRef.value) return
  dirInputRef.value.value = ''   // 清空以确保同目录选择也触发 change
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

async function startUpload(rowsToUpload = null) {
  const isRetry = Array.isArray(rowsToUpload)
  const rows = isRetry ? rowsToUpload : resolvedRows.value
  console.log('[QuickUpload] startUpload invoked', {
    isRetry,
    rowsCount: rows.length,
    rowsSample: rows.slice(0, 3).map(r => ({ filename: r?.filename, step_type: r?.step_type, workflow_type: r?.workflow_type })),
    fileMapSize: fileMap.size,
    dateStr: dateStr.value,
  })
  currentStep.value = 2
  uploading.value = true
  if (!isRetry) {
    // Fresh upload: reset all counters
    uploadSuccess.value = 0
    uploadFailed.value = 0
    failedUploads.value = []
  } else {
    // Retry: remove retrying items from failed list and decrement counter by retry count
    // (avoids double-counting if the retry also fails; worker will re-increment on failure)
    const retrySet = new Set(rows.map(r => r.filename))
    failedUploads.value = failedUploads.value.filter(f => !retrySet.has(f.filename))
    uploadFailed.value = Math.max(0, uploadFailed.value - rows.length)
  }
  // Each call to startUpload is its own progress batch: bar resets 0→100% over rows.length
  batchSize.value = rows.length
  doneInBatch.value = 0

  const concurrency = 4
  const queue = [...rows]
  const worker = async (workerId) => {
    while (queue.length) {
      const row = queue.shift()
      if (!row) break
      const file = fileMap.get(row.filename)
      if (!file) {
        console.warn('[QuickUpload] file missing in fileMap', row.filename)
        uploadFailed.value++
        doneInBatch.value++
        failedUploads.value.push({ filename: row.filename, error: '文件引用丢失', _row: row })
        continue
      }
      const t0 = performance.now()
      console.log(`[QuickUpload] worker#${workerId} POST ${row.filename} → ${row.workflow_type}/${row.step_type}`)
      try {
        const fd = new FormData()
        // row.filename 已经是叶子名（resolveTarget 用 file.name 解析时就是）；
        // 但某些浏览器在 webkitdirectory 下 file.name 可能带相对路径，
        // 所以显式传第三个参数强制使用叶子名，避免后端拼出
        // /app/data/excel/{wt}/{date}/<subdir>/<filename> 里混入多余目录层。
        const leafName = row.filename.split(/[\\/]/).pop()
        fd.append('file', file, leafName)
        fd.append('workflow_id', '0')
        fd.append('step_index', '0')
        fd.append('step_type', row.step_type)
        fd.append('workflow_type', row.workflow_type)
        fd.append('date_str', dateStr.value)
        const resp = await api.post('/workflows/upload-step-file/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const ms = Math.round(performance.now() - t0)
        if (resp?.success) {
          console.log(`[QuickUpload] worker#${workerId} OK ${row.filename} (${ms}ms)`)
          uploadSuccess.value++
        } else {
          console.warn(`[QuickUpload] worker#${workerId} FAIL ${row.filename} (${ms}ms)`, resp)
          uploadFailed.value++
          failedUploads.value.push({ filename: row.filename, error: resp?.message || '未知错误', _row: row })
        }
      } catch (err) {
        const ms = Math.round(performance.now() - t0)
        console.error(`[QuickUpload] worker#${workerId} ERROR ${row.filename} (${ms}ms)`, err)
        uploadFailed.value++
        failedUploads.value.push({ filename: row.filename, error: err.message || String(err), _row: row })
      }
      doneInBatch.value++
    }
  }
  await Promise.all(Array.from({ length: concurrency }, (_, i) => worker(i)))
  console.log('[QuickUpload] startUpload finished', {
    success: uploadSuccess.value,
    failed: uploadFailed.value,
  })
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
    ElMessage.warning('批量同步日期失败，请手动调整：' + (e?.message || e))
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
    dateStr.value = todayLocal()
    acceptedFiles.value = []
    skippedCount.value = 0
    parsedRows.value = []
    existingFilesMap.value = {}
    forcedSubdirTargetMap.value = {}
    uploadSuccess.value = 0
    uploadFailed.value = 0
    failedUploads.value = []
    batchSize.value = 0
    doneInBatch.value = 0
    fileMap.clear()
  }
})

// 仅测试用：暴露内部状态/方法便于单测断言（非正式 API）
defineExpose({
  // state
  acceptedFiles, parsedRows, existingFilesMap, fileMap,
  deletingFiles, clearingDirs, uploading, currentStep,
  // computeds
  publicSubdirsWithExisting, pledgeGroupIssue,
  // methods
  removeParsedRow, refreshDirectoryListing, deleteExistingFile, clearDirectory,
  refreshFromDirectoryPicker,
})
</script>
