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

        <!-- 图表区域 -->
        <div class="trend-charts" v-loading="trendLoading">
          <el-card v-for="wt in allWorkflowTypes" :key="wt" class="chart-card" shadow="hover">
            <template #header>
              <div class="chart-header">
                <span class="chart-title">{{ getTypeDisplay(wt) }}</span>
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
                <el-select v-model="manualForm.workflow_type" placeholder="选择类型" style="width: 180px">
                  <el-option v-for="t in INPUT_WORKFLOW_TYPES" :key="t" :label="getTypeDisplay(t)" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="日期">
                <el-date-picker v-model="manualForm.date_str" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 150px" />
              </el-form-item>
              <el-form-item :label="`${isYearlyManual ? CURRENT_YEAR + ' ' : ''}站20日均线数量`">
                <el-input-number v-model="manualForm.count" :min="0" controls-position="right" style="width: 130px" />
              </el-form-item>
              <el-form-item :label="`${isYearlyManual ? CURRENT_YEAR + ' ' : ''}总量`">
                <el-input-number v-model="manualForm.total" :min="0" controls-position="right" style="width: 130px" />
              </el-form-item>
              <el-form-item :label="`${isYearlyManual ? CURRENT_YEAR + ' ' : ''}占比`">
                <el-tag>{{ manualForm.total > 0 ? ((manualForm.count / manualForm.total) * 100).toFixed(2) + '%' : '--' }}</el-tag>
              </el-form-item>
              <template v-if="isYearlyManual">
                <el-form-item :label="`${PREV_YEAR} 站20日均线数量`">
                  <el-input-number v-model="manualForm.count_prev" :min="0" controls-position="right" style="width: 130px" />
                </el-form-item>
                <el-form-item :label="`${PREV_YEAR} 总量`">
                  <el-input-number v-model="manualForm.total_prev" :min="0" controls-position="right" style="width: 130px" />
                </el-form-item>
                <el-form-item :label="`${PREV_YEAR} 占比`">
                  <el-tag>{{ manualForm.total_prev > 0 ? ((manualForm.count_prev / manualForm.total_prev) * 100).toFixed(2) + '%' : '--' }}</el-tag>
                </el-form-item>
              </template>
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
                <el-select v-model="uploadType" placeholder="先选择类型" style="width: 260px">
                  <el-option v-for="t in INPUT_WORKFLOW_TYPES" :key="t" :label="getTypeDisplay(t)" :value="t" />
                  <el-option label="5质押（并排双列：中大盘+小盘）" value="质押(双列并排)" />
                  <el-option label="1并购重组（并排双列：本年+上年）" value="年度(并购重组)" />
                  <el-option label="2股权转让（并排双列：本年+上年）" value="年度(股权转让)" />
                  <el-option label="9招投标（并排双列：本年+上年）" value="年度(招投标)" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <input type="file" accept=".xlsx,.xls" ref="trendFileInput" @change="handleTrendUpload" style="display:none" />
                <el-button :disabled="!uploadType" @click="$refs.trendFileInput?.click()">选择文件</el-button>
              </el-form-item>
            </el-form>
            <el-alert
              v-if="uploadType === '质押(双列并排)'"
              title="上传图中所示的并排双列格式（日期 | 中大盘数量/占比 | 小盘数量/占比）。每一日期会自动拆成中大盘和小盘两条记录。"
              type="info" :closable="false" style="margin-top: 6px;"
            />
            <el-alert
              v-else-if="isYearlyUpload"
              :title="`双行表头：Row1 含 ${CURRENT_YEAR}(或 ${CURRENT_YEAR}至今) / ${PREV_YEAR} 标签，Row2 含 占20均线数量 / 占比。每一日期会自动拆成 ${uploadParent}(${CURRENT_YEAR}) 和 ${uploadParent}(${PREV_YEAR}) 两条记录。`"
              type="info" :closable="false" style="margin-top: 6px;"
            />
            <!-- 上传预览 -->
            <div v-if="uploadPreview.length">
              <el-table :data="uploadPreview" stripe border max-height="240" size="small" style="margin-top: 8px">
                <el-table-column prop="workflow_type" label="类型" width="160"
                  v-if="uploadType === '质押(双列并排)' || isYearlyUpload" />
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

      <!-- ===== Tab 3: 百日新高总趋势 ===== -->
      <el-tab-pane label="百日新高总趋势" name="hp_trend">
        <!-- 日期区间 + 导出 -->
        <div class="trend-toolbar">
          <div class="trend-date-btns">
            <el-button-group>
              <el-button :type="hpDatePreset === 'month' ? 'primary' : ''" size="small" @click="hpSetDatePreset('month')">本月</el-button>
              <el-button :type="hpDatePreset === 'lastMonth' ? 'primary' : ''" size="small" @click="hpSetDatePreset('lastMonth')">上月</el-button>
              <el-button :type="hpDatePreset === 'year' ? 'primary' : ''" size="small" @click="hpSetDatePreset('year')">本年</el-button>
            </el-button-group>
            <el-date-picker
              v-model="hpDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              size="small"
              style="width: 260px; margin-left: 12px"
              @change="hpOnDateRangeChange"
            />
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-button size="small" type="success" @click="hpExportAll">
              <el-icon><Download /></el-icon> 导出
            </el-button>
          </div>
        </div>

        <!-- 图表区域 -->
        <div class="trend-charts" v-loading="hpTrendLoading">
          <el-card class="chart-card" shadow="hover">
            <template #header>
              <div class="chart-header">
                <span class="chart-title">11百日新高总趋势</span>
                <span style="font-size:12px;color:#909399">数量 = 当日有效股票代码行数</span>
              </div>
            </template>
            <div v-if="hpTrendData.length" class="chart-container" ref="hpChartRef"></div>
            <el-empty v-else description="暂无数据，录入或执行工作流后会自动展示" :image-size="60" />
          </el-card>
        </div>

        <el-divider content-position="left">数据管理</el-divider>

        <div class="trend-data-mgmt">
          <!-- 手动录入 -->
          <el-card shadow="never" class="mgmt-card">
            <template #header><span>手动录入</span></template>
            <el-form :model="hpManualForm" inline size="small">
              <el-form-item label="日期">
                <el-date-picker v-model="hpManualForm.date_str" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 150px" />
              </el-form-item>
              <el-form-item label="数量">
                <el-input-number v-model="hpManualForm.count" :min="0" controls-position="right" style="width: 140px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="hpSubmitManual" :loading="hpSubmitting">保存</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- Excel 上传 -->
          <el-card shadow="never" class="mgmt-card">
            <template #header><span>Excel 上传</span></template>
            <el-form inline size="small">
              <el-form-item>
                <input type="file" accept=".xlsx,.xls" ref="hpFileInput" @change="hpHandleUpload" style="display:none" />
                <el-button @click="$refs.hpFileInput?.click()">选择文件</el-button>
              </el-form-item>
            </el-form>
            <el-alert title="两列格式：日期 + 数量。空数量行自动跳过。"
              type="info" :closable="false" style="margin-top: 6px;" />
            <div v-if="hpUploadPreview.length">
              <el-table :data="hpUploadPreview" stripe border max-height="240" size="small" style="margin-top: 8px">
                <el-table-column prop="date_str" label="日期" width="140" />
                <el-table-column prop="count" label="数量" width="140" />
              </el-table>
              <div style="margin-top: 8px; display: flex; gap: 8px">
                <el-button type="primary" size="small" @click="hpConfirmUpload" :loading="hpSubmitting">确认入库 ({{ hpUploadPreview.length }}条)</el-button>
                <el-button size="small" @click="hpUploadPreview = []">取消</el-button>
              </div>
            </div>
          </el-card>
        </div>

        <!-- 已录入数据 -->
        <el-card shadow="never" style="margin-top: 16px">
          <template #header><span>已录入数据</span></template>
          <el-table :data="hpTrendData" stripe border size="small" max-height="300">
            <el-table-column prop="date_str" label="日期" width="140" sortable />
            <el-table-column prop="count" label="数量" width="140" align="center" />
            <el-table-column prop="source" label="来源" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.source === 'auto' ? 'success' : row.source === 'excel' ? 'warning' : 'info'" size="small">
                  {{ { manual: '手动', excel: 'Excel', auto: '自动' }[row.source] || row.source }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button type="danger" link size="small" @click="hpDeleteItem(row)">删除</el-button>
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
import { beijingYMD, todayBeijing } from '@/utils/dateUtils'

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
  { key: '质押', display: '5质押' },
  { key: '质押(中大盘)', display: '5质押(中大盘)' },
  { key: '质押(小盘)', display: '5质押(小盘)' },
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
    // 涨幅排名 / 质押：使用后端格式化下载（含双 sheet / 条件格式 / 列宽 / 筛选）
    const wt = previewData.value?.workflow_type
    if (wt === '涨幅排名' || wt === '质押' || wt === '条件交集') {
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
// 图表/汇总用：'质押' 是合成类型，UI 里展示为 1 个卡片双曲线
const ALL_WORKFLOW_TYPES = ['并购重组', '股权转让', '增发实现', '申报并购重组', '质押', '减持叠加质押和大宗交易', '招投标']
const PLEDGE_SUBTYPES = ['质押(中大盘)', '质押(小盘)']
// 录入/上传用：直接写入 DB 的 workflow_type 值 —— 质押必须选中大盘或小盘
const INPUT_WORKFLOW_TYPES = ['并购重组', '股权转让', '增发实现', '申报并购重组',
  '质押(中大盘)', '质押(小盘)', '减持叠加质押和大宗交易', '招投标']
// 年度父类型：录入时需要同时收集本年 + 上年
const YEARLY_PARENTS = ['并购重组', '股权转让', '招投标']
const CURRENT_YEAR = beijingYMD().year
const PREV_YEAR = CURRENT_YEAR - 1
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
  count_prev: 0,
  total_prev: 0,
})

