<template>
  <div class="statistics-page">
    <div class="page-header">
      <h2>统计分析</h2>
      <p class="subtitle">查看各工作流类型的历史执行结果与趋势分析</p>
    </div>

    <el-tabs v-model="mainTab" type="border-card">
      <!-- ===== Tab 1: 执行结果 ===== -->
      <el-tab-pane label="执行结果" name="results">
        <el-card v-loading="loading" shadow="never">
          <el-tabs v-model="activeType" v-if="typeList.length">
            <el-tab-pane v-for="t in typeList" :key="t" :label="getTypeDisplay(t)" :name="t">
              <el-table :data="grouped[t] || []" stripe border style="width: 100%">
                <el-table-column prop="date_str" label="数据日期" width="130" sortable />
                <el-table-column prop="workflow_name" label="工作流名称" min-width="160" show-overflow-tooltip />
                <el-table-column prop="row_count" label="数据行数" width="100" align="center" />
                <el-table-column label="文件大小" width="100" align="center">
                  <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
                </el-table-column>
                <el-table-column prop="created_at" label="保存时间" width="180">
                  <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="160" align="center">
                  <template #default="{ row }">
                    <el-button type="primary" link size="small" @click="viewPreview(row)">查看</el-button>
                    <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
          <el-empty v-else-if="!loading" description="暂无数据，执行工作流并下载结果后会自动保存" />
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 2: 站上20日均线趋势 ===== -->
      <el-tab-pane label="站上20日均线趋势" name="trend">
        <!-- 日期区间 + 导出 -->
        <div class="trend-toolbar">
          <div class="trend-date-btns">
            <el-button-group>
              <el-button :type="datePreset === 'month' ? 'primary' : ''" size="small" @click="setDatePreset('month')">本月</el-button>
              <el-button :type="datePreset === 'lastMonth' ? 'primary' : ''" size="small" @click="setDatePreset('lastMonth')">上月</el-button>
              <el-button :type="datePreset === 'year' ? 'primary' : ''" size="small" @click="setDatePreset('year')">本年</el-button>
            </el-button-group>
            <el-date-picker
              v-model="trendDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              size="small"
              style="width: 260px; margin-left: 12px"
              @change="onDateRangeChange"
            />
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-switch v-model="dualYAxis" size="small" active-text="双Y轴" inactive-text="单Y轴" @change="renderAllCharts" />
            <el-button size="small" type="success" @click="exportAllTrend">
              <el-icon><Download /></el-icon> 导出全部
            </el-button>
          </div>
        </div>

        <!-- 汇总条 -->
        <div class="trend-summary" v-if="trendData.length">
          <div v-for="wt in allWorkflowTypes" :key="wt" class="summary-item">
            <span class="summary-type">{{ getTypeDisplay(wt) }}</span>
            <template v-if="latestByType[wt]">
              <span class="summary-ratio" :class="latestByType[wt].trend">
                {{ (latestByType[wt].ratio * 100).toFixed(2) }}%
                <span v-if="latestByType[wt].trend === 'up'">&#8593;</span>
                <span v-else-if="latestByType[wt].trend === 'down'">&#8595;</span>
              </span>
            </template>
            <span v-else class="summary-empty">--</span>
          </div>
        </div>

        <!-- 图表区域 -->
        <div class="trend-charts" v-loading="trendLoading">
          <el-card v-for="wt in allWorkflowTypes" :key="wt" class="chart-card" shadow="hover">
            <template #header>
              <div class="chart-header">
                <span class="chart-title">{{ getTypeDisplay(wt) }}</span>
                <span v-if="latestByType[wt]" class="chart-latest">
                  最新: {{ (latestByType[wt].ratio * 100).toFixed(2) }}%
                </span>
                <el-button size="small" link @click="exportSingleTrend(wt)">
                  <el-icon><Download /></el-icon> 导出
                </el-button>
              </div>
            </template>
            <div v-if="trendByType[wt]?.length" class="chart-container" :ref="el => setChartRef(wt, el)"></div>
            <el-empty v-else description="暂无数据，录入后自动展示" :image-size="60" />
          </el-card>
        </div>

        <!-- 数据管理区 -->
        <el-divider content-position="left">数据管理</el-divider>

        <div class="trend-data-mgmt">
          <!-- 手动录入 -->
          <el-card shadow="never" class="mgmt-card">
            <template #header><span>手动录入</span></template>
            <el-form :model="manualForm" inline size="small">
              <el-form-item label="工作流类型">
                <el-select v-model="manualForm.workflow_type" placeholder="选择类型" style="width: 160px">
                  <el-option v-for="t in allWorkflowTypes" :key="t" :label="getTypeDisplay(t)" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="日期">
                <el-date-picker v-model="manualForm.date_str" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 150px" />
              </el-form-item>
              <el-form-item label="站20日均线数量">
                <el-input-number v-model="manualForm.count" :min="0" controls-position="right" style="width: 130px" />
              </el-form-item>
              <el-form-item label="总量">
                <el-input-number v-model="manualForm.total" :min="0" controls-position="right" style="width: 130px" />
              </el-form-item>
              <el-form-item label="占比">
                <el-tag>{{ manualForm.total > 0 ? ((manualForm.count / manualForm.total) * 100).toFixed(2) + '%' : '--' }}</el-tag>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="submitManual" :loading="submitting">保存</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- Excel 上传 -->
          <el-card shadow="never" class="mgmt-card">
            <template #header><span>Excel 上传</span></template>
            <el-form inline size="small">
              <el-form-item label="工作流类型">
                <el-select v-model="uploadType" placeholder="先选择类型" style="width: 160px">
                  <el-option v-for="t in allWorkflowTypes" :key="t" :label="getTypeDisplay(t)" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <input type="file" accept=".xlsx,.xls" ref="trendFileInput" @change="handleTrendUpload" style="display:none" />
                <el-button :disabled="!uploadType" @click="$refs.trendFileInput?.click()">选择文件</el-button>
              </el-form-item>
            </el-form>
            <!-- 上传预览 -->
            <div v-if="uploadPreview.length">
              <el-table :data="uploadPreview" stripe border max-height="200" size="small" style="margin-top: 8px">
                <el-table-column prop="date_str" label="日期" width="120" />
                <el-table-column prop="count" label="站20均线数量" width="130" />
                <el-table-column prop="total" label="总量" width="100" />
                <el-table-column label="占比" width="100">
                  <template #default="{ row }">{{ (row.ratio * 100).toFixed(2) }}%</template>
                </el-table-column>
              </el-table>
              <div style="margin-top: 8px; display: flex; gap: 8px">
                <el-button type="primary" size="small" @click="confirmUpload" :loading="submitting">确认入库 ({{ uploadPreview.length }}条)</el-button>
                <el-button size="small" @click="uploadPreview = []">取消</el-button>
              </div>
            </div>
          </el-card>
        </div>

        <!-- 已录入数据列表 -->
        <el-card shadow="never" style="margin-top: 16px">
          <template #header><span>已录入数据</span></template>
          <el-table :data="trendData" stripe border size="small" max-height="300">
            <el-table-column prop="workflow_type" label="工作流类型" width="160" />
            <el-table-column prop="date_str" label="日期" width="120" sortable />
            <el-table-column prop="count" label="站20均线数量" width="130" align="center" />
            <el-table-column prop="total" label="总量" width="100" align="center" />
            <el-table-column label="占比" width="100" align="center">
              <template #default="{ row }">{{ (row.ratio * 100).toFixed(2) }}%</template>
            </el-table-column>
            <el-table-column prop="source" label="来源" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.source === 'auto' ? 'success' : row.source === 'excel' ? 'warning' : 'info'" size="small">
                  {{ { manual: '手动', excel: 'Excel', auto: '自动' }[row.source] || row.source }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button type="danger" link size="small" @click="deleteTrendItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 数据查看弹窗 (执行结果 tab) -->
    <el-dialog v-model="dialogVisible" :title="`${previewData?.workflow_name || ''} - ${previewData?.date_str || ''}`" width="95%" top="3vh" destroy-on-close>
      <div class="dialog-toolbar">
        <div class="toolbar-left">
          <el-tag>{{ previewData?.workflow_type || '并购重组' }}</el-tag>
          <span>共 {{ previewData?.row_count || 0 }} 行</span>
          <span v-if="isPreviewMode" class="preview-hint">（预览前 {{ previewData?.data?.length }} 行）</span>
          <el-button v-if="isPreviewMode" size="small" type="primary" link @click="loadFull" :loading="loadingFull">加载全部</el-button>
          <span v-if="hasActiveFilters" class="filter-hint">| 过滤后 {{ filteredData.length }} 行</span>
        </div>
        <div class="toolbar-right">
          <el-button v-if="hasActiveFilters" size="small" @click="clearAllFilters">清除过滤</el-button>
          <el-button size="small" type="success" @click="exportExcel" :loading="exporting">
            <el-icon><Download /></el-icon> 导出Excel
          </el-button>
        </div>
      </div>
      <div v-if="filterableCols.length" class="filter-row">
        <div v-for="col in filterableCols" :key="col" class="filter-item">
          <el-checkbox v-model="notEmptyFilters[col]" :label="col + ' 非空'" border size="small" />
        </div>
      </div>
      <el-table :data="filteredData" stripe border max-height="55vh" style="width: 100%; margin-top: 8px">
        <el-table-column v-for="col in (previewData?.columns || [])" :key="col" :prop="col" :label="col" :min-width="getColumnWidth(col)" show-overflow-tooltip sortable />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import api from '@/utils/api'

// ===== ECharts 按需引入 =====
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

// ===== 公共 =====
const mainTab = ref('results')

// 工作流类型排序 & 显示前缀
const TYPE_ORDER = [
  { key: '并购重组', display: '1并购重组' },
  { key: '股权转让', display: '2股权转让' },
  { key: '增发实现', display: '3增发实现' },
  { key: '申报并购重组', display: '4申报并购重组' },
  { key: '减持叠加质押和大宗交易', display: '6减持叠加质押和大宗交易' },
  { key: '条件交集', display: '7条件交集' },
  { key: '涨幅排名', display: '8涨幅排名' },
  { key: '招投标', display: '9招投标' },
]
const typeDisplayMap = Object.fromEntries(TYPE_ORDER.map(t => [t.key, t.display]))
const typeSortIndex = Object.fromEntries(TYPE_ORDER.map((t, i) => [t.key, i]))
const getTypeDisplay = (key) => typeDisplayMap[key] || key
const getTypeSortIdx = (key) => typeSortIndex[key] ?? 999

// ===== 执行结果 tab =====
const FILTERABLE_COLUMNS = ['百日新高', '20日均线', '站上20日线', '国企', '国央企', '一级板块', '所属板块', '所属一级板块']
const loading = ref(false)
const loadingFull = ref(false)
const exporting = ref(false)
const grouped = ref({})
const activeType = ref('')
const dialogVisible = ref(false)
const previewData = ref(null)
const currentResultId = ref(null)
const notEmptyFilters = reactive({})

const typeList = computed(() => Object.keys(grouped.value).sort((a, b) => getTypeSortIdx(a) - getTypeSortIdx(b)))
const isPreviewMode = computed(() => {
  if (!previewData.value) return false
  return (previewData.value.data?.length || 0) < (previewData.value.row_count || 0)
})
const filterableCols = computed(() => {
  const cols = previewData.value?.columns || []
  return cols.filter(c => FILTERABLE_COLUMNS.includes(c))
})
const hasActiveFilters = computed(() => Object.values(notEmptyFilters).some(v => v))
const filteredData = computed(() => {
  const data = previewData.value?.data || []
  if (!hasActiveFilters.value) return data
  return data.filter(row => {
    for (const [col, enabled] of Object.entries(notEmptyFilters)) {
      if (!enabled) continue
      if (!(row[col] ?? '').toString().trim()) return false
    }
    return true
  })
})
const clearAllFilters = () => { Object.keys(notEmptyFilters).forEach(k => { notEmptyFilters[k] = false }) }
watch(dialogVisible, v => { if (!v) clearAllFilters() })
watch(hasActiveFilters, active => { if (active && isPreviewMode.value) loadFull() })

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/statistics/results/grouped')
    if (res?.success) {
      grouped.value = res.data
      if (typeList.value.length && !activeType.value) activeType.value = typeList.value[0]
    }
  } catch { ElMessage.error('获取数据失败') }
  finally { loading.value = false }
}

