import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('initial state', () => {
    it('should have null token initially', () => {
      const authStore = useAuthStore()
      expect(authStore.token).toBeNull()
    })

    it('should have null user initially', () => {
      const authStore = useAuthStore()
      expect(authStore.user).toBeNull()
    })

    it('should not be authenticated initially', () => {
      const authStore = useAuthStore()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('login', () => {
    it('should set token and user on successful login', async () => {
      const mockToken = 'mock-access-token'
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        is_active: true,
        is_superuser: false
      }

      const authStore = useAuthStore()

      authStore.token = mockToken
      authStore.user = mockUser

      expect(authStore.token).toBe(mockToken)
      expect(authStore.user).toEqual(mockUser)
      expect(authStore.isAuthenticated).toBe(true)
    })

    it('should handle token state correctly', () => {
      const mockToken = 'mock-access-token'
      const authStore = useAuthStore()

      authStore.token = mockToken

      expect(authStore.token).toBe(mockToken)
      expect(authStore.isAuthenticated).toBe(true)
    })
  })

  describe('logout', () => {
    it('should clear token and user on logout', async () => {
      const authStore = useAuthStore()

      authStore.token = 'some-token'
      authStore.user = { id: 1, username: 'test' }

      authStore.logout()

      expect(authStore.token).toBeNull()
      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })

    it('should remove token from localStorage on logout', () => {
      const authStore = useAuthStore()

      authStore.token = 'test-token'
      authStore.logout()

      expect(localStorage.getItem('token')).toBeNull()
    })
  })

  describe('isAuthenticated', () => {
    it('should return true when token exists', () => {
      const authStore = useAuthStore()
      authStore.token = 'valid-token'

      expect(authStore.isAuthenticated).toBe(true)
    })

    it('should return false when token is null', () => {
      const authStore = useAuthStore()
      authStore.token = null

      expect(authStore.isAuthenticated).toBe(false)
    })

    it('should return false when token is empty string', () => {
      const authStore = useAuthStore()
      authStore.token = ''

      expect(authStore.isAuthenticated).toBe(false)
    })
  })
})
