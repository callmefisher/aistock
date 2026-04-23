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

      <!-- ===== Tab 3: 板块涨幅分析 ===== -->
      <el-tab-pane label="板块涨幅分析" name="ranking">
        <div v-loading="rankingLoading">
          <!-- 数据选择器 -->
          <div class="ranking-toolbar">
            <el-select v-model="rankingResultId" placeholder="选择数据" @change="loadRankingById" size="small" style="width: 340px">
              <el-option v-for="item in rankingAvailable" :key="item.id"
                :label="`${item.date_str} - ${item.workflow_name}`" :value="item.id" />
            </el-select>
            <span v-if="rankingParsed" class="ranking-hint">{{ rankingParsed.sectors.length }} 个板块 / {{ rankingParsed.dateCols.length }} 个交易日</span>
          </div>

          <template v-if="rankingParsed">
            <!-- 概览卡片 -->
            <div class="ranking-overview">
              <div class="ov-card">
                <div class="ov-title">当前 Top5 ({{ rankingParsed.dateCols[0] || '' }})</div>
                <div class="ov-items">
                  <span v-for="(s, i) in rankingTop5Now" :key="s" class="ov-tag ov-up">#{{ i + 1 }} {{ s }}</span>
                </div>
              </div>
              <div class="ov-card">
                <div class="ov-title">Top5 变动 (vs {{ rankingParsed.dateCols.length > 1 ? rankingParsed.dateCols[1] : '--' }})</div>
                <div class="ov-items">
                  <span v-for="s in rankingNewIn" :key="'in-'+s" class="ov-tag ov-new-in">+ {{ s }} &#8593;</span>
                  <span v-for="s in rankingNewOut" :key="'out-'+s" class="ov-tag ov-new-out">- {{ s }} &#8595;</span>
                  <span v-if="!rankingNewIn.length && !rankingNewOut.length" style="color:#909399;font-size:13px">无变动</span>
                </div>
              </div>
              <div class="ov-card">
                <div class="ov-title">今日排名变化最大</div>
                <div class="ov-items">
                  <span v-for="c in rankingBigMovers.up" :key="'bu-'+c.name" class="ov-tag ov-new-in">{{ c.name }} &#8593;{{ c.change }}</span>
                  <span v-for="c in rankingBigMovers.down" :key="'bd-'+c.name" class="ov-tag ov-new-out">{{ c.name }} &#8595;{{ Math.abs(c.change) }}</span>
                </div>
              </div>
            </div>

            <!-- Top5频率统计 -->
            <el-card shadow="hover" class="ranking-section">
              <template #header>
                <div class="chart-header">
                  <span class="chart-title">Top5 进入频率统计</span>
                  <span style="font-size:13px;color:#909399">按"迄今为止排进前5(次数)"降序</span>
                </div>
              </template>
              <div ref="rkTop5ChartRef" class="ranking-chart" style="height:420px"></div>
            </el-card>

            <!-- 板块排名趋势 -->
            <el-card shadow="hover" class="ranking-section">
              <template #header>
                <div class="chart-header">
                  <span class="chart-title">板块排名趋势</span>
                  <div style="display:flex;align-items:center;gap:8px">
                    <el-select v-model="rkSelectedSectors" multiple filterable collapse-tags collapse-tags-tooltip
                      placeholder="搜索添加板块" size="small" style="width:360px" @change="renderRkTrendChart">
                      <el-option v-for="s in rankingParsed.sectors" :key="s" :label="s" :value="s" />
                    </el-select>
                  </div>
                </div>
              </template>
              <div ref="rkTrendChartRef" class="ranking-chart" style="height:400px"></div>
            </el-card>

            <!-- 板块动量排行 -->
            <el-card shadow="hover" class="ranking-section">
              <template #header>
                <div class="chart-header">
                  <span class="chart-title">板块动量排行</span>
                  <span style="font-size:13px;color:#909399">近5日排名变化加权平均 | 正值=排名上升(变好)</span>
                </div>
              </template>
              <div class="momentum-grid">
                <div>
                  <div style="font-size:13px;color:#67c23a;font-weight:600;margin-bottom:8px">排名上升最快 Top10</div>
                  <div v-for="m in rankingMomentum.up" :key="'mu-'+m.name" class="momentum-item">
                    <div>
                      <div class="momentum-name">{{ m.name }}</div>
                      <div class="momentum-bar" :style="{ width: (m.score / rankingMomentum.maxUp * 120) + 'px', background: '#67c23a' }"></div>
                    </div>
                    <div class="momentum-detail">
                      <span class="momentum-change positive">+{{ m.score }} &#8593;</span>
                      <span class="momentum-rank">#{{ m.currentRank }} (前日 #{{ m.prevRank }})</span>
                    </div>
                  </div>
                </div>
                <div>
                  <div style="font-size:13px;color:#f56c6c;font-weight:600;margin-bottom:8px">排名下降最快 Top10</div>
                  <div v-for="m in rankingMomentum.down" :key="'md-'+m.name" class="momentum-item">
                    <div>
                      <div class="momentum-name">{{ m.name }}</div>
                      <div class="momentum-bar" :style="{ width: (Math.abs(m.score) / rankingMomentum.maxDown * 120) + 'px', background: '#f56c6c' }"></div>
                    </div>
                    <div class="momentum-detail">
                      <span class="momentum-change negative">{{ m.score }} &#8595;</span>
                      <span class="momentum-rank">#{{ m.currentRank }} (前日 #{{ m.prevRank }})</span>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>

            <!-- 排名热力矩阵 -->
            <el-card shadow="hover" class="ranking-section">
              <template #header>
                <div class="chart-header">
                  <span class="chart-title">板块排名矩阵</span>
                  <el-radio-group v-model="rkHeatmapTopN" size="small">
                    <el-radio-button :value="10">Top 10</el-radio-button>
                    <el-radio-button :value="20">Top 20</el-radio-button>
                    <el-radio-button :value="50">Top 50</el-radio-button>
                    <el-radio-button :value="0">全部</el-radio-button>
                  </el-radio-group>
                </div>
              </template>
              <div class="heatmap-legend">
                <span class="hl-item"><span class="hl-dot" style="background:#c00000"></span> 排名 1-5</span>
                <span class="hl-item"><span class="hl-dot" style="background:#ff9800"></span> 排名 6-10</span>
                <span class="hl-item"><span class="hl-dot" style="background:#fff3e0;border:1px solid #e65100"></span> 排名 11-20</span>
                <span class="hl-item"><span class="hl-dot" style="background:#ff0000"></span> 排名提升(最新日)</span>
                <span class="hl-item"><span class="hl-dot" style="background:#fafafa;border:1px solid #ddd"></span> 其他</span>
              </div>
              <div class="heatmap-scroll">
                <table class="heatmap-table">
                  <thead>
                    <tr>
                      <th style="min-width:100px">板块名称</th>
                      <th>Top5次数</th>
                      <th v-for="d in rankingParsed.dateCols" :key="d">{{ d }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in rkHeatmapRows" :key="row.name">
                      <td class="hm-name">{{ row.name }}</td>
                      <td style="font-weight:600">{{ row.top5 }}</td>
                      <td v-for="(rank, di) in row.ranks" :key="di" :class="getHeatmapClass(rank, di, row.ranks)">
                        {{ rank || '' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </el-card>
          </template>

          <el-empty v-else-if="!rankingLoading" description="暂无涨幅排名数据，请先执行涨幅排名工作流" />
        </div>
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
    if (wt === '涨幅排名' || wt === '质押') {
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
const CURRENT_YEAR = new Date().getFullYear()
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
  if (val === 'ranking' && !rankingData.value) fetchRankingAnalysis()
})

// resize
const handleResize = () => {
  Object.values(chartInstances).forEach(c => c?.resize())
  Object.values(rkChartInstances).forEach(c => c?.resize())
}
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  Object.values(chartInstances).forEach(c => c?.dispose())
  Object.values(rkChartInstances).forEach(c => c?.dispose())
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

// ===== 板块涨幅分析 tab =====
const rankingLoading = ref(false)
const rankingData = ref(null)
const rankingAvailable = ref([])
const rankingResultId = ref(null)
const rkSelectedSectors = ref([])
const rkHeatmapTopN = ref(20)
const rkTop5ChartRef = ref(null)
const rkTrendChartRef = ref(null)
const rkChartInstances = {}

const RANK_COLORS = ['#c00000', '#409eff', '#67c23a', '#e6a23c', '#9c27b0', '#00bcd4', '#ff5722', '#795548', '#607d8b', '#e91e63']

// 解析排名数据
const rankingParsed = computed(() => {
  if (!rankingData.value) return null
  const cols = rankingData.value.columns || []
  const data = rankingData.value.data || []
  if (cols.length < 4) return null
  // cols[0]=板块名称, cols[1]=排序列, cols[2]=Top5次数, cols[3+]=日期列
  // 数据中日期列已是降序（最新在前：4月15日, 4月14日, ...）
  const dateCols = cols.slice(3)
  const sectorCol = cols[0]
  const top5Col = cols[2]
  const sectors = data.map(r => r[sectorCol]).filter(Boolean)
  return { cols, dateCols, sectors, sectorCol, top5Col, data }
})

// 获取某板块在某日期列的排名
const getRank = (row, dateCol) => {
  const v = row[dateCol]
  if (v === '' || v === null || v === undefined) return null
  const n = parseInt(v)
  return isNaN(n) ? null : n
}

// 当前Top5
const rankingTop5Now = computed(() => {
  if (!rankingParsed.value) return []
  const { data, sectorCol, dateCols } = rankingParsed.value
  if (!dateCols.length) return []
  const latestCol = dateCols[0]
  return [...data]
    .filter(r => getRank(r, latestCol) !== null)
    .sort((a, b) => getRank(a, latestCol) - getRank(b, latestCol))
    .slice(0, 5)
    .map(r => r[sectorCol])
})

// Top5变动
const rankingNewIn = computed(() => {
  if (!rankingParsed.value || rankingParsed.value.dateCols.length < 2) return []
  const { data, sectorCol, dateCols } = rankingParsed.value
  const col0 = dateCols[0], col1 = dateCols[1]
  const top5Now = new Set([...data].filter(r => { const rk = getRank(r, col0); return rk !== null && rk <= 5 }).map(r => r[sectorCol]))
  const top5Prev = new Set([...data].filter(r => { const rk = getRank(r, col1); return rk !== null && rk <= 5 }).map(r => r[sectorCol]))
  return [...top5Now].filter(s => !top5Prev.has(s))
})
const rankingNewOut = computed(() => {
  if (!rankingParsed.value || rankingParsed.value.dateCols.length < 2) return []
  const { data, sectorCol, dateCols } = rankingParsed.value
  const col0 = dateCols[0], col1 = dateCols[1]
  const top5Now = new Set([...data].filter(r => { const rk = getRank(r, col0); return rk !== null && rk <= 5 }).map(r => r[sectorCol]))
  const top5Prev = new Set([...data].filter(r => { const rk = getRank(r, col1); return rk !== null && rk <= 5 }).map(r => r[sectorCol]))
  return [...top5Prev].filter(s => !top5Now.has(s))
})

// 今日排名变化最大
const rankingBigMovers = computed(() => {
  if (!rankingParsed.value || rankingParsed.value.dateCols.length < 2) return { up: [], down: [] }
  const { data, sectorCol, dateCols } = rankingParsed.value
  const col0 = dateCols[0], col1 = dateCols[1]
  const changes = data.map(r => {
    const now = getRank(r, col0), prev = getRank(r, col1)
    if (now === null || prev === null) return null
    return { name: r[sectorCol], change: prev - now }
  }).filter(Boolean)
  const up = changes.filter(c => c.change > 0).sort((a, b) => b.change - a.change).slice(0, 5)
  const down = changes.filter(c => c.change < 0).sort((a, b) => a.change - b.change).slice(0, 5)
  return { up, down }
})

// 动量排行
const rankingMomentum = computed(() => {
  if (!rankingParsed.value) return { up: [], down: [], maxUp: 1, maxDown: 1 }
  const { data, sectorCol, dateCols } = rankingParsed.value
  const weights = [5, 4, 3, 2, 1]
  const momentums = data.map(r => {
    let score = 0, totalW = 0
    for (let i = 0; i < Math.min(5, dateCols.length - 1); i++) {
      const now = getRank(r, dateCols[i]), prev = getRank(r, dateCols[i + 1])
      if (now !== null && prev !== null) {
        score += (prev - now) * weights[i]
        totalW += weights[i]
      }
    }
    const currentRank = getRank(r, dateCols[0]) ?? '?'
    const prevRank = dateCols.length > 1 ? (getRank(r, dateCols[1]) ?? '?') : '?'
    return { name: r[sectorCol], score: totalW > 0 ? +(score / totalW).toFixed(1) : 0, currentRank, prevRank }
  })
  const up = momentums.filter(m => m.score > 0).sort((a, b) => b.score - a.score).slice(0, 10)
  const down = momentums.filter(m => m.score < 0).sort((a, b) => a.score - b.score).slice(0, 10)
  return { up, down, maxUp: up[0]?.score || 1, maxDown: Math.abs(down[0]?.score || -1) }
})

// 热力矩阵行
const rkHeatmapRows = computed(() => {
  if (!rankingParsed.value) return []
  const { data, sectorCol, top5Col, dateCols } = rankingParsed.value
  const sorted = [...data].sort((a, b) => {
    const ra = getRank(a, dateCols[0]) ?? 9999
    const rb = getRank(b, dateCols[0]) ?? 9999
    return ra - rb
  })
  const display = rkHeatmapTopN.value > 0 ? sorted.slice(0, rkHeatmapTopN.value) : sorted
  return display.map(r => ({
    name: r[sectorCol],
    top5: r[top5Col] ?? 0,
    ranks: dateCols.map(d => getRank(r, d))
  }))
})

const getHeatmapClass = (rank, di, ranks) => {
  if (rank === null) return 'hm-other'
  if (rank <= 5) return 'hm-top5'
  // 最新日(di=0) 排名提升
  if (di === 0 && ranks.length > 1 && ranks[1] !== null && rank < ranks[1]) return 'hm-improve'
  if (rank <= 10) return 'hm-top10'
  if (rank <= 20) return 'hm-top20'
  return 'hm-other'
}

// 数据加载
const fetchRankingAnalysis = async (resultId) => {
  rankingLoading.value = true
  try {
    const params = resultId ? { result_id: resultId } : {}
    const res = await api.get('/statistics/results/ranking-analysis', { params })
    if (res?.success) {
      rankingAvailable.value = res.available || []
      if (res.data) {
        rankingData.value = res.data
        if (!rankingResultId.value && rankingAvailable.value.length) {
          rankingResultId.value = rankingAvailable.value[0].id
        }
        await nextTick()
        rkSelectedSectors.value = [...rankingTop5Now.value]
        await nextTick()
        renderRkTop5Chart()
        renderRkTrendChart()
      }
    }
  } catch { ElMessage.error('获取涨幅排名数据失败') }
  finally { rankingLoading.value = false }
}

const loadRankingById = () => fetchRankingAnalysis(rankingResultId.value)

// Top5 频率横向柱状图
const renderRkTop5Chart = () => {
  const el = rkTop5ChartRef.value
  if (!el || !rankingParsed.value) return
  if (rkChartInstances.top5) rkChartInstances.top5.dispose()
  const chart = echarts.init(el)
  rkChartInstances.top5 = chart

  const { data, sectorCol, top5Col } = rankingParsed.value
  const items = data
    .map(r => ({ name: r[sectorCol], count: parseInt(r[top5Col]) || 0 }))
    .filter(i => i.count > 0)
    .sort((a, b) => a.count - b.count)
  const threshold = items.length >= 5 ? items[items.length - 5].count : 0

  // 相同次数只在最后一个柱子显示标签
  const lastIndexByCount = {}
  items.forEach((item, idx) => { lastIndexByCount[item.count] = idx })

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 50, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '次数', minInterval: 1, axisLabel: { fontSize: 12 } },
    yAxis: { type: 'category', data: items.map(i => i.name), axisLabel: { fontSize: 12 } },
    series: [{
      type: 'bar',
      data: items.map((item, idx) => ({
        value: item.count,
        itemStyle: { color: item.count >= threshold ? '#c00000' : '#409eff', borderRadius: [0, 4, 4, 0] }
      })),
      barMaxWidth: 24,
      label: {
        show: true, position: 'right', fontSize: 12, color: '#606266',
        formatter: (params) => lastIndexByCount[params.value] === params.dataIndex ? params.value : ''
      }
    }]
  })
}

