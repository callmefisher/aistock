<template>
  <div class="excel-compare">
    <div class="page-header">
      <h1>Excel数据比对</h1>
      <p class="subtitle">比较两个Excel文件的数据差异，智能匹配列名和主键</p>
    </div>

    <div class="upload-section">
      <div class="upload-card" :class="{ 'has-file': fileA }">
        <div class="card-header">
          <span class="file-label">A文件</span>
          <el-tag v-if="fileA" type="success" size="small">
            {{ fileA.name }}
          </el-tag>
        </div>
        <el-upload
          ref="uploadA"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :on-change="(file) => handleFileChange(file, 'A')"
          drag
        >
          <div class="upload-content">
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              <span>拖拽文件到此处或</span>
              <em>点击上传</em>
            </div>
            <div class="upload-hint">支持 .xlsx, .xls 格式</div>
          </div>
        </el-upload>
        <div v-if="dataA.length" class="data-info">
          <el-icon><Document /></el-icon>
          <span>{{ dataA.length }} 行数据</span>
          <span class="divider">|</span>
          <span>{{ columnsA.length }} 列</span>
        </div>
      </div>

      <div class="compare-icon">
        <el-icon :size="32"><Switch /></el-icon>
      </div>

      <div class="upload-card" :class="{ 'has-file': fileB }">
        <div class="card-header">
          <span class="file-label">B文件</span>
          <el-tag v-if="fileB" type="success" size="small">
            {{ fileB.name }}
          </el-tag>
        </div>
        <el-upload
          ref="uploadB"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :on-change="(file) => handleFileChange(file, 'B')"
          drag
        >
          <div class="upload-content">
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              <span>拖拽文件到此处或</span>
              <em>点击上传</em>
            </div>
            <div class="upload-hint">支持 .xlsx, .xls 格式</div>
          </div>
        </el-upload>
        <div v-if="dataB.length" class="data-info">
          <el-icon><Document /></el-icon>
          <span>{{ dataB.length }} 行数据</span>
          <span class="divider">|</span>
          <span>{{ columnsB.length }} 列</span>
        </div>
      </div>
    </div>

    <div v-if="dataA.length && dataB.length" class="mapping-section">
      <div class="section-title">
        <el-icon><Connection /></el-icon>
        <span>列名映射</span>
        <el-tag type="info" size="small">自动识别</el-tag>
      </div>
      <div class="mapping-grid">
        <div class="mapping-header">
          <span>标准列名</span>
          <span>A文件列名</span>
          <span>B文件列名</span>
          <span>主键</span>
        </div>
        <div v-for="mapping in columnMappings" :key="mapping.standard" class="mapping-row">
          <span class="standard-name">{{ mapping.standard }}</span>
          <el-select v-model="mapping.columnA" placeholder="选择列" size="small" clearable>
            <el-option
              v-for="col in columnsA"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
          <el-select v-model="mapping.columnB" placeholder="选择列" size="small" clearable>
            <el-option
              v-for="col in columnsB"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
          <el-checkbox v-model="mapping.isKey" :disabled="!mapping.columnA && !mapping.columnB" />
        </div>
      </div>
      <div class="key-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>主键列用于匹配同一数据，建议选择：证券代码 + 最新公告日 + 百日新高 + 20日均线 + 国企 + 一级板块</span>
      </div>
    </div>

    <div v-if="canCompare" class="action-section">
      <el-button type="primary" size="large" @click="startCompare" :loading="comparing">
        <el-icon><DataAnalysis /></el-icon>
        开始比对
      </el-button>
      <span class="compare-hint">将比对 {{ dataA.length + dataB.length }} 行数据</span>
    </div>

    <div v-if="compareResult" class="result-section">
      <div class="result-header">
        <h2>比对结果</h2>
        <div class="result-summary">
          <div class="summary-item" :class="{ active: activeTab === 'onlyA' }" @click="activeTab = 'onlyA'">
            <span class="summary-count">{{ compareResult.onlyA.length }}</span>
            <span class="summary-label">A有B无</span>
          </div>
          <div class="summary-item" :class="{ active: activeTab === 'onlyB' }" @click="activeTab = 'onlyB'">
            <span class="summary-count">{{ compareResult.onlyB.length }}</span>
            <span class="summary-label">B有A无</span>
          </div>
          <div class="summary-item" :class="{ active: activeTab === 'same' }" @click="activeTab = 'same'">
            <span class="summary-count">{{ compareResult.same.length }}</span>
            <span class="summary-label">完全相同</span>
          </div>
          <div class="summary-item" :class="{ active: activeTab === 'diff' }" @click="activeTab = 'diff'">
            <span class="summary-count">{{ compareResult.diff.length }}</span>
            <span class="summary-label">值不同</span>
          </div>
        </div>
      </div>

      <div class="result-content">
        <div v-if="activeTab === 'onlyA'" class="result-panel">
          <div class="panel-header">
            <el-icon><Warning /></el-icon>
            <span>仅在A文件中存在的数据 ({{ compareResult.onlyA.length }}条)</span>
          </div>
          <el-table :data="compareResult.onlyA" stripe border max-height="500" style="width: 100%">
            <el-table-column
              v-for="col in displayColumns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="120"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <div v-if="activeTab === 'onlyB'" class="result-panel">
          <div class="panel-header">
            <el-icon><Warning /></el-icon>
            <span>仅在B文件中存在的数据 ({{ compareResult.onlyB.length }}条)</span>
          </div>
          <el-table :data="compareResult.onlyB" stripe border max-height="500" style="width: 100%">
            <el-table-column
              v-for="col in displayColumns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="120"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <div v-if="activeTab === 'same'" class="result-panel">
          <div class="panel-header success">
            <el-icon><CircleCheck /></el-icon>
            <span>两文件完全相同的数据 ({{ compareResult.same.length }}条)</span>
          </div>
          <el-table :data="compareResult.same" stripe border max-height="500" style="width: 100%">
            <el-table-column
              v-for="col in displayColumns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="120"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <div v-if="activeTab === 'diff'" class="result-panel">
          <div class="panel-header warning">
            <el-icon><Warning /></el-icon>
            <span>两文件中都存在但值不同的数据 ({{ compareResult.diff.length }}条)</span>
          </div>
          <el-table :data="compareResult.diff" stripe border max-height="500" style="width: 100%">
            <el-table-column prop="_keyDisplay" label="主键" min-width="200" fixed show-overflow-tooltip />
            <el-table-column prop="_diffField" label="差异字段" width="120" />
            <el-table-column label="A文件值" min-width="150">
              <template #default="{ row }">
                <span class="value-a">{{ row._valueA }}</span>
              </template>
            </el-table-column>
            <el-table-column label="B文件值" min-width="150">
              <template #default="{ row }">
                <span class="value-b">{{ row._valueB }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import * as XLSX from 'xlsx'
import { ElMessage } from 'element-plus'

const COLUMN_NAME_MAPPINGS = {
  '证券代码': ['证券代码', '代码', '股票代码', 'code', 'CODE'],
  '证券简称': ['证券简称', '名称', '股票名称', '简称', 'name', 'NAME'],
  '最新公告日': ['最新公告日', '公告日期', '公告日', '日期', 'date', 'DATE'],
  '百日新高': ['百日新高', '百日新高日期', '新高'],
  '20日均线': ['20日均线', '站上20日线', '20日线', '均线'],
  '国企': ['国企', '国央企', '国有企业', '央企'],
  '一级板块': ['一级板块', '所属板块', '板块', '行业板块']
}

const KEY_COLUMNS = ['证券代码', '最新公告日', '百日新高', '20日均线', '国企', '一级板块']

const fileA = ref(null)
const fileB = ref(null)
const dataA = ref([])
const dataB = ref([])
const columnsA = ref([])
const columnsB = ref([])
const comparing = ref(false)
const compareResult = ref(null)
const activeTab = ref('onlyA')

const columnMappings = ref([])

const initColumnMappings = () => {
  columnMappings.value = Object.keys(COLUMN_NAME_MAPPINGS).map(standard => ({
    standard,
    columnA: '',
    columnB: '',
    isKey: KEY_COLUMNS.includes(standard)
  }))
}

initColumnMappings()

const displayColumns = computed(() => {
  return columnMappings.value
    .filter(m => m.columnA || m.columnB)
    .map(m => m.standard)
})

const canCompare = computed(() => {
  const hasKey = columnMappings.value.some(m => m.isKey && (m.columnA || m.columnB))
  return dataA.value.length > 0 && dataB.value.length > 0 && hasKey
})

const normalizeColumnName = (colName) => {
  const normalized = colName?.toString().trim() || ''
  for (const [standard, aliases] of Object.entries(COLUMN_NAME_MAPPINGS)) {
    if (aliases.some(alias => normalized.includes(alias))) {
      return standard
    }
  }
  return normalized
}

const handleFileChange = async (file, type) => {
  const fileRef = type === 'A' ? fileA : fileB
  const dataRef = type === 'A' ? dataA : dataB
  const columnsRef = type === 'A' ? columnsA : columnsB

  fileRef.value = file.raw

  try {
    const data = await file.raw.arrayBuffer()
    const workbook = XLSX.read(data, { type: 'array' })
    const sheetName = workbook.SheetNames[0]
    const worksheet = workbook.Sheets[sheetName]
    const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' })

    if (jsonData.length === 0) {
      ElMessage.warning('文件没有数据')
      return
    }

    dataRef.value = jsonData
    columnsRef.value = Object.keys(jsonData[0])

    autoMapColumns(type)

    ElMessage.success(`文件${type}加载成功：${jsonData.length}行数据`)
  } catch (error) {
    console.error('解析文件失败:', error)
    ElMessage.error('解析文件失败，请检查文件格式')
  }
}

const autoMapColumns = (type) => {
  const columns = type === 'A' ? columnsA.value : columnsB.value
  const mappingKey = type === 'A' ? 'columnA' : 'columnB'

  columns.forEach(col => {
    const normalizedCol = normalizeColumnName(col)
    const mapping = columnMappings.value.find(m => m.standard === normalizedCol)
    if (mapping && !mapping[mappingKey]) {
      mapping[mappingKey] = col
    }
  })
}

const buildKey = (row, mappings, file) => {
  const keyParts = []
  mappings.forEach(m => {
    if (m.isKey) {
      const colName = file === 'A' ? m.columnA : m.columnB
      const value = row[colName]?.toString().trim() || ''
      keyParts.push(`${m.standard}:${value}`)
    }
  })
  return keyParts.join('|')
}

const buildDisplayRow = (row, mappings, file) => {
  const displayRow = {}
  mappings.forEach(m => {
    const colName = file === 'A' ? m.columnA : m.columnB
    if (colName) {
      displayRow[m.standard] = row[colName] ?? ''
    }
  })
  return displayRow
}

const startCompare = () => {
  comparing.value = true

  try {
    const keyMappings = columnMappings.value.filter(m => m.isKey)
    const compareMappings = columnMappings.value.filter(m => m.columnA && m.columnB)

    if (keyMappings.length === 0) {
      ElMessage.warning('请至少选择一个主键列')
      comparing.value = false
      return
    }

    const mapA = new Map()
    dataA.value.forEach(row => {
      const key = buildKey(row, keyMappings, 'A')
      if (key) {
        mapA.set(key, row)
      }
    })

    const mapB = new Map()
    dataB.value.forEach(row => {
      const key = buildKey(row, keyMappings, 'B')
      if (key) {
        mapB.set(key, row)
      }
    })

    const onlyA = []
    const onlyB = []
    const same = []
    const diff = []

    mapA.forEach((rowA, key) => {
      if (mapB.has(key)) {
        const rowB = mapB.get(key)
        let hasDiff = false
        const diffFields = []

        compareMappings.forEach(m => {
          const valA = (rowA[m.columnA] ?? '').toString().trim()
          const valB = (rowB[m.columnB] ?? '').toString().trim()
          if (valA !== valB) {
            hasDiff = true
            diffFields.push({
              field: m.standard,
              valueA: valA,
              valueB: valB
            })
          }
        })

        if (hasDiff) {
          diffFields.forEach(d => {
            diff.push({
              _keyDisplay: key,
              _diffField: d.field,
              _valueA: d.valueA,
              _valueB: d.valueB
            })
          })
        } else {
          same.push(buildDisplayRow(rowA, columnMappings.value, 'A'))
        }
      } else {
        onlyA.push(buildDisplayRow(rowA, columnMappings.value, 'A'))
      }
    })

    mapB.forEach((rowB, key) => {
      if (!mapA.has(key)) {
        onlyB.push(buildDisplayRow(rowB, columnMappings.value, 'B'))
      }
    })

    compareResult.value = { onlyA, onlyB, same, diff }
    activeTab.value = onlyA.length > 0 ? 'onlyA' : (onlyB.length > 0 ? 'onlyB' : (diff.length > 0 ? 'diff' : 'same'))

    ElMessage.success(`比对完成！A有B无: ${onlyA.length}, B有A无: ${onlyB.length}, 相同: ${same.length}, 不同: ${diff.length}`)
  } catch (error) {
    console.error('比对失败:', error)
    ElMessage.error('比对失败: ' + error.message)
  } finally {
    comparing.value = false
  }
}
</script>

<style scoped>
.excel-compare {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 32px;
  text-align: center;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.upload-section {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 32px;
}

.upload-card {
  flex: 1;
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.upload-card.has-file {
  border-color: #52c41a;
  background: linear-gradient(135deg, #f6ffed 0%, #fff 100%);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.file-label {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
}

.upload-content {
  padding: 40px 20px;
  text-align: center;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 16px;
}

.upload-text {
  color: #666;
  font-size: 14px;
}

.upload-text em {
  color: #409eff;
  font-style: normal;
}

.upload-hint {
  color: #999;
  font-size: 12px;
  margin-top: 8px;
}

.data-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  color: #52c41a;
  font-size: 14px;
}

.divider {
  color: #d9d9d9;
}

.compare-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #409eff;
  padding-top: 80px;
}

.mapping-section {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
}

.mapping-grid {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}

.mapping-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 60px;
  gap: 16px;
  padding: 12px 16px;
  background: #fafafa;
  font-weight: 500;
  font-size: 13px;
  color: #666;
}

.mapping-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 60px;
  gap: 16px;
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  align-items: center;
}

