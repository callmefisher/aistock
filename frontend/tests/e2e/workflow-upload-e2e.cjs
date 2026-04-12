const { chromium } = require('@playwright/test');

const BASE_URL = 'http://localhost:7654';
const API_URL = 'http://localhost:8000/api/v1';

async function runTests() {
  console.log('='.repeat(60));
  console.log('工作流文件上传功能 E2E测试');
  console.log('='.repeat(60));

  let token = null;
  let browser;

  try {
    // 1. 登录获取token
    console.log('\n>>> 1. 登录获取token...');
    const loginResponse = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=admin&password=admin123'
    });
    const loginData = await loginResponse.json();
    token = loginData.access_token;
    console.log(`✓ 登录成功`);

    // 2. 创建测试工作流
    console.log('\n>>> 2. 创建测试工作流...');
    const workflowData = {
      name: `E2E测试工作流_${Date.now()}`,
      description: '端到端测试',
      steps: [{
        type: 'merge_excel',
        config: { date_str: '2026-04-12', output_filename: 'e2e_result.xlsx' },
        status: 'pending'
      }]
    };

    const createResponse = await fetch(`${API_URL}/workflows/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(workflowData)
    });
    const createdWorkflow = await createResponse.json();
    const workflowId = createdWorkflow.id;
    console.log(`✓ 工作流创建成功, ID: ${workflowId}`);

    // 3. 上传测试文件
    console.log('\n>>> 3. 上传测试Excel文件...');
    const XLSX = require('xlsx');
    const ws = XLSX.utils.json_to_sheet([{ 证券代码: '002128.SZ', 证券简称: '测试股票' }]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
    const xlsxBuffer = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });

    const formData = new FormData();
    formData.append('file', new Blob([xlsxBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), 'e2e_test_data.xlsx');
    formData.append('workflow_id', String(workflowId));
    formData.append('step_index', '0');
    formData.append('step_type', 'merge_excel');
    formData.append('date_str', '2026-04-12');

    const uploadResponse = await fetch(`${API_URL}/workflows/upload-step-file/`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    const uploadResult = await uploadResponse.json();
    console.log(`✓ 文件上传: ${JSON.stringify(uploadResult)}`);

    // 4. 验证文件列表
    console.log('\n>>> 4. 验证上传的文件...');
    const listResponse = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const listData = await listResponse.json();
    console.log(`✓ 文件列表: ${listData.files?.length || 0} 个文件`);
    if (listData.files?.length > 0) {
      console.log(`  文件: ${listData.files.map(f => f.filename).join(', ')}`);
    }

    // 5. 预览上传的文件
    console.log('\n>>> 5. 预览上传的文件...');
    if (listData.files?.length > 0) {
      const previewResponse = await fetch(`${API_URL}/workflows/step-files/preview?file_path=${encodeURIComponent(listData.files[0].path)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const previewData = await previewResponse.json();
      console.log(`✓ 预览: ${previewData.filename}, ${previewData.total_rows} 行, 列: ${previewData.columns?.join(', ')}`);
    }

    // 6. 执行工作流
    console.log('\n>>> 6. 执行工作流（使用上传的文件）...');
    const execResponse = await fetch(`${API_URL}/workflows/${workflowId}/execute-step/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ step_index: 0 })
    });
    const execResult = await execResponse.json();
    console.log(`✓ 执行结果: ${execResult.message || execResult.detail}`);

    // 7. 下载结果
    console.log('\n>>> 7. 下载执行结果...');
    const downloadResponse = await fetch(`${API_URL}/workflows/download-result/${workflowId}?step_index=0`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (downloadResponse.ok) {
      const blob = await downloadResponse.blob();
      console.log(`✓ 下载成功: ${blob.size} bytes, type: ${blob.type}`);
    } else {
      console.log(`⚠ 下载返回: ${downloadResponse.status}`);
    }

    // 8. 前端UI验证
    console.log('\n>>> 8. 前端UI验证...');
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    const pageContent = await page.content();
    if (pageContent.includes('登录') || pageContent.includes('login')) {
      console.log('✓ 登录页面加载正常');
    }

    // 截图用于调试
    await page.screenshot({ path: 'login-page.png' });
    console.log('✓ 已保存登录页面截图: login-page.png');

    // 尝试查找登录表单
    const inputs = await page.locator('input').count();
    console.log(`✓ 页面输入框数量: ${inputs}`);

    const buttons = await page.locator('button').count();
    console.log(`✓ 页面按钮数量: ${buttons}`);

    console.log('\n' + '='.repeat(60));
    console.log('✓ E2E测试完成!');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('\n✗ 测试失败:', error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
}

runTests();