const viewPreview = async (row) => {
  currentResultId.value = row.id
  try {
    const res = await api.get(`/statistics/results/${row.id}/preview`)
    if (res?.success) { previewData.value = res.data; dialogVisible.value = true }
  } catch { ElMessage.error('获取预览数据失败') }
}

const loadFull = async () => {
  if (!currentResultId.value || loadingFull.value) return
  loadingFull.value = true
  try {
    const res = await api.get(`/statistics/results/${currentResultId.value}/full`)
    if (res?.success) previewData.value = res.data
  } catch { ElMessage.error('获取完整数据失败') }
  finally { loadingFull.value = false }
}

const exportExcel = async () => {
  exporting.value = true
  try {
    // 涨幅排名使用后端格式化下载
    if (previewData.value?.workflow_type === '涨幅排名') {
      await api.download(`/statistics/results/${currentResultId.value}/download`)
      ElMessage.success('已导出（含格式化）')
      return
    }
    if (isPreviewMode.value) {
      loadingFull.value = true
      try {
        const res = await api.get(`/statistics/results/${currentResultId.value}/full`)
        if (res?.success) previewData.value = res.data
      } finally { loadingFull.value = false }
    }
    const columns = previewData.value?.columns || []
    const rows = filteredData.value
    const wsData = [columns, ...rows.map(row => columns.map(col => row[col] ?? ''))]
    const ws = XLSX.utils.aoa_to_sheet(wsData)
    ws['!cols'] = columns.map(() => ({ wch: 20 }))
    ws['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: rows.length, c: columns.length - 1 } }) }
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
    const name = previewData.value?.source_filename
      || `${previewData.value?.workflow_name || '导出'}_${previewData.value?.date_str || ''}`
    const suffix = hasActiveFilters.value ? '_filtered' : ''
    const exportName = name.endsWith('.xlsx') ? name.replace('.xlsx', `${suffix}.xlsx`) : `${name}${suffix}.xlsx`
    XLSX.writeFile(wb, exportName)
    ElMessage.success(`已导出 ${rows.length} 行数据`)
  } catch (e) { ElMessage.error('导出失败: ' + e.message) }
  finally { exporting.value = false }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.workflow_name} (${row.date_str}) 的结果？`, '确认删除', { type: 'warning' })
    const res = await api.delete(`/statistics/results/${row.id}`)
    if (res?.success) { ElMessage.success('已删除'); fetchData() }
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

// ===== 20日均线趋势 tab =====
const ALL_WORKFLOW_TYPES = ['并购重组', '股权转让', '增发实现', '申报并购重组', '减持叠加质押和大宗交易', '招投标']
const allWorkflowTypes = ref(ALL_WORKFLOW_TYPES)

const trendLoading = ref(false)
const dualYAxis = ref(false)
const trendData = ref([])
const datePreset = ref('year')
const trendDateRange = ref([])
const submitting = ref(false)
const uploadType = ref('')
const uploadPreview = ref([])
const trendFileInput = ref(null)

const manualForm = reactive({
  workflow_type: '',
  date_str: '',
  count: 0,
  total: 0,
})

// 日期快捷
const setDatePreset = (preset) => {
  datePreset.value = preset
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  const fmt = d => d.toISOString().split('T')[0]
  if (preset === 'month') {
    trendDateRange.value = [fmt(new Date(y, m, 1)), fmt(now)]
  } else if (preset === 'lastMonth') {
    trendDateRange.value = [fmt(new Date(y, m - 1, 1)), fmt(new Date(y, m, 0))]
  } else {
    trendDateRange.value = [fmt(new Date(y, 0, 1)), fmt(now)]
  }
  fetchTrendData()
}

const onDateRangeChange = () => {
  datePreset.value = ''
  fetchTrendData()
}

// 按 type 分组
const trendByType = computed(() => {
  const map = {}
  allWorkflowTypes.value.forEach(t => { map[t] = [] })
  trendData.value.forEach(d => {
    if (!map[d.workflow_type]) map[d.workflow_type] = []
    map[d.workflow_type].push(d)
  })
  return map
})

// 最新数据 + 环比
const latestByType = computed(() => {
  const result = {}
  for (const [wt, arr] of Object.entries(trendByType.value)) {
    if (!arr.length) continue
    const sorted = [...arr].sort((a, b) => a.date_str.localeCompare(b.date_str))
    const latest = sorted[sorted.length - 1]
    let trend = ''
    if (sorted.length >= 2) {
      const prev = sorted[sorted.length - 2]
      trend = latest.ratio > prev.ratio ? 'up' : latest.ratio < prev.ratio ? 'down' : ''
    }
    result[wt] = { ...latest, trend }
  }
  return result
})

const fetchTrendData = async () => {
  trendLoading.value = true
  try {
    const [start, end] = trendDateRange.value || []
    const res = await api.get('/statistics/trend/trend-data/', {
      params: { metric_type: 'ma20', start_date: start, end_date: end }
    })
    if (res?.success) trendData.value = res.data
  } catch { ElMessage.error('获取趋势数据失败') }
  finally { trendLoading.value = false }
}

// ===== ECharts 渲染 =====
const chartRefs = {}
const chartInstances = {}

const setChartRef = (wt, el) => { chartRefs[wt] = el }

const renderChart = (wt) => {
  const el = chartRefs[wt]
  const data = trendByType.value[wt] || []
  if (!el || !data.length) return

  if (chartInstances[wt]) chartInstances[wt].dispose()
  const chart = echarts.init(el)
  chartInstances[wt] = chart

  const dates = data.map(d => d.date_str)
  const counts = data.map(d => d.count)
  const ratios = data.map(d => +(d.ratio * 100).toFixed(2))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const idx = params[0].dataIndex
        const fullDate = dates[idx] || params[0].axisValue
        let html = `<b>${fullDate}</b><br/>`
        params.forEach(p => { html += `${p.marker} ${p.seriesName}: ${p.value}${p.seriesName === '占比' ? '%' : ''}<br/>` })
        const item = data[idx]
        if (item) html += `总量: ${item.total}`
        return html
      }
    },
    legend: { data: dualYAxis.value ? ['站20均线数量', '占比'] : ['占比'], top: 0 },
    grid: { left: 50, right: 50, bottom: dates.length > 30 ? 70 : 40, top: 36 },
    xAxis: {
      type: 'category',
      data: dates.map(d => { const p = d.split('-'); return `${+p[1]}/${+p[2]}` }),
      axisLabel: {
        rotate: dates.length > 15 ? 45 : 0,
        fontSize: 11,
        interval: dates.length > 60 ? Math.floor(dates.length / 20) - 1 : dates.length > 30 ? Math.floor(dates.length / 15) - 1 : 'auto'
      }
    },
    dataZoom: dates.length > 30 ? [{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }] : [],
    yAxis: dualYAxis.value
      ? [
          { type: 'value', name: '数量', position: 'left', min: 0, splitNumber: 5, axisLabel: { fontSize: 11 } },
          { type: 'value', name: '占比%', position: 'right', min: 0, max: 100, splitNumber: 5, axisLabel: { formatter: '{value}%', fontSize: 11 } }
        ]
      : [
          { type: 'value', name: '占比%', min: 0, splitNumber: 5, axisLabel: { formatter: '{value}%', fontSize: 11 } }
        ],
    series: dualYAxis.value
      ? [
          { name: '站20均线数量', type: 'bar', data: counts, itemStyle: { color: '#409EFF', borderRadius: [3, 3, 0, 0] }, barMaxWidth: 30 },
          { name: '占比', type: 'line', yAxisIndex: 1, data: ratios, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2, color: '#E6A23C' }, itemStyle: { color: '#E6A23C' } }
        ]
      : [
          { name: '占比', type: 'line', data: ratios, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2, color: '#409EFF' }, itemStyle: { color: '#409EFF' }, areaStyle: { color: 'rgba(64,158,255,0.1)' } }
        ]
  })
}

const renderAllCharts = async () => {
  await nextTick()
  allWorkflowTypes.value.forEach(wt => renderChart(wt))
}

// 日期区间 / 数据变化时重新渲染
watch(trendData, () => { nextTick(() => renderAllCharts()) })
watch(mainTab, (val) => {
  if (val === 'trend') {
    if (!trendDateRange.value?.length) setDatePreset('year')
    else fetchTrendData()
  }
})

// resize
const handleResize = () => { Object.values(chartInstances).forEach(c => c?.resize()) }
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  Object.values(chartInstances).forEach(c => c?.dispose())
})

// ===== 手动录入 =====
const submitManual = async () => {
  if (!manualForm.workflow_type || !manualForm.date_str) {
    ElMessage.warning('请填写工作流类型和日期'); return
  }
  if (manualForm.total <= 0) { ElMessage.warning('总量必须大于0'); return }
  submitting.value = true
  try {
    const res = await api.post('/statistics/trend/trend-data/', {
      metric_type: 'ma20', ...manualForm
    })
    if (res?.success) { ElMessage.success('已保存'); fetchTrendData() }
  } catch { ElMessage.error('保存失败') }
  finally { submitting.value = false }
}

// ===== Excel 上传 =====
const handleTrendUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('workflow_type', uploadType.value)
  try {
    const res = await api.post('/statistics/trend/trend-data/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    if (res?.success) uploadPreview.value = res.records
    else ElMessage.error(res?.detail || '解析失败')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  }
  e.target.value = ''
}

const confirmUpload = async () => {
  submitting.value = true
  try {
    const res = await api.post('/statistics/trend/trend-data/batch', {
      metric_type: 'ma20', source: 'excel', records: uploadPreview.value
    })
    if (res?.success) {
      ElMessage.success(res.message)
      uploadPreview.value = []
      fetchTrendData()
    }
  } catch { ElMessage.error('入库失败') }
  finally { submitting.value = false }
}

// ===== 删除 =====
const deleteTrendItem = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.workflow_type} (${row.date_str}) 的趋势数据？`, '确认', { type: 'warning' })
    const res = await api.delete(`/statistics/trend/trend-data/${row.id}`)
    if (res?.success) { ElMessage.success('已删除'); fetchTrendData() }
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

