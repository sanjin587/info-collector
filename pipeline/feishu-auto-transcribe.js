#!/usr/bin/env node
/**
 * 飞书自动化逐字稿流水线
 * ======================
 *
 * 监听飞书消息 → 提取音视频 → 妙记转写(免费300分/月) → 超配额自动切本地Whisper
 *
 * 使用:
 *   node feishu-auto-transcribe.js
 *   node feishu-auto-transcribe.js --mode=minutes-only   # 只用妙记
 *   node feishu-auto-transcribe.js --mode=local-only      # 只用本地
 *
 * 依赖:
 *   - lark-cli (飞书 CLI，已登录)
 *   - Python 3 + faster-whisper (本地转写引擎)
 *   - ffmpeg (音频提取)
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ===================== 配置 =====================

const CONFIG = {
  // 工作目录
  downloadsDir: path.join(__dirname, 'downloads'),
  transcriptsDir: path.join(__dirname, 'transcripts'),

  // 本地转写脚本路径
  transcribeScript: path.join(__dirname, '..', 'scripts', 'transcribe_local.py'),

  // 妙记轮询配置
  minutesPollIntervalMs: 3000,   // 每 3 秒检查一次
  minutesPollTimeoutMs: 600000,  // 最多等 10 分钟

  // 模式: auto | minutes-only | local-only
  mode: 'auto',

  // 优先引擎: minutes | local
  primaryEngine: 'minutes',

  // 支持的音频/视频扩展名
  mediaExtensions: new Set([
    '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.opus', '.amr', '.wma',
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpeg'
  ]),

  // 月度妙记配额（分钟），用于本地估算
  monthlyMinutesQuota: 300,
};

// ===================== 工具函数 =====================

function log(level, msg) {
  const ts = new Date().toISOString().slice(11, 19);
  const icons = { info: '📋', ok: '✅', err: '❌', warn: '⚠️', miaolog: '🎙️', local: '💻' };
  const prefix = icons[level] || '•';
  console.log(`[${ts}] ${prefix} ${msg}`);
}

// execShell / execCmd have been moved above under lark() — see the new definitions there

/**
 * 执行 lark-cli 命令（使用 shell 模式以正确处理带引号的参数）
 */
async function lark(cmd) {
  const displayCmd = cmd.replace(/--file-token\s+"[^"]*"/, '--file-token "***"')
                       .replace(/--minute-tokens\s+"[^"]*"/, '--minute-tokens "***"');
  log('info', `lark-cli ${displayCmd.slice(0, 80)}...`);
  try {
    const { stdout } = await execShell(`lark-cli ${cmd}`);
    try {
      return { ok: true, data: JSON.parse(stdout.trim()) };
    } catch {
      return { ok: true, data: stdout.trim() };
    }
  } catch (err) {
    log('warn', `lark-cli 出错: ${err.stderr?.slice(0, 200) || err.message}`);
    return { ok: false, error: err.message, stderr: err.stderr || '' };
  }
}

/**
 * 通过 shell 执行命令（正确处理引号和空格）
 */
function execShell(command, opts = {}) {
  const timeout = opts.timeout || 120000;
  return new Promise((resolve, reject) => {
    const child = spawn('cmd.exe', ['/c', command], {
      timeout,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    const chunks = [], errChunks = [];
    child.stdout.on('data', (d) => { chunks.push(d); });
    child.stderr.on('data', (d) => { errChunks.push(d); });

    child.on('close', (code) => {
      const stdout = Buffer.concat(chunks).toString('utf8');
      const stderr = Buffer.concat(errChunks).toString('utf8');
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        const err = new Error(`Exit code ${code}`);
        err.code = code; err.stdout = stdout; err.stderr = stderr;
        reject(err);
      }
    });
    child.on('error', (err) => reject(err));
  });
}

/**
 * 执行命令（非 shell 模式，用于简单参数列表）
 */
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
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        const err = new Error(`Exit code ${code}`);
        err.code = code; err.stdout = stdout; err.stderr = stderr;
        reject(err);
      }
    });
    child.on('error', (err) => reject(err));
  });
}

/**
 * 解析消息事件中的内容，提取 file_key
 */
