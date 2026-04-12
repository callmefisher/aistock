const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const os = require('os');

const BASE_URL = 'http://localhost:7654';
const API_URL = 'http://localhost:8000/api/v1';

async function testUpload() {
  console.log('=== 专门测试上传功能 ===\n');

  // 1. 登录获取token
  console.log('1. 登录...');
  const loginResponse = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=admin&password=admin123'
  });
  const loginData = await loginResponse.json();
  const token = loginData.access_token;
  console.log('✓ 登录成功\n');

  // 2. 检查上传前文件列表
  console.log('2. 检查上传前文件列表...');
  const beforeList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const beforeData = await beforeList.json();
  const beforeCount = beforeData.files?.length || 0;
  console.log(`上传前文件数: ${beforeCount}\n`);

  // 3. 创建测试Excel
  console.log('3. 创建测试Excel...');
  const XLSX = require('xlsx');
  const testData = [{ 证券代码: `TEST${Date.now()}`, 证券简称: '上传测试' }];
  const ws = XLSX.utils.json_to_sheet(testData);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
  const xlsxBuffer = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  const tmpFile = path.join(os.tmpdir(), `upload_test_${Date.now()}.xlsx`);
  fs.writeFileSync(tmpFile, xlsxBuffer);
  console.log(`✓ 测试文件: ${tmpFile}\n`);

  // 4. 浏览器测试
  console.log('4. 浏览器测试...');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push(`[Browser ${msg.type()}]: ${msg.text()}`);
    if (msg.type() === 'error') {
      console.log(`  ERROR: ${msg.text()}`);
    }
  });

  try {
    // 登录
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('button:has-text("登录")');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    console.log('✓ 登录成功');

    // 进入工作流页面
    await page.goto(`${BASE_URL}/workflows`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    console.log('✓ 进入工作流页面');

    // 点击创建工作流
    await page.locator('button:has-text("创建工作流")').click();
    await page.waitForTimeout(1000);
    console.log('✓ 打开对话框');

    // 填写名称
    await page.locator('.el-dialog input[placeholder*="工作流名称"]').fill('上传测试');
    console.log('✓ 填写名称');

    // 添加步骤
    await page.locator('.el-dialog button:has-text("添加步骤")').click();
    await page.waitForTimeout(500);
    await page.locator('.el-dialog .el-select').last().click();
    await page.waitForTimeout(300);
    await page.getByRole('option', { name: '合并当日数据源' }).click();
    await page.waitForTimeout(1000);
    console.log('✓ 添加merge_excel步骤');

    // 查找上传按钮
    console.log('\n5. 查找上传组件...');
    const uploadBtn = page.locator('.el-dialog button:has-text("上传Excel文件")').first();
    const btnCount = await page.locator('.el-dialog button:has-text("上传Excel文件")').count();
    console.log(`上传按钮数量: ${btnCount}`);

    if (btnCount > 0) {
      const isVisible = await uploadBtn.isVisible();
      console.log(`按钮可见: ${isVisible}`);

      // 找到文件输入框
      const fileInput = page.locator('.el-dialog input[type="file"]').first();
      const inputCount = await page.locator('.el-dialog input[type="file"]').count();
      console.log(`文件输入框数量: ${inputCount}`);

      if (inputCount > 0) {
        // 设置文件（这会触发change事件）
        console.log('\n6. 设置文件到输入框...');
        await fileInput.setInputFiles(tmpFile);

        // 等待上传完成
        await page.waitForTimeout(3000);

        // 打印所有控制台消息
        console.log('\n7. 控制台消息:');
        consoleMessages.forEach(msg => console.log(`  ${msg}`));

        // 检查成功消息
        const successMsg = await page.locator('.el-message--success').textContent().catch(() => null);
        if (successMsg) {
          console.log(`\n✓ 成功消息: ${successMsg}`);
        }
      }
    }

    await page.screenshot({ path: 'upload-result.png', fullPage: true });
    console.log('\n✓ 截图: upload-result.png');

  } catch (error) {
    console.error('\n测试错误:', error.message);
    await page.screenshot({ path: 'upload-error.png', fullPage: true });
    console.log('截图: upload-error.png');

    // 打印控制台消息
    console.log('\n控制台消息:');
    consoleMessages.forEach(msg => console.log(`  ${msg}`));
  } finally {
    await browser.close();
  }

  // 8. 验证上传结果
  console.log('\n8. 验证上传结果...');
  const afterList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const afterData = await afterList.json();
  const afterCount = afterData.files?.length || 0;
  console.log(`上传后文件数: ${afterCount}`);

  // 验证
  console.log('\n9. 最终结果:');
  if (afterCount > beforeCount) {
    console.log(`✓✓✓ 上传成功！文件数从 ${beforeCount} 增加到 ${afterCount}`);
  } else {
    console.log(`⚠⚠⚠ 上传可能失败，文件数未增加 (${beforeCount} -> ${afterCount})`);
    console.log('这可能是因为：');
    console.log('  1. 前端没有正确触发上传');
    console.log('  2. 日期没有选择（step.config.date_str 为空）');
    console.log('  3. 上传到了不同的目录');
  }

  // 清理
  if (fs.existsSync(tmpFile)) {
    fs.unlinkSync(tmpFile);
  }

  console.log('\n=== 测试完成 ===');
}

testUpload().catch(console.error);
