/**
 * 启动 Chrome 调试模式 — 方便 CDP 连接
 * 如果 Chrome 已在运行，先杀再起
 */
const { execSync } = require('child_process');
const http = require('http');

// 1. 检查端口
function checkPort() {
  return new Promise((resolve) => {
    http.get('http://127.0.0.1:9222/json/version', (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d).Browser); } catch(e) { resolve(null); } });
    }).on('error', () => resolve(null));
  });
}

async function main() {
  let browser = await checkPort();
  if (browser) {
    console.log(`✅ Chrome 调试模式已在运行: ${browser}`);
    return;
  }

  // 2. 杀掉现有 Chrome
  console.log('杀掉现有 Chrome 进程...');
  try { execSync('taskkill //F //IM chrome.exe', { stdio: 'ignore' }); } catch(e) {}

  // 3. 等待确保进程已死
  await new Promise(r => setTimeout(r, 2000));

  // 4. 启动 Chrome 调试模式
  console.log('启动 Chrome 调试模式...');
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

  const { spawn } = require('child_process');
  const proc = spawn(chromePath, [
    '--remote-debugging-port=9222',
    '--user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Google\\Chrome\\User Data',
    'https://www.douyin.com',
  ], {
    detached: true,
    stdio: 'ignore',
    windowsHide: false,
  });
  proc.unref();

  // 5. 等待 Chrome 启动
  console.log('等待 Chrome 启动...');
  for (let i = 0; i < 15; i++) {
    await new Promise(r => setTimeout(r, 2000));
    browser = await checkPort();
    if (browser) {
      console.log(`✅ Chrome 调试模式已启动: ${browser}`);
      console.log('');
      console.log('请在 Chrome 窗口中登录抖音，登录完成后告诉我。');
      return;
    }
    process.stdout.write(`.`);
  }
  console.log('\n❌ Chrome 调试模式启动失败');
  console.log('请手动执行: chrome.exe --remote-debugging-port=9222');
}

main().catch(e => { console.error(e); process.exit(1); });
