import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/stock-pools'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'data-sources',
        name: 'DataSources',
        component: () => import('@/views/DataSources.vue'),
        meta: { title: '数据源管理' }
      },
      {
        path: 'rules',
        name: 'Rules',
        component: () => import('@/views/Rules.vue'),
        meta: { title: '规则管理' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/Tasks.vue'),
        meta: { title: '任务管理' }
      },
      {
        path: 'stock-pools',
        name: 'StockPools',
        component: () => import('@/views/StockPools.vue'),
        meta: { title: '选股池' }
      },
      {
        path: 'finance-data',
        name: 'FinanceData',
        component: () => import('@/views/FinanceData.vue'),
        meta: { title: '金融数据' }
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('@/views/Workflows.vue'),
        meta: { title: '工作流' }
      },
      {
        path: 'excel-compare',
        name: 'ExcelCompare',
        component: () => import('@/views/ExcelCompare.vue'),
        meta: { title: 'Excel比对' }
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/Statistics.vue'),
        meta: { title: '统计分析' }
      },
      {
        path: 'database-backup',
        name: 'DatabaseBackup',
        component: () => import('@/views/DatabaseBackup.vue'),
        meta: { title: '数据库备份' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/stock-pools')
  } else {
    next()
  }
})

export default router