// 排名趋势折线图
const renderRkTrendChart = () => {
  const el = rkTrendChartRef.value
  if (!el || !rankingParsed.value) return
  if (rkChartInstances.trend) rkChartInstances.trend.dispose()
  const chart = echarts.init(el)
  rkChartInstances.trend = chart

  const { data, sectorCol, dateCols } = rankingParsed.value
  // X轴时间正序（旧→新，左→右）
  const xDates = [...dateCols].reverse()
  const dataMap = {}
  data.forEach(r => { dataMap[r[sectorCol]] = r })

  // 动态计算Y轴上限：基于选中板块的实际最大排名
  let maxRank = 10
  rkSelectedSectors.value.forEach(s => {
    const row = dataMap[s]
    if (!row) return
    xDates.forEach(d => {
      const r = getRank(row, d)
      if (r !== null && r > maxRank) maxRank = r
    })
  })
  maxRank = Math.min(maxRank + 5, data.length)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = `<b>${params[0].axisValue}</b><br/>`
        params.sort((a, b) => (a.value ?? 999) - (b.value ?? 999))
        params.forEach(p => {
          if (p.value != null) html += `${p.marker} ${p.seriesName}: 第${p.value}名<br/>`
        })
        return html
      }
    },
    legend: { data: rkSelectedSectors.value, top: 0 },
    grid: { left: 50, right: 30, top: 40, bottom: 80 },
    xAxis: {
      type: 'category', data: xDates, boundaryGap: false,
      axisLabel: {
        fontSize: 11, rotate: 45,
        interval: xDates.length > 30 ? Math.floor(xDates.length / 20) - 1 : 'auto'
      }
    },
    yAxis: {
      type: 'value', name: '排名', inverse: true, min: 1, max: maxRank,
      axisLabel: { fontSize: 12, formatter: '第{value}' },
      splitLine: { lineStyle: { type: 'dashed' } }
    },
    dataZoom: [{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }],
    series: rkSelectedSectors.value.map((s, i) => {
      const row = dataMap[s]
      const values = xDates.map(d => row ? getRank(row, d) : null)
      return {
        name: s, type: 'line', data: values, smooth: true, symbol: 'circle', symbolSize: 8,
        connectNulls: true,
        lineStyle: { width: 2.5, color: RANK_COLORS[i % RANK_COLORS.length] },
        itemStyle: { color: RANK_COLORS[i % RANK_COLORS.length] },
        emphasis: { lineStyle: { width: 4 } }
      }
    })
  })
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