.standard-name {
  font-weight: 500;
  color: #1a1a2e;
}

.key-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px 16px;
  background: #e6f7ff;
  border-radius: 8px;
  color: #1890ff;
  font-size: 13px;
}

.action-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 32px;
}

.compare-hint {
  color: #999;
  font-size: 14px;
}

.result-section {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.result-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1a1a2e;
}

.result-summary {
  display: flex;
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 24px;
  background: #f5f5f5;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 100px;
}

.summary-item:hover {
  background: #e6e6e6;
}

.summary-item.active {
  background: #1890ff;
  color: #fff;
}

.summary-count {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.summary-label {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.8;
}

.result-content {
  margin-top: 16px;
}

.result-panel {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff2f0;
  border-radius: 8px;
  margin-bottom: 16px;
  color: #ff4d4f;
  font-weight: 500;
}

.panel-header.success {
  background: #f6ffed;
  color: #52c41a;
}

.panel-header.warning {
  background: #fffbe6;
  color: #faad14;
}

.value-a {
  color: #1890ff;
  font-weight: 500;
}

.value-b {
  color: #52c41a;
  font-weight: 500;
}

:deep(.el-upload-dragger) {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  transition: all 0.3s ease;
}

:deep(.el-upload-dragger:hover) {
  border-color: #409eff;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background: #fafafa;
  font-weight: 600;
}
</style>