const isYearlyManual = computed(() => YEARLY_PARENTS.includes(manualForm.workflow_type))
const isYearlyUpload = computed(() => typeof uploadType.value === 'string' && uploadType.value.startsWith('年度(') && uploadType.value.endsWith(')'))
const uploadParent = computed(() => isYearlyUpload.value ? uploadType.value.slice(3, -1) : '')

// 日期快捷
const pad2 = (n) => String(n).padStart(2, '0')
const bjDatePresetRange = (preset) => {
  const { year, month } = beijingYMD()
  const today = todayBeijing()
  if (preset === 'month') {
    return [`${year}-${pad2(month)}-01`, today]
  }
  if (preset === 'lastMonth') {
    const pY = month === 1 ? year - 1 : year
    const pM = month === 1 ? 12 : month - 1
    // 上月最后一天 = 本月 1 日 - 1 天。用 UTC 构造避免 DST：北京无 DST，等价直接减 1 天
    const lastDay = new Date(Date.UTC(year, month - 1, 0)).getUTCDate()
    return [`${pY}-${pad2(pM)}-01`, `${pY}-${pad2(pM)}-${pad2(lastDay)}`]
  }
  // year
  return [`${year}-01-01`, today]
}

const setDatePreset = (preset) => {
  datePreset.value = preset
  trendDateRange.value = bjDatePresetRange(preset)
  fetchTrendData()
}

