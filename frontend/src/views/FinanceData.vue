<template>
  <div class="finance-data-container">
    <el-card class="header-card">
      <template #header>
        <div class="header-title">
          <span>金融数据平台</span>
          <el-tag type="success" v-if="isConnected">已连接</el-tag>
          <el-tag type="danger" v-else>未连接</el-tag>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">股票数量</div>
            <div class="stat-value">{{ stats.stock_count || 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">行情数据</div>
            <div class="stat-value">{{ formatNumber(stats.daily_bar_count) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">财务数据</div>
            <div class="stat-value">{{ formatNumber(stats.financial_count) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">最后更新</div>
            <div class="stat-value">{{ stats.last_trade_date || 'N/A' }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="20" class="action-row">
      <el-col :span="24">
        <el-button type="primary" @click="refreshStats" :loading="loading">刷新状态</el-button>
        <el-button type="success" @click="showUpdateDialog = true">手动更新数据</el-button>
        <el-button type="warning" @click="showConfigDialog = true">配置管理</el-button>
        <el-button type="info" @click="showQueryDialog = true">SQL查询</el-button>
        <el-button type="primary" @click="showAIQueryDialog = true">AI查询</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="data-card">
          <template #header>
            <span>数据获取配置</span>
          </template>
          <el-table :data="fetchConfigs" border stripe>
            <el-table-column prop="data_type" label="数据类型" width="120" />
            <el-table-column prop="fetch_frequency" label="更新频率" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.fetch_frequency === 'hourly'" type="danger">每小时</el-tag>
                <el-tag v-else-if="row.fetch_frequency === 'daily'" type="warning">每天</el-tag>
                <el-tag v-else type="info">{{ row.fetch_frequency }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_fetch_time" label="最后更新" width="150">
              <template #default="{ row }">
                {{ row.last_fetch_time || '从未' }}
              </template>
            </el-table-column>
            <el-table-column prop="is_enabled" label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_enabled" type="success">启用</el-tag>
                <el-tag v-else type="danger">禁用</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="data-card">
          <template #header>
            <span>保留策略配置</span>
          </template>
          <el-table :data="retentionConfigs" border stripe>
            <el-table-column prop="data_type" label="数据类型" width="120" />
            <el-table-column prop="retention_days" label="保留天数" width="100">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.retention_days < 365 }">
                  {{ row.retention_days }}天
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="archive_before_delete" label="归档后删除">
              <template #default="{ row }">
                <el-tag v-if="row.archive_before_delete" type="warning">是</el-tag>
                <el-tag v-else type="info">否</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showUpdateDialog" title="手动更新数据" width="500px">
      <el-form :model="updateForm" label-width="100px">
        <el-form-item label="数据类型">
          <el-select v-model="updateForm.data_type" placeholder="请选择数据类型">
            <el-option label="股票日线" value="stock_daily" />
            <el-option label="实时行情" value="stock_spot" />
            <el-option label="财务数据" value="financial" />
            <el-option label="基金净值" value="fund_nav" />
            <el-option label="指数行情" value="index_bar" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票代码" v-if="updateForm.data_type === 'stock_daily'">
          <el-input v-model="updateForm.stock_code" placeholder="留空则更新全部" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="updateForm.start_date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="updateForm.end_date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpdateDialog = false">取消</el-button>
        <el-button type="primary" @click="executeUpdate" :loading="updating">执行更新</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showConfigDialog" title="配置管理" width="600px">
      <el-tabs>
        <el-tab-pane label="更新策略">
          <el-form :model="newRetentionConfig" label-width="120px">
            <el-form-item label="数据类型">
              <el-input v-model="newRetentionConfig.data_type" />
            </el-form-item>
            <el-form-item label="保留天数">
              <el-input-number v-model="newRetentionConfig.retention_days" :min="1" :max="3650" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveRetentionConfig">保存配置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="清理任务">
          <el-form label-width="120px">
            <el-form-item label="执行方式">
              <el-radio-group v-model="cleanupSchedule">
                <el-radio label="weekly">每周</el-radio>
                <el-radio label="daily">每天</el-radio>
                <el-radio label="monthly">每月</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="danger" @click="executeCleanup">立即清理过期数据</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog v-model="showQueryDialog" title="SQL查询" width="800px">
      <el-input
        v-model="sqlQuery"
        type="textarea"
        :rows="6"
        placeholder="SELECT stock_code, trade_date, close FROM fact_daily_bar WHERE trade_date >= '2026-01-01'"
      />
      <el-button type="primary" @click="executeSQL" :loading="querying" class="query-btn">执行查询</el-button>
      <el-divider v-if="queryResult.data" />
      <el-table v-if="queryResult.data && queryResult.data.length" :data="queryResult.data" border max-height="300">
        <el-table-column
          v-for="(col, idx) in queryResult.columns"
          :key="col"
          :prop="Object.keys(queryResult.data[0] || {})[idx]"
          :label="col"
          width="120"
        />
      </el-table>
      <div v-if="queryResult.row_count !== undefined" class="query-info">
        查询结果: {{ queryResult.row_count }} 行
      </div>
      <div v-if="queryResult.error" class="query-error">
        {{ queryResult.error }}
      </div>
    </el-dialog>

    <el-dialog v-model="showAIQueryDialog" title="AI智能查询" width="600px">
      <el-input
        v-model="aiQuery"
        type="textarea"
        :rows="4"
        placeholder="查询近三年净利润增长均超过20%且市盈率低于30倍的消费股"
      />
      <el-button type="primary" @click="executeAIQuery" :loading="aiQuerying" class="query-btn">查询</el-button>
      <el-divider v-if="aiQueryResult.sql" />
      <div v-if="aiQueryResult.sql" class="sql-preview">
        <h4>生成的SQL:</h4>
        <pre>{{ aiQueryResult.sql }}</pre>
      </div>
      <div v-if="aiQueryResult.explanation" class="explanation">
        {{ aiQueryResult.explanation }}
      </div>
      <el-divider v-if="aiQueryResult.results" />
      <el-table v-if="aiQueryResult.results && aiQueryResult.results.length" :data="aiQueryResult.results" border max-height="200">
        <el-table-column
          v-for="(col, idx) in aiQueryResult.columns || Object.keys(aiQueryResult.results[0] || {})"
          :key="col"
          :prop="Object.keys(aiQueryResult.results[0] || {})[idx]"
          :label="col"
          width="120"
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const isConnected = ref(true)
const loading = ref(false)
const updating = ref(false)
const querying = ref(false)
const aiQuerying = ref(false)

const stats = ref({
  stock_count: 0,
  daily_bar_count: 0,
  financial_count: 0,
  last_trade_date: null
})

const fetchConfigs = ref([])
const retentionConfigs = ref([])

const showUpdateDialog = ref(false)
const showConfigDialog = ref(false)
const showQueryDialog = ref(false)
const showAIQueryDialog = ref(false)

const updateForm = reactive({
  data_type: 'stock_daily',
  stock_code: '',
  start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }),
  end_date: new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
})

const newRetentionConfig = reactive({
  data_type: '',
  retention_days: 730
})

const cleanupSchedule = ref('weekly')

const sqlQuery = ref('')
const queryResult = ref({})

const aiQuery = ref('')
const aiQueryResult = ref({})

const api = axios.create({
  baseURL: '/api/v1'
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      isConnected.value = false
    }
    return Promise.reject(error)
  }
)

onMounted(() => {
  refreshStats()
  loadConfigs()
})

const refreshStats = async () => {
  loading.value = true
  try {
    const response = await api.get('/data/fetch/status')
    if (response.data.success) {
      stats.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('获取状态失败')
  } finally {
    loading.value = false
  }
}

const loadConfigs = async () => {
  try {
    const response = await api.get('/data/config/list')
    if (response.data.success) {
      fetchConfigs.value = response.data.data.fetch_configs || []
      retentionConfigs.value = response.data.data.retention_configs || []
    }
  } catch (error) {
    console.error('加载配置失败', error)
  }
}

const executeUpdate = async () => {
  updating.value = true
  try {
    const response = await api.post('/data/fetch/daily-bar', {
      data_type: updateForm.data_type,
      stock_code: updateForm.stock_code || null,
      start_date: updateForm.start_date,
      end_date: updateForm.end_date || updateForm.start_date
    })
    if (response.data.success) {
      ElMessage.success(response.data.message)
      showUpdateDialog.value = false
      refreshStats()
    } else {
      ElMessage.error(response.data.message)
    }
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    updating.value = false
  }
}

const saveRetentionConfig = async () => {
  try {
    const response = await api.post('/data/config/retention', newRetentionConfig)
    if (response.data.success) {
      ElMessage.success('配置已保存')
      loadConfigs()
    }
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const executeCleanup = async () => {
  try {
    const response = await api.post('/data/config/cleanup')
    if (response.data.success) {
      ElMessage.success(`清理完成，删除 ${response.data.total_deleted} 条过期数据`)
    }
  } catch (error) {
    ElMessage.error('清理失败')
  }
}

const executeSQL = async () => {
  if (!sqlQuery.value.trim()) {
    ElMessage.warning('请输入SQL语句')
    return
  }
  querying.value = true
  try {
    const response = await api.post('/data/query/sql', {
      sql: sqlQuery.value
    })
    queryResult.value = response.data
  } catch (error) {
    queryResult.value = { error: '查询执行失败' }
  } finally {
    querying.value = false
  }
}

const executeAIQuery = async () => {
  if (!aiQuery.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  aiQuerying.value = true
  try {
    const response = await api.post('/data/query/ai', {
      query: aiQuery.value,
      mode: 'nl2sql'
    })
    aiQueryResult.value = response.data
  } catch (error) {
    aiQueryResult.value = { error: 'AI查询失败' }
  } finally {
    aiQuerying.value = false
  }
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toString()
}
</script>

<style scoped>
.finance-data-container {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.header-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item {
  text-align: center;
  padding: 10px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409EFF;
}

.action-row {
  margin-bottom: 20px;
}

.data-card {
  margin-bottom: 20px;
}

.query-btn {
  margin-top: 10px;
}

.query-info {
  margin-top: 10px;
  color: #67C23A;
}

.query-error {
  margin-top: 10px;
  color: #F56C6C;
}

.sql-preview {
  margin-top: 10px;
}

.sql-preview pre {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.explanation {
  margin-top: 10px;
  color: #909399;
  font-style: italic;
}

.text-danger {
  color: #F56C6C;
}
</style>
