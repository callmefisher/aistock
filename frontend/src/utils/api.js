import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          window.location.href = '/login'
          ElMessage.error('登录已过期，请重新登录')
          break
        case 403:
          ElMessage.error('没有权限访问')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器错误')
          break
        default:
          ElMessage.error(error.response.data?.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

api.download = async (url, filename) => {
  const token = localStorage.getItem('token')
  const response = await axios.get(`/api/v1${url}`, {
    responseType: 'blob',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    timeout: 300000
  })
  if (!filename) {
    const contentDisposition = response.headers['content-disposition'] || ''
    const match = contentDisposition.match(/filename\*?=(?:UTF-8''|")?([^";\n]+)(?="|$)/i)
    if (match) {
      filename = decodeURIComponent(match[1])
    }
    if (!filename) {
      filename = 'download.xlsx'
    }
  }
  const blob = new Blob([response.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(downloadUrl)
}

export default api