const onDateRangeChange = () => {
  datePreset.value = ''
  fetchTrendData()
}

// 按 type 分组；质押的两个子类型合并到 "质押" key 下，附带 _source_label
// 年度父类型(并购重组/股权转让/招投标)(YYYY) 折叠到父类型下，附带 _year_label
// 旧版本裸 "质押" 记录（无来源）直接丢弃
const YEARLY_RE = /^(并购重组|股权转让|招投标)\((\d{4})\)$/
const trendByType = computed(() => {
  const map = {}
  allWorkflowTypes.value.forEach(t => { map[t] = [] })
  trendData.value.forEach(d => {
    const wt = d.workflow_type
    if (PLEDGE_SUBTYPES.includes(wt)) {
      const sub = wt === '质押(中大盘)' ? '中大盘' : '小盘'
      if (!map['质押']) map['质押'] = []
      map['质押'].push({ ...d, _source_label: sub })
      return
    }
    if (wt === '质押') return
    const ym = YEARLY_RE.exec(wt || '')
    if (ym) {
      const parent = ym[1]
      if (!map[parent]) map[parent] = []
      map[parent].push({ ...d, _year_label: ym[2] })
      return
    }
    if (!map[wt]) map[wt] = []
    map[wt].push(d)
  })
  return map
})

