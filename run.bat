@echo off
chcp 65001 >nul
title 信息采集官工具包
color 0B

:menu
cls
echo ╔══════════════════════════════════════════╗
echo ║        🕵️  信息采集官工具包              ║
echo ╠══════════════════════════════════════════╣
echo ║                                          ║
echo ║  1. 📺  视频号文案抓取+入库               ║
echo ║  2. 🎬  抖音账号视频列表抓取              ║
echo ║  3. 📝  抖音逐字稿提取                    ║
echo ║  4. 🎤  本地视频转文字                    ║
echo ║  5. 🔄  同步数据到飞书对标作品库           ║
echo ║  6. 📦  知乎关键词采集                    ║
echo ║  7. 📦  小红书关键词采集                   ║
echo ║  8. 📂  同步到 Obsidian 知识库             ║
echo ║  9. 🎬  批量视频转逐字稿                   ║
echo ║  0. ❌  退出                              ║
echo ║                                          ║
echo ╚══════════════════════════════════════════╝
echo.

set /p choice="请选择操作 (0-9): "

if "%choice%"=="1" goto sph_feishu
if "%choice%"=="2" goto douyin_videos
if "%choice%"=="3" goto dy_transcript
if "%choice%"=="4" goto transcribe
if "%choice%"=="5" goto sync_feishu
if "%choice%"=="6" goto zhihu_collect
if "%choice%"=="7" goto xhs_collect
if "%choice%"=="8" goto obsidian_sync
if "%choice%"=="9" goto batch_transcribe
if "%choice%"=="0" goto end
goto menu

REM ==================== 1. 视频号采集 ====================
:sph_feishu
cls
echo ╔══════════════════════════════════════════╗
echo ║    📺  视频号文案抓取+入库                 ║
echo ╚══════════════════════════════════════════╝
echo.
echo 支持单条或批量（用空格分隔）
echo 示例: AH9KmByTvv
echo 批量: AH9KmByTvv 另一个ID 第三个ID
echo.
set /p sph_input="输入视频号 ID（可多个，空格分隔）: "
if "%sph_input%"=="" goto menu

echo.
echo 获取文案 + 互动数据 + 飞书入库 + Obsidian 归档...
python scripts/sph_to_feishu.py --batch %sph_input% --to-obsidian
echo.
pause
goto menu

REM ==================== 2. 抖音账号视频列表 ====================
:douyin_videos
cls
echo ╔══════════════════════════════════════════╗
echo ║    🎬  抖音账号视频列表抓取               ║
echo ╚══════════════════════════════════════════╝
echo.
echo 请输入抖音用户主页链接
echo 示例: https://www.douyin.com/user/MS4wLjAB...
echo.
set /p douyin_url="链接: "
if "%douyin_url%"=="" goto menu

echo 最大抓取数量？（直接回车默认50）
set /p max_count="数量: "
if "%max_count%"=="" set max_count=50

echo.
echo 开始抓取...
python scripts/douyin_account_videos.py "%douyin_url%" --max %max_count% -o douyin_videos.json
echo.
echo 是否同步到 Obsidian？(y/n)
set /p douyin_obs="同步 Obsidian: "
if /i "%douyin_obs%"=="y" python scripts/sync_to_obsidian.py douyin_videos.json -p douyin

echo 是否同步到飞书？(y/n)
set /p douyin_fs="同步飞书: "
if /i "%douyin_fs%"=="y" node scripts/sync-to-feishu.js --account-file=douyin_videos.json

echo.
echo ✅ 完成！
pause
goto menu

REM ==================== 3. 抖音逐字稿 ====================
:dy_transcript
cls
echo ╔══════════════════════════════════════════╗
echo ║    📝  抖音逐字稿提取                     ║
echo ╚══════════════════════════════════════════╝
echo.
echo ⚠ 使用前请确保：
echo   1. 关闭所有 Chrome 窗口
echo   2. 按 Win+R，运行：chrome.exe --remote-debugging-port=9222
echo   3. 在打开的 Chrome 中登录抖音
echo.
echo 然后输入抖音视频链接：
echo 示例: https://www.douyin.com/video/74123456789
echo.
set /p video_url="链接: "
if "%video_url%"=="" goto menu

echo.
echo 开始提取逐字稿...
python scripts/dytranscript.py "%video_url%"
echo.
pause
goto menu

REM ==================== 4. 本地视频转文字 ====================
:transcribe
cls
echo ╔══════════════════════════════════════════╗
echo ║    🎤  本地视频转文字                     ║
echo ╚══════════════════════════════════════════╝
echo.
echo 选择转写引擎：
echo   1. Paraformer（百炼在线，中文极准，需联网）
echo   2. Whisper medium（本地离线，推荐）
echo   3. Whisper large-v3（本地离线，最准但慢）
echo.
set /p engine_choice="引擎 (1/2/3): "

set engine=paraformer
set model=medium
if "%engine_choice%"=="2" set engine=whisper
if "%engine_choice%"=="3" set engine=whisper
if "%engine_choice%"=="3" set model=large-v3

echo.
echo 请拖拽视频文件到窗口，或输入路径：
echo 支持: mp4/mp3/wav/m4a/aac/flac/ogg/mov/avi/mkv
echo.
set /p file_path="文件路径: "
if "%file_path%"=="" goto menu

echo.
echo 开始转写（引擎: %engine%）...
python scripts/transcribe_local.py "%file_path%" --engine %engine% -m %model% --lang zh -o transcript.txt
echo.
echo ✅ 完成！文稿已保存到 transcript.txt
pause
goto menu

