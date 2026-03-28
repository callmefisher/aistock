import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(username, password) {
    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)
      
      const response = await api.post('/auth/login', formData)
      
      token.value = response.access_token
      localStorage.setItem('token', response.access_token)
      
      await fetchUser()
      
      return { success: true }
    } catch (error) {
      return { success: false, message: error.response?.data?.detail || '登录失败' }
    }
  }

  async function register(userData) {
    try {
      await api.post('/auth/register', userData)
      return { success: true }
    } catch (error) {
      return { success: false, message: error.response?.data?.detail || '注册失败' }
    }
  }

  async function fetchUser() {
    try {
      const response = await api.get('/auth/me')
      user.value = response
      localStorage.setItem('user', JSON.stringify(response))
    } catch (error) {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    fetchUser,
    logout
  }
})