// 最新数据 + 环比
const latestByType = computed(() => {
  const result = {}
  for (const [wt, arr] of Object.entries(trendByType.value)) {
    if (!arr.length) continue
    // 质押：按 _source_label 分组各自取最新
    if (wt === '质押') {
      const groups = { '中大盘': [], '小盘': [] }
      arr.forEach(d => { if (groups[d._source_label]) groups[d._source_label].push(d) })
      const subLatest = {}
      for (const [sub, subArr] of Object.entries(groups)) {
        if (!subArr.length) continue
        const sorted = [...subArr].sort((a, b) => a.date_str.localeCompare(b.date_str))
        const latest = sorted[sorted.length - 1]
        let trend = ''
        if (sorted.length >= 2) {
          const prev = sorted[sorted.length - 2]
          trend = latest.ratio > prev.ratio ? 'up' : latest.ratio < prev.ratio ? 'down' : ''
        }
        subLatest[sub] = { ...latest, trend }
      }
      result[wt] = { _sub: subLatest }
      continue
    }
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

  // 质押类型：画中大盘 + 小盘双曲线
  if (wt === '质押') {
    renderPledgeChart(chart, data)
    return
  }

  // 年度父类型：画本年 + 上年双曲线
  if (YEARLY_PARENTS.includes(wt) && data.some(d => d._year_label)) {
    renderYearlyChart(chart, data)
    return
  }

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

// 质押：把中大盘 + 小盘画成双曲线（x 轴 = 所有日期并集）
const renderPledgeChart = (chart, data) => {
  const zdp = data.filter(d => d._source_label === '中大盘')
  const xp = data.filter(d => d._source_label === '小盘')

  const allDatesSet = new Set([...zdp.map(d => d.date_str), ...xp.map(d => d.date_str)])
  const allDates = [...allDatesSet].sort()

  const zdpMap = Object.fromEntries(zdp.map(d => [d.date_str, d]))
  const xpMap = Object.fromEntries(xp.map(d => [d.date_str, d]))

  const toRatio = (m, d) => m[d] ? +(m[d].ratio * 100).toFixed(2) : null
  const zdpRatios = allDates.map(d => toRatio(zdpMap, d))
  const xpRatios = allDates.map(d => toRatio(xpMap, d))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const idx = params[0].dataIndex
        const fullDate = allDates[idx] || params[0].axisValue
        let html = `<b>${fullDate}</b><br/>`
        params.forEach(p => {
          if (p.value == null) return
          html += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`
          const m = p.seriesName === '中大盘' ? zdpMap[fullDate] : xpMap[fullDate]
          if (m) html += `&nbsp;&nbsp;（站上 ${m.count} / 总量 ${m.total}）<br/>`
        })
        return html
      }
    },
    legend: { data: ['中大盘', '小盘'], top: 0 },
    grid: { left: 50, right: 50, bottom: allDates.length > 30 ? 70 : 40, top: 36 },
    xAxis: {
      type: 'category',
      data: allDates.map(d => { const p = d.split('-'); return `${+p[1]}/${+p[2]}` }),
      axisLabel: {
        rotate: allDates.length > 15 ? 45 : 0,
        fontSize: 11,
        interval: allDates.length > 60 ? Math.floor(allDates.length / 20) - 1 : allDates.length > 30 ? Math.floor(allDates.length / 15) - 1 : 'auto'
      }
    },
    dataZoom: allDates.length > 30 ? [{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }] : [],
    yAxis: [
      { type: 'value', name: '占比%', min: 0, splitNumber: 5, axisLabel: { formatter: '{value}%', fontSize: 11 } }
    ],
    series: [
      { name: '中大盘', type: 'line', data: zdpRatios, smooth: true, connectNulls: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#409EFF' },
        itemStyle: { color: '#409EFF' } },
      { name: '小盘', type: 'line', data: xpRatios, smooth: true, connectNulls: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#E6A23C' },
        itemStyle: { color: '#E6A23C' } }
    ]
  })
}

// 年度父类型：最新 2 个年份双线（例 '2026' vs '2025'）
const renderYearlyChart = (chart, data) => {
  const byYear = {}
  data.forEach(d => {
    const y = d._year_label
    if (!y) return
    if (!byYear[y]) byYear[y] = []
    byYear[y].push(d)
  })
  const years = Object.keys(byYear).sort().reverse().slice(0, 2)
  if (!years.length) return
  const [Y, Y1] = years
  const yArr = (byYear[Y] || []).slice().sort((a, b) => a.date_str.localeCompare(b.date_str))
  const y1Arr = Y1 ? (byYear[Y1] || []).slice().sort((a, b) => a.date_str.localeCompare(b.date_str)) : []

  const allDatesSet = new Set([...yArr.map(d => d.date_str), ...y1Arr.map(d => d.date_str)])
  const allDates = [...allDatesSet].sort()
  const yMap = Object.fromEntries(yArr.map(d => [d.date_str, d]))
  const y1Map = Object.fromEntries(y1Arr.map(d => [d.date_str, d]))
  const toRatio = (m, d) => m[d] ? +(m[d].ratio * 100).toFixed(2) : null
  const yRatios = allDates.map(d => toRatio(yMap, d))
  const y1Ratios = allDates.map(d => toRatio(y1Map, d))

  const legendData = Y1 ? [Y, Y1] : [Y]
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const idx = params[0].dataIndex
        const fullDate = allDates[idx] || params[0].axisValue
        let html = `<b>${fullDate}</b><br/>`
        params.forEach(p => {
          if (p.value == null) return
          html += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`
          const m = p.seriesName === Y ? yMap[fullDate] : y1Map[fullDate]
          if (m) html += `&nbsp;&nbsp;（站上 ${m.count} / 总量 ${m.total}）<br/>`
        })
        return html
      }
    },
    legend: { data: legendData, top: 0 },
    grid: { left: 50, right: 50, bottom: allDates.length > 30 ? 70 : 40, top: 36 },
    xAxis: {
      type: 'category',
      data: allDates.map(d => { const p = d.split('-'); return `${+p[1]}/${+p[2]}` }),
      axisLabel: {
        rotate: allDates.length > 15 ? 45 : 0,
        fontSize: 11,
        interval: allDates.length > 60 ? Math.floor(allDates.length / 20) - 1 : allDates.length > 30 ? Math.floor(allDates.length / 15) - 1 : 'auto'
      }
    },
    dataZoom: allDates.length > 30 ? [{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }] : [],
    yAxis: [
      { type: 'value', name: '占比%', min: 0, splitNumber: 5, axisLabel: { formatter: '{value}%', fontSize: 11 } }
    ],
    series: Y1 ? [
      { name: Y, type: 'line', data: yRatios, smooth: true, connectNulls: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#409EFF' },
        itemStyle: { color: '#409EFF' } },
      { name: Y1, type: 'line', data: y1Ratios, smooth: true, connectNulls: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#E6A23C' },
        itemStyle: { color: '#E6A23C' } }
    ] : [
      { name: Y, type: 'line', data: yRatios, smooth: true, connectNulls: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#409EFF' },
        itemStyle: { color: '#409EFF' } }
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
  if (val === 'hp_trend') {
    if (!hpDateRange.value?.length) hpSetDatePreset('year')
    else hpFetchTrendData()
  }
})

// resize
const handleResize = () => {
  Object.values(chartInstances).forEach(c => c?.resize())
  hpChartInstance?.resize()
}
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  Object.values(chartInstances).forEach(c => c?.dispose())
  hpChartInstance?.dispose()
})