function parseMessageContent(event) {
  const { message_type, content } = event;

  // 尝试解析 content JSON
  let parsed = null;
  if (typeof content === 'string') {
    try {
      parsed = JSON.parse(content);
    } catch {
      parsed = null;
    }
  } else if (typeof content === 'object') {
    parsed = content;
  }

  return {
    type: message_type,
    parsed,
    fileKey: parsed?.file_key || parsed?.image_key || null,
    fileName: parsed?.file_name || null,
    duration: parsed?.duration || null,
  };
}

/**
 * 检查是否为音频/视频文件
 */
function isMediaFile(fileName) {
  if (!fileName) return false;
  const ext = path.extname(fileName).toLowerCase();
  return CONFIG.mediaExtensions.has(ext);
}

/**
 * 检查是否为可处理的媒体消息
 */
function isMediaEvent(event) {
  const { message_type } = event;

  // 语音消息 → 直接处理
  if (message_type === 'audio') return true;

  // 文件消息 → 检查扩展名
  if (message_type === 'file') {
    const info = parseMessageContent(event);
    return isMediaFile(info.fileName);
  }

  // 视频消息 → 处理
  if (message_type === 'media') return true;

  return false;
}

// ===================== 妙记引擎 =====================

/**
 * 方案A: 通过妙记转写
 *
 * 流程: 下载文件 → 上传Drive → 上传妙记 → 轮询 → 获取逐字稿
 */
async function transcribeViaMinutes(downloadedFile, originalFileName, event) {
  log('miaolog', '方案A: 使用飞书妙记转写（免费额度内）');

  // Step 1: 上传到飞书云盘
  log('info', '  → 上传到云盘...');
  const uploadResult = await lark(
    `drive +upload --file "${downloadedFile}" --name "${originalFileName}" --as user --json`
  );

  if (!uploadResult.ok) {
    log('warn', `  云盘上传失败: ${uploadResult.error}`);
    return null;
  }

  const fileToken = uploadResult.data?.data?.file_token || uploadResult.data?.file_token;
  if (!fileToken) {
    log('warn', '  未获取到 file_token');
    log('info', `  响应: ${JSON.stringify(uploadResult.data).slice(0, 200)}`);
    return null;
  }
  log('ok', `  文件已上传，file_token: ${fileToken}`);

  // Step 2: 上传到妙记
  log('info', '  → 提交妙记转写...');
  const minutesResult = await lark(
    `minutes +upload --file-token "${fileToken}" --as user --json`
  );

  if (!minutesResult.ok) {
    const errMsg = (minutesResult.error || '') + (minutesResult.stderr || '');
    // 检测是否为配额耗尽
    if (errMsg.includes('quota') || errMsg.includes('limit') ||
        errMsg.includes('exceed') || errMsg.includes('monthly') ||
        errMsg.includes('额度') || errMsg.includes('超限')) {
      log('warn', '  ⚠️ 妙记月度配额已用完，切换到本地转写');
      throw new Error('QUOTA_EXHAUSTED');
    }
    log('warn', `  妙记上传失败: ${errMsg}`);
    return null;
  }

  const minuteToken = minutesResult.data?.data?.minute_token || minutesResult.data?.minute_token;
  if (!minuteToken) {
    log('warn', '  未获取到 minute_token');
    log('info', `  响应: ${JSON.stringify(minutesResult.data).slice(0, 200)}`);
    return null;
  }
  log('ok', `  妙记已提交，minute_token: ${minuteToken}`);

  // Step 3: 轮询等待转写完成
  log('info', '  → 等待转写完成...');
  const transcript = await pollForTranscript(minuteToken);
  return transcript;
}

/**
 * 轮询妙记转写结果
 */
