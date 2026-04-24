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

// -------- mount-based integration tests --------
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import QuickUploadDialog from '@/components/QuickUploadDialog.vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  }
})

beforeEach(() => {
  vi.clearAllMocks()
})

function makeFile(name) {
  return new File([''], name, { type: 'application/vnd.ms-excel' })
}

function mountDialog() {
  return mount(QuickUploadDialog, {
    props: { modelValue: true },
    global: { stubs: { teleport: true } },
  })
}

describe('QuickUploadDialog · removeParsedRow', () => {
  it('removes a parsed row and cleans fileMap, no API call', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    const f1 = makeFile('a.xlsx')
    const f2 = makeFile('b.xlsx')
    vm.acceptedFiles.push(f1, f2)
    vm.fileMap.set('a.xlsx', f1)
    vm.fileMap.set('b.xlsx', f2)
    const row1 = { filename: 'a.xlsx', target_dir: 'data/excel/2026-04-24/', status: 'resolved' }
    const row2 = { filename: 'b.xlsx', target_dir: 'data/excel/2026-04-24/', status: 'resolved' }
    vm.parsedRows.push(row1, row2)

    vm.removeParsedRow(row1)
    await nextTick()

    expect(vm.parsedRows).toHaveLength(1)
    expect(vm.parsedRows[0]).toEqual(row2)  // Vue wraps plain objects in reactive proxy; use toEqual not toBe
    expect(vm.acceptedFiles).toHaveLength(1)
    expect(vm.acceptedFiles[0]).toBe(f2)
    expect(vm.fileMap.has('a.xlsx')).toBe(false)
    expect(vm.fileMap.has('b.xlsx')).toBe(true)
    expect(api.delete).not.toHaveBeenCalled()
    expect(api.get).not.toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })
})