// ===== 手动录入 =====
const submitManual = async () => {
  if (!manualForm.workflow_type || !manualForm.date_str) {
    ElMessage.warning('请填写工作流类型和日期'); return
  }
  const isYearly = YEARLY_PARENTS.includes(manualForm.workflow_type)
  const payloads = []
  if (isYearly) {
    if (manualForm.count > 0 && manualForm.total > 0) {
      payloads.push({
        metric_type: 'ma20',
        workflow_type: `${manualForm.workflow_type}(${CURRENT_YEAR})`,
        date_str: manualForm.date_str,
        count: manualForm.count,
        total: manualForm.total,
      })
    }
    if (manualForm.count_prev > 0 && manualForm.total_prev > 0) {
      payloads.push({
        metric_type: 'ma20',
        workflow_type: `${manualForm.workflow_type}(${PREV_YEAR})`,
        date_str: manualForm.date_str,
        count: manualForm.count_prev,
        total: manualForm.total_prev,
      })
    }
    if (!payloads.length) {
      ElMessage.warning(`请至少填一组(${CURRENT_YEAR} 或 ${PREV_YEAR})数量/总量`); return
    }
  } else {
    if (manualForm.total <= 0) { ElMessage.warning('总量必须大于0'); return }
    payloads.push({
      metric_type: 'ma20',
      workflow_type: manualForm.workflow_type,
      date_str: manualForm.date_str,
      count: manualForm.count,
      total: manualForm.total,
    })
  }
  submitting.value = true
  try {
    for (const p of payloads) {
      await api.post('/statistics/trend/trend-data/', p)
    }
    ElMessage.success(`已保存${payloads.length}条`)
    fetchTrendData()
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

// ===== 百日新高总趋势 tab =====
const hpTrendLoading = ref(false)
const hpTrendData = ref([])
const hpDatePreset = ref('year')
const hpDateRange = ref([])
const hpSubmitting = ref(false)
const hpManualForm = reactive({ date_str: '', count: 0 })
const hpUploadPreview = ref([])
const hpFileInput = ref(null)
const hpChartRef = ref(null)
let hpChartInstance = null

const hpSetDatePreset = (preset) => {
  hpDatePreset.value = preset
  hpDateRange.value = bjDatePresetRange(preset)
  hpFetchTrendData()
}

const hpOnDateRangeChange = () => {
  hpDatePreset.value = ''
  hpFetchTrendData()
}

const hpFetchTrendData = async () => {
  hpTrendLoading.value = true
  try {
    const [start, end] = hpDateRange.value || []
    const res = await api.get('/statistics/trend/trend-data/', {
      params: { metric_type: 'high_price', start_date: start, end_date: end }
    })
    if (res?.success) hpTrendData.value = res.data || []
  } catch { ElMessage.error('获取百日新高趋势数据失败') }
  finally { hpTrendLoading.value = false }
}

const hpRenderChart = async () => {
  await nextTick()
  if (!hpChartRef.value) return
  if (!hpChartInstance) {
    hpChartInstance = echarts.init(hpChartRef.value)
  }
  const data = [...hpTrendData.value].sort((a, b) => a.date_str.localeCompare(b.date_str))
  const dates = data.map(d => d.date_str)
  const counts = data.map(d => d.count)
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const idx = params[0].dataIndex
        const fullDate = dates[idx] || params[0].axisValue
        let html = `<b>${fullDate}</b><br/>`
        params.forEach(p => { html += `${p.marker} ${p.seriesName}: ${p.value}<br/>` })
        return html
      }
    },
    legend: { data: ['数量'], top: 0 },
    grid: { left: 50, right: 50, bottom: dates.length > 30 ? 70 : 40, top: 36 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates.map(d => { const p = d.split('-'); return `${+p[1]}/${+p[2]}` }),
      axisLabel: {
        rotate: dates.length > 15 ? 45 : 0,
        fontSize: 11,
        interval: dates.length > 60 ? Math.floor(dates.length / 20) - 1 : dates.length > 30 ? Math.floor(dates.length / 15) - 1 : 'auto'
      }
    },
    dataZoom: dates.length > 30 ? [{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }] : [],
    yAxis: { type: 'value', name: '数量', min: 0, minInterval: 1, splitNumber: 5, axisLabel: { fontSize: 11 } },
    series: [{
      name: '数量', type: 'line', smooth: true, data: counts,
      itemStyle: { color: '#67C23A' },
      lineStyle: { width: 2.5, color: '#67C23A' },
      symbol: 'circle', symbolSize: 6,
    }]
  }
  hpChartInstance.setOption(option, true)
}

