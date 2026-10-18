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

// 快捷批量上传专用规则（优先级高于子目录关键字与数字前缀）：
// 1) 全部A股：文件名含"全部A股"，即使含板块关键字也当作全部A股（不按日期，全局共享一份）
// 2) 39日新高：文件名含"39日新高"或"39日"（按数据日期）
// 3) 16 AI筛选汇总：以"16"开头且含"AI筛选汇总"（按数据日期月份，目录 data/excel/YYYY-MM/）
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
  // 严格"单数字前缀"：首字符是数字，且第二字符不是数字。
  // 1adbd.xlsx → '1' 命中；11xxx.xlsx / 88xxx.xlsx → 不命中（交回"未匹配"）。
  // 带"百日新高/20日均线/国央企/板块"等子目录关键字的文件走 SUBDIR 分支，
  // 不受此约束影响——`11百日新高.xlsx` 仍能落到 data/excel/{date}/百日新高/。
  const first = base.charAt(0)
  const second = base.charAt(1)
  const isSingleDigitPrefix = /^\d$/.test(first) && !/^\d$/.test(second)

  // 例外：严格单数字 8 + 含"涨跌幅"视为"涨幅排名"，绕过"板块"等子目录关键字
  // (e.g. `8、板块涨跌幅排名 0422.xlsx` 应落入 data/excel/涨幅排名/{date}/，
  //  而不是 data/excel/{date}/一级板块/)
  // 88xxx 涨跌幅.xlsx 不会命中（非单数字前缀）
  if (isSingleDigitPrefix && first === '8' && base.includes('涨跌幅')) {
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

  // 专用规则 0: 减持叠加质押和大宗交易（含"叠加质押"，优先级高于"全部A股"关键字）
  // e.g. `6、全部A股减持中叠加质押和大宗交易1013.xlsx` 含"全部A股"字样但实为
  // "减持叠加质押和大宗交易"数据文件 → data/excel/减持叠加质押和大宗交易/{date}/
  if (base.includes('叠加质押')) {
    const wt = '减持叠加质押和大宗交易'
    return {
      filename,
      workflow_type: wt,
      step_type: 'merge_excel',
      sub_dir: null,
      target_dir: buildTargetDir(wt, null, date_str),
      status: 'resolved',
      reason: '含"叠加质押" → 减持叠加质押和大宗交易（按数据日期）',
    }
  }

  // 专用规则 W0: 「13 占20日线无振幅」输出文件（13号表工作流产物，优先级最高）
  // e.g. `13 占20日线无振幅 1015.xlsx` → data/excel/{date}/本周20日收盘价新高输出/
  // 注意：含"20日线"字样但不是老的"20日均线"公共数据，必须先于 SUBDIR_KEYWORDS 判定
  if (base.includes('占20日线无振幅')) {
    const d = date_str || '{date}'
    return {
      filename,
      workflow_type: '并购重组',
      step_type: 'upload_weekly_ma20_out',
      sub_dir: '本周20日收盘价新高输出',
      target_dir: `data/excel/${d}/本周20日收盘价新高输出/`,
      status: 'resolved',
      reason: '含"占20日线无振幅" → 13号表输出目录（本周20日收盘价新高输出）',
    }
  }

  // 专用规则 W1: 「本周20日收盘价新高」公共文件
  // 文件名同时含"收盘价"+"20日均线/20日线"+"上周"（新文件，勿当作老的"20日均线"公共数据）
  // e.g. `本周20日收盘价大于20日均线且大于上周最高价格1016.xlsx` → data/excel/{date}/本周20日收盘价新高/
  if (base.includes('收盘价') && (base.includes('20日均线') || base.includes('20日线')) && base.includes('上周')) {
    const d = date_str || '{date}'
    return {
      filename,
      workflow_type: '并购重组',
      step_type: 'upload_weekly_ma20_high',
      sub_dir: '本周20日收盘价新高',
      target_dir: `data/excel/${d}/本周20日收盘价新高/`,
      status: 'resolved',
      reason: '含"收盘价"+"20日均线/20日线"+"上周" → 本周20日收盘价新高（公共数据）',
    }
  }

  // 专用规则 W2: 「本周总市值千亿新高」公共文件 / 「14」开头输出文件
  // 文件名含"总市值大于"+"亿"+"大于上周最高价格"；
  // 若同时以"14"开头且结尾4位为数字（如 `14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx`）
  // → 输出目录，否则 → 公共目录。注意区分两者。
  if (base.includes('总市值大于') && base.includes('亿') && base.includes('大于上周最高价格')) {
    const d = date_str || '{date}'
    const isOut = base.startsWith('14') && /^\d{4}$/.test(base.slice(-4))
    return {
      filename,
      workflow_type: '并购重组',
      step_type: isOut ? 'upload_weekly_mv1000_out' : 'upload_weekly_mv1000_high',
      sub_dir: isOut ? '本周总市值千亿新高输出' : '本周总市值千亿新高',
      target_dir: `data/excel/${d}/${isOut ? '本周总市值千亿新高输出' : '本周总市值千亿新高'}/`,
      status: 'resolved',
      reason: isOut
        ? '"14"开头+结尾4位数字 → 14号表输出目录（本周总市值千亿新高输出）'
        : '含"总市值大于"+"亿"+"大于上周最高价格" → 本周总市值千亿新高（公共数据）',
    }
  }

  // 专用规则 W3: 「全部A股800亿」公共文件 / 「18」开头输出文件
  // 文件名含"全部A股总市值大于800亿"；
  // 若同时以"18"开头且结尾4位为数字（如 `18 全部A股总市值大于800亿1015.xlsx`）
  // → 输出目录，否则 → 公共目录。注意与老的"全部A股"全局公共目录区分。
  if (base.includes('全部A股总市值大于800亿')) {
    const d = date_str || '{date}'
    const isOut = base.startsWith('18') && /^\d{4}$/.test(base.slice(-4))
    return {
      filename,
      workflow_type: '并购重组',
      step_type: isOut ? 'upload_all_a_800_out' : 'upload_all_a_800',
      sub_dir: isOut ? '全部A股800亿输出' : '全部A股800亿',
      target_dir: `data/excel/${d}/${isOut ? '全部A股800亿输出' : '全部A股800亿'}/`,
      status: 'resolved',
      reason: isOut
        ? '"18"开头+结尾4位数字 → 18号表输出目录（全部A股800亿输出）'
        : '含"全部A股总市值大于800亿" → 全部A股800亿（公共数据）',
    }
  }

  // 专用规则 1: 全部A股（含"全部A股"关键字；即使含"板块"等关键字也优先当作全部A股）
  // e.g. `6、全部A股 板块信息2026 0901.xlsx` → data/excel/全部A股/（而非一级板块）
  if (base.includes('全部A股')) {
    return {
      filename,
      workflow_type: '并购重组',
      step_type: 'upload_all_a',
      sub_dir: '全部A股',
      target_dir: 'data/excel/全部A股/',
      status: 'resolved',
      reason: '含"全部A股" → 全部A股（全局共享，与日期无关）',
    }
  }

  // 专用规则 2: 39日新高（含"39日新高"或"39日"，按数据日期）
  if (base.includes('39日新高') || base.includes('39日')) {
    const d = date_str || '{date}'
    return {
      filename,
      workflow_type: '并购重组',
      step_type: 'match_39day_high',
      sub_dir: '39日新高',
      target_dir: `data/excel/${d}/39日新高/`,
      status: 'resolved',
      reason: '含"39日新高/39日" → 39日新高（按数据日期）',
    }
  }

  // 专用规则 3: 16 AI筛选汇总（"16"开头且含"AI筛选汇总"，按数据日期月份）
  // e.g. `16 3月AI筛选汇总0312.xlsx`（数据日期2027-03-12）→ data/excel/2027-03/
  if (base.startsWith('16') && base.includes('AI筛选汇总')) {
    const d = date_str || '{date}'
    const month = /^\d{4}-\d{2}-\d{2}$/.test(d) ? d.slice(0, 7) : d
    return {
      filename,
      workflow_type: '本月AI筛选汇总',
      step_type: 'upload_ai_summary',
      sub_dir: null,
      target_dir: `data/excel/${month}/`,
      status: 'resolved',
      reason: '"16"开头 + 含"AI筛选汇总" → 按月目录',
    }
  }

  // 专用规则 4: 19 AI筛选20日线汇总（"19"开头且含"AI筛选20日线汇总"，按数据日期月份）
  // e.g. `19 3月AI筛选20日线汇总0312.xlsx`（数据日期2027-03-12）→ data/excel/本月AI筛选20日线汇总/2027-03/
  if (base.startsWith('19') && base.includes('AI筛选20日线汇总')) {
    const d = date_str || '{date}'
    const month = /^\d{4}-\d{2}-\d{2}$/.test(d) ? d.slice(0, 7) : d
    return {
      filename,
      workflow_type: '本月AI筛选20日线汇总',
      step_type: 'upload_ai_ma20_summary',
      sub_dir: null,
      target_dir: `data/excel/本月AI筛选20日线汇总/${month}/`,
      status: 'resolved',
      reason: '"19"开头 + 含"AI筛选20日线汇总" → 本月AI筛选20日线汇总按月目录',
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

  // 优先级 2: 严格单数字前缀
  if (isSingleDigitPrefix && PREFIX_TO_TYPE[first]) {
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

// 判定 target_dir 是公共目录（走 public-files 端点）还是日期目录（走 step-files 端点）
// 路径含 /public/ 或以 /public 结尾，或含 /2025public/ 或以 /2025public 结尾 → public
export function isPublicTarget(targetDir) {
  if (!targetDir) return false
  return targetDir.includes('/public/')
      || targetDir.endsWith('/public')
      || targetDir.includes('/2025public/')
      || targetDir.endsWith('/2025public')
}
