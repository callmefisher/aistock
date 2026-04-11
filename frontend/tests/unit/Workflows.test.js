import { describe, it, expect, vi } from 'vitest'

vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('Workflows Component Logic', () => {

  describe('getStatusType', () => {
    const getStatusType = (status) => {
      const types = {
        active: 'success',
        inactive: 'info',
        running: 'primary',
        completed: 'success',
        failed: 'danger'
      }
      return types[status] || 'info'
    }

    it('should return success for active', () => {
      expect(getStatusType('active')).toBe('success')
    })

    it('should return info for inactive', () => {
      expect(getStatusType('inactive')).toBe('info')
    })

    it('should return primary for running', () => {
      expect(getStatusType('running')).toBe('primary')
    })

    it('should return danger for failed', () => {
      expect(getStatusType('failed')).toBe('danger')
    })

    it('should return info for unknown status', () => {
      expect(getStatusType('unknown')).toBe('info')
    })
  })

  describe('getStepType', () => {
    const getStepType = (type) => {
      const types = {
        import_excel: 'primary',
        merge_excel: 'primary',
        dedup: 'success',
        smart_dedup: 'success',
        extract_columns: 'warning',
        export_excel: 'info',
        pending: 'danger'
      }
      return types[type] || 'info'
    }

    it('should return correct types for all step types', () => {
      expect(getStepType('import_excel')).toBe('primary')
      expect(getStepType('merge_excel')).toBe('primary')
      expect(getStepType('dedup')).toBe('success')
      expect(getStepType('smart_dedup')).toBe('success')
      expect(getStepType('extract_columns')).toBe('warning')
      expect(getStepType('export_excel')).toBe('info')
      expect(getStepType('pending')).toBe('danger')
    })

    it('should return info for unknown type', () => {
      expect(getStepType('unknown')).toBe('info')
    })
  })

  describe('getStepTypeName', () => {
    const getStepTypeName = (type) => {
      const names = {
        import_excel: '导入Excel',
        merge_excel: '合并当日数据源',
        dedup: '去除重复行',
        smart_dedup: '智能去重',
        extract_columns: '提取列',
        export_excel: '导出Excel',
        pending: '待定'
      }
      return names[type] || type
    }

    it('should return correct names for all step types', () => {
      expect(getStepTypeName('import_excel')).toBe('导入Excel')
      expect(getStepTypeName('merge_excel')).toBe('合并当日数据源')
      expect(getStepTypeName('dedup')).toBe('去除重复行')
      expect(getStepTypeName('smart_dedup')).toBe('智能去重')
      expect(getStepTypeName('extract_columns')).toBe('提取列')
      expect(getStepTypeName('export_excel')).toBe('导出Excel')
      expect(getStepTypeName('pending')).toBe('待定')
    })
  })

  describe('defaultStep', () => {
    const defaultStep = () => ({
      type: 'merge_excel',
      config: {
        date_str: new Date().toISOString().split('T')[0],
        data_source_id: null,
        file_path: '',
        columns: [1, 2],
        output_filename: 'output_1.xlsx',
        apply_formatting: true,
        stock_code_column: '',
        date_column: ''
      },
      status: 'pending'
    })

    it('should create default step with merge_excel type', () => {
      const step = defaultStep()
      expect(step.type).toBe('merge_excel')
      expect(step.config.output_filename).toBe('output_1.xlsx')
      expect(step.config.stock_code_column).toBe('')
      expect(step.config.date_column).toBe('')
    })

    it('should have date_str by default', () => {
      const step = defaultStep()
      expect(step.config.date_str).toBeDefined()
      expect(step.config.date_str).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })
  })

  describe('Step Management Logic', () => {
    it('should add step correctly', () => {
      const steps = [{ type: 'merge_excel' }]
      const newStep = { type: 'smart_dedup' }
      steps.push(newStep)
      expect(steps).toHaveLength(2)
      expect(steps[1].type).toBe('smart_dedup')
    })

    it('should remove step correctly', () => {
      const steps = [{ type: 'merge_excel' }, { type: 'smart_dedup' }]
      steps.splice(0, 1)
      expect(steps).toHaveLength(1)
      expect(steps[0].type).toBe('smart_dedup')
    })

    it('should reset config on step type change', () => {
      const config = {
        data_source_id: 1,
        file_path: '/test.xlsx',
        columns: [1, 2, 3],
        output_filename: 'old.xlsx',
        stock_code_column: '代码',
        date_column: '日期'
      }

      const newConfig = {
        date_str: new Date().toISOString().split('T')[0],
        data_source_id: null,
        file_path: '',
        columns: [1, 2],
        output_filename: 'output_1.xlsx',
        apply_formatting: true,
        stock_code_column: '',
        date_column: ''
      }

      Object.assign(config, newConfig)
      expect(config.file_path).toBe('')
      expect(config.data_source_id).toBe(null)
      expect(config.stock_code_column).toBe('')
      expect(config.date_column).toBe('')
    })
  })

  describe('Workflow Edit Logic', () => {
    it('should populate form for editing', () => {
      const workflow = {
        id: 1,
        name: '编辑工作流',
        description: '编辑描述',
        steps: [
          { type: 'merge_excel', config: { output_filename: 'total_1.xlsx' }, status: 'completed' },
          { type: 'smart_dedup', config: { stock_code_column: '证券代码', date_column: '最新公告日' }, status: 'pending' }
        ]
      }

      const form = {
        name: workflow.name,
        description: workflow.description || '',
        steps: (workflow.steps || []).map(step => ({
          type: step.type,
          config: { ...step.config },
          status: step.status || 'pending'
        }))
      }

      expect(form.name).toBe('编辑工作流')
      expect(form.description).toBe('编辑描述')
      expect(form.steps).toHaveLength(2)
      expect(form.steps[0].type).toBe('merge_excel')
      expect(form.steps[1].type).toBe('smart_dedup')
      expect(form.steps[1].config.stock_code_column).toBe('证券代码')
    })
  })

  describe('Form Validation Logic', () => {
    it('should validate import_excel step needs file_path or data_source_id', () => {
      const steps = [
        {
          type: 'import_excel',
          config: { file_path: '', data_source_id: null }
        }
      ]

      const isInvalid = steps.some(
        s => s.type === 'import_excel' && !s.config.file_path && !s.config.data_source_id
      )

      expect(isInvalid).toBe(true)
    })

    it('should validate smart_dedup step needs stock_code and date columns', () => {
      const steps = [
        {
          type: 'smart_dedup',
          config: { stock_code_column: '', date_column: '' }
        }
      ]

      const needsConfig = steps.filter(
        s => s.type === 'smart_dedup' && (!s.config.stock_code_column || !s.config.date_column)
      )

      expect(needsConfig.length).toBe(1)
    })

    it('should pass validation when smart_dedup has columns specified', () => {
      const steps = [
        {
          type: 'smart_dedup',
          config: { stock_code_column: '证券代码', date_column: '最新公告日' }
        }
      ]

      const needsConfig = steps.filter(
        s => s.type === 'smart_dedup' && (!s.config.stock_code_column || !s.config.date_column)
      )

      expect(needsConfig.length).toBe(0)
    })
  })

  describe('Step Status Helpers', () => {
    const getTimelineType = (status) => {
      if (status === 'completed') return 'success'
      if (status === 'running') return 'primary'
      if (status === 'failed') return 'danger'
      return 'info'
    }

    const getStepStatus = (status) => {
      if (status === 'completed') return 'success'
      if (status === 'running') return 'process'
      if (status === 'failed') return 'error'
      return 'wait'
    }

    it('should return correct timeline types', () => {
      expect(getTimelineType('completed')).toBe('success')
      expect(getTimelineType('running')).toBe('primary')
      expect(getTimelineType('failed')).toBe('danger')
      expect(getTimelineType('pending')).toBe('info')
    })

    it('should return correct step statuses', () => {
      expect(getStepStatus('completed')).toBe('success')
      expect(getStepStatus('running')).toBe('process')
      expect(getStepStatus('failed')).toBe('error')
      expect(getStepStatus('pending')).toBe('wait')
    })
  })

  describe('API Payload Construction', () => {
    it('should create correct payload for workflow with new step types', () => {
      const form = {
        name: '新工作流',
        description: '测试新步骤类型',
        steps: [
          { type: 'merge_excel', config: { date_str: '2026-04-09', output_filename: 'total_1.xlsx' }, status: 'pending' },
          { type: 'smart_dedup', config: { stock_code_column: '证券代码', date_column: '最新公告日' }, status: 'pending' },
          { type: 'extract_columns', config: { output_filename: 'output_1.xlsx' }, status: 'pending' }
        ]
      }

      const payload = {
        name: form.name,
        description: form.description,
        steps: form.steps.map(step => ({
          type: step.type,
          config: step.config,
          status: step.status || 'pending'
        }))
      }

      expect(payload.name).toBe('新工作流')
      expect(payload.steps).toHaveLength(3)
      expect(payload.steps[0].type).toBe('merge_excel')
      expect(payload.steps[1].type).toBe('smart_dedup')
      expect(payload.steps[2].type).toBe('extract_columns')
    })

    it('should create correct payload for update workflow', () => {
      const editingId = 1
      const form = {
        name: '更新工作流',
        description: '更新描述',
        steps: [
          { type: 'smart_dedup', config: { stock_code_column: '代码', date_column: '日期' }, status: 'completed' }
        ]
      }

      const payload = {
        name: form.name,
        description: form.description,
        steps: form.steps.map(step => ({
          type: step.type,
          config: step.config,
          status: step.status || 'pending'
        }))
      }

      expect(payload.name).toBe('更新工作流')
      expect(payload.steps[0].status).toBe('completed')
    })
  })

  describe('Fixed Columns Logic', () => {
    it('should have fixed 4 columns for extract_columns', () => {
      const fixedColumns = ['序号', '证券代码', '证券简称', '最新公告日']
      expect(fixedColumns).toHaveLength(4)
      expect(fixedColumns).toContain('证券代码')
      expect(fixedColumns).toContain('最新公告日')
    })
  })

  describe('Merge Excel Logic', () => {
    it('should understand merge_excel excludes total_ and output_ files', () => {
      const files = [
        'source_1.xlsx',
        'source_2.xlsx',
        'total_1.xlsx',
        'output_1.xlsx',
        'public_data.xlsx'
      ]

      const excludedFiles = files.filter(
        f => f.startsWith('total_') || f.startsWith('output_')
      )

      const includedFiles = files.filter(
        f => !f.startsWith('total_') && !f.startsWith('output_')
      )

      expect(excludedFiles).toHaveLength(2)
      expect(includedFiles).toHaveLength(3)
      expect(includedFiles).toContain('source_1.xlsx')
      expect(includedFiles).toContain('public_data.xlsx')
    })
  })

  describe('Smart Dedup Logic', () => {
    it('should select latest date for duplicate stocks', () => {
      const stocks = [
        { code: '002128.SZ', date: '2026-04-09' },
        { code: '002128.SZ', date: '2026-04-01' },
        { code: '002128.SZ', date: '2026-05-01' }
      ]

      const sorted = [...stocks].sort((a, b) => new Date(b.date) - new Date(a.date))
      const deduped = []
      const seen = new Set()

      for (const stock of sorted) {
        if (!seen.has(stock.code)) {
          deduped.push(stock)
          seen.add(stock.code)
        }
      }

      expect(deduped).toHaveLength(1)
      expect(deduped[0].date).toBe('2026-05-01')
    })
  })
})