// ===== 导出 =====

const exportAllTrend = async () => {
  if (!trendData.value.length) { ElMessage.warning('暂无数据可导出'); return }
  try {
    const params = new URLSearchParams({ metric_type: 'ma20' })
    if (trendDateRange.value?.[0]) params.append('start_date', trendDateRange.value[0])
    if (trendDateRange.value?.[1]) params.append('end_date', trendDateRange.value[1])
    await api.download(`/statistics/trend/trend-data/export?${params}`, `20日均线趋势_${trendDateRange.value?.[0] || ''}_${trendDateRange.value?.[1] || ''}.xlsx`)
    ElMessage.success('已导出（含趋势图）')
  } catch (e) { ElMessage.error('导出失败') }
}

const exportSingleTrend = async (wt) => {
  const data = trendByType.value[wt] || []
  if (!data.length) { ElMessage.warning('暂无数据'); return }
  try {
    const params = new URLSearchParams({ metric_type: 'ma20', workflow_type: wt })
    if (trendDateRange.value?.[0]) params.append('start_date', trendDateRange.value[0])
    if (trendDateRange.value?.[1]) params.append('end_date', trendDateRange.value[1])
    await api.download(`/statistics/trend/trend-data/export?${params}`, `20日均线趋势_${wt}.xlsx`)
    ElMessage.success('已导出（含趋势图）')
  } catch (e) { ElMessage.error('导出失败') }
}

