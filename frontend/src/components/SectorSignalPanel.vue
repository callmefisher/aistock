<template>
  <el-card shadow="hover" class="sector-signal-panel" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">板块信号榜</span>
        <div class="panel-controls">
          <el-select v-model="topN" size="small" style="width: 100px">
            <el-option :value="10" label="Top 10" />
            <el-option :value="20" label="Top 20" />
            <el-option :value="30" label="Top 30" />
          </el-select>
          <el-button size="small" :icon="Refresh" @click="refresh" :loading="refreshing">强制重算</el-button>
          <span v-if="meta" class="panel-meta">
            {{ meta.date }} · {{ meta.sector_count }} 板块 · 长窗 {{ meta.window_long_days }} 日
          </span>
        </div>
      </div>
    </template>

    <el-alert v-if="errorMsg" type="error" :closable="false" show-icon>
      {{ errorMsg }}
    </el-alert>

    <el-row :gutter="16" v-if="!errorMsg">
      <el-col :span="12">
        <div class="board-title">持续强势榜</div>
        <el-table :data="strongSlice" size="small" border stripe empty-text="暂无数据">
          <el-table-column label="#" type="index" width="40" />
          <el-table-column prop="sector" label="板块" min-width="100" />
          <el-table-column prop="strong_score" label="强势分" width="80" sortable>
            <template #default="{ row }">
              <el-tooltip placement="top">
                <template #content>
                  <div>子分：</div>
                  <div v-for="(v, k) in row.sub_scores" :key="k">{{ k }}: {{ v }}</div>
                </template>
                <strong>{{ row.strong_score }}</strong>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="today_pct" label="当日%" width="70">
            <template #default="{ row }">{{ fmtPct(row.today_pct) }}</template>
          </el-table-column>
          <el-table-column prop="recent_avg_rank" label="5日均排名" width="90" />
          <el-table-column prop="long_avg_rank" label="20日均排名" width="90" />
          <el-table-column prop="top20_count" label="进前20(次)" width="100" />
        </el-table>
      </el-col>

      <el-col :span="12">
        <div class="board-title">低位启动榜</div>
        <el-table :data="reversalSlice" size="small" border stripe empty-text="暂无数据">
          <el-table-column label="#" type="index" width="40" />
          <el-table-column prop="sector" label="板块" min-width="100" />
          <el-table-column prop="reversal_score" label="反转分" width="80" sortable>
            <template #default="{ row }">
              <el-tooltip placement="top">
                <template #content>
                  <div>子分：</div>
                  <div v-for="(v, k) in row.sub_scores" :key="k">{{ k }}: {{ v }}</div>
                </template>
                <strong>{{ row.reversal_score }}</strong>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="today_pct" label="当日%" width="70">
            <template #default="{ row }">{{ fmtPct(row.today_pct) }}</template>
          </el-table-column>
          <el-table-column prop="ytd_pct" label="年初%" width="80">
            <template #default="{ row }">{{ fmtPct(row.ytd_pct) }}</template>
          </el-table-column>
          <el-table-column prop="recent_avg_rank" label="5日均排名" width="90" />
          <el-table-column prop="early_avg_rank" label="前半段均排名" width="110" />
          <el-table-column prop="first_enter_top20_date" label="首入前20" width="100" />
        </el-table>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import api from '@/utils/api'

const props = defineProps({
  date: { type: String, default: null },
})

const topN = ref(10)
const loading = ref(false)
const refreshing = ref(false)
const errorMsg = ref('')
const payload = ref(null)

const meta = computed(() => payload.value && {
  date: payload.value.date,
  sector_count: payload.value.sector_count,
  window_long_days: payload.value.window_long_days,
})

const strongSlice = computed(() => (payload.value?.top_strong || []).slice(0, topN.value))
const reversalSlice = computed(() => (payload.value?.top_reversal || []).slice(0, topN.value))

function fmtPct(v) {
  if (v === null || v === undefined) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = { top_n: 30 }
    if (props.date) params.date = props.date
    // api interceptor 已解包 response.data → 返回值即 payload
    payload.value = await api.get('/sector-signal/', { params })
  } catch (e) {
    const detail = e.response?.data?.detail
    errorMsg.value = (typeof detail === 'object' ? detail?.message : detail) || '加载失败'
    payload.value = null
  } finally {
    loading.value = false
  }
}

async function refresh() {
  if (!payload.value?.date && !props.date) return
  refreshing.value = true
  try {
    await api.post('/sector-signal/recompute', {
      date: props.date || payload.value.date,
    })
    await load()
  } catch (e) {
    const detail = e.response?.data?.detail
    errorMsg.value = (typeof detail === 'object' ? detail?.message : detail) || '重算失败'
  } finally {
    refreshing.value = false
  }
}

watch(() => props.date, load)
onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped>
.sector-signal-panel { margin-bottom: 16px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-title { font-weight: 600; font-size: 15px; }
.panel-controls { display: flex; gap: 8px; align-items: center; }
.panel-meta { color: #909399; font-size: 12px; margin-left: 8px; }
.board-title { font-weight: 600; margin-bottom: 8px; color: #303133; }
</style>
