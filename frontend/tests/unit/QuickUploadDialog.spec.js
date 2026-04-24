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

describe('QuickUploadDialog · refreshDirectoryListing', () => {
  it('calls step-files endpoint for non-public dir and updates map', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'a.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
    api.get.mockResolvedValueOnce({
      files: [{ filename: 'old.xlsx', path: '/app/data/excel/2026-04-24/old.xlsx', modified_time: '2026-04-23 10:00' }],
    })

    await vm.refreshDirectoryListing('data/excel/2026-04-24/')

    expect(api.get).toHaveBeenCalledWith('/workflows/step-files/', {
      params: { step_type: 'merge_excel', workflow_type: '并购重组', date_str: expect.any(String) },
    })
    expect(vm.existingFilesMap['data/excel/2026-04-24/']).toHaveLength(1)
    expect(vm.existingFilesMap['data/excel/2026-04-24/'][0].filename).toBe('old.xlsx')
  })

  it('calls public-files endpoint for public dir', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: '百日新高.xlsx',
      target_dir: 'data/excel/股权转让/public/',
      step_type: 'merge_excel',
      workflow_type: '股权转让',
      status: 'resolved',
    })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.refreshDirectoryListing('data/excel/股权转让/public/')

    expect(api.get).toHaveBeenCalledWith('/workflows/public-files/', expect.any(Object))
  })

  it('no-op when target_dir not in parsedRows', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    // 不加任何 parsedRows
    await vm.refreshDirectoryListing('data/excel/不存在/')
    expect(api.get).not.toHaveBeenCalled()
  })
})

describe('QuickUploadDialog · deleteExistingFile', () => {
  function setupDialogWithRow(targetDir = 'data/excel/2026-04-24/', workflowType = '并购重组') {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'a.xlsx',
      target_dir: targetDir,
      step_type: 'merge_excel',
      workflow_type: workflowType,
      status: 'resolved',
    })
    return vm
  }

  it('success: ElMessage.success + refresh', async () => {
    const vm = setupDialogWithRow()
    api.delete.mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/app/data/excel/2026-04-24/a.xlsx')

    expect(api.delete).toHaveBeenCalledWith('/workflows/step-files/', {
      params: { file_path: '/app/data/excel/2026-04-24/a.xlsx' },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(api.get).toHaveBeenCalled()
  })

  it('file already gone: ElMessage.info + refresh', async () => {
    const vm = setupDialogWithRow()
    api.delete.mockResolvedValueOnce({ success: false, message: '文件不存在' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.info).toHaveBeenCalledWith('文件已被删除')
    expect(api.get).toHaveBeenCalled()
  })

  it('business error: ElMessage.error + refresh', async () => {
    const vm = setupDialogWithRow()
    api.delete.mockResolvedValueOnce({ success: false, message: '删除失败: Permission denied' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败: Permission denied')
    expect(api.get).toHaveBeenCalled()
  })

  it('network error: ElMessage.error 网络异常 + NO refresh', async () => {
    const vm = setupDialogWithRow()
    api.delete.mockRejectedValueOnce(new Error('Network down'))

    await vm.deleteExistingFile('data/excel/2026-04-24/', '/p/a.xlsx')

    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
    expect(api.get).not.toHaveBeenCalled()
  })

  it('routes public endpoint when target dir is public', async () => {
    const vm = setupDialogWithRow('data/excel/股权转让/public/', '股权转让')
    api.delete.mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.deleteExistingFile('data/excel/股权转让/public/', '/p/b.xlsx')

    expect(api.delete).toHaveBeenCalledWith('/workflows/public-files/', expect.any(Object))
  })
})

describe('QuickUploadDialog · clearDirectory', () => {
  function setupDialogWithDir() {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'new.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'a.xlsx', path: '/p/a.xlsx' },
      { filename: 'b.xlsx', path: '/p/b.xlsx' },
      { filename: 'c.xlsx', path: '/p/c.xlsx' },
    ]
    return vm
  }

  it('confirm + all success → ElMessage.success', async () => {
    const vm = setupDialogWithDir()
    api.delete
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: true })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    const confirmArgs = ElMessageBox.confirm.mock.calls[0]
    expect(confirmArgs[0]).toContain('3 个文件')
    expect(api.delete).toHaveBeenCalledTimes(3)
    expect(ElMessage.success).toHaveBeenCalledWith('已清空 3 个文件')
  })

  it('partial failure → warning with top 3', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'new.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      status: 'resolved',
    })
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'a.xlsx', path: '/p/a.xlsx' },
      { filename: 'b.xlsx', path: '/p/b.xlsx' },
      { filename: 'c.xlsx', path: '/p/c.xlsx' },
      { filename: 'd.xlsx', path: '/p/d.xlsx' },
      { filename: 'e.xlsx', path: '/p/e.xlsx' },
    ]
    api.delete
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
      .mockResolvedValueOnce({ success: false, message: '删除失败: IO error' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessage.warning).toHaveBeenCalled()
    const msg = ElMessage.warning.mock.calls[0][0]
    expect(msg).toContain('4 个失败')
    expect(msg).toContain('b.xlsx')
    expect(msg).toContain('c.xlsx')
    expect(msg).toContain('d.xlsx')
    expect(msg).not.toContain('e.xlsx')  // only top 3
  })

  it('all 文件不存在 → success (counts as gone)', async () => {
    const vm = setupDialogWithDir()
    api.delete
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
      .mockResolvedValueOnce({ success: false, message: '文件不存在' })
    api.get.mockResolvedValueOnce({ files: [] })

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessage.success).toHaveBeenCalledWith('已清空 3 个文件')
  })

  it('user cancels confirm → no api call', async () => {
    const vm = setupDialogWithDir()
    ElMessageBox.confirm.mockRejectedValueOnce('cancel')

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(api.delete).not.toHaveBeenCalled()
  })

  it('empty dir → no-op', async () => {
    const vm = setupDialogWithDir()
    vm.existingFilesMap['data/excel/2026-04-24/'] = []

    await vm.clearDirectory('data/excel/2026-04-24/')

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(api.delete).not.toHaveBeenCalled()
  })
})

