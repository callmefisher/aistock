<template>
  <div class="workflows">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工作流列表</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            创建工作流
          </el-button>
        </div>
      </template>

      <el-table :data="workflows" stripe v-loading="loading">
        <el-table-column prop="name" label="工作流名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="handleRun(row)">
              执行
            </el-button>
            <el-button size="small" @click="handleViewSteps(row)">
              步骤
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEditing ? '编辑工作流' : '创建工作流'" width="800px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="工作流名称">
          <el-input v-model="form.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="2" placeholder="请输入描述" />
        </el-form-item>

        <el-divider content-position="left">工作流步骤</el-divider>

        <div class="steps-container">
          <div v-for="(step, index) in form.steps" :key="index" class="step-item">
            <el-card shadow="hover" class="step-card">
              <template #header>
                <div class="step-header">
                  <el-tag type="success" size="small">步骤 {{ index + 1 }}</el-tag>
                  <el-tag :type="getStepType(step.type)" size="small">{{ getStepTypeName(step.type) }}</el-tag>
                  <el-button link type="danger" size="small" @click="removeStep(index)" :disabled="form.steps.length <= 1">
                    删除
                  </el-button>
                </div>
              </template>

              <el-form-item label="步骤类型">
                <el-select v-model="step.type" style="width: 100%" @change="onStepTypeChange(step)">
                  <el-option label="导入Excel" value="import_excel" />
                  <el-option label="合并当日数据源" value="merge_excel" />
                  <el-option label="智能去重" value="smart_dedup" />
                  <el-option label="提取列" value="extract_columns" />
                  <el-option label="导出Excel" value="export_excel" />
                  <el-option label="匹配百日新高" value="match_high_price" />
                  <el-option label="待定" value="pending" />
                </el-select>
              </el-form-item>

              <template v-if="step.type === 'import_excel'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="选择文件">
                  <div class="file-input-wrapper">
                    <el-input v-model="step.config.file_path" placeholder="请选择或输入文件名" readonly />
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      @change="onFileSelect($event, step)"
                      class="file-input"
                    />
                    <el-button @click="triggerFileInput(index)" class="file-btn">
                      选择文件
                    </el-button>
                  </div>
                </el-form-item>
                <el-form-item label="或选择数据源">
                  <el-select v-model="step.config.data_source_id" style="width: 100%" placeholder="请选择数据源" clearable>
                    <el-option
                      v-for="ds in dataSources"
                      :key="ds.id"
                      :label="ds.name"
                      :value="ds.id"
                    />
                  </el-select>
                </el-form-item>
              </template>

              <template v-if="step.type === 'merge_excel'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="默认: total_1.xlsx" />
                </el-form-item>
                <el-form-item label="排除文件名">
                  <el-input
                    v-model="step.config.exclude_patterns_text"
                    placeholder="多个用逗号分隔，如: total_,output_,temp_"
                    @blur="onExcludePatternsChange(step)"
                  />
                </el-form-item>
                <el-alert title="合并当日目录和2025public目录下所有Excel文件" type="info" :closable="false" />
              </template>

              <template v-if="step.type === 'smart_dedup'">
                <el-form-item label="证券代码列">
                  <el-input v-model="step.config.stock_code_column" placeholder="自动检测或手动输入列名" />
                </el-form-item>
                <el-form-item label="日期列">
                  <el-input v-model="step.config.date_column" placeholder="自动检测或手动输入列名" />
                </el-form-item>
                <el-alert title="按证券代码去重，保留最新公告日的数据" type="success" :closable="false" />
              </template>

              <template v-if="step.type === 'extract_columns'">
                <el-form-item label="选择模式">
                  <el-radio-group v-model="step.config.use_fixed_columns" @change="onColumnModeChange(step)">
                    <el-radio :value="true">固定4列</el-radio>
                    <el-radio :value="false">自定义列</el-radio>
                  </el-radio-group>
                </el-form-item>

                <template v-if="step.config.use_fixed_columns !== false">
                  <el-alert title="提取: 序号、证券代码、证券简称、最新公告日" type="success" :closable="false" />
                </template>
                <template v-else>
                  <el-form-item label="选择列">
                    <el-select v-model="step.config.columns" multiple style="width: 100%" placeholder="选择要提取的列">
                      <el-option label="序号" value="序号" />
                      <el-option label="证券代码" value="证券代码" />
                      <el-option label="证券简称" value="证券简称" />
                      <el-option label="最新公告日" value="最新公告日" />
                      <el-option label="其他可配置列..." value="__custom__" disabled />
                    </el-select>
                  </el-form-item>
                  <el-alert title="提示: 如需其他列名，请在config.columns中手动配置" type="info" :closable="false" />
                </template>

                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="默认: output_1.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'export_excel'">
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="请输入输出文件名" />
                </el-form-item>
                <el-form-item label="应用格式化">
                  <el-switch v-model="step.config.apply_formatting" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'match_high_price'">
                <el-form-item label="源目录">
                  <el-input v-model="step.config.source_dir" placeholder="百日新高" />
                </el-form-item>
                <el-form-item label="新增列名">
                  <el-input v-model="step.config.new_column_name" placeholder="百日新高" />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="output_2.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'pending'">
                <el-alert title="此步骤暂未配置，待后续开发" type="info" :closable="false" />
              </template>
            </el-card>
          </div>
        </div>

        <el-form-item>
          <el-button @click="addStep">
            <el-icon><Plus /></el-icon>
            添加步骤
          </el-button>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStepsDialog" title="工作流步骤详情" width="700px">
      <el-timeline>
        <el-timeline-item
          v-for="(step, index) in currentWorkflow?.steps"
          :key="index"
          :timestamp="'步骤 ' + (index + 1)"
          :type="getTimelineType(step.status)"
          placement="top"
        >
          <el-card>
            <h4>{{ getStepTypeName(step.type) }}</h4>
            <p><strong>类型:</strong> {{ step.type }}</p>
            <template v-if="step.config">
              <p v-if="step.config.data_source_id"><strong>数据源ID:</strong> {{ step.config.data_source_id }}</p>
              <p v-if="step.config.file_path"><strong>文件路径:</strong> {{ step.config.file_path }}</p>
              <p v-if="step.config.columns"><strong>保留列:</strong> {{ step.config.columns.join(', ') }}</p>
              <p v-if="step.config.output_filename"><strong>输出文件:</strong> {{ step.config.output_filename }}</p>
            </template>
            <p><strong>状态:</strong> <el-tag size="small" :type="getStepStatusType(step.status)">{{ step.status || '未执行' }}</el-tag></p>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>

    <el-dialog v-model="showExecuteDialog" title="工作流执行" width="600px">
      <el-form label-width="120px">
        <el-form-item label="工作流名称">
          <span>{{ currentWorkflow?.name }}</span>
        </el-form-item>
        <el-form-item label="执行步骤">
          <el-steps :active="executionStep" direction="vertical">
            <el-step
              v-for="(step, index) in currentWorkflow?.steps"
              :key="index"
              :title="getStepTypeName(step.type)"
              :status="getStepStatus(step.status)"
            />
          </el-steps>
        </el-form-item>
        <el-form-item label="当前步骤" v-if="executing">
          <el-tag type="primary" size="large">{{ getStepTypeName(currentWorkflow?.steps[executionStep]?.type) }}</el-tag>
        </el-form-item>
        <el-form-item label="执行结果" v-if="executionResult">
          <el-alert :type="executionResult.type" :title="executionResult.message" show-icon />
        </el-form-item>
        <template v-if="executionComplete && resultData.length">
          <el-form-item label="过滤列">
            <el-select v-model="filterColumn" placeholder="选择要过滤的列" style="width: 200px">
              <el-option v-for="col in resultColumns" :key="col" :label="col" :value="col" />
            </el-select>
          </el-form-item>
          <el-form-item label="过滤条件">
            <el-radio-group v-model="filterType">
              <el-radio label="非空">非空</el-radio>
              <el-radio label="空">空</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="过滤结果">
            <span>共 {{ filteredResultData.length }} 条 / {{ resultData.length }} 条</span>
          </el-form-item>
          <el-table :data="filteredResultData" border max-height="300" size="small">
            <el-table-column v-for="col in resultColumns" :key="col" :prop="col" :label="col" width="120" show-overflow-tooltip />
          </el-table>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showExecuteDialog = false" v-if="!executing">关闭</el-button>
        <el-button type="primary" @click="startExecution" v-if="!executing && !executionComplete">开始执行</el-button>
        <el-button type="success" @click="downloadResult" v-if="executionComplete && executionResult?.file_path">
          下载结果
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const showDialog = ref(false)
const showStepsDialog = ref(false)
const showExecuteDialog = ref(false)
const executing = ref(false)
const executionComplete = ref(false)
const executionStep = ref(0)
const executionResult = ref(null)
const resultData = ref([])
const resultColumns = ref([])
const filterColumn = ref('')
const filterType = ref('非空')
const workflows = ref([])
const dataSources = ref([])
const currentWorkflow = ref(null)
const isEditing = ref(false)
const editingId = ref(null)
const fileInputRefs = ref([])

