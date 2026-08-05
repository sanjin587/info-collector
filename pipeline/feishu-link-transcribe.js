#!/usr/bin/env node
/**
 * 飞书 → 视频链接 → 逐字稿 → 知识库 全自动流水线
 * ==============================================
 *
 * 流程:
 *   飞书发视频链接 → yt-dlp 下载视频 → 妙记转写(免费) → 超配额切本地Whisper
 *   → 逐字稿保存 Obsidian → 回复飞书
 *
 * 使用:
 *   node feishu-link-transcribe.js
 *
 * 依赖:
 *   - lark-cli (飞书 CLI)
 *   - yt-dlp (视频下载)
 *   - Python 3 + faster-whisper (本地转写)
 *   - ffmpeg (音频提取)
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// ===================== 配置 =====================

const CONFIG = {
  // 工作目录
  downloadsDir: path.join(__dirname, 'video_downloads'),
  transcriptsDir: path.join(__dirname, 'transcripts'),

  // 本地转写脚本
  transcribeScript: path.join(__dirname, '..', 'scripts', 'transcribe_local.py'),

  // Obsidian 知识库路径
  obsidianVault: 'd:/知识库/知识库',
  obsidianTarget: '05_内容生产库/三金AI实验室_30天万粉作战计划/逐字稿',

  // 妙记轮询
  minutesPollIntervalMs: 3000,
  minutesPollTimeoutMs: 600000,

  // 支持的视频平台链接正则
  linkPatterns: [
    // 抖音
    { name: '抖音', regex: /https?:\/\/(?:www\.)?(?:douyin\.com\/video\/\d+|v\.douyin\.com\/[a-zA-Z0-9_-]+)/ },
    // 抖音分享链接（包含完整文案）
    { name: '抖音', regex: /https?:\/\/(?:www\.)?douyin\.com\/user\/[^\s]+/ },
    // B站
    { name: 'B站', regex: /https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[a-zA-Z0-9]+/ },
    // 视频号
    { name: '视频号', regex: /https?:\/\/(?:www\.)?weixin\.qq\.com\/sph\/[a-zA-Z0-9]+/ },
    // YouTube
    { name: 'YouTube', regex: /https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)[a-zA-Z0-9_-]+/ },
    // 小红书
    { name: '小红书', regex: /https?:\/\/(?:www\.)?xiaohongshu\.com\/[^\s]+/ },
    // 快手
    { name: '快手', regex: /https?:\/\/(?:www\.)?kuaishou\.com\/[^\s]+/ },
  ],
};

// ===================== 日志 =====================

function log(level, msg) {
  const ts = new Date().toISOString().slice(11, 19);
  const icons = { info: '📋', ok: '✅', err: '❌', warn: '⚠️', dl: '📥', trans: '🎙️', obs: '📝' };
  console.log(`[${ts}] ${icons[level] || '•'} ${msg}`);
}

// ===================== 命令执行 =====================

function execShell(command, opts = {}) {
  const timeout = opts.timeout || 120000;
  return new Promise((resolve, reject) => {
    const child = spawn('cmd.exe', ['/c', command], { timeout, stdio: ['pipe', 'pipe', 'pipe'] });
    const chunks = [], errChunks = [];
    child.stdout.on('data', (d) => { chunks.push(d); });
    child.stderr.on('data', (d) => { errChunks.push(d); });
    child.on('close', (code) => {
      const stdout = Buffer.concat(chunks).toString('utf8');
      const stderr = Buffer.concat(errChunks).toString('utf8');
      if (code === 0) resolve({ stdout, stderr });
      else { const e = new Error(`code ${code}`); e.stdout = stdout; e.stderr = stderr; reject(e); }
    });
    child.on('error', reject);
  });
}

function execCmd(command, args = [], opts = {}) {
  const timeout = opts.timeout || 120000;
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...opts, timeout, stdio: ['pipe', 'pipe', 'pipe'] });
    const chunks = [], errChunks = [];
    child.stdout.on('data', (d) => { chunks.push(d); });
    child.stderr.on('data', (d) => { errChunks.push(d); });
    child.on('close', (code) => {
      const stdout = Buffer.concat(chunks).toString('utf8');
      const stderr = Buffer.concat(errChunks).toString('utf8');
      if (code === 0) resolve({ stdout, stderr });
      else { const e = new Error(`code ${code}`); e.stdout = stdout; e.stderr = stderr; reject(e); }
    });
    child.on('error', reject);
  });
}

/**
 * 调用 lark-cli
 * 用 PowerShell + 完整路径避免中文编码和 PATH 问题
 */
