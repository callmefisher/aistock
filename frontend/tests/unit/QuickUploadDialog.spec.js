import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isPublicTarget } from '@/utils/quickUploadRules'

describe('isPublicTarget', () => {
  it.each([
    ['data/excel/2025public/', true],
    ['data/excel/2025public', true],
    ['data/excel/股权转让/public/', true],
    ['data/excel/股权转让/public', true],
    ['data/excel/质押/public/', true],
    ['data/excel/涨幅排名/2026-04-23/public/', true],
    ['data/excel/2026-04-24/', false],
    ['data/excel/2026-04-24/百日新高/', false],
    ['', false],
    [null, false],
    [undefined, false],
  ])('returns %s for %s', (dir, expected) => {
    expect(isPublicTarget(dir)).toBe(expected)
  })
})
