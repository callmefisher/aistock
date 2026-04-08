import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { setupTestEnvironment } from '../setup'
import Login from '@/views/Login.vue'

setupTestEnvironment()

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: Login
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: { template: '<div>Dashboard</div>' }
    }
  ]
})

describe('Login Component', () => {
  let wrapper

  beforeEach(async () => {
    await router.push('/login')
    wrapper = mount(Login, {
      global: {
        plugins: [router],
        stubs: {
          'el-input': { template: '<input @input="$emit(\'input\', $event.target.value)" />' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'el-card': { template: '<div><slot /></div>' },
          'el-form': { template: '<form @submit.prevent="$emit(\'submit\')"><slot /></form>' },
          'el-form-item': { template: '<div><slot /></div>' },
          'el-tabs': { template: '<div><slot /></div>' },
          'el-tab-pane': { template: '<div><slot /></div>' }
        }
      }
    })
  })

  describe('UI Elements', () => {
    it('should render login form', () => {
      expect(wrapper.find('form').exists()).toBe(true)
    })

    it('should have username input field', () => {
      const usernameInput = wrapper.find('input')
      expect(usernameInput.exists()).toBe(true)
    })
  })

  describe('Login Form', () => {
    it('should have empty initial username', () => {
      expect(wrapper.vm.loginForm.username).toBe('')
    })

    it('should have empty initial password', () => {
      expect(wrapper.vm.loginForm.password).toBe('')
    })

    it('should update loginForm data on username change', async () => {
      wrapper.vm.loginForm.username = 'testuser'
      expect(wrapper.vm.loginForm.username).toBe('testuser')
    })

    it('should update loginForm data on password change', async () => {
      wrapper.vm.loginForm.password = 'testpass'
      expect(wrapper.vm.loginForm.password).toBe('testpass')
    })
  })

  describe('Register Form', () => {
    it('should have empty initial register form values', () => {
      expect(wrapper.vm.registerForm.username).toBe('')
      expect(wrapper.vm.registerForm.email).toBe('')
      expect(wrapper.vm.registerForm.password).toBe('')
      expect(wrapper.vm.registerForm.confirmPassword).toBe('')
    })

    it('should update registerForm data', async () => {
      wrapper.vm.registerForm.username = 'newuser'
      wrapper.vm.registerForm.email = 'new@example.com'
      wrapper.vm.registerForm.password = 'password123'

      expect(wrapper.vm.registerForm.username).toBe('newuser')
      expect(wrapper.vm.registerForm.email).toBe('new@example.com')
      expect(wrapper.vm.registerForm.password).toBe('password123')
    })
  })

  describe('Form Validation Rules', () => {
    it('should have login validation rules', () => {
      expect(wrapper.vm.loginRules).toBeDefined()
    })

    it('should have register validation rules', () => {
      expect(wrapper.vm.registerRules).toBeDefined()
    })
  })
})