// ===== 工具函数 =====
const getColumnWidth = (col) => {
  if (previewData.value?.workflow_type === '涨幅排名') {
    const cols = previewData.value?.columns || []
    const idx = cols.indexOf(col)
    return (idx === 1 || idx === 2) ? 160 : 70
  }
  return 120
}
const formatSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
const formatTime = (iso) => { if (!iso) return '-'; return iso.replace('T', ' ').slice(0, 19) }
</script>

<style scoped>
.statistics-page { max-width: 1400px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; font-size: 22px; color: #303133; }
.subtitle { margin: 0; color: #909399; font-size: 14px; }

/* 执行结果 dialog */
.dialog-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 12px; font-size: 14px; color: #606266; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.preview-hint { color: #909399; font-size: 13px; }
.filter-hint { color: #e6a23c; font-weight: 500; }
.filter-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; padding: 10px 12px; background: #f5f7fa; border-radius: 6px; }
.filter-item { display: flex; align-items: center; gap: 6px; }

/* 趋势 tab */
.trend-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.trend-date-btns { display: flex; align-items: center; }

.trend-summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.summary-item { display: flex; align-items: center; gap: 6px; padding: 4px 12px; background: #fff; border-radius: 6px; font-size: 13px; }
.summary-type { color: #606266; font-weight: 500; }
.summary-ratio { font-weight: 600; }
.summary-ratio.up { color: #67c23a; }
.summary-ratio.down { color: #f56c6c; }
.summary-empty { color: #c0c4cc; }

.trend-charts { display: flex; flex-direction: column; gap: 16px; }
.chart-card { }
.chart-header { display: flex; justify-content: space-between; align-items: center; }
.chart-title { font-weight: 600; font-size: 15px; color: #303133; }
.chart-latest { color: #409eff; font-size: 13px; }
.chart-container { width: 100%; height: 280px; }

.trend-data-mgmt { display: flex; gap: 16px; flex-wrap: wrap; }
.mgmt-card { flex: 1; min-width: 400px; }
</style>
