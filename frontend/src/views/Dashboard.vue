<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409eff">
              <el-icon :size="30"><Connection /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.dataSources }}</div>
              <div class="stat-label">数据源</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon :size="30"><Filter /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.rules }}</div>
              <div class="stat-label">规则</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon :size="30"><Timer /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.tasks }}</div>
              <div class="stat-label">任务</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon :size="30"><Document /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ stats.stockPools }}</div>
              <div class="stat-label">选股池</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>最近执行记录</span>
          </template>
          <el-table :data="recentLogs" stripe>
            <el-table-column prop="task_id" label="任务ID" width="80" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="start_time" label="开始时间" width="180" />
            <el-table-column prop="duration" label="耗时(秒)" width="100" />
            <el-table-column prop="records_processed" label="处理记录数" width="120" />
            <el-table-column prop="error_message" label="错误信息" />
          </el-table>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>快速操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/data-sources')">
              <el-icon><Plus /></el-icon>
              添加数据源
            </el-button>
            <el-button type="success" @click="$router.push('/rules')">
              <el-icon><Plus /></el-icon>
              创建规则
            </el-button>
            <el-button type="warning" @click="$router.push('/tasks')">
              <el-icon><Plus /></el-icon>
              新建任务
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const stats = ref({
  dataSources: 0,
  rules: 0,
  tasks: 0,
  stockPools: 0
})

const recentLogs = ref([])

const getStatusType = (status) => {
  const types = {
    completed: 'success',
    running: 'primary',
    failed: 'danger',
    pending: 'info'
  }
  return types[status] || 'info'
}

const fetchStats = async () => {
  try {
    const [dataSources, rules, tasks, stockPools] = await Promise.all([
      api.get('/data-sources/'),
      api.get('/rules/'),
      api.get('/tasks/'),
      api.get('/stock-pools/')
    ])
    
    stats.value = {
      dataSources: dataSources.length,
      rules: rules.length,
      tasks: tasks.length,
      stockPools: stockPools.length
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stat-card {
  display: flex;
  align-items: center;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-right: 15px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quick-actions .el-button {
  width: 100%;
}
</style>
