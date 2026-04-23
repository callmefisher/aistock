import { describe, it, expect } from 'vitest'
import { resolveTarget, isAcceptableFile } from '@/utils/quickUploadRules'

describe('resolveTarget - 子目录关键字（优先级 1）', () => {
  it('含"百日新高" → 并购重组/match_high_price', () => {
    const r = resolveTarget('百日新高0422.xlsx')
    expect(r.status).toBe('resolved')
    expect(r.workflow_type).toBe('并购重组')
    expect(r.step_type).toBe('match_high_price')
    expect(r.sub_dir).toBe('百日新高')
  })

  it('含"20日均线" → match_ma20', () => {
    const r = resolveTarget('20日均线0422.xlsx')
    expect(r.step_type).toBe('match_ma20')
    expect(r.sub_dir).toBe('20日均线')
  })

  it('含"20日线"同义词 → match_ma20', () => {
    const r = resolveTarget('站上20日线0422.xlsx')
    expect(r.step_type).toBe('match_ma20')
  })

  it('含"国央企" → match_soe', () => {
    const r = resolveTarget('国央企0422.xlsx')
    expect(r.step_type).toBe('match_soe')
    expect(r.sub_dir).toBe('国企')
  })

  it('含"板块" → match_sector', () => {
    const r = resolveTarget('一级板块0422.xlsx')
    expect(r.step_type).toBe('match_sector')
    expect(r.sub_dir).toBe('一级板块')
  })

  it('"1百日新高0422" 关键字优先于数字前缀', () => {
    const r = resolveTarget('1百日新高0422.xlsx')
    expect(r.step_type).toBe('match_high_price')
    expect(r.workflow_type).toBe('并购重组')
  })
})

describe('resolveTarget - 数字前缀（优先级 2）', () => {
  const cases = [
    ['1并购重组0422.xlsx', '并购重组'],
    ['2股权转让0422.xlsx', '股权转让'],
    ['3增发实现0422.xlsx', '增发实现'],
    ['4申报并购重组0422.xlsx', '申报并购重组'],
    ['5质押中大盘0422.xlsx', '质押'],
    ['5质押小盘0422.xlsx', '质押'],
    ['6减持叠加质押和大宗交易0422.xlsx', '减持叠加质押和大宗交易'],
    ['8涨幅排名0422.xlsx', '涨幅排名'],
    ['9招投标0422.xlsx', '招投标'],
  ]
  cases.forEach(([name, wt]) => {
    it(`${name} → ${wt}`, () => {
      const r = resolveTarget(name)
      expect(r.status).toBe('resolved')
      expect(r.workflow_type).toBe(wt)
      expect(r.step_type).toBe('merge_excel')
      expect(r.sub_dir).toBeNull()
    })
  })
})

describe('resolveTarget - 未识别', () => {
  it('无数字前缀无关键字 → unresolved', () => {
    const r = resolveTarget('abc.xlsx')
    expect(r.status).toBe('unresolved')
  })

  it('0 或 7 开头 → unresolved', () => {
    expect(resolveTarget('0foo.xlsx').status).toBe('unresolved')
    expect(resolveTarget('7条件交集.xlsx').status).toBe('unresolved')
  })
})

describe('isAcceptableFile - 扩展名和隐藏文件过滤', () => {
  it('接受 .xlsx/.xls', () => {
    expect(isAcceptableFile('a.xlsx')).toBe(true)
    expect(isAcceptableFile('a.xls')).toBe(true)
  })

  it('拒绝非 Excel 扩展名', () => {
    expect(isAcceptableFile('a.txt')).toBe(false)
    expect(isAcceptableFile('a.csv')).toBe(false)
    expect(isAcceptableFile('readme')).toBe(false)
  })

  it('拒绝隐藏文件和 Office 锁文件', () => {
    expect(isAcceptableFile('.DS_Store')).toBe(false)
    expect(isAcceptableFile('.hidden.xlsx')).toBe(false)
    expect(isAcceptableFile('~$temp.xlsx')).toBe(false)
  })
})

describe('resolveTarget - 目标路径展示字符串', () => {
  it('1 开头 target_dir 相对路径', () => {
    const r = resolveTarget('1并购重组0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/2026-04-23/')
  })

  it('2 开头 target_dir', () => {
    const r = resolveTarget('2股权转让0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/股权转让/2026-04-23/')
  })

  it('子目录 target_dir', () => {
    const r = resolveTarget('百日新高0422.xlsx', '2026-04-23')
    expect(r.target_dir).toBe('data/excel/2026-04-23/百日新高/')
  })
})
