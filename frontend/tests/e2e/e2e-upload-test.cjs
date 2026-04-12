const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const os = require('os');

const BASE_URL = 'http://localhost:7654';
const API_URL = 'http://localhost:8000/api/v1';

async function testUpload() {
  console.log('=== 完整端到端上传测试 ===\n');

  // 1. 登录获取token
  console.log('1. 登录获取token...');
  const loginResponse = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=admin&password=admin123'
  });
  const loginData = await loginResponse.json();
  const token = loginData.access_token;
  console.log('✓ 登录成功\n');

  // 2. 检查上传前的文件列表
  console.log('2. 检查上传前文件列表...');
  const beforeList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const beforeData = await beforeList.json();
  const beforeCount = beforeData.files?.length || 0;
  console.log(`上传前文件数: ${beforeCount}\n`);

  // 3. 创建测试Excel文件
  console.log('3. 创建测试Excel文件...');
  const XLSX = require('xlsx');
  const testData = [{ 证券代码: `TEST${Date.now()}`, 证券简称: '端到端测试' }];
  const ws = XLSX.utils.json_to_sheet(testData);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
  const xlsxBuffer = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  const tmpFile = path.join(os.tmpdir(), `e2e_final_${Date.now()}.xlsx`);
  fs.writeFileSync(tmpFile, xlsxBuffer);
  console.log(`✓ 创建测试文件: ${tmpFile}\n`);

  // 4. 启动浏览器测试
  console.log('4. 启动浏览器进行前端测试...');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 添加控制台监听
  page.on('console', msg => {
    console.log(`[Browser]: ${msg.text()}`);
  });

  try {
    // 5. 登录前端
    console.log('5. 登录前端...');
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('button:has-text("登录")');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    console.log('✓ 前端登录成功\n');

    // 6. 进入工作流页面
    console.log('6. 进入工作流页面...');
    await page.goto(`${BASE_URL}/workflows`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    console.log('✓ 进入工作流页面');

    // 7. 点击创建工作流
    console.log('7. 点击创建工作流...');
    await page.locator('button:has-text("创建工作流")').click();
    await page.waitForTimeout(1000);
    console.log('✓ 打开创建对话框');

    // 8. 填写工作流名称
    console.log('8. 填写工作流名称...');
    await page.locator('.el-dialog input[placeholder*="工作流名称"]').fill('端到端测试工作流');
    console.log('✓ 填写名称');

    // 9. 添加merge_excel步骤
    console.log('9. 添加merge_excel步骤...');
    await page.locator('.el-dialog button:has-text("添加步骤")').click();
    await page.waitForTimeout(500);
    await page.locator('.el-dialog .el-select').last().click();
    await page.waitForTimeout(300);
    await page.getByRole('option', { name: '合并当日数据源' }).click();
    await page.waitForTimeout(1000);
    console.log('✓ 添加步骤成功');

    // 10. 选择日期
    console.log('10. 选择日期...');
    await page.locator('.el-dialog input[placeholder="选择数据日期"]').fill('2026-04-12');
    await page.waitForTimeout(500);
    console.log('✓ 选择日期 2026-04-12');

    // 11. 截图看当前状态
    await page.screenshot({ path: 'e2e-step1.png', fullPage: true });
    console.log('✓ 截图: e2e-step1.png');

    // 12. 找到文件输入框并设置文件
    console.log('11. 设置文件到上传组件...');
    const fileInput = page.locator('.el-dialog input[type="file"]').first();
    const inputCount = await page.locator('.el-dialog input[type="file"]').count();
    console.log(`文件输入框数量: ${inputCount}`);

    if (inputCount > 0) {
      await fileInput.setInputFiles(tmpFile);
      console.log('✓ 文件已设置');

      // 等待上传完成
      await page.waitForTimeout(3000);

      // 检查是否有成功消息
      const successMsg = await page.locator('.el-message--success').textContent().catch(() => null);
      if (successMsg) {
        console.log(`✓ 上传成功消息: ${successMsg}`);
      }

      // 截图看结果
      await page.screenshot({ path: 'e2e-step2.png', fullPage: true });
      console.log('✓ 截图: e2e-step2.png');
    }

    // 13. 关闭对话框
    console.log('12. 关闭对话框...');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

  } catch (error) {
    console.error('\n前端测试失败:', error.message);
    await page.screenshot({ path: 'e2e-error.png', fullPage: true });
  } finally {
    await browser.close();
  }

  // 14. 验证上传结果
  console.log('\n13. 验证上传结果...');
  const afterList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const afterData = await afterList.json();
  const afterCount = afterData.files?.length || 0;
  const afterFiles = afterData.files?.map(f => f.filename) || [];
  console.log(`上传后文件数: ${afterCount}`);
  console.log(`文件列表: ${JSON.stringify(afterFiles)}\n`);

  // 验证
  console.log('14. 验证结果:');
  if (afterCount > beforeCount) {
    console.log(`✓ 上传成功！文件数从 ${beforeCount} 增加到 ${afterCount}`);
  } else {
    console.log(`⚠ 文件数未增加 (${beforeCount} -> ${afterCount})`);
  }

  // 15. 清理
  if (fs.existsSync(tmpFile)) {
    fs.unlinkSync(tmpFile);
    console.log('✓ 清理测试文件');
  }

  console.log('\n=== 端到端测试完成 ===');
}

testUpload().catch(console.error);