REM ==================== 5. 飞书同步 ====================
:sync_feishu
cls
echo ╔══════════════════════════════════════════╗
echo ║    🔄  同步数据到飞书对标作品库            ║
echo ╚══════════════════════════════════════════╝
echo.
echo 将已有的 videos.json 同步到飞书
echo.
set /p fs_file="JSON 文件名（默认 douyin_videos.json）: "
if "%fs_file%"=="" set fs_file=douyin_videos.json

echo 同步到飞书...
node scripts/sync-to-feishu.js --account-file=%fs_file%
echo.
pause
goto menu

REM ==================== 6. 知乎采集 ====================
:zhihu_collect
cls
echo ╔══════════════════════════════════════════╗
echo ║    📦  知乎关键词采集                     ║
echo ╠══════════════════════════════════════════╣
echo ║  ⚠ 首次使用需要扫码登录知乎               ║
echo ║  请先确保 Chrome 已启用远程调试            ║
echo ╚══════════════════════════════════════════╝
echo.

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv 未安装，请先运行 setup.bat
    pause
    goto menu
)

if not exist media-crawler\main.py (
    echo ❌ MediaCrawler 未安装，请先运行 setup.bat
    pause
    goto menu
)

set /p zh_kw="关键词（多个用逗号分隔）: "
if "%zh_kw%"=="" goto menu
set /p zh_n="最多条数（默认 20）: "
if "%zh_n%"=="" set zh_n=20

echo.
echo 正在启动 MediaCrawler 采集（会弹出二维码，用知乎APP扫码登录）...
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd media-crawler
uv run main.py --platform zhihu --lt qrcode --type search --keywords "%zh_kw%" --max_notes_count %zh_n% --save_data_option jsonl
cd ..

echo.
echo 转换格式 + 写入 Obsidian...
python scripts/media_crawler_bridge.py -p zhihu --auto -o zhihu_videos.json --to-obsidian

echo.
echo 是否同步到飞书？(y/n)
set /p zh_fs="同步飞书: "
if /i "%zh_fs%"=="y" node scripts/sync-to-feishu.js --account-file=zhihu_videos.json

echo.
echo ✅ 知乎采集完成！
pause
goto menu

REM ==================== 7. 小红书采集 ====================
:xhs_collect
cls
echo ╔══════════════════════════════════════════╗
echo ║    📦  小红书关键词采集                   ║
echo ╠══════════════════════════════════════════╣
echo ║  ⚠ 首次使用需要扫码登录小红书             ║
echo ║  请先确保 Chrome 已启用远程调试            ║
echo ╚══════════════════════════════════════════╝
echo.

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv 未安装，请先运行 setup.bat
    pause
    goto menu
)

if not exist media-crawler\main.py (
    echo ❌ MediaCrawler 未安装，请先运行 setup.bat
    pause
    goto menu
)

set /p xhs_kw="关键词（多个用逗号分隔）: "
if "%xhs_kw%"=="" goto menu
set /p xhs_n="最多条数（默认 20）: "
if "%xhs_n%"=="" set xhs_n=20

echo.
echo 正在启动 MediaCrawler 采集（会弹出二维码，用小红书APP扫码登录）...
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd media-crawler
uv run main.py --platform xhs --lt qrcode --type search --keywords "%xhs_kw%" --max_notes_count %xhs_n% --save_data_option jsonl
cd ..

echo.
echo 转换格式 + 写入 Obsidian...
python scripts/media_crawler_bridge.py -p xhs --auto -o xhs_videos.json --to-obsidian

echo.
echo 是否同步到飞书？(y/n)
set /p xhs_fs="同步飞书: "
if /i "%xhs_fs%"=="y" node scripts/sync-to-feishu.js --account-file=xhs_videos.json

echo.
echo ✅ 小红书采集完成！
pause
goto menu

REM ==================== 8. 同步 Obsidian ====================
:obsidian_sync
cls
echo ╔══════════════════════════════════════════╗
echo ║    📂  同步 JSON 到 Obsidian 知识库       ║
echo ╚══════════════════════════════════════════╝
echo.
echo 将已有的 videos.json 写入 Obsidian 对标账号目录
echo.
set /p obs_file="JSON 文件路径（默认 videos.json）: "
if "%obs_file%"=="" set obs_file=videos.json

echo.
echo 平台选择: douyin / xhs / zhihu / bilibili / kuaishou / weibo / tieba / sph
set /p obs_plat="平台: "
if "%obs_plat%"=="" set obs_plat=douyin

echo.
python scripts/sync_to_obsidian.py "%obs_file%" -p "%obs_plat%"
echo.
pause
goto menu

REM ==================== 9. 批量转录 ====================
:batch_transcribe
cls
echo ╔══════════════════════════════════════════╗
echo ║    🎬  批量视频转逐字稿                   ║
echo ╠══════════════════════════════════════════╣
echo ║  扫描本地视频 → Whisper 转录              ║
echo ║  → 逐字稿自动回填 Obsidian 笔记           ║
echo ╚══════════════════════════════════════════╝
echo.
echo 基于 bridge 输出的 *_videos.json 文件
echo.
set /p bt_file="JSON 文件名（默认 zhihu_videos.json）: "
if "%bt_file%"=="" set bt_file=zhihu_videos.json

echo 预览模式？先看看会转录哪些文件 (y/n，默认 y)
set /p bt_dry="预览: "
if "%bt_dry%"=="" set bt_dry=y

if /i "%bt_dry%"=="y" (
    python scripts/transcribe_batch.py "%bt_file%" --dry-run
) else (
    echo 开始转录（需要较长时间）...
    python scripts/transcribe_batch.py "%bt_file%"
)

echo.
pause
goto menu

REM ==================== 退出 ====================
:end
cls
echo.
echo 感谢使用信息采集官工具包！
echo GitHub: https://github.com/sanjin587/info-collector
echo.
timeout /t 2 >nul
