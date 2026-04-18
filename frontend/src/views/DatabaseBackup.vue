<template>
  <div class="database-backup">
    <h2 class="page-title">数据库备份</h2>

    <el-card class="section-card">
      <template #header><span>导出备份</span></template>
      <p class="description">将当前数据库全部表导出为 SQL 文件。</p>
      <el-button type="primary" :loading="exporting" @click="handleExport">
        {{ exporting ? '导出中...' : '立即导出' }}
      </el-button>
      <el-alert v-if="exportError" :title="exportError" type="error"
        show-icon :closable="false" class="mt-16" />
    </el-card>

    <el-card class="section-card">
      <template #header><span>导入恢复</span></template>
      <el-alert
        title="警告：导入将覆盖数据库中的全部现有数据，操作不可逆！"
        type="error" show-icon :closable="false" class="mb-16"
      />
      <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".sql"
        :on-change="onFileChange"
        :on-exceed="() => ElMessage.warning('只能选择一个文件')"
      >
        <el-button>选择 .sql 文件</el-button>
        <template #tip>
          <div class="upload-tip">仅支持 .sql 格式</div>
        </template>
      </el-upload>
      <p v-if="selectedFile" class="file-info">已选择：{{ selectedFile.name }}</p>
      <el-button type="danger" :loading="importing" :disabled="!selectedFile"
        class="mt-16" @click="handleImport">
        {{ importing ? '恢复中...' : '确认导入恢复' }}
      </el-button>
      <el-alert v-if="importResult" :title="importResult.message"
        :type="importResult.success ? 'success' : 'error'"
        show-icon :closable="false" class="mt-16" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const exporting = ref(false)
const exportError = ref('')
const importing = ref(false)
const selectedFile = ref(null)
const importResult = ref(null)
const uploadRef = ref(null)

async function handleExport() {
  exporting.value = true
  exportError.value = ''
  try {
    const dateStr = new Date().toISOString().slice(0, 10)
    const response = await api.get(`/database/export?_t=${Date.now()}`, {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'application/octet-stream' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `aistock_backup_${dateStr}.sql`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    setTimeout(() => window.URL.revokeObjectURL(url), 100)
  } catch (e) {
    exportError.value = e.response?.data?.detail || '导出失败，请检查服务状态'
  } finally {
    exporting.value = false
  }
}

function onFileChange(file) {
  selectedFile.value = file.raw
}

async function handleImport() {
  try {
    await ElMessageBox.confirm(
      '此操作将覆盖数据库中的全部现有数据，且不可撤销。确认继续？',
      '危险操作确认',
      { confirmButtonText: '确认导入', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const form = new FormData()
    form.append('file', selectedFile.value)
    const res = await api.post('/database/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    importResult.value = { success: true, message: res.message || '恢复成功' }
    selectedFile.value = null
    uploadRef.value?.clearFiles()
  } catch (e) {
    importResult.value = {
      success: false,
      message: e.response?.data?.detail || '导入失败，请检查文件格式',
    }
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.database-backup { padding: 24px; max-width: 720px; }
.page-title { margin-bottom: 20px; font-size: 20px; color: #303133; }
.section-card { margin-bottom: 24px; }
.description { color: #606266; margin-bottom: 16px; }
.mt-16 { margin-top: 16px; }
.mb-16 { margin-bottom: 16px; }
.upload-tip { font-size: 12px; color: #909399; margin-top: 4px; }
.file-info { margin-top: 8px; font-size: 13px; color: #606266; }
</style>
