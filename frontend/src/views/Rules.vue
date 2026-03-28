<template>
  <div class="rules">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>规则列表</span>
          <el-button type="primary" @click="showDialog = true">
            <el-icon><Plus /></el-icon>
            添加规则
          </el-button>
        </div>
      </template>
      
      <el-table :data="rules" stripe v-loading="loading">
        <el-table-column prop="name" label="规则名称" />
        <el-table-column prop="natural_language" label="自然语言描述" />
        <el-table-column prop="excel_formula" label="Excel公式" />
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
    
    <el-dialog v-model="showDialog" title="添加规则" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="规则名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="规则描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="自然语言规则">
          <el-input
            v-model="form.natural_language"
            type="textarea"
            :rows="3"
            placeholder="例如：筛选PE小于20且ROE大于15%的股票"
          />
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
const rules = ref([])

const form = ref({
  name: '',
  description: '',
  natural_language: ''
})

const fetchRules = async () => {
  loading.value = true
  try {
    rules.value = await api.get('/rules')
  } catch (error) {
    ElMessage.error('获取规则失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  try {
    await api.post('/rules', form.value)
    ElMessage.success('添加成功')
    showDialog.value = false
    fetchRules()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此规则?', '提示', {
      type: 'warning'
    })
    await api.delete(`/rules/${id}`)
    ElMessage.success('删除成功')
    fetchRules()
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
  fetchRules()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
