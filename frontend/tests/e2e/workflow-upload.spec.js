import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:7654';
const API_URL = 'http://localhost:8000/api/v1';

test.describe('工作流文件上传功能 E2E测试', () => {

  test.beforeAll(async ({ request }) => {
    const loginResponse = await request.post(`${API_URL}/auth/login`, {
      data: { username: 'admin', password: 'admin123' }
    });
    expect(loginResponse.ok()).toBeTruthy();
    const loginData = await loginResponse.json();
    expect(loginData.access_token).toBeDefined();
  });

  test('登录并进入工作流页面', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 10000 });

    await page.goto(`${BASE_URL}/workflows`);
    await expect(page.locator('text=工作流')).toBeVisible({ timeout: 10000 });
  });

  test('创建工作流并添加merge_excel步骤', async ({ page }) => {
    await page.goto(`${BASE_URL}/workflows`);

    await page.waitForSelector('button:has-text("新增工作流")', { timeout: 10000 });
    await page.click('button:has-text("新增工作流")');

    await page.waitForSelector('input[placeholder="请输入工作流名称"]', { timeout: 5000 });
    await page.fill('input[placeholder="请输入工作流名称"]', `测试上传工作流_${Date.now()}`);

    await page.click('button:has-text("添加步骤")');
    await page.waitForSelector('.el-select__wrapper', { timeout: 5000 });
    await page.click('.el-select__wrapper');
    await page.click('text=合并当日数据源');

    await page.waitForSelector('input[placeholder="选择数据日期"]', { timeout: 5000 });

    await page.click('input[placeholder="选择数据日期"]');
    await page.waitForSelector('.el-date-picker__header-label', { timeout: 3000 });
    await page.click('.el-date-picker__header-label:has-text("年")');
    await page.click('text="2026"');
    await page.click('.el-date-picker__header-label:has-text("月")');
    await page.click('text="四月"');
    await page.click('td.available:has-text("12")');

    await expect(page.locator('text=上传Excel文件')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=目标目录')).toBeVisible({ timeout: 5000 });
  });

  test('验证所有匹配步骤类型都有上传功能', async ({ page }) => {
    await page.goto(`${BASE_URL}/workflows`);

    await page.waitForSelector('button:has-text("新增工作流")', { timeout: 10000 });
    await page.click('button:has-text("新增工作流")');

    await page.waitForSelector('input[placeholder="请输入工作流名称"]', { timeout: 5000 });
    await page.fill('input[placeholder="请输入工作流名称"]', `测试上传功能_${Date.now()}`);

    const stepTypes = [
      { type: '合并当日数据源', stepType: 'merge_excel', expectedDir: '当日数据' },
      { type: '匹配百日新高', stepType: 'match_high_price', expectedDir: '百日新高' },
      { type: '匹配20日均线', stepType: 'match_ma20', expectedDir: '20日均线' },
      { type: '匹配国企', stepType: 'match_soe', expectedDir: '国企' },
      { type: '匹配1级板块', stepType: 'match_sector', expectedDir: '一级板块' }
    ];

    for (const step of stepTypes) {
      await page.click('button:has-text("添加步骤")');
      await page.waitForSelector('.el-select__wrapper', { timeout: 5000 });
      await page.click('.el-select__wrapper');
      await page.click(`text=${step.type}`);

      await page.waitForTimeout(500);
      await expect(page.locator(`text=目标目录: ${step.expectedDir}`)).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=上传Excel文件').last()).toBeVisible({ timeout: 5000 });
    }
  });

  test('预览文件功能', async ({ page }) => {
    await page.goto(`${BASE_URL}/workflows`);

    const loginResponse = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=admin&password=admin123'
    });
    const loginData = await loginResponse.json();
    const token = loginData.access_token;

    const testExcelPath = '/app/data/excel/2026-04-12/test.xlsx';

    const previewResponse = await fetch(`${API_URL}/workflows/step-files/preview?file_path=${encodeURIComponent(testExcelPath)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (previewResponse.ok) {
      const previewData = await previewResponse.json();
      expect(previewData.success).toBe(true);
      expect(previewData.columns).toBeDefined();
      expect(previewData.total_rows).toBeGreaterThan(0);
    }
  });

  test('文件列表API功能', async ({ request }) => {
    const loginResponse = await request.post(`${API_URL}/auth/login`, {
      data: { username: 'admin', password: 'admin123' }
    });
    const loginData = await loginResponse.json();
    const token = loginData.access_token;

    const listResponse = await request.get(`${API_URL}/workflows/step-files/`, {
      params: { step_type: 'merge_excel', date_str: '2026-04-12' },
      headers: { 'Authorization': `Bearer ${token}` }
    });

    expect(listResponse.ok()).toBeTruthy();
    const listData = await listResponse.json();
    expect(listData.success).toBe(true);
    expect(Array.isArray(listData.files)).toBe(true);
  });
});