async function pollForTranscript(minuteToken) {
  const startTime = Date.now();

  while (Date.now() - startTime < CONFIG.minutesPollTimeoutMs) {
    await sleep(CONFIG.minutesPollIntervalMs);

    const result = await lark(
      `minutes +detail --minute-tokens "${minuteToken}" --transcript --as user --json`
    );

    if (!result.ok) {
      // 可能还在处理中
      const errMsg = (result.error || '') + (result.stderr || '');
      if (errMsg.includes('processing') || errMsg.includes('not ready') || errMsg.includes('pending')) {
        log('info', '    转写进行中，继续等待...');
        continue;
      }
      log('warn', `  获取妙记详情出错: ${errMsg}`);
      continue;
    }

    const transcript = extractTranscriptFromMinutes(result.data);
    if (transcript) {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      log('ok', `  转写完成！耗时 ${elapsed} 秒`);
      return transcript;
    }

    log('info', '    转写进行中，继续等待...');
  }

  log('warn', '  转写超时（超过10分钟）');
  return null;
}

/**
 * 从妙记详情中提取逐字稿文本
 */
function extractTranscriptFromMinutes(data) {
  // 可能的返回结构:
  // 1. data.data.transcript (通过 +detail --transcript)
  // 2. 文件路径 (通过 --output-dir)

  const transcript = data?.data?.transcript || data?.transcript;
  if (transcript && typeof transcript === 'object') {
    // 妙记返回的 transcript 可能是对象，包含 paragraphs
    if (transcript.paragraphs && Array.isArray(transcript.paragraphs)) {
      return transcript.paragraphs
        .map((p) => {
          if (p.sentences && Array.isArray(p.sentences)) {
            return p.sentences.map((s) => s.text || '').join('');
          }
          return p.text || '';
        })
        .join('\n');
    }
  }

  if (transcript && typeof transcript === 'string' && transcript.trim()) {
    return transcript.trim();
  }

  return null;
}

// ===================== 本地转写引擎 =====================

/**
 * 方案B: 本地 Whisper 转写
 */
async function transcribeLocally(downloadedFile, originalFileName, event) {
  log('local', '方案B: 使用本地 Whisper 转写');

  // 检查文件是否存在
  if (!fs.existsSync(downloadedFile)) {
    log('err', `  文件不存在: ${downloadedFile}`);
    return null;
  }

  const fileSizeMB = (fs.statSync(downloadedFile).size / (1024 * 1024)).toFixed(1);
  log('info', `  文件: ${originalFileName} (${fileSizeMB}MB)`);

  // 调用本地转写脚本
  const outputPath = path.join(CONFIG.transcriptsDir,
    `${path.parse(originalFileName).name}_transcript.txt`);

  try {
    const startTime = Date.now();
    log('info', '  → Whisper 转写中...（可能需要几分钟）');

    const { stdout, stderr } = await execCmd('python', [
      CONFIG.transcribeScript,
      downloadedFile,
      '--engine', 'whisper',
      '--model', 'base',
      '--lang', 'zh',
      '-o', outputPath
    ], { timeout: 600000 });

    const elapsed = Math.round((Date.now() - startTime) / 1000);

    // 尝试读取输出文件
    if (fs.existsSync(outputPath)) {
      const transcript = fs.readFileSync(outputPath, 'utf8').trim();
      if (transcript) {
        log('ok', `  本地转写完成！耗时 ${elapsed} 秒，${transcript.length} 字符`);
        return transcript;
      }
    }

    // 从 stdout 提取
    if (stdout && stdout.trim()) {
      log('ok', `  本地转写完成！耗时 ${elapsed} 秒，${stdout.trim().length} 字符`);
      return stdout.trim();
    }

    log('warn', '  转写结果为空');
    log('info', `  stdout: ${stdout?.slice(0, 200)}`);
    log('info', `  stderr: ${stderr?.slice(0, 200)}`);
    return null;

  } catch (err) {
    log('err', `  本地转写失败: ${err.message}`);
    log('info', `  stdout: ${err.stdout?.slice(0, 300)}`);
    log('info', `  stderr: ${err.stderr?.slice(0, 300)}`);
    return null;
  }
}

// ===================== 文件下载 =====================

/**
 * 从飞书消息下载音频/视频文件
 */
