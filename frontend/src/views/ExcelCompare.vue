<template>
  <div class="excel-compare">
    <div class="page-header">
      <h1>Excel数据比对</h1>
      <p class="subtitle">比较两个Excel文件的数据差异，支持自定义列映射和主键</p>
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
        <div v-if="sheetsA.length" class="sheet-selector">
          <span class="sheet-label">Sheet:</span>
          <el-select v-model="selectedSheetA" size="small" @change="onSheetChange('A')">
            <el-option v-for="s in sheetsA" :key="s" :label="s" :value="s" />
          </el-select>
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
        <div v-if="sheetsB.length" class="sheet-selector">
          <span class="sheet-label">Sheet:</span>
          <el-select v-model="selectedSheetB" size="small" @change="onSheetChange('B')">
            <el-option v-for="s in sheetsB" :key="s" :label="s" :value="s" />
          </el-select>
        </div>
      </div>
    </div>

    <div v-if="columnsA.length && columnsB.length" class="mapping-section">
      <div class="section-title">
        <el-icon><Connection /></el-icon>
        <span>列映射配置</span>
        <div class="section-actions">
          <el-button size="small" @click="autoMatch">
            <el-icon><Refresh /></el-icon>
            自动匹配
          </el-button>
          <el-button size="small" type="primary" @click="addMappingRow">
            <el-icon><Plus /></el-icon>
            添加映射
          </el-button>
        </div>
      </div>
      <div class="mapping-grid">
        <div class="mapping-header">
          <span>对比列名</span>
          <span>A文件列</span>
          <span>B文件列</span>
          <span>主键</span>
          <span>对比</span>
          <span></span>
        </div>
        <div v-for="(mapping, idx) in columnMappings" :key="idx" class="mapping-row">
          <el-input v-model="mapping.label" size="small" placeholder="列名" />
          <el-select v-model="mapping.columnA" placeholder="选择列" size="small" clearable filterable>
            <el-option
              v-for="col in columnsA"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
          <el-select v-model="mapping.columnB" placeholder="选择列" size="small" clearable filterable>
            <el-option
              v-for="col in columnsB"
              :key="col"
              :label="col"
              :value="col"
            />
          </el-select>
          <el-checkbox v-model="mapping.isKey" />
          <el-checkbox v-model="mapping.enabled" />
          <el-button link type="danger" size="small" @click="removeMappingRow(idx)" :disabled="columnMappings.length <= 1">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="key-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>主键列用于匹配同一条数据；对比列决定哪些字段参与差异检测</span>
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
              :class-name="keyColumnLabels.has(col) ? 'key-col-cell' : ''"
            >
              <template #header>
                <span :style="keyColumnLabels.has(col) ? keyHeaderStyle : {}">{{ col }}</span>
              </template>
              <template #default="{ row }">
                <span :style="keyColumnLabels.has(col) ? keyHighlightStyle : {}">{{ row[col] }}</span>
              </template>
            </el-table-column>
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
              :class-name="keyColumnLabels.has(col) ? 'key-col-cell' : ''"
            >
              <template #header>
                <span :style="keyColumnLabels.has(col) ? keyHeaderStyle : {}">{{ col }}</span>
              </template>
              <template #default="{ row }">
                <span :style="keyColumnLabels.has(col) ? keyHighlightStyle : {}">{{ row[col] }}</span>
              </template>
            </el-table-column>
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
          <el-table :data="compareResult.diff" border max-height="500" style="width: 100%">
            <el-table-column
              v-for="col in diffDisplayColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              min-width="130"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <span :style="getDiffStyle(col.prop, row)">{{ row[col.prop] }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed } from 'vue'
import * as XLSX from 'xlsx'
import { ElMessage } from 'element-plus'
import {
  UploadFilled, Document, Switch, Connection, DataAnalysis,
  Warning, CircleCheck, InfoFilled, Delete, Refresh, Plus
} from '@element-plus/icons-vue'

const fileA = ref(null)
const fileB = ref(null)
const dataA = shallowRef([])
const dataB = shallowRef([])
const columnsA = ref([])
const columnsB = ref([])
const sheetsA = ref([])
const sheetsB = ref([])
const selectedSheetA = ref('')
const selectedSheetB = ref('')
const workbookA = shallowRef(null)
const workbookB = shallowRef(null)
const comparing = ref(false)
const compareResult = shallowRef(null)
const activeTab = ref('onlyA')
const columnMappings = ref([])

