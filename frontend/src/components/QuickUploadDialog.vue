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
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.will_overwrite" type="danger" size="small">将覆盖</el-tag>
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
      <el-button v-if="currentStep === 2 && failedUploads.length && !uploading" @click="retryFailed">重试失败项</el-button>
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
  if (resolvedRows.value.length > 0 && uploadSuccess.value === resolvedRows.value.length) return 'success'
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
  if (!rowsToUpload) {
    uploadSuccess.value = 0
    uploadFailed.value = 0
    failedUploads.value = []
  } else {
    failedUploads.value = failedUploads.value.filter(f => !rows.some(r => r.filename === f.filename))
    uploadFailed.value = failedUploads.value.length
  }

  const concurrency = 4
  const queue = [...rows]
  const worker = async () => {
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
  }
  await Promise.all(Array.from({ length: concurrency }, () => worker()))
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
