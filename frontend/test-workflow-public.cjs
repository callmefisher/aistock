const { chromium } = require('@playwright/test');

async function testMergeExcel() {
  console.log('启动可见浏览器（慢速模式）...');
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

  console.log('3. 点击创建工作流按钮...');
  await page.click('button:has-text("创建工作流")');
  await page.waitForTimeout(1500);

  console.log('4. 填写工作流名称...');
  await page.fill('input[placeholder*="工作流名称"]', '测试工作流');
  await page.waitForTimeout(500);

  console.log('5. 添加步骤...');
  await page.click('button:has-text("添加步骤")');
  await page.waitForTimeout(800);

  console.log('6. 选择步骤类型 - 点击下拉框...');
  const stepSelect = page.locator('.el-select').last();
  await stepSelect.click();
  await page.waitForTimeout(1000);

  console.log('7. 等待下拉选项出现并点击"合并Excel"...');
  try {
    await page.waitForSelector('.el-select-dropdown__item', { timeout: 5000 });
    const items = await page.locator('.el-select-dropdown__item').all();
    console.log('下拉选项数量:', items.length);
    for (const item of items) {
      const text = await item.textContent();
      console.log('  选项:', text);
      if (text.includes('合并Excel') || text.includes('合并当日')) {
        await item.click();
        console.log('点击了:', text);
        break;
      }
    }
  } catch (e) {
    console.log('下拉选项超时');
    await page.keyboard.press('Escape');
  }

  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/test-merge-01.png', fullPage: true });

  console.log('8. 检查对话框内容...');
  const bodyText = await page.textContent('.el-dialog');
  console.log('对话框包含"上传公共数据":', bodyText.includes('上传公共数据'));
  console.log('对话框包含"公共文件列表":', bodyText.includes('公共文件列表'));
  console.log('对话框包含"已上传文件":', bodyText.includes('已上传文件'));

  console.log('\n=== 测试完成 ===');
  await page.waitForTimeout(3000);
  await browser.close();
}

testMergeExcel().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