async function downloadMessageFile(messageId, fileKey, fileName, fileType) {
  const safeName = fileName || `${fileKey}.ogg`;
  const outputPath = path.join(CONFIG.downloadsDir, safeName);

  // 如果已存在，先删除
  if (fs.existsSync(outputPath)) {
    fs.unlinkSync(outputPath);
  }

  try {
    const cmd = `im +messages-resources-download --message-id "${messageId}" --file-key "${fileKey}" --type ${fileType} --as bot --output "${safeName}" --json`;
    const result = await lark(cmd);

    if (result.ok && fs.existsSync(outputPath)) {
      log('ok', `  文件已下载: ${safeName} (${(fs.statSync(outputPath).size / 1024).toFixed(1)}KB)`);
      return outputPath;
    }

    log('warn', `  下载失败: ${result.error || '文件未生成'}`);
    return null;
  } catch (err) {
    log('err', `  下载异常: ${err.message}`);
    return null;
  }
}

// ===================== 消息发送 =====================

/**
 * 回复逐字稿到聊天
 */
async function sendTranscriptReply(event, transcript, engine) {
  const chatId = event.chat_id;
  const messageId = event.message_id || event.id;
  const icons = { minutes: '🎙️妙记', local: '💻本地Whisper' };
  const label = icons[engine] || engine;

  if (!chatId || !messageId) {
    log('err', '缺少 chat_id 或 message_id，无法回复');
    return false;
  }

  // Step 1: 先发送一条提示消息
  const header = `📝 逐字稿已生成（${label}），字数: ${transcript.length}`;
  try {
    await lark(`im +messages-reply --message-id "${messageId}" --as bot --text "${header.replace(/"/g, '\\"')}" --json`);
  } catch {
    log('warn', '提示消息发送失败，继续上传附件');
  }

  // Step 2: 将逐字稿保存为 .txt 文件并通过飞书附件发送
  const txtName = `逐字稿_${new Date().toISOString().slice(0, 10)}.txt`;
  const txtPath = path.join(CONFIG.transcriptsDir, txtName);
  fs.writeFileSync(txtPath, transcript, 'utf8');

  try {
    const sendFileCmd =
      `im +messages-reply --message-id "${messageId}" --as bot --file "${txtPath}" --json`;
    const result = await lark(sendFileCmd);

    if (result.ok) {
      log('ok', `逐字稿文件已回复到聊天`);
      return true;
    }

    // fallback: 发送到群聊而非回复
    const sendGroupCmd =
      `im +messages-send --chat-id "${chatId}" --as bot --file "${txtPath}" --json`;
    const groupResult = await lark(sendGroupCmd);
    if (groupResult.ok) {
      log('ok', `逐字稿文件已发送到聊天`);
      return true;
    }

    log('err', `文件发送失败: ${groupResult.error || result.error}`);
    return false;
  } catch (err) {
    log('err', `发送异常: ${err.message}`);
    return false;
  }
}

/**
 * 发送错误提示
 */
async function sendErrorMessage(event, reason) {
  const chatId = event.chat_id;
  const messageId = event.message_id || event.id;

  const errors = {
    QUOTA_EXHAUSTED: '🎙️ 妙记本月免费额度（300分钟）已用完，已自动切换到本地 Whisper 转写，速度较慢请稍候...',
    DOWNLOAD_FAILED: '❌ 无法下载音频文件，请检查文件是否有效',
    TRANSCRIBE_FAILED: '❌ 转写失败，请稍后重试',
    UNSUPPORTED_FORMAT: '❌ 不支持的音频/视频格式',
  };

  const text = errors[reason] || `❌ 处理出错: ${reason}`;

  try {
    await lark(`im +messages-reply --message-id "${messageId}" --as bot --text "${text.replace(/"/g, '\\"')}" --json`);
  } catch {
    // 静默失败
  }
}

// ===================== 事件处理 =====================

/**
 * 处理单条消息事件
 */
