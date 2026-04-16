<template>
  <div class="stock-pools">
    <el-card>
      <template #header>
        <span>选股池列表</span>
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
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatBeijingTime(row.created_at) }}
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
    </el-card>

    <!-- 选股池数据详情弹窗 -->
    <el-dialog v-model="showDataDialog" :title="dataDialogTitle" width="90%" top="5vh">
      <div v-if="dataLoading" v-loading="true" style="height: 200px;"></div>
      <template v-else>
        <div style="margin-bottom: 12px; display: flex; gap: 16px; align-items: center;">
          <el-tag>共 {{ poolData.total_stocks || 0 }} 条</el-tag>
          <el-tag type="info" v-if="poolData.date_str">日期: {{ poolData.date_str }}</el-tag>
          <el-tag type="warning" v-for="t in (poolData.source_types || [])" :key="t" size="small">{{ t }}</el-tag>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const stockPools = ref([])
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
    stockPools.value = await api.get('/stock-pools/')
  } catch (error) {
    ElMessage.error('获取选股池失败')
  } finally {
    loading.value = false
  }
}

const handleViewData = async (row) => {
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

onMounted(() => {
  fetchStockPools()
})
</script>

<style scoped>
.stock-pools {
  padding: 20px;
}
</style>