const defaultStep = () => ({
  type: 'merge_excel',
  config: {
    date_str: new Date().toISOString().split('T')[0],
    data_source_id: null,
    file_path: '',
    columns: [],
    output_filename: 'output_1.xlsx',
    apply_formatting: true,
    stock_code_column: '',
    date_column: '',
    use_fixed_columns: true,
    exclude_patterns_text: 'total_,output_',
    exclude_patterns: ['total_', 'output_'],
    source_dir: '百日新高',
    new_column_name: '百日新高',
    output_filename: 'output_2.xlsx'
  },
  status: 'pending'
})

const form = ref({
  name: '',
  description: '',
  steps: [defaultStep()]
})

const getStatusType = (status) => {
  const types = {
    active: 'success',
    inactive: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStepType = (type) => {
  const types = {
    import_excel: 'primary',
    merge_excel: 'primary',
    dedup: 'success',
    smart_dedup: 'success',
    extract_columns: 'warning',
    export_excel: 'info',
    pending: 'danger'
  }
  return types[type] || 'info'
}

const getStepTypeName = (type) => {
  const names = {
    import_excel: '导入Excel',
    merge_excel: '合并当日数据源',
    dedup: '去除重复行',
    smart_dedup: '智能去重',
    extract_columns: '提取列',
    export_excel: '导出Excel',
    match_high_price: '匹配百日新高',
    pending: '待定'
  }
  return names[type] || type
}

const getTimelineType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getStepStatusType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getStepStatus = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'process'
  if (status === 'failed') return 'error'
  return 'wait'
}

const openCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  form.value = {
    name: '',
    description: '',
    steps: [defaultStep()]
  }
  showDialog.value = true
}

