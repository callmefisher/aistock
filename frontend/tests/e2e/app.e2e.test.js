import { describe, it, expect, beforeEach, afterEach } from 'vitest'

const BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:7654'

describe('E2E Test Suite - User Authentication', () => {
  let browser
  let page

  beforeEach(async () => {
    await page.goto(`${BASE_URL}/login`)
  })

  describe('Login Page', () => {
    it('should display login form', async () => {
      await expect(page.locator('input[placeholder="用户名"]')).toBeVisible()
      await expect(page.locator('input[placeholder="密码"]')).toBeVisible()
      await expect(page.locator('button:has-text("登录")')).toBeVisible()
    })

    it('should have register tab', async () => {
      await expect(page.locator('.el-tabs__item:has-text("注册")')).toBeVisible()
    })
  })

  describe('Login Flow', () => {
    it('should login with valid credentials', async () => {
      await page.fill('input[placeholder="用户名"]', 'testuser')
      await page.fill('input[placeholder="密码"]', 'test123')
      await page.click('button:has-text("登录")')

      await page.waitForURL('**/dashboard', { timeout: 5000 })
      await expect(page.locator('body')).toContainText('仪表盘')
    })

    it('should show error with invalid credentials', async () => {
      await page.fill('input[placeholder="用户名"]', 'wronguser')
      await page.fill('input[placeholder="密码"]', 'wrongpass')
      await page.click('button:has-text("登录")')

      await expect(page.locator('.el-message--error')).toBeVisible()
    })
  })

  describe('Register Flow', () => {
    it('should switch to register tab', async () => {
      await page.click('.el-tabs__item:has-text("注册")')
      await expect(page.locator('input[placeholder="确认密码"]')).toBeVisible()
    })

    it('should register new user', async () => {
      const randomUser = `user_${Date.now()}`

      await page.click('.el-tabs__item:has-text("注册")')
      await page.fill('input[placeholder="用户名"]', randomUser)
      await page.fill('input[placeholder="邮箱"]', `${randomUser}@test.com`)
      await page.fill('input[placeholder="密码"]', 'Password123!')
      await page.fill('input[placeholder="确认密码"]', 'Password123!')
      await page.click('button:has-text("注册")')

      await expect(page.locator('.el-message--success')).toBeVisible()
    })
  })
})

describe('E2E Test Suite - Dashboard', () => {
  beforeEach(async () => {
    await page.goto(`${BASE_URL}/login`)
    await page.fill('input[placeholder="用户名"]', 'testuser')
    await page.fill('input[placeholder="密码"]', 'test123')
    await page.click('button:has-text("登录")')
    await page.waitForURL('**/dashboard', { timeout: 5000 })
  })

  describe('Dashboard Page', () => {
    it('should display dashboard', async () => {
      await expect(page.locator('.el-card')).toBeVisible()
    })

    it('should show statistics', async () => {
      await expect(page.locator('text=数据源')).toBeVisible()
      await expect(page.locator('text=规则')).toBeVisible()
      await expect(page.locator('text=任务')).toBeVisible()
    })
  })
})

describe('E2E Test Suite - Navigation', () => {
  beforeEach(async () => {
    await page.goto(`${BASE_URL}/login`)
    await page.fill('input[placeholder="用户名"]', 'testuser')
    await page.fill('input[placeholder="密码"]', 'test123')
    await page.click('button:has-text("登录")')
    await page.waitForURL('**/dashboard', { timeout: 5000 })
  })

  describe('Sidebar Navigation', () => {
    it('should navigate to data sources', async () => {
      await page.click('text=数据源管理')
      await expect(page).toHaveURL('**/data-sources')
    })

    it('should navigate to rules', async () => {
      await page.click('text=规则管理')
      await expect(page).toHaveURL('**/rules')
    })

    it('should navigate to tasks', async () => {
      await page.click('text=任务管理')
      await expect(page).toHaveURL('**/tasks')
    })

    it('should navigate to stock pools', async () => {
      await page.click('text=选股池')
      await expect(page).toHaveURL('**/stock-pools')
    })
  })
})