const LARK_BIN = 'C:\\Program Files\\nodejs\\lark-cli.cmd';

async function lark(cmd) {
  const short = cmd.replace(/om_[a-z0-9]+/g, '***').replace(/file_[a-z0-9]+/g, 'f***').slice(0, 90);
  log('info', `lark ${short}`);
  try {
    const { stdout } = await execCmd('powershell.exe', [
      '-NoProfile', '-Command',
      `& "${LARK_BIN}" ${cmd}`
    ]);
    try { return { ok: true, data: JSON.parse(stdout.trim()) }; }
    catch { return { ok: true, data: stdout.trim() }; }
  } catch (err) {
    const msg = err.stderr?.slice(0, 250) || err.message;
    log('warn', `lark: ${msg}`);
    return { ok: false, error: err.message, stderr: err.stderr || '' };
  }
}

// ===================== 链接识别 =====================

function detectLink(text) {
  for (const platform of CONFIG.linkPatterns) {
    const match = text.match(platform.regex);
    if (match) return { url: match[0], platform: platform.name };
  }
  return null;
}

// ===================== 视频下载 (yt-dlp) =====================

async function downloadVideo(url, platform) {
  log('dl', `下载视频: ${platform} - ${url}`);

  const ts = Date.now();
  const outTemplate = path.join(CONFIG.downloadsDir, `%(id)s_${ts}.%(ext)s`);

  // 抖音需要登录态，尝试三种策略
  const strategies = [
    { label: '直接下载', args: [] },
    { label: 'Chrome Cookie', args: ['--cookies-from-browser', 'chrome'] },
    { label: 'Edge Cookie', args: ['--cookies-from-browser', 'edge'] },
  ];

  if (platform !== '抖音') strategies.splice(1); // 非抖音只用直接下载

  for (const strat of strategies) {
    try {
      log('info', `  策略: ${strat.label}`);
      const { stdout, stderr } = await execCmd('yt-dlp', [
        '-f', 'bestvideo*+bestaudio/best',
        '--merge-output-format', 'mp4',
        '-o', outTemplate,
        '--no-playlist',
        '--socket-timeout', '30',
        '--retries', '2',
        ...strat.args,
        url,
      ], { timeout: 300000 });

      // 找下载到的文件
      const dir = CONFIG.downloadsDir;
      const files = fs.readdirSync(dir)
        .filter(f => f.includes(`_${ts}.`))
        .map(f => path.join(dir, f))
        .sort((a, b) => fs.statSync(b).mtime - fs.statSync(a).mtime);

      if (files.length > 0) {
        const file = files[0];
        const sizeMB = (fs.statSync(file).size / 1024 / 1024).toFixed(1);
        log('ok', `下载完成: ${path.basename(file)} (${sizeMB}MB)`);
        let title = '';
        const titleMatch = stdout.match(/\[download\] Destination: (.+)/);
        if (titleMatch) title = path.basename(titleMatch[1], path.extname(titleMatch[1]));
        return { file, title };
      }

      log('warn', `  下载后未找到文件，尝试下一个策略...`);
    } catch (err) {
      const errMsg = (err.stderr || err.message).slice(0, 200);
      log('warn', `  ${strat.label} 失败: ${errMsg}`);

      // Cookie DB 被锁 → 尝试下一个
      if (errMsg.includes('Could not copy') || errMsg.includes('cookies')) {
        log('info', '  Cookie DB 被锁，尝试下一个...');
        continue;
      }
      // 需要登录 → 继续重试
      if (errMsg.includes('Fresh cookies') || errMsg.includes('logged in')) {
        log('info', '  需要登录，尝试下一个...');
        continue;
      }
    }
  }

  // 特殊情况：B站等可能不需要 cookie
  if (platform !== '抖音') {
    log('err', '下载失败，请检查链接是否有效');
  } else {
    log('err', '抖音下载失败：需要登录。请确保 Chrome 或 Edge 已登录抖音。');
  }
  return null;
}

