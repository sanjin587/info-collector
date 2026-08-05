# 飞书逐字稿自动化流水线

向飞书机器人发送语音/音频/视频 → 自动回复逐字稿。

## 引擎策略

| 优先级 | 引擎 | 说明 | 费用 |
|--------|------|------|------|
| 1 | 飞书妙记 | 云端转写，95%+准确率，分说话人 | 免费 300分/月 |
| 2 | 本地 Whisper | 离线运行，CPU 即跑 | 免费 |

**自动降级**: 妙记月额度用完 → 自动切换到本地 Whisper，无需手动干预。

## 快速开始

### 环境要求

- Node.js 16+
- Python 3.10~3.12 + faster-whisper
- ffmpeg
- lark-cli (`npm install -g @larksuite/cli`)

### 启动

```bash
# 自动模式（妙记优先，超配额切本地）
node feishu-auto-transcribe.js

# 只走妙记
node feishu-auto-transcribe.js --mode=minutes-only

# 只走本地
node feishu-auto-transcribe.js --mode=local-only

# Windows 双击
start.bat
```

### 配置飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app) → 你的应用
2. **事件订阅** → 添加事件: `im.message.receive_v1`（接收消息）
3. **权限管理** → 添加权限:
   - `im:message`（获取消息）
   - `im:message.p2p_msg:readonly`（读取私聊）
   - `im:message.group_msg:readonly`（读取群聊）
   - `drive:drive:readonly`（云盘读取）
   - `drive:file:upload`（云盘上传）
   - `minutes:minutes.upload:write`（妙记上传）
   - `minutes:minutes.artifacts:read`（妙记产物读取）
4. **安全设置** → 添加机器人到需要的群聊
5. **发布版本** → 创建新版本并发布

### 验证

```bash
# 确认登录状态
lark-cli auth status

# 确认事件可用
lark-cli event list | findstr "im.message"

# 测试发送消息
lark-cli im +messages-send --chat-id oc_xxx --text "测试"
```

## 使用效果

```
用户: [发送一条语音消息]
  ↓
机器人: 📝 逐字稿已生成（🎙️妙记）
  
  今天我们要聊的是关于AI Agent在企业落地的三个关键问题...
```

如果妙记配额用完：

```
机器人: 🎙️ 妙记本月免费额度（300分钟）已用完，已自动切换到本地 Whisper 转写
机器人: 📝 逐字稿已生成（💻本地Whisper）
  
  今天我们要聊的是关于AI Agent...
```

## 目录结构

```
pipeline/
├── feishu-auto-transcribe.js   # 主控制器
├── start.bat                    # Windows 启动脚本
├── README.md                    # 本文档
├── downloads/                   # 临时下载目录（自动清理）
└── transcripts/                 # 逐字稿存档
```
