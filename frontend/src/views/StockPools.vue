<template>
  <div class="stock-pools">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>选股池列表</span>
          <div>
            <input type="file" accept=".xlsx,.xls" ref="importInput" @change="handleImportFile" style="display:none" />
            <el-button type="primary" size="small" @click="$refs.importInput?.click()">
              <el-icon><Upload /></el-icon> 批量导入
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="stockPools" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="date_str" label="数据日期" width="120" />
        <el-table-column prop="total_stocks" label="股票数量" width="100" />
        <el-table-column label="来源类型" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="t in (row.source_types || [])" :key="t" size="small" style="margin-right: 4px; margin-bottom: 2px;">
              {{ t }}
            </el-tag>
            <span v-if="!row.source_types || row.source_types.length === 0" style="color: #999;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <el-button size="small" @click="handleViewData(row)">
              查看
            </el-button>
            <el-button size="small" type="primary" @click="handleDownload(row.id)">
              下载
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > 0"
        style="margin-top: 12px; justify-content: flex-end; display: flex;"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :page-sizes="[30, 50, 100]"
        :page-size="pageSize"
        :current-page="currentPage"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>

    <!-- 选股池数据详情弹窗 -->
    <el-dialog v-model="showDataDialog" :title="dataDialogTitle" width="90%" top="5vh">
      <div v-if="dataLoading" v-loading="true" style="height: 200px;"></div>
      <template v-else>
        <div style="margin-bottom: 12px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
          <el-tag>共 {{ poolData.total_stocks || 0 }} 条</el-tag>
          <el-tag type="info" v-if="poolData.date_str">日期: {{ poolData.date_str }}</el-tag>
          <el-tag type="warning" v-for="t in (poolData.source_types || [])" :key="t" size="small">{{ t }}</el-tag>
          <el-tag type="info" v-if="currentRow?.created_at">创建时间: {{ formatBeijingTime(currentRow.created_at) }}</el-tag>
        </div>
        <el-table :data="poolData.data || []" stripe border max-height="500" style="width: 100%">
          <el-table-column
            v-for="col in poolDataColumns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
      </template>
    </el-dialog>

    <!-- 批量导入对话框：逐个日期确认 -->
    <el-dialog v-model="showImportDialog" title="批量导入选股池" width="90%" top="5vh" :close-on-click-modal="false">
      <div v-if="importLoading" v-loading="true" style="height: 200px;"></div>
      <template v-else>
        <div v-if="importSheets.length === 0" style="padding: 40px; text-align: center; color: #999;">
          请先上传文件
        </div>
        <template v-else>
          <el-alert
            :title="`共 ${importSheets.length} 个合格 sheet（>= 2026-03-18）。当前处理第 ${currentSheetIndex + 1} 个。逐个确认后入库。`"
            type="info" :closable="false" style="margin-bottom: 12px;"
          />
          <div v-if="currentSheet" style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <el-tag>Sheet: {{ currentSheet.sheet_name }}</el-tag>
            <el-tag type="success">数据日期: {{ currentSheet.date_str }}</el-tag>
            <el-tag type="info">结构: {{ currentSheet.style === 'horizontal' ? '横向并排' : '纵向多段' }}</el-tag>
            <el-tag type="warning">{{ currentSheet.record_count }}条合并后</el-tag>
            <el-tag type="info">原始行 {{ currentSheet.raw_row_count }}</el-tag>
          </div>
          <div v-if="currentSheetDetailLoading" v-loading="true" style="height: 200px;"></div>
          <el-table v-else :data="currentSheetRecords" stripe border max-height="420" size="small" style="width:100%">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="证券代码" label="证券代码" width="120" />
            <el-table-column prop="证券简称" label="证券简称" width="120" />
            <el-table-column prop="最新公告日" label="最新公告日" width="120" />
            <el-table-column prop="百日新高" label="百日新高" width="120" />
            <el-table-column prop="站上20日线" label="站上20日线" width="120" />
            <el-table-column prop="所属板块" label="所属板块" width="120" />
            <el-table-column prop="国央企" label="国央企" width="100" />
            <el-table-column prop="资本运作行为" label="资本运作行为" min-width="200" show-overflow-tooltip />
          </el-table>
        </template>
      </template>
      <template #footer>
        <el-button @click="skipCurrentSheet" :disabled="!importSheets.length || importLoading">跳过</el-button>
        <el-button type="primary" @click="confirmCurrentSheet" :loading="importSubmitting" :disabled="!currentSheet">
          确认入库并处理下一个
        </el-button>
        <el-button @click="showImportDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'

const loading = ref(false)
const stockPools = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(30)
const showDataDialog = ref(false)
const dataLoading = ref(false)
const dataDialogTitle = ref('')
const poolData = ref({})

