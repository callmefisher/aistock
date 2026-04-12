const { chromium } = require('@playwright/test');

async function testFix() {
  console.log('启动浏览器验证修复...\n');

  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.text().includes('[Debug]') || msg.type() === 'error') {
      console.log('Browser:', msg.text());
    }
  });

  try {
    // 登录
    console.log('1. 登录...');
    await page.goto('http://localhost:7654/login');
    await page.waitForTimeout(1000);
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('button:has-text("登录")');
    await page.waitForTimeout(3000);

    // 进入工作流
    console.log('2. 进入工作流...');
    await page.goto('http://localhost:7654/workflows');
    await page.waitForTimeout(2000);

    // 创建工作流
    console.log('3. 创建工作流...');
    await page.click('button:has-text("创建工作流")');
    await page.waitForTimeout(1500);
    await page.fill('.el-dialog input[placeholder*="工作流名称"]', '验证修复');

    // 添加步骤
    console.log('4. 添加合并当日数据源步骤...');
    await page.click('.el-dialog button:has-text("添加步骤")');
    await page.waitForTimeout(800);

    const select = page.locator('.el-dialog .el-select').last();
    await select.click();
    await page.waitForTimeout(500);

    try {
      await page.waitForSelector('.el-select-dropdown__item', { timeout: 5000 });
      const options = page.locator('.el-select-dropdown__item');
      for (let i = 0; i < (await options.count()); i++) {
        const text = await options.nth(i).textContent();
        if (text.includes('合并当日')) {
          await options.nth(i).click();
          break;
        }
      }
    } catch(e) {
      console.log('下拉选项超时，使用键盘...');
      await page.keyboard.press('Escape');
    }

    await page.waitForTimeout(1500);

    // 选择日期
    console.log('5. 选择日期 2026-04-09...');
    const dateInput = page.locator('.el-dialog .el-date-editor input').first();
    const hasDateInput = await dateInput.count() > 0;
    console.log('日期输入框存在:', hasDateInput);

    if (hasDateInput) {
      await dateInput.click();
      await dateInput.fill('2026-04-09');
      await dateInput.blur();
      await page.waitForTimeout(2000);
      console.log('✓ 已选择日期');
    }

    // 截图
    await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/verify-01.png', fullPage: true });

    // 检查UI元素
    console.log('\n6. 检查文件列表标签...');
    
    const dialogText = await page.locator('.el-dialog').textContent();

    console.log('\n=== UI检查结果 ===');
    console.log('"上传公共数据":', dialogText.includes('上传公共数据'));
    console.log('"公共文件列表":', dialogText.includes('公共文件列表'));
    console.log('"已上传文件":', dialogText.includes('已上传文件'));

    const uploadedLabel = page.locator('.el-dialog >> text=已上传文件');
    console.log('"已上传文件"标签可见:', await uploadedLabel.count() > 0);

    const publicLabel = page.locator('.el-dialog >> text=公共文件列表');
    console.log('"公共文件列表"标签可见:', await publicLabel.count() > 0);

    // 等待API调用完成
    console.log('\n7. 等待API调用...');
    await page.waitForTimeout(3000);

    // 再次检查（API可能已返回）
    const dialogText2 = await page.locator('.el-dialog').textContent();
    console.log('\n8. API调用后检查...');
    console.log('包含文件名(0409):', dialogText2.includes('并购重组事件0409'));
    console.log('包含公共文件:', dialogText2.includes('并购重组事件') || dialogText2.includes('test.xlsx'));

    await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/verify-final.png', fullPage: true });
    console.log('\n=== 测试完成 ===');
    
    await page.waitForTimeout(5000);

  } catch(err) {
    console.error('错误:', err.message);
    await page.screenshot({ path: '/Users/xiayanji/qbox/aistock/frontend/verify-error.png' });
  } finally {
    await browser.close();
  }
}

testFix().catch(err => {
  console.error('失败:', err);
  process.exit(1);
});
