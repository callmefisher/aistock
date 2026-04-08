import { describe, it, expect, beforeEach } from 'vitest'
import api from '@/utils/api'

describe('API Utility', () => {
  describe('axios instance configuration', () => {
    it('should have baseURL set to /api/v1', () => {
      expect(api.defaults.baseURL).toBe('/api/v1')
    })

    it('should have timeout set to 30000ms', () => {
      expect(api.defaults.timeout).toBe(30000)
    })

    it('should have Content-Type header set to application/json', () => {
      expect(api.defaults.headers['Content-Type']).toBe('application/json')
    })
  })

  describe('request interceptor', () => {
    it('should be defined', () => {
      expect(api.interceptors.request).toBeDefined()
    })

    it('should have at least one request interceptor', () => {
      expect(api.interceptors.request.handlers.length).toBeGreaterThan(0)
    })
  })

  describe('response interceptor', () => {
    it('should be defined', () => {
      expect(api.interceptors.response).toBeDefined()
    })

    it('should have at least one response interceptor', () => {
      expect(api.interceptors.response.handlers.length).toBeGreaterThan(0)
    })
  })
})