const displayColumns = computed(() => {
  return columnMappings.value
    .filter(m => m.columnA || m.columnB)
    .map(m => m.label)
})

const keyColumnLabels = computed(() => {
  return new Set(columnMappings.value.filter(m => m.isKey).map(m => m.label))
})

const alwaysShowLabels = computed(() => {
  const labels = new Set()
  columnMappings.value.forEach(m => {
    if (m.isKey || SKIP_COMPARE_COLUMNS.includes(m.label.trim())) {
      labels.add(m.label)
    }
  })
  return labels
})

const diffDisplayColumns = computed(() => {
  if (!compareResult.value) return []
  const allDiffLabels = new Set()
  compareResult.value.diff.forEach(row => {
    if (row._diffColumns) {
      row._diffColumns.forEach(l => allDiffLabels.add(l))
    }
  })

  const cols = []
  const pairedMappings = columnMappings.value.filter(m => m.columnA && m.columnB)
  pairedMappings.forEach(m => {
    const show = alwaysShowLabels.value.has(m.label) || allDiffLabels.has(m.label)
    if (show) {
      cols.push({ prop: `A_${m.label}`, label: `A: ${m.label}` })
      cols.push({ prop: `B_${m.label}`, label: `B: ${m.label}` })
    }
  })
  return cols
})

const canCompare = computed(() => {
  const hasKey = columnMappings.value.some(m => m.isKey && m.columnA && m.columnB)
  return dataA.value.length > 0 && dataB.value.length > 0 && hasKey
})

const SKIP_COMPARE_COLUMNS = ['序号']
const KEY_COLUMN_KEYWORDS = ['证券代码', '代码', '股票代码']

// 同义列名组：同组内的列名视为同一字段
const COLUMN_SYNONYMS = [
  ['证券代码', '代码', '股票代码'],
  ['证券简称', '名称', '股票简称'],
  ['最新公告日', '公告日期', '首次公告日', '上市公告日', '更新日期'],
  ['20日均线', '站上20日线'],
  ['国企', '国央企'],
  ['一级板块', '所属板块', '所属一级板块', '板块'],
  ['序号'],
  ['百日新高'],
]

const findSynonymMatch = (colA, colsB) => {
  if (colsB.includes(colA)) return colA
  for (const group of COLUMN_SYNONYMS) {
    if (group.includes(colA)) {
      for (const synonym of group) {
        if (colsB.includes(synonym)) return synonym
      }
    }
  }
  return ''
}

const generateMappings = () => {
  const mappings = []
  const usedB = new Set()

  columnsA.value.forEach(colA => {
    const matchedB = findSynonymMatch(colA, columnsB.value)
    if (matchedB) usedB.add(matchedB)

    const isSkipCompare = SKIP_COMPARE_COLUMNS.includes(colA.trim())
    const isKey = KEY_COLUMN_KEYWORDS.some(k => colA.includes(k))
    mappings.push({
      label: colA,
      columnA: colA,
      columnB: matchedB,
      isKey: isKey && !!matchedB,
      enabled: !isSkipCompare && !!matchedB
    })
  })

  // B文件中未匹配到的列
  columnsB.value.forEach(colB => {
    if (!usedB.has(colB)) {
      mappings.push({
        label: colB,
        columnA: '',
        columnB: colB,
        isKey: false,
        enabled: false
      })
    }
  })

  columnMappings.value = mappings

  const enabledIndices = mappings.reduce((acc, m, i) => {
    if (m.enabled) acc.push(i)
    return acc
  }, [])
  if (enabledIndices.length >= 9) {
    enabledIndices.slice(9).forEach(i => {
      mappings[i].enabled = false
    })
  }
}

const autoMatch = () => {
  generateMappings()
  ElMessage.success('已重新自动匹配列')
}

const addMappingRow = () => {
  columnMappings.value.push({
    label: '',
    columnA: '',
    columnB: '',
    isKey: false,
    enabled: true
  })
}

const removeMappingRow = (idx) => {
  columnMappings.value.splice(idx, 1)
}

