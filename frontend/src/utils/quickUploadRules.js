const ACCEPT_EXTS = ['.xlsx', '.xls']

// Files that should be silently ignored (hidden, OS metadata, Office lock files).
// These are filtered out BEFORE counting, so the user sees a clean "已选 N 个 / 过滤 K 个非 Excel"
// without .DS_Store / Thumbs.db / ~$temp inflating the "过滤" count.
export function isSilentlyIgnored(filename) {
  if (!filename) return true
  if (filename.startsWith('.')) return true
  if (filename.startsWith('~$')) return true
  const lower = filename.toLowerCase()
  if (lower === 'thumbs.db' || lower === 'desktop.ini') return true
  return false
}

export function isAcceptableFile(filename) {
  if (!filename) return false
  if (isSilentlyIgnored(filename)) return false
  const lower = filename.toLowerCase()
  return ACCEPT_EXTS.some(ext => lower.endsWith(ext))
}

const SUBDIR_KEYWORDS = [
  { keywords: ['百日新高'], step_type: 'match_high_price', sub_dir: '百日新高' },
  { keywords: ['20日均线', '20日线'], step_type: 'match_ma20', sub_dir: '20日均线' },
  { keywords: ['国央企'], step_type: 'match_soe', sub_dir: '国企' },
  { keywords: ['板块'], step_type: 'match_sector', sub_dir: '一级板块' },
]

const PREFIX_TO_TYPE = {
  '1': '并购重组',
  '2': '股权转让',
  '3': '增发实现',
  '4': '申报并购重组',
  '5': '质押',
  '6': '减持叠加质押和大宗交易',
  '8': '涨幅排名',
  '9': '招投标',
}

const WORKFLOW_TYPE_TO_BASE = {
  '并购重组': '',
  '股权转让': '股权转让',
  '增发实现': '增发实现',
  '申报并购重组': '申报并购重组',
  '质押': '质押',
  '减持叠加质押和大宗交易': '减持叠加质押和大宗交易',
  '涨幅排名': '涨幅排名',
  '招投标': '招投标',
}

function stripExt(name) {
  const idx = name.lastIndexOf('.')
  return idx > 0 ? name.slice(0, idx) : name
}

function buildTargetDir(workflow_type, sub_dir, date_str) {
  const base = WORKFLOW_TYPE_TO_BASE[workflow_type]
  const d = date_str || '{date}'
  const parts = ['data/excel']
  if (base) parts.push(base)
  parts.push(d)
  if (sub_dir) parts.push(sub_dir)
  return parts.join('/') + '/'
}

export function resolveTarget(filename, date_str = '{date}') {
  if (!filename) {
    return {
      filename,
      workflow_type: null,
      step_type: null,
      sub_dir: null,
      target_dir: '',
      status: 'unresolved',
      reason: '文件名为空',
    }
  }
  const base = stripExt(filename)
  const first = base.charAt(0)

  // 例外：8 开头 + 含"涨跌幅"视为"涨幅排名"，绕过"板块"等子目录关键字
  // (e.g. `8、板块涨跌幅排名 0422.xlsx` 应落入 data/excel/涨幅排名/{date}/，
  //  而不是 data/excel/{date}/一级板块/)
  if (first === '8' && base.includes('涨跌幅')) {
    const wt = PREFIX_TO_TYPE['8']
    return {
      filename,
      workflow_type: wt,
      step_type: 'merge_excel',
      sub_dir: null,
      target_dir: buildTargetDir(wt, null, date_str),
      status: 'resolved',
      reason: `首位数字 "8" + 含"涨跌幅" → ${wt}`,
    }
  }

  // 优先级 1: 子目录关键字
  for (const { keywords, step_type, sub_dir } of SUBDIR_KEYWORDS) {
    const matchedKeyword = keywords.find(k => base.includes(k))
    if (matchedKeyword) {
      return {
        filename,
        workflow_type: '并购重组',
        step_type,
        sub_dir,
        target_dir: buildTargetDir('并购重组', sub_dir, date_str),
        status: 'resolved',
        reason: `命中关键字 "${matchedKeyword}"`,
      }
    }
  }

  // 优先级 2: 数字前缀
  if (PREFIX_TO_TYPE[first]) {
    const wt = PREFIX_TO_TYPE[first]
    return {
      filename,
      workflow_type: wt,
      step_type: 'merge_excel',
      sub_dir: null,
      target_dir: buildTargetDir(wt, null, date_str),
      status: 'resolved',
      reason: `首位数字 "${first}" → ${wt}`,
    }
  }

  return {
    filename,
    workflow_type: null,
    step_type: null,
    sub_dir: null,
    target_dir: '',
    status: 'unresolved',
    reason: '未匹配任何规则',
  }
}
