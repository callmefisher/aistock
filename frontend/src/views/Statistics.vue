<template>
  <div class="statistics-page">
    <div class="page-header">
      <h2>统计分析</h2>
      <p class="subtitle">查看各工作流类型的历史执行结果</p>
    </div>

    <el-card v-loading="loading">
      <el-tabs v-model="activeType" v-if="typeList.length">
        <el-tab-pane
          v-for="t in typeList"
          :key="t"
          :label="t"
          :name="t"
        >
          <el-table :data="grouped[t] || []" stripe border style="width: 100%">
            <el-table-column prop="date_str" label="数据日期" width="130" sortable />
            <el-table-column prop="workflow_name" label="工作流名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="row_count" label="数据行数" width="100" align="center" />
            <el-table-column label="文件大小" width="100" align="center">
              <template #default="{ row }">
                {{ formatSize(row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="保存时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="viewPreview(row)">
                  查看
                </el-button>
                <el-button type="danger" link size="small" @click="handleDelete(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <el-empty v-else-if="!loading" description="暂无数据，执行工作流并下载结果后会自动保存" />
    </el-card>

    <!-- 数据查看弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="`${previewData?.workflow_name || ''} - ${previewData?.date_str || ''}`"
      width="95%"
      top="3vh"
      destroy-on-close
    >
      <div class="dialog-toolbar">
        <div class="toolbar-left">
          <el-tag>{{ previewData?.workflow_type || '并购重组' }}</el-tag>
          <span>共 {{ previewData?.row_count || 0 }} 行</span>
          <span v-if="isPreviewMode" class="preview-hint">
            （预览前 {{ previewData?.data?.length }} 行）
          </span>
          <el-button
            v-if="isPreviewMode"
            size="small"
            type="primary"
            link
            @click="loadFull"
            :loading="loadingFull"
          >
            加载全部
          </el-button>
          <span v-if="hasActiveFilters" class="filter-hint">
            | 过滤后 {{ filteredData.length }} 行
          </span>
        </div>
        <div class="toolbar-right">
          <el-button v-if="hasActiveFilters" size="small" @click="clearAllFilters">
            清除过滤
          </el-button>
          <el-button size="small" type="success" @click="exportExcel" :loading="exporting">
            <el-icon><Download /></el-icon>
            导出Excel
          </el-button>
        </div>
      </div>

      <!-- 过滤器行 -->
      <div v-if="filterableCols.length" class="filter-row">
        <div v-for="col in filterableCols" :key="col" class="filter-item">
          <el-checkbox
            v-model="notEmptyFilters[col]"
            :label="col + ' 非空'"
            border
            size="small"
          />
        </div>
      </div>

      <el-table
        :data="filteredData"
        stripe
        border
        max-height="55vh"
        style="width: 100%; margin-top: 8px"
      >
        <el-table-column
          v-for="col in (previewData?.columns || [])"
          :key="col"
          :prop="col"
          :label="col"
          min-width="120"
          show-overflow-tooltip
          sortable
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import api from '@/utils/api'

const FILTERABLE_COLUMNS = ['百日新高', '20日均线', '国企', '国央企', '一级板块', '所属板块', '所属一级板块']

const loading = ref(false)
const loadingFull = ref(false)
const exporting = ref(false)
const grouped = ref({})
const activeType = ref('')
const dialogVisible = ref(false)
const previewData = ref(null)
const currentResultId = ref(null)
const notEmptyFilters = reactive({})

const typeList = computed(() => Object.keys(grouped.value))

const isPreviewMode = computed(() => {
  if (!previewData.value) return false
  return (previewData.value.data?.length || 0) < (previewData.value.row_count || 0)
})

const filterableCols = computed(() => {
  const cols = previewData.value?.columns || []
  return cols.filter(c => FILTERABLE_COLUMNS.includes(c))
})

const hasActiveFilters = computed(() => {
  return Object.values(notEmptyFilters).some(v => v)
})

const filteredData = computed(() => {
  const data = previewData.value?.data || []
  if (!hasActiveFilters.value) return data
  return data.filter(row => {
    for (const [col, enabled] of Object.entries(notEmptyFilters)) {
      if (!enabled) continue
      const val = (row[col] ?? '').toString().trim()
      if (!val) return false
    }
    return true
  })
})

const clearAllFilters = () => {
  Object.keys(notEmptyFilters).forEach(k => { notEmptyFilters[k] = false })
}

// 打开弹窗时重置过滤器
watch(dialogVisible, (v) => {
  if (!v) clearAllFilters()
})

// 勾选非空过滤时，自动加载全部数据
watch(hasActiveFilters, (active) => {
  if (active && isPreviewMode.value) {
    loadFull()
  }
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/statistics/results/grouped')
    if (res?.success) {
      grouped.value = res.data
      if (typeList.value.length && !activeType.value) {
        activeType.value = typeList.value[0]
      }
    }
  } catch (e) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const viewPreview = async (row) => {
  currentResultId.value = row.id
  try {
    const res = await api.get(`/statistics/results/${row.id}/preview`)
    if (res?.success) {
      previewData.value = res.data
      dialogVisible.value = true
    }
  } catch (e) {
    ElMessage.error('获取预览数据失败')
  }
}

const loadFull = async () => {
  if (!currentResultId.value) return
  loadingFull.value = true
  try {
    const res = await api.get(`/statistics/results/${currentResultId.value}/full`)
    if (res?.success) {
      previewData.value = res.data
    }
  } catch (e) {
    ElMessage.error('获取完整数据失败')
  } finally {
    loadingFull.value = false
  }
}

// 导出当前过滤后的数据为 Excel
const exportExcel = async () => {
  // 如果还是预览模式，先加载全部
  if (isPreviewMode.value) {
    loadingFull.value = true
    exporting.value = true
    try {
      const res = await api.get(`/statistics/results/${currentResultId.value}/full`)
      if (res?.success) {
        previewData.value = res.data
      }
    } catch (e) {
      ElMessage.error('加载完整数据失败')
      exporting.value = false
      loadingFull.value = false
      return
    } finally {
      loadingFull.value = false
    }
  }

  exporting.value = true
  try {
    const columns = previewData.value?.columns || []
    const rows = filteredData.value

    // 构建与原始下载完全一致的格式
    const wsData = [columns]
    rows.forEach(row => {
      wsData.push(columns.map(col => row[col] ?? ''))
    })

    const ws = XLSX.utils.aoa_to_sheet(wsData)

    // 设置列宽（和后端 auto_adjust_excel_width 一致，固定20字符宽）
    ws['!cols'] = columns.map(() => ({ wch: 20 }))

    // 设置自动筛选（与原始下载文件一致）
    ws['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: rows.length, c: columns.length - 1 } }) }

    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')

    const name = previewData.value?.workflow_name || '导出'
    const date = previewData.value?.date_str || ''
    const suffix = hasActiveFilters.value ? '_filtered' : ''
    XLSX.writeFile(wb, `${name}_${date}${suffix}.xlsx`)

    ElMessage.success(`已导出 ${rows.length} 行数据`)
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    exporting.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.workflow_name} (${row.date_str}) 的结果？`, '确认删除', {
      type: 'warning'
    })
    const res = await api.delete(`/statistics/results/${row.id}`)
    if (res?.success) {
      ElMessage.success('已删除')
      fetchData()
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const formatSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatTime = (iso) => {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

onMounted(fetchData)
</script>

<style scoped>
.statistics-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.dialog-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #606266;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-hint {
  color: #909399;
  font-size: 13px;
}

.filter-hint {
  color: #e6a23c;
  font-weight: 500;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}
</style>