const addStep = () => {
  form.value.steps.push(defaultStep())
}

const removeStep = (index) => {
  form.value.steps.splice(index, 1)
}

const onStepTypeChange = (step) => {
  step.config = {
    date_str: new Date().toISOString().split('T')[0],
    data_source_id: null,
    file_path: '',
    columns: [],
    output_filename: 'output_1.xlsx',
    apply_formatting: true,
    stock_code_column: '',
    date_column: '',
    use_fixed_columns: true,
    exclude_patterns_text: 'total_,output_',
    exclude_patterns: ['total_', 'output_']
  }
}

const onExcludePatternsChange = (step) => {
  const text = step.config.exclude_patterns_text || ''
  const patterns = text.split(',').map(p => p.trim()).filter(p => p)
  step.config.exclude_patterns = patterns
}

const onColumnModeChange = (step) => {
  if (step.config.use_fixed_columns) {
    step.config.columns = []
  }
}

const triggerFileInput = (index) => {
  const inputs = document.querySelectorAll('.file-input')
  if (inputs[index]) {
    inputs[index].click()
  }
}

const onFileSelect = (event, step) => {
  const file = event.target.files[0]
  if (file) {
    step.config.file_path = file.name
    step.config.file_obj = file
  }
}

const fetchWorkflows = async () => {
  loading.value = true
  try {
    workflows.value = await api.get('/workflows/')
  } catch (error) {
    ElMessage.error('获取工作流失败')
  } finally {
    loading.value = false
  }
}

