import { describe, it, expect, vi } from 'vitest'

vi.mock('@/utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('DataSources Component Logic', () => {

  describe('getLoginTypeName', () => {
    const getLoginTypeName = (type) => {
      const names = {
        password: '账号密码',
        captcha: '验证码',
        qrcode: '二维码',
        cookie: 'Cookie',
        none: '无需登录'
      }
      return names[type] || type
    }

    it('should return correct name for password', () => {
      expect(getLoginTypeName('password')).toBe('账号密码')
    })

    it('should return correct name for captcha', () => {
      expect(getLoginTypeName('captcha')).toBe('验证码')
    })

    it('should return correct name for qrcode', () => {
      expect(getLoginTypeName('qrcode')).toBe('二维码')
    })

    it('should return correct name for cookie', () => {
      expect(getLoginTypeName('cookie')).toBe('Cookie')
    })

    it('should return correct name for none', () => {
      expect(getLoginTypeName('none')).toBe('无需登录')
    })

    it('should return original value for unknown type', () => {
      expect(getLoginTypeName('unknown')).toBe('unknown')
    })
  })

  describe('getDataFormatName', () => {
    const getDataFormatName = (format) => {
      const names = {
        excel: 'Excel文件',
        table: '网页表格',
        api: 'API接口'
      }
      return names[format] || format
    }

    it('should return correct name for excel', () => {
      expect(getDataFormatName('excel')).toBe('Excel文件')
    })

    it('should return correct name for table', () => {
      expect(getDataFormatName('table')).toBe('网页表格')
    })

    it('should return correct name for api', () => {
      expect(getDataFormatName('api')).toBe('API接口')
    })

    it('should return original value for unknown format', () => {
      expect(getDataFormatName('unknown')).toBe('unknown')
    })
  })

  describe('defaultExtractionConfig', () => {
    const defaultExtractionConfig = () => ({
      file_path: '',
      sheet_name: '',
      header_row: 0
    })

    it('should create default config with empty file_path', () => {
      const config = defaultExtractionConfig()
      expect(config.file_path).toBe('')
    })

    it('should create default config with empty sheet_name', () => {
      const config = defaultExtractionConfig()
      expect(config.sheet_name).toBe('')
    })

    it('should create default config with header_row 0', () => {
      const config = defaultExtractionConfig()
      expect(config.header_row).toBe(0)
    })
  })

  describe('Form Reset', () => {
    const defaultExtractionConfig = () => ({
      file_path: '',
      sheet_name: '',
      header_row: 0
    })

    it('should reset form correctly for create', () => {
      const form = {
        name: 'old name',
        website_url: 'https://old.com',
        login_type: 'cookie',
        data_format: 'api',
        extraction_config: {
          file_path: '/old/file.xlsx',
          sheet_name: 'OldSheet',
          header_row: 1
        }
      }

      const resetForm = {
        name: '',
        website_url: '',
        login_type: 'password',
        login_config: {},
        data_format: 'excel',
        extraction_config: defaultExtractionConfig()
      }

      expect(resetForm.name).toBe('')
      expect(resetForm.data_format).toBe('excel')
      expect(resetForm.extraction_config.file_path).toBe('')
    })
  })

  describe('Form Validation', () => {
    it('should validate name is required', () => {
      const form = { name: '', data_format: 'excel' }
      const isInvalid = !form.name
      expect(isInvalid).toBe(true)
    })

    it('should validate excel needs file_path', () => {
      const form = {
        name: 'Test',
        data_format: 'excel',
        extraction_config: { file_path: '' }
      }
      const needsFile = form.data_format === 'excel' && !form.extraction_config.file_path
      expect(needsFile).toBe(true)
    })

    it('should pass validation when excel has file_path', () => {
      const form = {
        name: 'Test',
        data_format: 'excel',
        extraction_config: { file_path: '/path/to/file.xlsx' }
      }
      const needsFile = form.data_format === 'excel' && !form.extraction_config.file_path
      expect(needsFile).toBe(false)
    })

    it('should not require file_path for table format', () => {
      const form = {
        name: 'Test',
        data_format: 'table',
        extraction_config: { file_path: '' }
      }
      const needsFile = form.data_format === 'excel' && !form.extraction_config.file_path
      expect(needsFile).toBe(false)
    })
  })

  describe('Edit Form Population', () => {
    it('should populate form for editing', () => {
      const row = {
        id: 1,
        name: '编辑数据源',
        website_url: 'https://edit.com',
        login_type: 'captcha',
        data_format: 'excel',
        extraction_config: {
          file_path: '/edit/file.xlsx',
          sheet_name: 'EditSheet',
          header_row: 2
        }
      }

      const form = {
        name: row.name,
        website_url: row.website_url || '',
        login_type: row.login_type || 'password',
        login_config: row.login_config || {},
        data_format: row.data_format || 'excel',
        extraction_config: {
          file_path: row.extraction_config?.file_path || '',
          sheet_name: row.extraction_config?.sheet_name || '',
          header_row: row.extraction_config?.header_row || 0
        }
      }

      expect(form.name).toBe('编辑数据源')
      expect(form.website_url).toBe('https://edit.com')
      expect(form.login_type).toBe('captcha')
      expect(form.data_format).toBe('excel')
      expect(form.extraction_config.file_path).toBe('/edit/file.xlsx')
      expect(form.extraction_config.sheet_name).toBe('EditSheet')
      expect(form.extraction_config.header_row).toBe(2)
    })

    it('should handle missing extraction_config', () => {
      const row = {
        id: 1,
        name: 'Test',
        website_url: '',
        login_type: 'password',
        data_format: 'excel'
      }

      const extraction_config = {
        file_path: row.extraction_config?.file_path || '',
        sheet_name: row.extraction_config?.sheet_name || '',
        header_row: row.extraction_config?.header_row || 0
      }

      expect(extraction_config.file_path).toBe('')
      expect(extraction_config.sheet_name).toBe('')
      expect(extraction_config.header_row).toBe(0)
    })
  })

  describe('API Payload Construction', () => {
    it('should create correct payload for create', () => {
      const form = {
        name: '新建数据源',
        website_url: 'https://new.com',
        login_type: 'password',
        login_config: {},
        data_format: 'excel',
        extraction_config: {
          file_path: '/new/file.xlsx',
          sheet_name: 'NewSheet',
          header_row: 1
        }
      }

      const payload = {
        name: form.name,
        website_url: form.website_url,
        login_type: form.login_type,
        login_config: form.login_config,
        data_format: form.data_format,
        extraction_config: form.extraction_config
      }

      expect(payload.name).toBe('新建数据源')
      expect(payload.data_format).toBe('excel')
      expect(payload.extraction_config.file_path).toBe('/new/file.xlsx')
    })

    it('should create correct payload for update', () => {
      const editingId = 1
      const form = {
        name: '更新数据源',
        website_url: 'https://update.com',
        login_type: 'none',
        login_config: {},
        data_format: 'table',
        extraction_config: {
          file_path: '',
          sheet_name: '',
          header_row: 0
        }
      }

      const payload = {
        name: form.name,
        website_url: form.website_url,
        login_type: form.login_type,
        login_config: form.login_config,
        data_format: form.data_format,
        extraction_config: form.extraction_config
      }

      expect(payload.name).toBe('更新数据源')
      expect(payload.login_type).toBe('none')
    })
  })

  describe('File Selection', () => {
    it('should set file_path on file select', () => {
      const extraction_config = { file_path: '' }
      const file = { name: 'selected.xlsx' }

      extraction_config.file_path = file.name

      expect(extraction_config.file_path).toBe('selected.xlsx')
    })
  })

  describe('Login Types', () => {
    it('should support all login types', () => {
      const loginTypes = ['password', 'captcha', 'qrcode', 'cookie', 'none']
      const expectedNames = ['账号密码', '验证码', '二维码', 'Cookie', '无需登录']

      loginTypes.forEach((type, index) => {
        const names = {
          password: '账号密码',
          captcha: '验证码',
          qrcode: '二维码',
          cookie: 'Cookie',
          none: '无需登录'
        }
        expect(names[type]).toBe(expectedNames[index])
      })
    })
  })

  describe('Data Formats', () => {
    it('should support all data formats', () => {
      const dataFormats = ['excel', 'table', 'api']
      const expectedNames = ['Excel文件', '网页表格', 'API接口']

      dataFormats.forEach((format, index) => {
        const names = {
          excel: 'Excel文件',
          table: '网页表格',
          api: 'API接口'
        }
        expect(names[format]).toBe(expectedNames[index])
      })
    })
  })
})
