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
echo ║  1. 🎬  抖音账号视频列表抓取              ║
echo ║  2. 📝  抖音逐字稿提取                    ║
echo ║  3. 🎤  本地视频转文字                    ║
echo ║  4. 📺  视频号文案抓取+飞书入库            ║
echo ║  5. 🔄  同步数据到飞书对标作品库           ║
echo ║  6. 📖  查看使用说明                      ║
echo ║  0. ❌  退出                              ║
echo ║                                          ║
echo ╚══════════════════════════════════════════╝
echo.

set /p choice="请选择操作 (0-6): "

if "%choice%"=="1" goto douyin_videos
if "%choice%"=="2" goto dy_transcript
if "%choice%"=="3" goto transcribe
if "%choice%"=="4" goto sph_feishu
if "%choice%"=="5" goto sync_feishu
if "%choice%"=="6" goto readme
if "%choice%"=="0" goto end
goto menu

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
echo ✅ 完成！结果已保存到 douyin_videos.json
pause
goto menu

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

:transcribe
cls
echo ╔══════════════════════════════════════════╗
echo ║    🎤  本地视频转文字                     ║
echo ╚══════════════════════════════════════════╝
echo.
echo 选择转写引擎：
echo   1. Paraformer（百炼在线，中文准，需联网）
echo   2. Whisper（本地离线，稍慢）
echo.
set /p engine_choice="引擎 (1/2): "

set engine=paraformer
if "%engine_choice%"=="2" set engine=whisper

echo.
echo 请拖拽视频文件到窗口，或输入路径：
echo 支持: mp4/mp3/wav/m4a/aac/flac/ogg/mov/avi/mkv
echo.
set /p file_path="文件路径: "
if "%file_path%"=="" goto menu

echo.
echo 开始转写（引擎: %engine%）...
if "%engine%"=="whisper" (
    python scripts/transcribe_local.py "%file_path%" --engine whisper -m medium -o transcript.txt
) else (
    python scripts/transcribe_local.py "%file_path%" --engine paraformer -o transcript.txt
)
echo.
echo ✅ 完成！文稿已保存到 transcript.txt
pause
goto menu

:sph_feishu
cls
echo ╔══════════════════════════════════════════╗
echo ║    📺  视频号文案抓取+飞书入库             ║
echo ╚══════════════════════════════════════════╝
echo.
echo 请输入视频号 sph 链接或 ID：
echo 示例: https://weixin.qq.com/sph/AH9KmByTvv
echo 或: AH9KmByTvv
echo.
set /p sph_input="输入: "
if "%sph_input%"=="" goto menu

echo.
echo 开始抓取并写入飞书...
python scripts/sph_to_feishu.py "%sph_input%"
echo.
pause
goto menu

:sync_feishu
cls
echo ╔══════════════════════════════════════════╗
echo ║    🔄  同步数据到飞书对标作品库            ║
echo ╚══════════════════════════════════════════╝
echo.
echo 请确认已经抓取过视频列表（douyin_videos.json）
echo.
set /p confirm="是否继续？(y/n): "
if /i not "%confirm%"=="y" goto menu

echo.
echo 同步到飞书...
node scripts/sync-to-feishu.js --account-file=douyin_videos.json
echo.
pause
goto menu

:readme
cls
type README.md
echo.
echo ══════════════════════════════════════════
echo 按任意键返回菜单...
pause >nul
goto menu

:end
cls
echo.
echo 感谢使用信息采集官工具包！
echo.
timeout /t 2 >nul