/* 板块涨幅分析 tab */
.ranking-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.ranking-hint { font-size: 13px; color: #909399; }
.ranking-section { margin-bottom: 16px; }
.ranking-chart { width: 100%; }

.ranking-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-bottom: 16px; }
.ov-card { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.ov-title { font-size: 13px; color: #909399; margin-bottom: 10px; font-weight: 500; }
.ov-items { display: flex; flex-wrap: wrap; gap: 6px; }
.ov-tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 4px; font-size: 13px; font-weight: 500; }
.ov-up { background: #fef0f0; color: #c00000; }
.ov-new-in { background: #f0f9eb; color: #67c23a; border: 1px solid #e1f3d8; }
.ov-new-out { background: #fef0f0; color: #f56c6c; border: 1px solid #fde2e2; }

.momentum-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .momentum-grid { grid-template-columns: 1fr; } }
.momentum-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid #f2f3f5; }
.momentum-item:last-child { border-bottom: none; }
.momentum-name { font-size: 13px; font-weight: 500; }
.momentum-bar { height: 6px; border-radius: 3px; margin-top: 2px; }
.momentum-detail { display: flex; flex-direction: column; align-items: flex-end; }
.momentum-change { font-size: 13px; font-weight: 600; }
.momentum-change.positive { color: #67c23a; }
.momentum-change.negative { color: #f56c6c; }
.momentum-rank { font-size: 11px; color: #909399; }

.heatmap-legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #606266; margin-bottom: 12px; }
.hl-item { display: flex; align-items: center; gap: 4px; }
.hl-dot { width: 14px; height: 14px; border-radius: 2px; display: inline-block; }
.heatmap-scroll { max-height: 520px; overflow: auto; }
.heatmap-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.heatmap-table th, .heatmap-table td { padding: 6px 4px; text-align: center; border: 1px solid #ebeef5; white-space: nowrap; }
.heatmap-table th { background: #f5f7fa; font-weight: 600; position: sticky; top: 0; z-index: 1; }
.hm-name { position: sticky; left: 0; background: #fff; font-weight: 500; z-index: 1; text-align: left !important; padding-left: 8px !important; min-width: 100px; }
.hm-top5 { background: #c00000; color: #fff; font-weight: 700; }
.hm-top10 { background: #ff9800; color: #fff; font-weight: 600; }
.hm-top20 { background: #fff3e0; color: #e65100; }
.hm-improve { background: #ff0000; color: #fff; font-weight: 600; }
.hm-other { background: #fafafa; color: #c0c4cc; }
</style>
