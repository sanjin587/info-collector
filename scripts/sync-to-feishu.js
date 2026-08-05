/**
 * 抖音账号视频 → 飞书对标作品库 同步脚本
 *
 * 用法:
 *   # 先抓取视频列表
 *   python douyin_account_videos.py "https://www.douyin.com/user/XXX" --output videos.json
 *
 *   # 再同步到飞书
 *   node sync-to-feishu.js --account-file=videos.json
 *
 * 环境变量（.env 或 settings.json env）:
 *   FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN
 *   ACCOUNT_TABLE_ID, WORKS_TABLE_ID
 */
const fs = require("fs");
const path = require("path");

// 加载项目根目录的 .env
require("dotenv").config({ path: path.resolve(__dirname, "..", ".env") });

// ============ 配置：从环境变量读取 ============
const FEISHU_APP_ID = process.env.FEISHU_APP_ID;
const FEISHU_APP_SECRET = process.env.FEISHU_APP_SECRET;
const APP_TOKEN = process.env.FEISHU_APP_TOKEN;
const ACCOUNT_TABLE_ID = process.env.ACCOUNT_TABLE_ID;
const WORKS_TABLE_ID = process.env.WORKS_TABLE_ID;

const BATCH_SIZE = 20; // 飞书批量写入建议分批

// ============ 参数解析 ============
function parseArgs() {
  const arg = process.argv.find(a => a.startsWith("--account-file="));
  if (!arg) {
    console.error("用法: node sync-to-feishu.js --account-file=<路径>");
    process.exit(1);
  }
  return arg.split("=")[1];
}

// ============ 飞书 API 工具 ============
async function getToken() {
  const res = await fetch("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ app_id: FEISHU_APP_ID, app_secret: FEISHU_APP_SECRET }),
  });
  const data = await res.json();
  if (data.code !== 0) throw new Error("获取 token 失败: " + JSON.stringify(data));
  return data.tenant_access_token;
}

async function feishuApi(method, path, body) {
  const token = await getToken();
  const url = `https://open.feishu.cn/open-apis${path}`;
  const res = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (data.code !== 0) throw new Error(`API ${method} ${path} 失败: ${JSON.stringify(data)}`);
  return data.data;
}

// ============ 查重：账号是否已存在 ============
async function findOrCreateAccount(accountUrl) {
  const searchResult = await feishuApi("POST", `/bitable/v1/apps/${APP_TOKEN}/tables/${ACCOUNT_TABLE_ID}/records/search`, {
    filter: {
      conjunction: "and",
      conditions: [{ field_name: "账号链接", operator: "is", value: [accountUrl] }],
    },
  });

  if (searchResult.items && searchResult.items.length > 0) {
    console.error(`账号已存在: ${searchResult.items[0].record_id}`);
    return searchResult.items[0].record_id;
  }

  const createResult = await feishuApi("POST", `/bitable/v1/apps/${APP_TOKEN}/tables/${ACCOUNT_TABLE_ID}/records`, {
    fields: { "账号链接": accountUrl, "状态": "采集中" },
  });
  console.error(`已新建账号记录: ${createResult.record.record_id}`);
  return createResult.record.record_id;
}

// ============ 查重：已有作品链接 ============
async function fetchExistingLinks() {
  const result = await feishuApi("POST", `/bitable/v1/apps/${APP_TOKEN}/tables/${WORKS_TABLE_ID}/records/search`, {
    field_names: ["视频链接"],
    page_size: 500,
  });
  const items = result.items || [];
  return new Set(items.map(r => r.fields["视频链接"]).filter(Boolean));
}

// ============ 批量写入 ============
async function batchCreateWorks(accountRecordId, videos) {
  let created = 0;
  for (let i = 0; i < videos.length; i += BATCH_SIZE) {
    const batch = videos.slice(i, i + BATCH_SIZE);
    const records = batch.map(v => ({
      fields: {
        "视频链接": { link: v.videoUrl },
        "作品标题": v.title || "",
        "发布时间": v.publishTime || null,
        "播放量": v.playCount ?? null,
        "点赞": v.likeCount ?? null,
        "评论": v.commentCount ?? null,
        "下载直链": v.downloadUrl ? { link: v.downloadUrl } : null,
        "封面图": v.coverUrl ? { link: v.coverUrl } : null,
        "所属账号": [accountRecordId],
        "状态": "待分析",
      },
    }));

    await feishuApi("POST", `/bitable/v1/apps/${APP_TOKEN}/tables/${WORKS_TABLE_ID}/records/batch_create`, { records });
    created += records.length;
    console.error(`已写入 ${created}/${videos.length}`);
  }
  return created;
}

// ============ 主流程 ============
async function main() {
  // 校验环境变量
  const required = [FEISHU_APP_ID, FEISHU_APP_SECRET, APP_TOKEN, ACCOUNT_TABLE_ID, WORKS_TABLE_ID];
  if (required.some(v => !v)) {
    console.error("缺少环境变量，请确保设置了:");
    console.error("  FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN");
    console.error("  ACCOUNT_TABLE_ID, WORKS_TABLE_ID");
    process.exit(1);
  }

  const filePath = parseArgs();
  const payload = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  const { accountUrl, videos } = payload;

  console.error(`账号: ${accountUrl}`);
  console.error(`视频数: ${videos.length}`);

  const accountRecordId = await findOrCreateAccount(accountUrl);
  const existingLinks = await fetchExistingLinks();
  const newVideos = videos.filter(v => !existingLinks.has(v.videoUrl));

  console.error(`去重后新增: ${newVideos.length}/${videos.length}`);

  if (newVideos.length === 0) {
    console.log(JSON.stringify({ accountUrl, total: videos.length, created: 0, skipped: videos.length }));
    return;
  }

  const created = await batchCreateWorks(accountRecordId, newVideos);
  console.log(JSON.stringify({ accountUrl, total: videos.length, created, skipped: videos.length - newVideos.length }));
}

main().catch(err => {
  console.error("同步失败:", err.message);
  process.exit(1);
});