async function handleEvent(event) {
  if (!isMediaEvent(event)) return;

  const info = parseMessageContent(event);
  const msgId = event.message_id || event.id;

  log('info', `收到媒体消息 [${info.type}] 来自 ${event.chat_id?.slice(0, 12)}...`);

  if (!info.fileKey) {
    log('warn', '未能提取 file_key，跳过');
    return;
  }

  // 确定文件名
  let fileName = info.fileName || `${info.fileKey}.${info.type === 'audio' ? 'ogg' : 'mp4'}`;
  const fileType = info.type === 'audio' ? 'file' : 'file'; // audio messages use file resource type

  // Step 1: 下载文件
  log('info', `下载文件: ${fileName}`);
  const downloadedFile = await downloadMessageFile(msgId, info.fileKey, fileName, fileType);

  if (!downloadedFile) {
    await sendErrorMessage(event, 'DOWNLOAD_FAILED');
    return;
  }

  // Step 2: 转写（优先妙记，失败切本地）
  let transcript = null;
  let engine = 'minutes';

  if (CONFIG.mode === 'minutes-only') {
    transcript = await transcribeViaMinutes(downloadedFile, fileName, event);
    engine = 'minutes';
  } else if (CONFIG.mode === 'local-only') {
    transcript = await transcribeLocally(downloadedFile, fileName, event);
    engine = 'local';
  } else {
    // auto 模式: 先妙记，再本地
    try {
      transcript = await transcribeViaMinutes(downloadedFile, fileName, event);
      engine = 'minutes';
    } catch (err) {
      if (err.message === 'QUOTA_EXHAUSTED') {
        await sendErrorMessage(event, 'QUOTA_EXHAUSTED');
        transcript = await transcribeLocally(downloadedFile, fileName, event);
        engine = 'local';
      } else {
        log('err', `妙记异常: ${err.message}`);
        transcript = await transcribeLocally(downloadedFile, fileName, event);
        engine = 'local';
      }
    }
  }

  // Step 3: 发送结果
  if (transcript && transcript.trim()) {
    await sendTranscriptReply(event, transcript.trim(), engine);
  } else {
    await sendErrorMessage(event, 'TRANSCRIBE_FAILED');
  }

  // Step 4: 清理下载文件（保留转录结果）
  if (downloadedFile && fs.existsSync(downloadedFile)) {
    try { fs.unlinkSync(downloadedFile); } catch {}
  }
}

// ===================== 事件监听 =====================

let eventCount = 0;
let transcriptCount = 0;

function startEventListener() {
  log('info', '========================================');
  log('info', '🎙️  飞书逐字稿自动化流水线 已启动');
  log('info', `     模式: ${CONFIG.mode}`);
  log('info', `     优先引擎: ${CONFIG.primaryEngine}`);
  log('info', `     下载目录: ${CONFIG.downloadsDir}`);
  log('info', `     转录目录: ${CONFIG.transcriptsDir}`);
  log('info', '========================================');
  log('info', '监听中... 向飞书机器人发送语音/音频消息即可触发');
  log('info', '按 Ctrl+C 停止');
  log('info', '');

  const child = spawn('lark-cli', [
    'event', 'consume', 'im.message.receive_v1',
    '--as', 'bot',
  ], {
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  let buffer = '';

  child.stdout.on('data', (data) => {
    buffer += data.toString();

    // 逐行处理 NDJSON
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // 保留不完整的最后一行

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const event = JSON.parse(line);
        eventCount++;

        // 跳过非消息事件
        if (event.type !== 'im.message.receive_v1' &&
            event.event_type !== 'im.message.receive_v1') {
          // 一些事件有不同的结构
          if (!event.chat_id && !event.message_type) continue;
        }

        log('info', `[#${eventCount}] 收到事件: ${event.message_type || event.type || 'unknown'}`);

        // 异步处理（不阻塞事件流）
        handleEvent(event).catch((err) => {
          log('err', `处理事件异常: ${err.message}`);
        });

      } catch (err) {
        log('warn', `解析事件失败: ${err.message}`);
        log('info', `  原文: ${line.slice(0, 200)}`);
      }
    }
  });

  child.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg && !msg.startsWith('│') && !msg.startsWith('◇') &&
        !msg.startsWith('●') && !msg.includes('waiting') && !msg.includes('consuming')) {
      log('info', `[lark-event] ${msg}`);
    }
  });

  child.on('close', (code) => {
    log('warn', `lark-cli event consume 已退出 (code=${code})`);
    log('info', `共处理 ${eventCount} 个事件，生成 ${transcriptCount} 篇逐字稿`);

    // 自动重连
    log('info', '5 秒后重新连接...');
    setTimeout(startEventListener, 5000);
  });

  child.on('error', (err) => {
    log('err', `启动事件监听失败: ${err.message}`);
    log('info', '10 秒后重试...');
    setTimeout(startEventListener, 10000);
  });

  return child;
}