const fetchDataSources = async () => {
  try {
    dataSources.value = await api.get('/data-sources/')
  } catch (error) {
    console.error('获取数据源失败', error)
  }
}

const handleSave = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入工作流名称')
    return
  }

  if (form.value.steps.some(s => s.type === 'import_excel' && !s.config.file_path && !s.config.data_source_id)) {
    ElMessage.warning('导入Excel步骤必须选择文件或数据源')
    return
  }

  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      steps: form.value.steps.map(step => ({
        type: step.type,
        config: step.config,
        status: step.status || 'pending'
      }))
    }

    if (isEditing.value && editingId.value) {
      await api.put(`/workflows/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/workflows/', payload)
      ElMessage.success('创建成功')
    }

    showDialog.value = false
    fetchWorkflows()
  } catch (error) {
    ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
  }
}

const handleRun = (workflow) => {
  currentWorkflow.value = JSON.parse(JSON.stringify(workflow))
  executionStep.value = 0
  executionResult.value = null
  executionComplete.value = false
  resultData.value = []
  resultColumns.value = []
  showExecuteDialog.value = true
}

const startExecution = async () => {
  executing.value = true
  executionResult.value = null
  resultData.value = []
  resultColumns.value = []

  for (let i = 0; i < currentWorkflow.value.steps.length; i++) {
    executionStep.value = i
    try {
      const response = await api.post(`/workflows/${currentWorkflow.value.id}/execute-step/`, {
        step_index: i
      })
      currentWorkflow.value.steps[i].status = 'completed'
      if (response.data?.records) {
        resultData.value = response.data.records
        resultColumns.value = response.data.columns || []
      }
    } catch (error) {
      currentWorkflow.value.steps[i].status = 'failed'
      executionResult.value = {
        type: 'error',
        message: `步骤 ${i + 1} 执行失败`
      }
      executing.value = false
      return
    }
  }

  executing.value = false
  executionComplete.value = true
  executionResult.value = {
    type: 'success',
    message: '工作流执行完成',
    file_path: '/app/data/excel/excel_2.xlsx'
  }
  ElMessage.success('工作流执行完成')
}

const downloadResult = () => {
  ElMessage.info('下载功能待实现')
}

const filteredResultData = computed(() => {
  if (!filterColumn.value || !resultData.value.length) {
    return resultData.value
  }
  if (filterType.value === '非空') {
    return resultData.value.filter(row => row[filterColumn.value] !== '' && row[filterColumn.value] !== null && row[filterColumn.value] !== undefined)
  } else {
    return resultData.value.filter(row => row[filterColumn.value] === '' || row[filterColumn.value] === null || row[filterColumn.value] === undefined)
  }
})

const handleViewSteps = (workflow) => {
  currentWorkflow.value = workflow
  showStepsDialog.value = true
}

const handleEdit = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    description: row.description || '',
    steps: (row.steps || []).map(step => ({
      type: step.type,
      config: { ...step.config },
      status: step.status || 'pending'
    }))
  }
  if (form.value.steps.length === 0) {
    form.value.steps = [defaultStep()]
  }
  showDialog.value = true
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此工作流?', '提示', {
      type: 'warning'
    })
    await api.delete(`/workflows/${id}`)
    ElMessage.success('删除成功')
    fetchWorkflows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchWorkflows()
  fetchDataSources()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-container {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.step-item {
  margin-bottom: 15px;
}

.step-card {
  margin-bottom: 0;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-input-wrapper {
  display: flex;
  gap: 10px;
  align-items: center;
}

.file-input-wrapper .el-input {
  flex: 1;
}

.file-input {
  display: none;
}

.file-btn {
  flex-shrink: 0;
}
</style>
