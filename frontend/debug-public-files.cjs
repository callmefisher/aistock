const { chromium } = require('@playwright/test');

async function debugPublicFiles() {
  console.log('启动可见浏览器...');
  const browser = await chromium.launch({
    headless: false,
    slowMo: 300
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    console.log('Browser:', msg.text());
  });

  console.log('1. 登录...');
  await page.goto('http://localhost:7654/login');
  await page.waitForTimeout(1000);
  await page.fill('input[placeholder="用户名"]', 'admin');
  await page.fill('input[placeholder="密码"]', 'admin123');
  await page.click('button:has-text("登录")');
  await page.waitForTimeout(3000);

  console.log('2. 进入工作流页面...');
  await page.goto('http://localhost:7654/workflows');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/debug-01-workflows.png', fullPage: true });

  console.log('3. 点击创建工作流...');
  await page.click('button:has-text("创建工作流")');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/debug-02-dialog.png', fullPage: true });

  console.log('4. 填写工作流名称...');
  await page.fill('input[placeholder*="工作流名称"]', '测试工作流');
  await page.waitForTimeout(500);

  console.log('5. 添加步骤...');
  await page.click('button:has-text("添加步骤")');
  await page.waitForTimeout(800);

  console.log('6. 选择步骤类型...');
  const stepSelect = page.locator('.el-select').first();
  await stepSelect.click();
  await page.waitForTimeout(500);

  // 截图下拉选项
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/debug-03-dropdown.png', fullPage: true });

  // 等待下拉选项出现
  await page.waitForSelector('.el-select-dropdown', { timeout: 3000 }).catch(() => {
    console.log('下拉选项未出现');
  });

  // 点击合并Excel选项
  await page.locator('.el-select-dropdown__item').filter({ hasText: '合并Excel' }).click();
  await page.waitForTimeout(2000);

  console.log('7. 截图查看步骤详情...');
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/debug-04-step-detail.png', fullPage: true });

  console.log('8. 滚动到页面底部查看完整步骤...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/debug-05-scrolled.png', fullPage: true });

  console.log('9. 查看整个对话框内容...');
  const dialogContent = await page.locator('.el-dialog').innerHTML().catch(() => '无法获取对话框');
  console.log('对话框包含"上传公共数据":', dialogContent.includes('上传公共数据'));
  console.log('对话框包含"公共文件列表":', dialogContent.includes('公共文件列表'));
  console.log('对话框包含"2025public":', dialogContent.includes('2025public'));

  console.log('10. 尝试获取所有表单项标签...');
  const formLabels = await page.locator('.el-form-item__label').allTextContents();
  console.log('所有表单标签:', formLabels);

  console.log('\n=== 测试完成，请查看截图 ===');
  await page.waitForTimeout(5000);
  await browser.close();
}

debugPublicFiles().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
