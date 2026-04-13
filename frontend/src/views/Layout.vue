<template>
  <el-container class="layout-container">
    <el-aside width="250px">
      <div class="logo">
        <h1>选股池系统</h1>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#545c64"
        text-color="#fff"
        active-text-color="#ffd04b"
      >
        <el-menu-item index="/dashboard" v-show="false">
          <el-icon><DataAnalysis /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/data-sources" v-show="false">
          <el-icon><Connection /></el-icon>
          <span>数据源管理</span>
        </el-menu-item>
        <el-menu-item index="/rules" v-show="false">
          <el-icon><Filter /></el-icon>
          <span>规则管理</span>
        </el-menu-item>
        <el-menu-item index="/tasks" v-show="false">
          <el-icon><Timer /></el-icon>
          <span>任务管理</span>
        </el-menu-item>
        <el-menu-item index="/stock-pools">
          <el-icon><Document /></el-icon>
          <span>选股池</span>
        </el-menu-item>
        <el-menu-item index="/finance-data">
          <el-icon><Money /></el-icon>
          <span>金融数据</span>
        </el-menu-item>
        <el-menu-item index="/workflows">
          <el-icon><Operation /></el-icon>
          <span>工作流</span>
        </el-menu-item>
        <el-menu-item index="/excel-compare">
          <el-icon><DocumentCopy /></el-icon>
          <span>Excel比对</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header>
        <div class="header-content">
          <h3>{{ pageTitle }}</h3>
          <div class="user-info">
            <el-dropdown>
              <span class="el-dropdown-link">
                <el-icon><User /></el-icon>
                {{ authStore.user?.username }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleLogout">
                    <el-icon><SwitchButton /></el-icon>
                    退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>
      
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => route.meta.title || '仪表盘')

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.el-aside {
  background-color: #545c64;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #434a50;
}

.logo h1 {
  margin: 0;
  font-size: 20px;
  color: #fff;
}

.el-menu {
  border-right: none;
}

.el-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h3 {
  margin: 0;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #303133;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