const KNOWN_COLUMNS = new Set([
  '证券代码', '证券简称', '最新公告日', '公告日期', '代码', '名称',
  '百日新高', '20日均线', '站上20日线', '国企', '国央企',
  '一级板块', '所属板块', '所属一级板块', '板块',
  '首次公告日', '上市公告日', '更新日期', '受理日期', '重组类型',
  '交易概述', '序号', '股票代码', '股票简称'
])

const parseSheet = (workbook, sheetName, type) => {
  const worksheet = workbook.Sheets[sheetName]

  // 先读为二维数组，检测双行表头
  const rawData = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' })

  if (rawData.length === 0) {
    ElMessage.warning('该Sheet没有数据')
    return
  }

  let headerRowIndex = 0
  let dataStartIndex = 1

  // 查找序号=1的行（实际数据起始行），与后端 _merge_excel 逻辑一致
  const maxSearch = Math.min(10, rawData.length)
  for (let i = 1; i < maxSearch; i++) {
    const firstCell = rawData[i][0]
    try {
      if (firstCell !== '' && firstCell != null && parseInt(String(firstCell).toString().trim()) === 1) {
        // 检查上一行是否包含已知列名
        const prevRow = rawData[i - 1]
        const knownCount = prevRow.filter(cell => {
          const val = (cell ?? '').toString().trim()
          return KNOWN_COLUMNS.has(val)
        }).length

        if (knownCount >= 2) {
          headerRowIndex = i - 1
          dataStartIndex = i
        }
        break
      }
    } catch { /* ignore */ }
  }

  let jsonData
  if (headerRowIndex > 0) {
    // 双行表头：用检测到的行作为列名，空列名回退到分组行
    const headerRow = rawData[headerRowIndex]
    const groupRow = rawData[0]

    const headers = headerRow.map((h, idx) => {
      const val = (h ?? '').toString().trim()
      if (val) return val
      const groupVal = (groupRow[idx] ?? '').toString().trim()
      return groupVal || `列${idx + 1}`
    })

    // 去重列名（重复的追加 _1 后缀）
    const seen = {}
    const uniqueHeaders = headers.map(h => {
      if (h in seen) {
        seen[h]++
        return `${h}_${seen[h]}`
      }
      seen[h] = 0
      return h
    })

    jsonData = []
    for (let i = dataStartIndex; i < rawData.length; i++) {
      const row = rawData[i]
      if (row.every(cell => cell === '' || cell == null)) continue
      const obj = {}
      uniqueHeaders.forEach((header, idx) => {
        obj[header] = row[idx] ?? ''
      })
      jsonData.push(obj)
    }
  } else {
    jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' })
  }

  if (jsonData.length === 0) {
    ElMessage.warning('该Sheet没有数据')
    return
  }

  if (type === 'A') {
    dataA.value = jsonData
    columnsA.value = Object.keys(jsonData[0])
  } else {
    dataB.value = jsonData
    columnsB.value = Object.keys(jsonData[0])
  }

  if (columnsA.value.length && columnsB.value.length) {
    generateMappings()
  }
}

const handleFileChange = async (file, type) => {
  const fileRef = type === 'A' ? fileA : fileB

  fileRef.value = file.raw
  compareResult.value = null

  try {
    const data = await file.raw.arrayBuffer()
    const workbook = XLSX.read(data, { type: 'array' })

    if (type === 'A') {
      workbookA.value = workbook
      sheetsA.value = workbook.SheetNames
      selectedSheetA.value = workbook.SheetNames[0]
    } else {
      workbookB.value = workbook
      sheetsB.value = workbook.SheetNames
      selectedSheetB.value = workbook.SheetNames[0]
    }

    parseSheet(workbook, workbook.SheetNames[0], type)

    ElMessage.success(`文件${type}加载成功：${type === 'A' ? dataA.value.length : dataB.value.length}行数据`)
  } catch (error) {
    ElMessage.error('解析文件失败，请检查文件格式')
  }
}

const onSheetChange = (type) => {
  compareResult.value = null
  if (type === 'A' && workbookA.value) {
    parseSheet(workbookA.value, selectedSheetA.value, 'A')
  } else if (type === 'B' && workbookB.value) {
    parseSheet(workbookB.value, selectedSheetB.value, 'B')
  }
}