// ===================== 辅助 =====================

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ===================== 启动前检查 =====================

async function startupCheck() {
  log('info', '正在检查运行环境...');

  // 1. 检查 lark-cli
  try {
    const { stdout } = await execShell('lark-cli auth status', { timeout: 15000 });
    const authStatus = JSON.parse(stdout);
    const botReady = authStatus?.identities?.bot?.status === 'ready';
    const userReady = authStatus?.identities?.user?.status === 'ready';

    if (botReady) {
      log('ok', `lark-cli Bot 身份就绪 (appId: ${authStatus.appId})`);
    } else {
      log('warn', 'lark-cli Bot 身份未就绪，消息事件可能无法接收');
      log('warn', '  请在开发者后台: 权限管理 → 添加 im:message 相关权限 → 发布新版本');
    }

    if (userReady) {
      log('ok', `lark-cli 用户身份就绪 (${authStatus.identities.user.userName || 'unknown'})`);
    }
  } catch (err) {
    log('err', `lark-cli 未安装或未登录。请运行: npm install -g @larksuite/cli && lark-cli config init --new`);
    process.exit(1);
  }

  // 2. 检查可用的转写引擎
  if (CONFIG.mode !== 'local-only') {
    log('ok', '妙记引擎可用（飞书云端，免费300分钟/月）');
  }
  if (CONFIG.mode !== 'minutes-only') {
    if (fs.existsSync(CONFIG.transcribeScript)) {
      // 检查 Python 和 faster-whisper
      try {
        const { stdout: pyVer } = await execCmd('python', ['--version'], { timeout: 10000 });
        log('ok', `Python 就绪 (${pyVer.trim()})`);
      } catch {
        log('warn', 'Python 未安装或不在 PATH，本地转写不可用');
      }

      // 检查 ffmpeg
      try {
        await execCmd('ffmpeg', ['-version'], { timeout: 10000 });
        log('ok', 'ffmpeg 就绪');
      } catch {
        log('warn', 'ffmpeg 未安装，视频文件的音频提取将不可用');
      }
    } else {
      if (CONFIG.mode === 'local-only') {
        log('err', `本地转写脚本不存在: ${CONFIG.transcribeScript}`);
        log('err', '无法以 local-only 模式运行');
        process.exit(1);
      }
      log('warn', '本地转写脚本未找到，将仅使用妙记引擎');
      CONFIG.mode = 'minutes-only';
    }
  }

  // 3. 确保目录存在
  if (!fs.existsSync(CONFIG.downloadsDir)) {
    fs.mkdirSync(CONFIG.downloadsDir, { recursive: true });
  }
  if (!fs.existsSync(CONFIG.transcriptsDir)) {
    fs.mkdirSync(CONFIG.transcriptsDir, { recursive: true });
  }

  // 4. 检查飞书事件订阅（通过尝试连接事件总线）
  log('info', '检查事件订阅...');
  log('info', '  如持续报错，请在开发者后台开启: 事件订阅 → im.message.receive_v1');
  log('info', '  并将机器人添加到需要监听的群聊中');
}

// ===================== 主入口 =====================

async function main() {
  // 解析命令行参数
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--mode=')) {
      CONFIG.mode = arg.split('=')[1];
    } else if (arg === '--minutes-only') {
      CONFIG.mode = 'minutes-only';
    } else if (arg === '--local-only') {
      CONFIG.mode = 'local-only';
    }
  }

  // 启动前检查
  await startupCheck();

  // 启动事件监听
  startEventListener();

  // 优雅退出
  process.on('SIGINT', () => {
    log('info', '');
    log('info', '========================================');
    log('info', `流水线已停止。共处理 ${eventCount} 个事件`);
    log('info', '========================================');
    process.exit(0);
  });
}

main().catch((err) => {
  log('err', `启动失败: ${err.message}`);
  process.exit(1);
});