// ===================== 妙记转写 =====================

async function transcribeViaMinutes(videoFile, fileName) {
  log('trans', '方案A: 飞书妙记转写（免费额度内）');

  // 上传到云盘
  log('info', '  上传到飞书云盘...');
  const upload = await lark(
    `drive +upload --file "${videoFile}" --name "${fileName}" --as user --json`
  );
  const ft = upload.data?.data?.file_token || upload.data?.file_token;
  if (!ft) { log('warn', '  云盘上传失败'); return null; }
  log('ok', `  已上传 file_token=${ft}`);

  // 提交妙记
  log('info', '  提交妙记转写...');
  const min = await lark(
    `minutes +upload --file-token "${ft}" --as user --json`
  );
  const mt = min.data?.data?.minute_token || min.data?.minute_token;
  if (!mt) {
    const err = (min.error || '') + (min.stderr || '');
    if (/(quota|limit|exceed|monthly|额度|超限)/i.test(err)) {
      log('warn', '  ⚠️ 妙记月度配额已用完');
      throw new Error('QUOTA_EXHAUSTED');
    }
    log('warn', `  妙记提交失败: ${err.slice(0, 200)}`);
    return null;
  }
  log('ok', `  妙记已提交 minute_token=${mt}`);

  // 轮询等待
  return await pollMinutes(mt);
}

async function pollMinutes(minuteToken) {
  const start = Date.now();
  while (Date.now() - start < CONFIG.minutesPollTimeoutMs) {
    await sleep(CONFIG.minutesPollIntervalMs);
    const r = await lark(
      `minutes +detail --minute-tokens "${minuteToken}" --transcript --as user --json`
    );
    if (!r.ok) continue;

    // 尝试多种结构提取逐字稿
    const d = r.data;
    const t = d?.data?.transcript || d?.transcript;
    if (!t) continue;

    // 对象结构: paragraphs → sentences
    if (typeof t === 'object') {
      if (t.paragraphs) {
        const text = t.paragraphs.map(p =>
          (p.sentences || []).map(s => s.text || '').join('')
        ).join('\n');
        if (text.trim()) {
          log('ok', `  转写完成 ${text.length}字`);
          return text.trim();
        }
      }
    }
    // 字符串
    if (typeof t === 'string' && t.trim()) {
      log('ok', `  转写完成 ${t.trim().length}字`);
      return t.trim();
    }
  }
  log('warn', '  转写超时');
  return null;
}

// ===================== 本地转写 =====================

async function transcribeLocally(videoFile, fileName) {
  log('trans', '方案B: 本地 Whisper 转写');

  if (!fs.existsSync(CONFIG.transcribeScript)) {
    log('err', '本地转写脚本不存在');
    return null;
  }

  const outName = path.parse(fileName).name + '_逐字稿.txt';
  const outPath = path.join(CONFIG.transcriptsDir, outName);

  try {
    const start = Date.now();
    log('info', '  Whisper 转写中...');

    await execCmd('python', [
      CONFIG.transcribeScript,
      videoFile,
      '--engine', 'whisper',
      '--model', 'base',
      '--lang', 'zh',
      '-o', outPath,
    ], { timeout: 600000 });

    if (fs.existsSync(outPath)) {
      const text = fs.readFileSync(outPath, 'utf8').trim();
      const elapsed = Math.round((Date.now() - start) / 1000);
      log('ok', `  完成! ${elapsed}秒 ${text.length}字`);
      return text;
    }

    log('warn', '  输出文件为空');
    return null;
  } catch (err) {
    log('err', `  转写失败: ${err.stderr?.slice(0, 200) || err.message}`);
    return null;
  }
}

// ===================== Obsidian 保存 =====================