const buildKey = (row, keyMappings, file) => {
  const parts = []
  keyMappings.forEach(m => {
    const colName = file === 'A' ? m.columnA : m.columnB
    const value = (row[colName] ?? '').toString().trim()
    parts.push(value)
  })
  return parts.join('|')
}

const buildDisplayRow = (row, mappings, file) => {
  const displayRow = {}
  mappings.forEach(m => {
    const colName = file === 'A' ? m.columnA : m.columnB
    if (colName) {
      displayRow[m.label] = row[colName] ?? ''
    }
  })
  return displayRow
}

const startCompare = () => {
  comparing.value = true

  try {
    const keyMappings = columnMappings.value.filter(m => m.isKey && m.columnA && m.columnB)
    const compareMappings = columnMappings.value.filter(m => m.enabled && m.columnA && m.columnB)

    if (keyMappings.length === 0) {
      ElMessage.warning('请至少选择一个主键列（需要同时配置A和B列）')
      comparing.value = false
      return
    }

    const mapA = new Map()
    dataA.value.forEach(row => {
      const key = buildKey(row, keyMappings, 'A')
      if (key) mapA.set(key, row)
    })

    const mapB = new Map()
    dataB.value.forEach(row => {
      const key = buildKey(row, keyMappings, 'B')
      if (key) mapB.set(key, row)
    })

    const onlyA = []
    const onlyB = []
    const same = []
    const diff = []

    mapA.forEach((rowA, key) => {
      if (mapB.has(key)) {
        const rowB = mapB.get(key)
        const diffCols = []

        compareMappings.forEach(m => {
          const valA = (rowA[m.columnA] ?? '').toString().trim()
          const valB = (rowB[m.columnB] ?? '').toString().trim()
          if (valA !== valB) {
            diffCols.push(m.label)
          }
        })

        if (diffCols.length > 0) {
          const diffRow = { _diffColumns: diffCols }
          const allPaired = columnMappings.value.filter(m => m.columnA && m.columnB)
          allPaired.forEach(m => {
            diffRow[`A_${m.label}`] = (rowA[m.columnA] ?? '').toString().trim()
            diffRow[`B_${m.label}`] = (rowB[m.columnB] ?? '').toString().trim()
          })
          diff.push(diffRow)
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
    ElMessage.error('比对失败: ' + error.message)
  } finally {
    comparing.value = false
  }
}

const keyHighlightStyle = { color: '#d46b08', fontWeight: '700', background: '#fff7e6', padding: '2px 6px', borderRadius: '3px' }
const keyHeaderStyle = { color: '#fff', fontWeight: '700', background: '#fa8c16', padding: '4px 10px', borderRadius: '4px', display: 'inline-block' }

const getDiffStyle = (prop, row) => {
  if (!row._diffColumns) return {}
  const match = prop.match(/^[AB]_(.+)$/)
  if (!match) return {}
  const label = match[1]
  if (!row._diffColumns.includes(label)) return {}
  if (prop.startsWith('A_')) {
    return { color: '#cf1322', fontWeight: '700', background: '#fff1f0', padding: '2px 6px', borderRadius: '3px' }
  }
  return { color: '#389e0d', fontWeight: '700', background: '#f6ffed', padding: '2px 6px', borderRadius: '3px' }
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

.sheet-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.sheet-label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.sheet-selector .el-select {
  flex: 1;
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

.section-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.mapping-grid {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  max-height: 400px;
  overflow-y: auto;
}

.mapping-header {
  display: grid;
  grid-template-columns: 1.2fr 1.2fr 1.2fr 50px 50px 40px;
  gap: 12px;
  padding: 12px 16px;
  background: #fafafa;
  font-weight: 500;
  font-size: 13px;
  color: #666;
  position: sticky;
  top: 0;
  z-index: 1;
}

.mapping-row {
  display: grid;
  grid-template-columns: 1.2fr 1.2fr 1.2fr 50px 50px 40px;
  gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
  align-items: center;
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

:deep(.key-col-cell) {
  background-color: #fff7e6 !important;
  border-left: 2px solid #fa8c16 !important;
  border-right: 2px solid #fa8c16 !important;
}

.card-header :deep(.el-tag) {
  font-size: 24px;
  height: auto;
  padding: 4px 12px;
  line-height: 1.4;
}
</style>