watch(hpTrendData, () => { nextTick(() => hpRenderChart()) })

const hpSubmitManual = async () => {
  if (!hpManualForm.date_str) { ElMessage.warning('请选择日期'); return }
  if (hpManualForm.count < 0) { ElMessage.warning('数量不能为负'); return }
  hpSubmitting.value = true
  try {
    await api.post('/statistics/trend/trend-data/', {
      metric_type: 'high_price',
      workflow_type: '百日新高总趋势',
      date_str: hpManualForm.date_str,
      count: hpManualForm.count,
      total: 0,
    })
    ElMessage.success('已保存')
    hpManualForm.count = 0
    await hpFetchTrendData()
  } catch (e) { ElMessage.error('保存失败') }
  finally { hpSubmitting.value = false }
}

const hpHandleUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('workflow_type', '百日新高总趋势')
  formData.append('metric_type', 'high_price')
  try {
    const res = await api.post('/statistics/trend/trend-data/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    if (res?.success) {
      hpUploadPreview.value = res.records || []
      ElMessage.success(`解析成功，共${res.count}条`)
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  } finally {
    e.target.value = ''
  }
}

const hpConfirmUpload = async () => {
  hpSubmitting.value = true
  try {
    const res = await api.post('/statistics/trend/trend-data/batch', {
      metric_type: 'high_price', source: 'excel', records: hpUploadPreview.value
    })
    ElMessage.success(res.message || '已入库')
    hpUploadPreview.value = []
    await hpFetchTrendData()
  } catch { ElMessage.error('入库失败') }
  finally { hpSubmitting.value = false }
}

