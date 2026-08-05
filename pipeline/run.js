#!/usr/bin/env node
/**
 * 飞书 → 视频链接 → 逐字稿 → Obsidian
 * =====================================
 *
 * 抖音: dytranscript.py (Chrome CDP, 无需下载, 直接读字幕)
 * 其他: yt-dlp 下载 → Whisper 本地转写
 *
 * 前提:
 *   1. lark-cli 已登录
 *   2. Chrome --remote-debugging-port=9222 (抖音需要)
 *   3. Chrome 已登录抖音
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// ========== 配置 ==========
const LARK = 'C:\\Program Files\\nodejs\\lark-cli.cmd';
const SCRIPTS = path.join(__dirname, '..', 'scripts');
const DL = path.join(__dirname, 'downloads');
const TXT = path.join(__dirname, 'transcripts');
const OBS = 'D:/知识库/知识库/05_内容生产库/三金AI实验室_30天万粉作战计划/逐字稿';

[DL, TXT, OBS].forEach(d => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); });

// ========== 日志 ==========
function log(lvl, msg) {
  const t = new Date().toISOString().slice(11, 19);
  const icons = { info:'📋', ok:'✅', err:'❌', warn:'⚠️' };
  console.log(`[${t}] ${icons[lvl]||'•'} ${msg}`);
}

// ========== 指挥中心上报 ==========
const CMD_URL = 'http://localhost:3000/api/pipeline/event';
let httpMod;
try { httpMod = require('http'); } catch { httpMod = null; }

function report(type, message, extra = {}) {
  const payload = JSON.stringify({
    type,
    pipelineId: 'feishu-transcribe',
    agentRole: 'collector',
    agentName: '信息采集官',
    message,
    data: {
      pipelineId: 'feishu-transcribe',
      ...extra,
    },
  });

  // 用 http 模块发请求，不阻塞
  if (httpMod) {
    const req = httpMod.request(
      CMD_URL,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } },
      () => {} // no-op — 不关心响应
    );
    req.on('error', () => {}); // 指挥中心不在线时静默失败
    req.write(payload);
    req.end();
  }
}

// ========== 命令执行 ==========
function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const c = spawn(cmd, args, { ...opts, timeout: opts.timeout || 120000,
      stdio: ['pipe', 'pipe', 'pipe'] });
    const out = [], err = [];
    c.stdout.on('data', d => out.push(d));
    c.stderr.on('data', d => err.push(d));
    c.on('close', code => {
      const so = Buffer.concat(out).toString('utf8');
      const se = Buffer.concat(err).toString('utf8');
      if (code === 0) resolve({ stdout: so, stderr: se });
      else { const e = new Error(`exit ${code}`); e.stdout = so; e.stderr = se; reject(e); }
    });
    c.on('error', reject);
  });
}

// ========== lark-cli (直接 spawn, 无 shell, 无引号问题) ==========
async function lark(...args) {
  const display = args.join(' ').replace(/om_[a-z0-9]+/g, '***').slice(0, 90);
  log('info', display);
  try {
    const { stdout } = await run(LARK, args);
    try { return { ok: true, data: JSON.parse(stdout.trim()) }; }
    catch { return { ok: true, data: stdout.trim() }; }
  } catch (err) {
    log('warn', `lark: ${err.stderr?.slice(0, 150) || err.message}`);
    return { ok: false, error: err.stderr?.slice(0, 200) || err.message };
  }
}

// ========== 链接检测 ==========
const LINK_PATTERNS = [
  ['抖音', /https?:\/\/(?:www\.)?(?:douyin\.com\/video\/\d+|v\.douyin\.com\/[\w-]+)/],
  ['B站', /https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[\w]+/],
  ['YouTube', /https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)[\w-]+/],
  ['视频号', /https?:\/\/(?:www\.)?weixin\.qq\.com\/sph\/[\w]+/],
  ['小红书', /https?:\/\/(?:www\.)?xiaohongshu\.com\/\S+/],
];

function detect(text) {
  for (const [name, re] of LINK_PATTERNS) {
    const m = text.match(re);
    if (m) return { platform: name, url: m[0] };
  }
  return null;
}

// ========== 抖音: dytranscript.py (Chrome CDP) ==========
async function douyinTranscript(url) {
  log('info', '🎯 dytranscript.py (Chrome CDP)...');
  try {
    const { stdout } = await run('python', [
      path.join(SCRIPTS, 'dytranscript.py'), url
    ], { timeout: 60000, cwd: SCRIPTS });

    // Parse output
    let author = '', desc = '', fullText = '';
    const lines = stdout.split('\n');
    for (const line of lines) {
      if (line.includes('👤')) author = line.split('👤')[1]?.trim() || '';
    }
    // Check for saved file
    const outDir = path.join(require('os').homedir(), '.dytranscript_output');
    if (fs.existsSync(outDir)) {
      const files = fs.readdirSync(outDir)
        .filter(f => f.startsWith('dy_') && f.endsWith('.txt'))
        .map(f => path.join(outDir, f))
        .sort((a, b) => fs.statSync(b).mtime - fs.statSync(a).mtime);
      if (files.length > 0) {
        const content = fs.readFileSync(files[0], 'utf8');
        const m = content.match(/逐字稿:\n([\s\S]+)/);
        fullText = m ? m[1].trim() : content.trim();
        const dm = content.match(/文案:\n([\s\S]*?)(?:\n\n逐字稿|$)/);
        desc = dm ? dm[1].trim() : '';
      }
    }

    // Fallback: extract from stdout
    if (!fullText) {
      const segs = [];
      for (const line of lines) {
        const m = line.match(/^\s*\[\d{2}:\d{2}\]\s+(.+)/);
        if (m) segs.push(m[1]);
      }
      fullText = segs.join('');
    }

    return fullText ? { transcript: fullText, author, desc } : null;
  } catch (err) {
    log('err', `dytranscript: ${err.stderr?.slice(0, 200) || err.message}`);
    return null;
  }
}

// ========== 其他平台: yt-dlp + Whisper ==========
async function downloadAndTranscribe(url) {
  log('info', '📥 yt-dlp...');
  const ts = Date.now();
  const out = path.join(DL, `%(id)s_${ts}.%(ext)s`);
  try {
    await run('yt-dlp', ['-f', 'best', '-o', out, '--no-playlist', url], { timeout: 300000 });
  } catch (err) {
    log('err', `yt-dlp: ${err.stderr?.slice(0, 200) || err.message}`);
    return null;
  }

  // Find downloaded file
  const files = fs.readdirSync(DL)
    .filter(f => f.includes(`_${ts}.`))
    .map(f => path.join(DL, f))
    .sort((a, b) => fs.statSync(b).mtime - fs.statSync(a).mtime);
  if (files.length === 0) return null;

  const videoFile = files[0];
  log('ok', `下载: ${path.basename(videoFile)}`);

  // Whisper
  log('info', '🎙️ Whisper...');
  try {
    await run('python', [
      path.join(SCRIPTS, 'transcribe_local.py'),
      videoFile, '--engine', 'whisper', '--model', 'base', '--lang', 'zh',
    ], { timeout: 600000, cwd: SCRIPTS });
  } catch (err) {
    log('err', `Whisper: ${err.stderr?.slice(0, 200) || err.message}`);
  }

  // Find transcript
  const txtFiles = fs.readdirSync(TXT)
    .map(f => ({ name: f, time: fs.statSync(path.join(TXT, f)).mtime }))
    .sort((a, b) => b.time - a.time);
  try { fs.unlinkSync(videoFile); } catch {}

  if (txtFiles.length > 0) {
    return { transcript: fs.readFileSync(path.join(TXT, txtFiles[0].name), 'utf8').trim(),
             author: '', desc: '' };
  }
  return null;
}

// ========== Obsidian 保存 ==========
function saveObs(transcript, info) {
  const now = new Date();
  const safe = (info.author || info.platform).replace(/[\/\\:*?"<>|]/g, '_').slice(0, 30);
  const fname = `${info.platform}_${safe}_${now.toISOString().slice(0,10)}.md`;
  const title = `${info.platform}视频逐字稿`;

  const md = `---
title: "${title}"
platform: ${info.platform}
source: ${info.url}
date: ${now.toISOString().slice(0, 10)}
tags:
  - 逐字稿
  - ${info.platform}
---

# ${title}

> **来源**: ${info.url}
> **平台**: ${info.platform}

---

## 逐字稿

${transcript}
`;
  fs.writeFileSync(path.join(OBS, fname), md, 'utf8');
  log('ok', `Obsidian: ${fname}`);
  return path.join(OBS, fname);
}

// ========== 消息处理 ==========
async function handle(msgId, chatId, text) {
  const d = detect(text);
  if (!d) return;

  log('info', '');
  log('info', `🎬 [${d.platform}] ${d.url}`);
  report('task_update', `📩 收到${d.platform}链接`, { platform: d.platform, url: d.url, status: 'running' });

  // Reply: processing
  await lark('im', '+messages-reply', '--message-id', msgId, '--as', 'bot',
    '--text', `🔍 收到${d.platform}链接，开始提取逐字稿...`, '--json');

  // Get transcript
  let result;
  report('pipeline_step', `🎯 开始提取${d.platform}逐字稿`, { platform: d.platform, status: 'running' });
  if (d.platform === '抖音') {
    result = await douyinTranscript(d.url);
  } else {
    result = await downloadAndTranscribe(d.url);
  }

  if (!result || !result.transcript) {
    report('system_alert', `❌ ${d.platform}逐字稿提取失败`, { platform: d.platform, status: 'error' });
    await lark('im', '+messages-reply', '--message-id', msgId, '--as', 'bot',
      '--text', '❌ 提取失败，请检查链接是否有效', '--json');
    return;
  }

  const { transcript, author, desc } = result;
  log('ok', `逐字稿 ${transcript.length} 字`);
  report('pipeline_step', `✅ 逐字稿完成 ${transcript.length}字`, { platform: d.platform, wordCount: transcript.length, status: 'done' });

  // Save
  const obsPath = saveObs(transcript, { platform: d.platform, url: d.url, author });
  report('task_update', `📁 已保存到 Obsidian`, { platform: d.platform, filePath: obsPath, status: 'idle' });

  // Reply preview
  const preview = transcript.slice(0, 300) + (transcript.length > 300 ? '...' : '');
  await lark('im', '+messages-reply', '--message-id', msgId, '--as', 'bot',
    '--text', `✅ 逐字稿 (${transcript.length}字)\n\n${preview}\n\n📁 已保存到 Obsidian`, '--json');

  // Send full text as file if long
  if (transcript.length > 2000) {
    const txtPath = path.join(TXT, `逐字稿_${d.platform}_${Date.now()}.txt`);
    fs.writeFileSync(txtPath, transcript, 'utf8');
    await lark('im', '+messages-send', '--chat-id', chatId, '--as', 'bot',
      '--file', txtPath, '--json');
  }
}

// ========== 启动 ==========
console.log('🚀 飞书 → 逐字稿 → Obsidian 流水线');
console.log('   抖音: Chrome CDP 直读字幕');
console.log('   其他: yt-dlp + Whisper');
console.log('   等待消息... Ctrl+C 停止\n');

const child = spawn('powershell.exe', [
  '-NoProfile', '-Command',
  `& '${LARK}' event consume im.message.receive_v1 --as bot`
], { stdio: ['pipe', 'pipe', 'pipe'] });

let buf = '';
child.stdout.on('data', data => {
  buf += data.toString();
  const lines = buf.split('\n');
  buf = lines.pop() || '';
  for (const line of lines) {
    if (!line.trim() || !line.startsWith('{')) continue;
    try {
      const evt = JSON.parse(line);
      if (evt.message_type !== 'text') continue;
      const text = (() => {
        try { return JSON.parse(evt.content).text || evt.content; }
        catch { return evt.content; }
      })();
      if (!text) continue;
      log('info', `📩 ${text.slice(0, 60)}...`);
      handle(evt.message_id || evt.id, evt.chat_id, text).catch(e =>
        log('err', `handle: ${e.message}`));
    } catch {}
  }
});

child.stderr.on('data', d => {
  const m = d.toString().trim();
  if (m) console.log(`[stderr] ${m.slice(0, 200)}`);
});

child.on('close', code => {
  log('warn', `断开 (code=${code})，5秒重连...`);
  setTimeout(() => process.exit(1), 5000);
});

process.on('SIGINT', () => { console.log('\n已停止'); process.exit(0); });
