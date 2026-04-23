// 所有"今天/日期"在前端一律按北京时间 (Asia/Shanghai) 生成，避免
// toISOString() 把本地 0:00 当作 UTC 减 8 小时导致日期回退 1 天。

const BJ_TZ = 'Asia/Shanghai'

export function todayBeijing() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: BJ_TZ })
}

// 返回北京时区下当前时刻的 {year, month(1-12), day}。
// 用 Intl.DateTimeFormat 而非 getFullYear/getMonth（后者按浏览器本地时区解读时间戳）。
export function beijingYMD(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BJ_TZ,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date).reduce((a, p) => { a[p.type] = p.value; return a }, {})
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
  }
}

export function formatBeijingDate(date) {
  return new Date(date).toLocaleDateString('sv-SE', { timeZone: BJ_TZ })
}

export function formatBeijingTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z')
  if (isNaN(d.getTime())) return '-'
  const parts = new Intl.DateTimeFormat('sv-SE', {
    timeZone: BJ_TZ,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).formatToParts(d).reduce((acc, p) => { acc[p.type] = p.value; return acc }, {})
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
}
