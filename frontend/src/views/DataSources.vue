<template>
  <div class="data-sources">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据源列表</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            添加数据源
          </el-button>
        </div>
      </template>

      <el-table :data="dataSources" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="website_url" label="网站URL" />
        <el-table-column prop="login_type" label="登录类型">
          <template #default="{ row }">
            {{ getLoginTypeName(row.login_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="data_format" label="数据格式">
          <template #default="{ row }">
            {{ getDataFormatName(row.data_format) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_path" label="本地文件" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.extraction_config?.file_path || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEditing ? '编辑数据源' : '添加数据源'" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="网站URL">
          <el-input v-model="form.website_url" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="登录类型">
          <el-select v-model="form.login_type" style="width: 100%">
            <el-option label="账号密码" value="password" />
            <el-option label="验证码" value="captcha" />
            <el-option label="二维码" value="qrcode" />
            <el-option label="Cookie" value="cookie" />
            <el-option label="无需登录" value="none" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据格式">
          <el-select v-model="form.data_format" style="width: 100%">
            <el-option label="Excel文件" value="excel" />
            <el-option label="网页表格" value="table" />
            <el-option label="API接口" value="api" />
          </el-select>
        </el-form-item>

        <template v-if="form.data_format === 'excel'">
          <el-divider content-position="left">本地文件配置</el-divider>
          <el-form-item label="选择文件">
            <div class="file-input-wrapper">
              <el-input
                v-model="form.extraction_config.file_path"
                placeholder="请选择或输入文件路径"
                readonly
              />
              <input
                type="file"
                accept=".xlsx,.xls"
                @change="onFileSelect"
                class="file-input"
              />
              <el-button @click="triggerFileInput" class="file-btn">
                选择文件
              </el-button>
            </div>
          </el-form-item>
          <el-form-item label="Sheet名称">
            <el-input
              v-model="form.extraction_config.sheet_name"
              placeholder="默认: 第一个Sheet"
            />
          </el-form-item>
          <el-form-item label="标题行">
            <el-input-number
              v-model="form.extraction_config.header_row"
              :min="0"
              :max="100"
              placeholder="默认: 0"
            />
          </el-form-item>
        </template>
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
const dataSources = ref([])
const isEditing = ref(false)
const editingId = ref(null)

const defaultExtractionConfig = () => ({
  file_path: '',
  sheet_name: '',
  header_row: 0
})

const form = ref({
  name: '',
  website_url: '',
  login_type: 'password',
  login_config: {},
  data_format: 'excel',
  extraction_config: defaultExtractionConfig()
})

const getLoginTypeName = (type) => {
  const names = {
    password: '账号密码',
    captcha: '验证码',
    qrcode: '二维码',
    cookie: 'Cookie',
    none: '无需登录'
  }
  return names[type] || type
}

const getDataFormatName = (format) => {
  const names = {
    excel: 'Excel文件',
    table: '网页表格',
    api: 'API接口'
  }
  return names[format] || format
}

const openCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  form.value = {
    name: '',
    website_url: '',
    login_type: 'password',
    login_config: {},
    data_format: 'excel',
    extraction_config: defaultExtractionConfig()
  }
  showDialog.value = true
}

const triggerFileInput = () => {
  const input = document.querySelector('.file-input')
  if (input) {
    input.click()
  }
}

const onFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    form.value.extraction_config.file_path = file.name
  }
}

const fetchDataSources = async () => {
  loading.value = true
  try {
    dataSources.value = await api.get('/data-sources/')
  } catch (error) {
    ElMessage.error('获取数据源失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入数据源名称')
    return
  }

  if (form.value.data_format === 'excel' && !form.value.extraction_config.file_path) {
    ElMessage.warning('请选择Excel文件')
    return
  }

  try {
    const payload = {
      name: form.value.name,
      website_url: form.value.website_url,
      login_type: form.value.login_type,
      login_config: form.value.login_config,
      data_format: form.value.data_format,
      extraction_config: form.value.extraction_config
    }

    if (isEditing.value && editingId.value) {
      await api.put(`/data-sources/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/data-sources/', payload)
      ElMessage.success('添加成功')
    }

    showDialog.value = false
    fetchDataSources()
  } catch (error) {
    ElMessage.error(isEditing.value ? '更新失败' : '添加失败')
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此数据源?', '提示', {
      type: 'warning'
    })
    await api.delete(`/data-sources/${id}`)
    ElMessage.success('删除成功')
    fetchDataSources()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleEdit = (row) => {
  isEditing.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    website_url: row.website_url || '',
    login_type: row.login_type || 'password',
    login_config: row.login_config || {},
    data_format: row.data_format || 'excel',
    extraction_config: {
      file_path: row.extraction_config?.file_path || '',
      sheet_name: row.extraction_config?.sheet_name || '',
      header_row: row.extraction_config?.header_row || 0
    }
  }
  showDialog.value = true
}

onMounted(() => {
  fetchDataSources()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-input-wrapper {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
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