const POOL_DISPLAY_COLUMNS = ['序号', '证券代码', '证券简称', '最新公告日', '百日新高', '站上20日线', '国央企', '所属板块', '资本运作行为']

const poolDataColumns = computed(() => {
  const data = poolData.value.data || []
  if (data.length === 0) return []
  // 固定列顺序，仅展示数据中实际存在的列
  const dataKeys = new Set(Object.keys(data[0]))
  return POOL_DISPLAY_COLUMNS.filter(c => dataKeys.has(c))
})

const formatBeijingTime = (dateStr) => {
  if (!dateStr) return '-'
  // 后端返回 UTC 时间（无时区标识），加 Z 后缀让 JS 识别为 UTC，再转 UTC+8
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z')
  const bj = new Date(d.getTime() + 8 * 3600000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${bj.getUTCFullYear()}-${pad(bj.getUTCMonth() + 1)}-${pad(bj.getUTCDate())} ${pad(bj.getUTCHours())}:${pad(bj.getUTCMinutes())}:${pad(bj.getUTCSeconds())}`
}

const fetchStockPools = async () => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const res = await api.get('/stock-pools/', { params: { skip, limit: pageSize.value } })
    stockPools.value = res?.items || []
    total.value = res?.total || 0
  } catch (error) {
    ElMessage.error('获取选股池失败')
  } finally {
    loading.value = false
  }
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchStockPools()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  fetchStockPools()
}

const currentRow = ref(null)

const handleViewData = async (row) => {
  currentRow.value = row
  dataDialogTitle.value = row.name
  showDataDialog.value = true
  dataLoading.value = true
  poolData.value = {}

  try {
    const data = await api.get(`/stock-pools/${row.id}/data`)
    poolData.value = data
  } catch (error) {
    ElMessage.error('获取选股池数据失败')
  } finally {
    dataLoading.value = false
  }
}

const handleDownload = async (id) => {
  try {
    await api.download(`/stock-pools/${id}/download`)
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此选股池?', '提示', {
      type: 'warning'
    })
    await api.delete(`/stock-pools/${id}`)
    ElMessage.success('删除成功')
    fetchStockPools()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// ========== 批量导入 ==========
const showImportDialog = ref(false)
const importLoading = ref(false)
const importSubmitting = ref(false)
const importSheets = ref([])
const importToken = ref('')
const currentSheetIndex = ref(0)
const currentSheetRecords = ref([])
const currentSheetDetailLoading = ref(false)
const importInput = ref(null)

const currentSheet = computed(() => importSheets.value[currentSheetIndex.value] || null)

const loadCurrentSheetDetails = async () => {
  if (!currentSheet.value) return
  currentSheetDetailLoading.value = true
  try {
    const res = await api.get('/stock-pools/import/sheet', {
      params: { token: importToken.value, sheet_name: currentSheet.value.sheet_name }
    })
    currentSheetRecords.value = res?.records || []
  } catch (e) {
    ElMessage.error('获取 sheet 详情失败')
    currentSheetRecords.value = []
  } finally {
    currentSheetDetailLoading.value = false
  }
}

const handleImportFile = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  showImportDialog.value = true
  importLoading.value = true
  importSheets.value = []
  importToken.value = ''
  currentSheetIndex.value = 0
  currentSheetRecords.value = []
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await api.post('/stock-pools/import/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importToken.value = res?.token || ''
    importSheets.value = res?.sheets || []
    if (importSheets.value.length === 0) {
      ElMessage.warning('未发现合格 sheet（需 MMDD 命名且 >= 2026-03-18）')
    } else {
      await loadCurrentSheetDetails()
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '上传/解析失败')
  } finally {
    importLoading.value = false
    if (importInput.value) importInput.value.value = ''
  }
}

const advanceToNext = async () => {
  if (currentSheetIndex.value + 1 < importSheets.value.length) {
    currentSheetIndex.value++
    await loadCurrentSheetDetails()
  } else {
    ElMessage.success('全部 sheet 处理完毕')
    showImportDialog.value = false
    fetchStockPools()
  }
}

const confirmCurrentSheet = async () => {
  if (!currentSheet.value) return
  importSubmitting.value = true
  try {
    const res = await api.post('/stock-pools/import/confirm', {
      token: importToken.value,
      sheet_name: currentSheet.value.sheet_name
    })
    ElMessage.success(`${res.pool_name} / ${res.date_str} 已入库 ${res.imported_count} 条`)
    await advanceToNext()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '入库失败')
  } finally {
    importSubmitting.value = false
  }
}

const skipCurrentSheet = async () => {
  await advanceToNext()
}

onMounted(() => {
  fetchStockPools()
})
</script>

<style scoped>
.stock-pools {
  padding: 20px;
}
</style>
