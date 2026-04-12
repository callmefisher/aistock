const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const os = require('os');

const BASE_URL = 'http://localhost:7654';
const API_URL = 'http://localhost:8000/api/v1';

async function testUpload() {
  console.log('=== 完整上传功能测试 ===\n');

  // 1. 登录获取token
  console.log('1. 登录获取token...');
  const loginResponse = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=admin&password=admin123'
  });
  const loginData = await loginResponse.json();
  const token = loginData.access_token;
  console.log(`✓ 登录成功\n`);

  // 2. 检查上传前的文件列表
  console.log('2. 检查上传前文件列表...');
  const beforeList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const beforeData = await beforeList.json();
  const beforeCount = beforeData.files?.length || 0;
  const beforeFiles = beforeData.files?.map(f => f.filename) || [];
  console.log(`上传前文件数: ${beforeCount}`);
  console.log(`文件列表: ${JSON.stringify(beforeFiles)}\n`);

  // 3. 创建测试Excel文件
  console.log('3. 创建测试Excel文件...');
  const XLSX = require('xlsx');
  const ws = XLSX.utils.json_to_sheet([{ 证券代码: 'TEST001.SZ', 证券简称: '测试股票A' }]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
  const xlsxBuffer = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  const tmpFile = path.join(os.tmpdir(), `e2e_test_${Date.now()}.xlsx`);
  fs.writeFileSync(tmpFile, xlsxBuffer);
  console.log(`✓ 创建测试文件: ${tmpFile}\n`);

  // 4. 通过API上传文件（使用curl）
  console.log('4. 上传文件到服务器...');

  const { spawn } = require('child_process');

  const curlCmd = [
    'curl', '-X', 'POST',
    '-H', `Authorization: Bearer ${token}`,
    '-F', `file=@${tmpFile}`,
    '-F', 'workflow_id=1',
    '-F', 'step_index=0',
    '-F', 'step_type=merge_excel',
    '-F', 'date_str=2026-04-12',
    `${API_URL}/workflows/upload-step-file/`
  ];

  const result = await new Promise((resolve) => {
    const curl = spawn(curlCmd[0], curlCmd.slice(1));
    let output = '';
    curl.stdout.on('data', (data) => { output += data.toString(); });
    curl.stderr.on('data', (data) => { output += data.toString(); });
    curl.on('close', (code) => resolve({ code, output }));
  });

  console.log(`上传响应: ${result.output}\n`);

  // 5. 检查上传后的文件列表
  console.log('5. 检查上传后文件列表...');
  const afterList = await fetch(`${API_URL}/workflows/step-files/?step_type=merge_excel&date_str=2026-04-12`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const afterData = await afterList.json();
  const afterCount = afterData.files?.length || 0;
  const afterFiles = afterData.files?.map(f => f.filename) || [];
  console.log(`上传后文件数: ${afterCount}`);
  console.log(`文件列表: ${JSON.stringify(afterFiles)}\n`);

  // 6. 验证上传成功
  console.log('6. 验证结果:');
  if (afterCount > beforeCount) {
    console.log(`✓ 上传成功！文件数从 ${beforeCount} 增加到 ${afterCount}`);
    const newFile = afterFiles.find(f => !beforeFiles.includes(f));
    if (newFile) {
      console.log(`✓ 新增文件: ${newFile}`);
    }
  } else {
    console.log(`⚠ 文件数未增加，可能文件名相同或上传失败`);
    const sameFile = afterFiles.find(f => f.includes('e2e_test'));
    if (sameFile) {
      console.log(`✓ 测试文件 ${sameFile} 已存在`);
    }
  }

  // 7. 清理测试文件
  if (fs.existsSync(tmpFile)) {
    fs.unlinkSync(tmpFile);
    console.log(`✓ 清理测试文件`);
  }

  console.log('\n=== 测试完成 ===');
}

testUpload().catch(console.error);