const hpDeleteItem = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.date_str} 的数据？`, '确认', { type: 'warning' })
    await api.delete(`/statistics/trend/trend-data/${row.id}`)
    ElMessage.success('已删除')
    await hpFetchTrendData()
  } catch {}
}

const hpExportAll = async () => {
  try {
    const params = new URLSearchParams({ metric_type: 'high_price' })
    if (hpDateRange.value?.[0]) params.append('start_date', hpDateRange.value[0])
    if (hpDateRange.value?.[1]) params.append('end_date', hpDateRange.value[1])
    const endDate = hpDateRange.value?.[1] || todayBeijing()
    await api.download(`/statistics/trend/trend-data/export?${params}`, `11百日新高趋势图${endDate}.xlsx`)
    ElMessage.success('已导出（含趋势图）')
  } catch { ElMessage.error('导出失败') }
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

.trend-charts { display: flex; flex-direction: column; gap: 16px; }
.chart-card { }
.chart-header { display: flex; justify-content: space-between; align-items: center; }
.chart-title { font-weight: 600; font-size: 15px; color: #303133; }
.chart-latest { color: #409eff; font-size: 13px; }
.chart-container { width: 100%; height: 280px; }

.trend-data-mgmt { display: flex; gap: 16px; flex-wrap: wrap; }
.mgmt-card { flex: 1; min-width: 400px; }
</style>
