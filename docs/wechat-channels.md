# 微信视频号分享链接下载与逐字稿

这条流程接收单个 `weixin.qq.com/sph/` 分享链接，使用本机的 `sanjin-yuanbao-wxvideo` Skill 下载 MP4，再通过工具包现有的 `scripts/transcribe_local.py` 和本地 Whisper 转写。解析与登录逻辑由上游 Skill 提供；本仓库不复制解析代码，也不调用第三方在线解析站。

## 运行

在 Windows PowerShell 中进入工具包根目录，运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wxvideo_to_transcript.ps1 -Url 'https://weixin.qq.com/sph/分享码'
```

入口会尝试从 `SANJIN_WXVIDEO_SKILL_DIR`、`CODEX_HOME` 和常见用户级 Skill 目录定位下载器。若没有自动找到，可传入原始 Skill 文件夹：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wxvideo_to_transcript.ps1 -DownloaderSkillDir '<本机 sanjin-yuanbao-wxvideo Skill 目录>' -Url 'https://weixin.qq.com/sph/分享码'
```

可选参数：

- `-OutputRoot <目录>`：指定保存根目录。默认是 `downloads\wechat-channels\`。
- `-Model base|small|medium|large-v3|tiny`：选择本地 Whisper 模型，默认 `base`。
- `-LoginWait 30..600`：设置等待元宝登录的最长秒数，默认 600 秒。
- `-DownloaderSkillDir <目录>`：指定上游 Skill 的安装目录；也可设置 `SANJIN_WXVIDEO_SKILL_DIR`。

运行前需要 Windows PowerShell、Python 转录依赖、Whisper 模型和 `ffprobe`。先用上游 Skill 的 `run.ps1 doctor` 检查下载器；缺少依赖时按上游 Skill 的安装说明处理，不要把浏览器资料或凭证放进仓库。

如果出现元宝专用浏览器窗口，请在该窗口由本人扫码登录。程序检测到登录后会自动继续；不要向 Agent 提供 Cookie、密码、token 或临时媒体地址。入口不会自动安装依赖、修改系统代理或证书。

## 输出与校验

每次运行创建一个新的 `run_<时间戳>_<随机后缀>` 子目录，不覆盖或清理已有文件。目录中包含：

- 下载器返回的 MP4 和安全报告；
- 与 MP4 同名的 `.transcript.txt` 逐字稿。

入口核对 MP4 实际字节数是否与下载报告一致，再用 `ffprobe` 确认存在视频轨、音轨和有效时长，通过后才启动 `transcribe_local.py --engine whisper`。逐字稿会记录来源文件、Whisper 引擎和模型；它是机器生成、未经人工校对的文本。

若转写失败，已下载媒体和下载报告会保留在本次目录，可稍后只对该 MP4 重试本地转写。手动重试时从工具包根目录执行，并选择一个尚不存在的输出文件名：

```powershell
$toolkitRoot = (Get-Location).Path
if ($env:PYTHONPATH) { $env:PYTHONPATH = "$toolkitRoot;$env:PYTHONPATH" } else { $env:PYTHONPATH = $toolkitRoot }
python scripts\transcribe_local.py '<本次目录中的 MP4 路径>' --engine whisper --model base --lang zh --output '<新逐字稿文件路径>'
```

下载失败、登录超时或媒体不可用时，不会报告为成功。

## 范围与安全

- 本入口一次处理一个分享链接，不枚举视频号主页或作者的全部作品。
- 视频号内部接口和媒体可用性可能变化；部分视频、直播回放或无访问权限内容可能无法下载。
- `scripts/sph_to_feishu.py` 是历史预览页/飞书流程，保留兼容用途，不作为当前 MP4 下载入口。
- `.gitignore` 排除下载目录和常见媒体扩展名、浏览器资料目录、Cookie、token、凭证文件和私钥；不要强制添加这些本地文件到 Git。
