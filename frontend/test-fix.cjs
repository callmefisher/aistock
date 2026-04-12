const { chromium } = require('@playwright/test');

async function testFix() {
  console.log('启动可见浏览器测试...');
  const browser = await chromium.launch({
    headless: false,
    slowMo: 300
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error' || msg.text().includes('[Debug]')) {
      console.log('Browser:', msg.text());
    }
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

  console.log('6. 选择步骤类型 - 合并当日数据源...');
  const stepSelect = page.locator('.el-select').last();
  await stepSelect.click();
  await page.waitForTimeout(1000);

  try {
    await page.waitForSelector('.el-select-dropdown__item', { timeout: 5000 });
    const items = await page.locator('.el-select-dropdown__item').all();
    for (const item of items) {
      const text = await item.textContent();
      if (text.includes('合并当日') || text.includes('merge_excel')) {
        await item.click();
        break;
      }
    }
  } catch (e) {
    console.log('下拉选项超时');
  }

  await page.waitForTimeout(2000);

  console.log('7. 检查UI元素...');
  const bodyText = await page.textContent('.el-dialog');

  console.log('\n=== UI检查结果 ===');
  console.log('"上传公共数据":', bodyText.includes('上传公共数据'));
  console.log('"公共文件列表":', bodyText.includes('公共文件列表'));
  console.log('"已上传文件":', bodyText.includes('已上传文件'));

  // 检查公共文件列表是否显示（即使为空）
  const publicListLabel = page.locator('text=公共文件列表');
  const hasPublicList = await publicListLabel.count() > 0;
  console.log('"公共文件列表"标签可见:', hasPublicList);

  // 检查已上传文件标签
  const uploadedLabel = page.locator('text=已上传文件');
  const hasUploaded = await uploadedLabel.count() > 0;
  console.log('"已上传文件"标签可见:', hasUploaded);

  console.log('\n=== 测试完成 ===');
  await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/test-fix-result.png', fullPage: true });

  await page.waitForTimeout(3000);
  await browser.close();
}

testFix().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
