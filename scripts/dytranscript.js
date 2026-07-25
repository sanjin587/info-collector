/**
 * dytranscript — Node.js 版本
 * 通过 CDP 连接已登录的 Chrome → 拦截抖音 API → 提取 video_text 逐字稿
 *
 * 第1步：关掉所有 Chrome，Win+R 执行:
 *   chrome.exe --remote-debugging-port=9222
 * 第2步：在打开的 Chrome 中登录 douyin.com
 * 第3步：运行本脚本
 *
 * 用法: node dytranscript.js <视频链接> [--batch] [--output-dir=<目录>]
 *   node dytranscript.js https://www.douyin.com/video/7643746305843514675
 *   node dytranscript.js --batch --input=../douyin_videos.json
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const https = require('http');

// ===== 配置 =====
const CDP_PORT = 9222;
const OUTPUT_DIR = path.join(require('os').homedir(), '.dytranscript_output');
if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// ===== 工具函数 =====
function p(msg) {
  try { console.log(msg); } catch (e) { console.log(String(msg)); }
}

function extractVideoId(text) {
  let m = text.match(/douyin\.com\/video\/(\d+)/);
  if (m) return m[1];
  m = text.match(/v\.douyin\.com\/([a-zA-Z0-9_-]+)/);
  if (m) return `short:${m[1]}`;
  return null;
}

function fmtTs(s) {
  const m = Math.floor(parseInt(s) / 60);
  const sec = parseInt(s) % 60;
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function extractTranscript(detail) {
  const result = {
    author: (detail.author || {}).nickname || '',
    desc: detail.desc || '',
    create_time: '',
    stats: {},
    hashtags: [],
    video_text: [],
    has_captions: false,
    aweme_id: detail.aweme_id || '',
  };

  const st = detail.statistics || {};
  result.stats = {
    likes: st.digg_count || 0,
    comments: st.comment_count || 0,
    favorites: st.collect_count || 0,
    shares: st.share_count || 0,
    plays: st.play_count || 0,
  };

  const ct = detail.create_time;
  if (ct) result.create_time = new Date(ct * 1000).toISOString().replace('T', ' ').substring(0, 16);

  for (const te of (detail.text_extra || [])) {
    if (te.hashtag_name) result.hashtags.push(te.hashtag_name);
  }

  const vt = detail.video_text || [];
  if (vt.length > 0) {
    result.has_captions = true;
    for (const seg of vt) {
      result.video_text.push({
        text: seg.text || '',
        start_time: seg.start_time || 0,
        end_time: seg.end_time || 0,
      });
    }
  }

  return result;
}

function outputTranscript(data, videoUrl) {
  p('='.repeat(55));
  p('🎬 抖音文案提取完成');
  p('='.repeat(55));
  if (data.author) p(`👤 ${data.author}`);
  if (data.stats) {
    const s = data.stats;
    p(`📊 👍${s.likes}  💬${s.comments}  ⭐${s.favorites}`);
  }
  if (data.hashtags.length) p(`🏷  ${data.hashtags.map(h => '#' + h).join('  ')}`);
  if (data.create_time) p(`🕐 ${data.create_time}`);
  p(`🔗 ${videoUrl}`);

  const desc = data.desc.trim();
  if (desc) p(`\n📝 文案描述:\n${'-'.repeat(40)}\n${desc}`);

  const vt = data.video_text;
  if (vt.length > 0) {
    p(`\n🎤 逐字稿 (${vt.length} 条):\n${'-'.repeat(40)}`);
    const fullText = [];
    for (const seg of vt) {
      p(`  [${fmtTs(seg.start_time)}] ${seg.text}`);
      fullText.push(seg.text);
    }
    p(`${'-'.repeat(40)}\n\n📋 全文:\n${fullText.join('')}`);
  } else if (!data.has_captions) {
    p('\n💡 该视频没有自动字幕，只有文案描述。');
  }
  p('='.repeat(55));

  // Save to file
  const ts = new Date().toISOString().replace(/[:.]/g, '').substring(0, 15);
  const name = (data.author || 'dy').replace(/[\\/:*?"<>|]/g, '').substring(0, 16);
  const fp = path.join(OUTPUT_DIR, `dy_${name}_${ts}.json`);
  fs.writeFileSync(fp, JSON.stringify(data, null, 2), 'utf-8');
  p(`\n💾 已保存: ${fp}`);
  return data;
}

// ===== CDP 连接检查 =====
async function checkCDP() {
  return new Promise((resolve) => {
    const req = https.get(`http://127.0.0.1:${CDP_PORT}/json/version`, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const d = JSON.parse(data);
          resolve(d.Browser ? d.Browser : null);
        } catch (e) { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(3000, () => { req.destroy(); resolve(null); });
  });
}

// ===== 主流程: 提取单个视频 =====
async function extractVideo(videoIdOrUrl) {
  const videoId = extractVideoId(videoIdOrUrl);
  if (!videoId) {
    p('❌ 未识别到抖音视频链接');
    return null;
  }

  // Resolve short URL
  let resolvedId = videoId.startsWith('short:') ? videoId.split(':')[1] : videoId;
  let videoUrl = videoId.startsWith('short:')
    ? `https://v.douyin.com/${resolvedId}/`
    : `https://www.douyin.com/video/${videoId}`;

  // Check CDP
  const browserInfo = await checkCDP();
  if (!browserInfo) {
    p('\n' + '!'.repeat(50));
    p('需要先以调试模式启动 Chrome');
    p('!'.repeat(50));
    p('\n请按以下步骤操作：');
    p('  ① 完全关闭所有 Chrome 窗口');
    p('  ② 按 Win+R，粘贴并回车：');
    p('     chrome.exe --remote-debugging-port=9222');
    p('  ③ 在打开的 Chrome 中登录抖音（如未登录）');
    p('  ④ 重新运行即可');
    return null;
  }

  // Connect via CDP
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${CDP_PORT}`);
  const ctx = browser.contexts()[0] || (await browser.newContext());
  const page = ctx.pages()[0] || (await ctx.newPage());

  p(`\n✅ 已连接到 ${browserInfo}`);

  // Check login
  p('检查登录状态...');
  await page.goto('https://www.douyin.com/', { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000);
  const cookies = await ctx.cookies();
  const loggedIn = cookies.some(c =>
    ['sessionid', 'sid_guard', 'sid_tt'].includes(c.name) && c.value
  );
  if (!loggedIn) {
    p('❌ 未登录抖音，请在 Chrome 中登录后重试');
    return null;
  }
  p('✅ 已登录');

  // Resolve short URL if needed
  if (videoId.startsWith('short:')) {
    const np = await ctx.newPage();
    await np.goto(videoUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await np.waitForTimeout(2000);
    const m = np.url().match(/douyin\.com\/video\/(\d+)/);
    if (m) {
      resolvedId = m[1];
      videoUrl = np.url();
      p(`  → 解析为完整ID: ${resolvedId}`);
    }
    await np.close();
  }

  // Capture detail API response
  let detailData = null;

  page.on('response', async (resp) => {
    const url = resp.url();
    if (url.includes('aweme/v1/web/aweme/detail/')) {
      try {
        const data = await resp.json();
        if (data.aweme_detail) {
          detailData = data.aweme_detail;
        }
      } catch (e) {}
    }
  });

  // Navigate to video page
  p('打开视频页面...');
  await page.goto(videoUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

  // Wait for detail data
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(1000);
    if (detailData) break;
  }
  await page.waitForTimeout(3000);

  if (!detailData) {
    p('⚠️ 未获取到视频数据（可能需要登录或视频不存在）');
    return null;
  }

  const data = extractTranscript(detailData);
  outputTranscript(data, videoUrl);
  return data;
}

// ===== 批量处理 =====
async function batchExtract(videoList) {
  const results = [];
  const videos = JSON.parse(fs.readFileSync(videoList, 'utf-8'));
  const total = videos.length;

  p(`\n📋 批量处理 ${total} 个视频\n`);

  for (let i = 0; i < total; i++) {
    const v = videos[i];
    p(`\n[${i + 1}/${total}] ${v.desc?.substring(0, 60) || v.share_url}`);
    try {
      const result = await extractVideo(v.share_url);
      results.push(result);
    } catch (e) {
      p(`  ❌ 失败: ${e.message}`);
      results.push({ aweme_id: v.aweme_id, share_url: v.share_url, error: e.message });
    }

    // Save incremental
    fs.writeFileSync(
      path.join(OUTPUT_DIR, 'batch_results.json'),
      JSON.stringify(results, null, 2),
      'utf-8'
    );

    // Rate limit
    await new Promise(r => setTimeout(r, 3000));
  }

  p(`\n✅ 批量完成: ${results.filter(r => r && r.has_captions).length}/${total} 有逐字稿`);
  fs.writeFileSync(path.join(OUTPUT_DIR, 'batch_results.json'), JSON.stringify(results, null, 2), 'utf-8');
  return results;
}

// ===== 入口 =====
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--batch')) {
    const inputArg = args.find(a => a.startsWith('--input='));
    if (!inputArg) {
      p('用法: node dytranscript.js --batch --input=<json文件路径>');
      process.exit(1);
    }
    await batchExtract(inputArg.split('=')[1]);
    return;
  }

  if (args.length < 1 || args[0].startsWith('--')) {
    p('用法:');
    p('  单视频: node dytranscript.js <抖音视频链接>');
    p('  批量:   node dytranscript.js --batch --input=videos.json');
    p('\n首次使用:');
    p('  1. 关闭所有 Chrome');
    p('  2. Win+R 输入: chrome.exe --remote-debugging-port=9222');
    p('  3. 登录抖音');
    p('  4. 运行本脚本');
    return;
  }

  // Find douyin URL in all args
  const input = args.join(' ');
  const videoId = extractVideoId(input);
  if (!videoId) {
    const linkInArgs = args.find(a => a.includes('douyin.com') || a.includes('v.douyin.com'));
    if (linkInArgs) {
      await extractVideo(linkInArgs);
    } else {
      p('❌ 未识别到抖音链接。请传入完整的 douyin.com/video/xxx 链接');
    }
    return;
  }

  await extractVideo(input);
}

main().catch(e => {
  p(`\n❌ 错误: ${e.message}`);
  console.error(e);
  process.exit(1);
});