function saveToObsidian(transcript, info) {
  log('obs', '保存到 Obsidian 知识库...');

  const vaultDir = path.join(CONFIG.obsidianVault, CONFIG.obsidianTarget);
  if (!fs.existsSync(vaultDir)) {
    fs.mkdirSync(vaultDir, { recursive: true });
    log('info', `  创建目录: ${vaultDir}`);
  }

  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10);
  const timeStr = now.toISOString().slice(0, 19).replace('T', ' ');

  // 安全的文件名
  const safeTitle = (info.title || info.platform + '_' + Date.now())
    .replace(/[\/\\:*?"<>|]/g, '_').slice(0, 50);
  const fileName = `${info.platform}_${safeTitle}_${dateStr}.md`;
  const filePath = path.join(vaultDir, fileName);

  const yamlFront = [
    '---',
    `title: "${info.title || '未命名'}"`,
    `platform: ${info.platform}`,
    `source: ${info.url}`,
    `date: ${dateStr}`,
    `created: ${timeStr}`,
    `engine: ${info.engine}`,
    'tags:',
    '  - 逐字稿',
    `  - ${info.platform}`,
    '---',
  ].join('\n');

  const body = [
    '',
    `# ${info.title || info.platform + '视频逐字稿'}`,
    '',
    `> **来源**: ${info.url}`,
    `> **平台**: ${info.platform}`,
    `> **引擎**: ${info.engine}`,
    `> **日期**: ${dateStr}`,
    '',
    '---',
    '',
    '## 逐字稿',
    '',
    transcript,
  ].join('\n');

  fs.writeFileSync(filePath, yamlFront + '\n' + body, 'utf8');
  log('ok', `已保存: ${fileName}`);
  return filePath;
}

// ===================== 飞书回复 =====================

async function sendReply(event, transcript, info) {
  const chatId = event.chat_id;
  const messageId = event.message_id || event.id;
  const engineLabel = info.engine === 'minutes' ? '🎙️妙记' : '💻本地Whisper';

  // 发送摘要
  const summary = [
    `📝 **逐字稿已生成**`,
    ``,
    `🔗 链接: ${info.url}`,
    `🎬 平台: ${info.platform}`,
    `⚙️ 引擎: ${engineLabel}`,
    `📊 字数: ${transcript.length}`,
    `📁 已保存: Obsidian → ${CONFIG.obsidianTarget}`,
  ].join('\n');

  await lark(
    `im +messages-reply --message-id "${messageId}" --as bot --text "${summary.replace(/"/g, '\\"')}" --json`
  );

  // 逐字稿保存为文件发送
  const txtName = `逐字稿_${info.platform}_${new Date().toISOString().slice(0, 10)}.txt`;
  const txtPath = path.join(CONFIG.transcriptsDir, txtName);
  fs.writeFileSync(txtPath, transcript, 'utf8');

  // 尝试作为文件附件发送
  const fileResult = await lark(
    `im +messages-reply --message-id "${messageId}" --as bot --file "${txtPath}" --json`
  );

  if (!fileResult.ok) {
    // 直接发文本（截断到合理长度）
    const maxLen = 2000;
    let preview = transcript.slice(0, maxLen);
    if (transcript.length > maxLen) preview += '\n\n...（完整内容已保存到Obsidian）';
    await lark(
      `im +messages-send --chat-id "${chatId}" --as bot --text "${preview.replace(/"/g, '\\"').replace(/\n/g, '\\n')}" --json`
    );
  }
}

// ===================== 事件处理 =====================

async function handleMessage(event) {
  const msgType = event.message_type;
  const content = event.content;
  const text = typeof content === 'string' ? content : JSON.stringify(content);

  // 检测视频链接
  const detected = detectLink(text);
  if (!detected) return; // 不是视频链接，忽略

  log('info', '');
  log('info', '═══════════════════════════════════════');
  log('info', `🎬 检测到视频链接: [${detected.platform}] ${detected.url}`);
  log('info', `   来自: ${event.chat_type === 'p2p' ? '私聊' : '群聊'}`);
  log('info', '═══════════════════════════════════════');

  // 发送处理中提示
  await lark(
    `im +messages-reply --message-id "${event.message_id}" --as bot --text "🔍 收到 ${detected.platform} 链接，开始下载视频..." --json`
  );

  // Step 1: 下载视频
  const dl = await downloadVideo(detected.url, detected.platform);
  if (!dl) {
    await lark(
      `im +messages-reply --message-id "${event.message_id}" --as bot --text "❌ 视频下载失败，请检查链接是否有效" --json`
    );
    return;
  }

  // Step 2: 转写（妙记优先 → 本地兜底）
  let transcript = null;
  let engine = 'minutes';
  const fileName = path.basename(dl.file);

  try {
    transcript = await transcribeViaMinutes(dl.file, fileName);
    engine = 'minutes';
  } catch (err) {
    if (err.message === 'QUOTA_EXHAUSTED') {
      await lark(
        `im +messages-reply --message-id "${event.message_id}" --as bot --text "🎙️ 妙记本月免费额度已用完，自动切换本地 Whisper 转写，稍候..." --json`
      );
    }
    transcript = await transcribeLocally(dl.file, fileName);
    engine = 'local';
  }

  // 兜底：妙记返回 null 也走本地
  if (!transcript) {
    transcript = await transcribeLocally(dl.file, fileName);
    engine = 'local';
  }

  if (!transcript) {
    await lark(
      `im +messages-reply --message-id "${event.message_id}" --as bot --text "❌ 转写失败，请稍后重试" --json`
    );
    return;
  }

  // Step 3: 保存 Obsidian
  saveToObsidian(transcript, {
    title: dl.title || detected.platform + '视频',
    platform: detected.platform,
    url: detected.url,
    engine,
  });

  // Step 4: 回复飞书
  await sendReply(event, transcript, {
    platform: detected.platform,
    url: detected.url,
    engine,
  });

  // 清理视频文件
  try { fs.unlinkSync(dl.file); log('info', '已清理临时视频文件'); } catch {}

  log('info', '═══════════════════════════════════════');
  log('ok', `完成! ${detected.platform} → ${transcript.length}字逐字稿`);
}

// ===================== 事件监听 =====================

function startListener() {
  log('info', '');
  log('info', '╔══════════════════════════════════════════╗');
  log('info', '║  🎬 飞书 → 逐字稿 → 知识库 流水线      ║');
  log('info', '╠══════════════════════════════════════════╣');
  log('info', '║  发视频链接到飞书机器人 → 自动处理      ║');
  log('info', '║  支持: 抖音 B站 视频号 YouTube 小红书    ║');
  log('info', '║  引擎: 妙记(免费) → 本地Whisper(兜底)   ║');
  log('info', '║  存档: Obsidian 知识库                  ║');
  log('info', '╚══════════════════════════════════════════╝');
  log('info', '');
  log('info', '等待消息... 按 Ctrl+C 停止');

  const child = spawn('cmd.exe', ['/c',
    `"${LARK_BIN}" event consume im.message.receive_v1 --as bot`
  ], { stdio: ['pipe', 'pipe', 'pipe'] });

  let buffer = '';

  child.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line);
        if (event.message_type === 'text') {
          handleMessage(event).catch(e => log('err', `处理异常: ${e.message}`));
        }
      } catch {}
    }
  });

  child.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg && !/│|◇|●|waiting|consuming|ready/i.test(msg)) {
      log('info', `[event] ${msg.slice(0, 100)}`);
    }
  });

  child.on('close', (code) => {
    log('warn', `事件连接断开 (code=${code})，5秒后重连...`);
    setTimeout(startListener, 5000);
  });

  child.on('error', (err) => {
    log('err', `启动失败: ${err.message}，10秒后重试...`);
    setTimeout(startListener, 10000);
  });
}

// ===================== 启动 =====================

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// 确保目录存在
[CONFIG.downloadsDir, CONFIG.transcriptsDir].forEach(d => {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
});

// 检查 yt-dlp
execShell('yt-dlp --version', { timeout: 10000 })
  .then(({ stdout }) => log('ok', `yt-dlp v${stdout.trim()} 就绪`))
  .catch(() => log('err', 'yt-dlp 未安装，请运行: pip install yt-dlp'))
  .finally(() => startListener());

process.on('SIGINT', () => {
  log('info', '\n流水线已停止');
  process.exit(0);
});
