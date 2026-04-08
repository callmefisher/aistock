<template>
  <div class="stock-pools">
    <el-card>
      <template #header>
        <span>选股池列表</span>
      </template>
      
      <el-table :data="stockPools" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="total_stocks" label="股票数量" />
        <el-table-column prop="created_at" label="创建时间" />
        <el-table-column prop="is_active" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleDownload(row.id)">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const stockPools = ref([])

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

const handleDownload = async (id) => {
  try {
    const response = await api.get(`/stock-pools/${id}/download/`, {
      responseType: 'blob'
    })
    
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `stock_pool_${id}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
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
</style>
