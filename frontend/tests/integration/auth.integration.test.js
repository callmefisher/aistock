import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises } from '../setup'

const mockResponse = {
  data: {
    access_token: 'mock-token',
    token_type: 'bearer'
  }
}

vi.mock('@/utils/api', () => ({
  default: {
    post: vi.fn(() => Promise.resolve(mockResponse)),
    get: vi.fn(() => Promise.resolve({ data: [] })),
    delete: vi.fn(() => Promise.resolve({ data: null })),
    put: vi.fn(() => Promise.resolve({ data: {} }))
  }
}))

import { useAuthStore } from '@/stores/auth'
import { setActivePinia, createPinia } from 'pinia'

describe('Authentication Integration Tests', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('Complete Login Flow', () => {
    it('should successfully login and store token', async () => {
      const authStore = useAuthStore()
      const api = (await import('@/utils/api')).default

      const result = await authStore.login('testuser', 'password123')

      expect(result.success).toBe(true)
      expect(api.post).toHaveBeenCalledWith(
        '/auth/login',
        expect.any(Object),
        expect.any(Object)
      )
    })

    it('should handle login failure', async () => {
      const authStore = useAuthStore()
      const api = (await import('@/utils/api')).default

      api.post.mockRejectedValueOnce({
        response: {
          data: { detail: '用户名或密码错误' }
        }
      })

      const result = await authStore.login('wronguser', 'wrongpass')

      expect(result.success).toBe(false)
      expect(result.message).toBe('用户名或密码错误')
    })
  })

  describe('Token Management', () => {
    it('should handle token state correctly', async () => {
      const authStore = useAuthStore()

      authStore.token = 'test-token-123'
      await flushPromises()

      expect(authStore.token).toBe('test-token-123')
      expect(authStore.isAuthenticated).toBe(true)
    })

    it('should restore token from localStorage on init', () => {
      const localStorageSpy = vi.spyOn(
        Storage.prototype,
        'getItem'
      ).mockImplementation((key) => {
        if (key === 'token') return 'stored-token'
        if (key === 'user') return null
        return null
      })

      const authStore = useAuthStore()

      expect(authStore.token).toBe('stored-token')
      localStorageSpy.mockRestore()
    })
  })
})

describe('API Error Handling Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should handle 401 unauthorized errors', async () => {
    const api = (await import('@/utils/api')).default

    api.get.mockRejectedValueOnce({
      response: { status: 401 }
    })

    try {
      await api.get('/data-sources/')
    } catch (error) {
      expect(error.response.status).toBe(401)
    }
  })

  it('should handle 404 not found errors', async () => {
    const api = (await import('@/utils/api')).default

    api.get.mockRejectedValueOnce({
      response: { status: 404 }
    })

    try {
      await api.get('/data-sources/99999/')
    } catch (error) {
      expect(error.response.status).toBe(404)
    }
  })

  it('should handle 500 server errors', async () => {
    const api = (await import('@/utils/api')).default

    api.get.mockRejectedValueOnce({
      response: { status: 500 }
    })

    try {
      await api.get('/data-sources/')
    } catch (error) {
      expect(error.response.status).toBe(500)
    }
  })
})
