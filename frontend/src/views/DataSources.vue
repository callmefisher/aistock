<template>
  <div class="data-sources">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据源列表</span>
          <el-button type="primary" @click="showDialog = true">
            <el-icon><Plus /></el-icon>
            添加数据源
          </el-button>
        </div>
      </template>
      
      <el-table :data="dataSources" stripe v-loading="loading">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="website_url" label="网站URL" />
        <el-table-column prop="login_type" label="登录类型" />
        <el-table-column prop="data_format" label="数据格式" />
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
    
    <el-dialog v-model="showDialog" title="添加数据源" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="网站URL">
          <el-input v-model="form.website_url" />
        </el-form-item>
        <el-form-item label="登录类型">
          <el-select v-model="form.login_type" style="width: 100%">
            <el-option label="账号密码" value="password" />
            <el-option label="验证码" value="captcha" />
            <el-option label="二维码" value="qrcode" />
            <el-option label="Cookie" value="cookie" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据格式">
          <el-select v-model="form.data_format" style="width: 100%">
            <el-option label="Excel文件" value="excel" />
            <el-option label="网页表格" value="table" />
            <el-option label="API接口" value="api" />
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
const dataSources = ref([])

const form = ref({
  name: '',
  website_url: '',
  login_type: 'password',
  login_config: {},
  data_format: 'excel',
  extraction_config: {}
})

const fetchDataSources = async () => {
  loading.value = true
  try {
    dataSources.value = await api.get('/data-sources')
  } catch (error) {
    ElMessage.error('获取数据源失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  try {
    await api.post('/data-sources', form.value)
    ElMessage.success('添加成功')
    showDialog.value = false
    fetchDataSources()
  } catch (error) {
    ElMessage.error('添加失败')
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
  ElMessage.info('编辑功能待实现')
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
</style>
