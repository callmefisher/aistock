import { createPinia, setActivePinia } from 'pinia'
import { vi } from 'vitest'

export const setupTestEnvironment = () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })
}

export const createMockRouter = (initialRoute = '/') => {
  return {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    currentRoute: {
      value: {
        path: initialRoute,
        name: 'test',
        meta: {}
      }
    }
  }
}

export const createMockRoute = (overrides = {}) => ({
  path: '/',
  name: 'test',
  meta: {},
  params: {},
  query: {},
  ...overrides
})

export const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0))