describe('QuickUploadDialog · refreshFromDirectoryPicker', () => {
  it('clicks the hidden input when ref is set', async () => {
    const wrapper = mountDialog()
    // 隐藏 input 应该在 DOM 里
    const input = wrapper.find('input[type="file"][webkitdirectory]')
    expect(input.exists()).toBe(true)

    // spy click
    const clickSpy = vi.fn()
    input.element.click = clickSpy

    wrapper.vm.refreshFromDirectoryPicker()
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(input.element.value).toBe('')  // 确保清空
  })

  it('no-op when dirInputRef is null', () => {
    const wrapper = mountDialog()
    // 核心：函数早期 return，不抛错即可
    expect(() => wrapper.vm.refreshFromDirectoryPicker()).not.toThrow()
  })
})

describe('QuickUploadDialog · template integration', () => {
  it('renders clear/delete buttons when on preview step with existing files', async () => {
    // Use a stub that renders both default and title slots so we can inspect the content
    const wrapper = mount(QuickUploadDialog, {
      props: { modelValue: true },
      global: {
        stubs: {
          teleport: true,
          ElCollapseItem: {
            template: `<div><slot name="title" /><slot /></div>`,
          },
        },
      },
    })
    const vm = wrapper.vm
    vm.parsedRows.push({
      filename: 'new.xlsx',
      target_dir: 'data/excel/2026-04-24/',
      step_type: 'merge_excel',
      workflow_type: '并购重组',
      sub_dir: null,
      status: 'resolved',
    })
    vm.existingFilesMap['data/excel/2026-04-24/'] = [
      { filename: 'old.xlsx', path: '/p/old.xlsx', modified_time: '2026-04-23 10:00' },
    ]
    vm.currentStep = 1  // preview step
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('清空本目录')
    expect(text).toContain('目录已有')
    expect(text).toContain('移除')
    // old.xlsx appears in existingFilesMap; verify data-level
    expect(vm.existingFilesMap['data/excel/2026-04-24/'][0].filename).toBe('old.xlsx')
  })
})
