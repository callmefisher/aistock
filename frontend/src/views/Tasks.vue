<template>
  <div class="tasks">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务列表</span>
          <el-button type="primary" @click="showDialog = true">
            <el-icon><Plus /></el-icon>
            添加任务
          </el-button>
        </div>
      </template>
      
      <el-table :data="tasks" stripe v-loading="loading">
        <el-table-column prop="name" label="任务名称" />
        <el-table-column prop="schedule_type" label="调度类型" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_run_time" label="最后运行时间" />
        <el-table-column prop="next_run_time" label="下次运行时间" />
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="handleRun(row.id)">
              执行
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-dialog v-model="showDialog" title="添加任务" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="任务名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="调度类型">
          <el-select v-model="form.schedule_type" style="width: 100%">
            <el-option label="手动执行" value="manual" />
            <el-option label="定时执行" value="cron" />
            <el-option label="间隔执行" value="interval" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const showDialog = ref(false)
const tasks = ref([])

const form = ref({
  name: '',
  data_source_ids: [],
  rule_ids: [],
  schedule_type: 'manual',
  schedule_config: {}
})

const getStatusType = (status) => {
  const types = {
    completed: 'success',
    running: 'primary',
    failed: 'danger',
    pending: 'info'
  }
  return types[status] || 'info'
}

const fetchTasks = async () => {
  loading.value = true
  try {
    tasks.value = await api.get('/tasks/')
  } catch (error) {
    ElMessage.error('获取任务失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  try {
    await api.post('/tasks/', form.value)
    ElMessage.success('添加成功')
    showDialog.value = false
    fetchTasks()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const handleRun = async (id) => {
  try {
    await api.post(`/tasks/${id}/run/`)
    ElMessage.success('任务已加入执行队列')
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此任务?', '提示', {
      type: 'warning'
    })
    await api.delete(`/tasks/${id}`)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleEdit = (row) => {
  ElMessage.info('编辑功能待实现')
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
