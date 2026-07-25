@echo off
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title Info Collector Toolkit
color 0B

:menu
cls
echo ============================================
echo       Info Collector Toolkit (info-collector)
echo ============================================
echo.
echo   1. Shipinhao - get content + Feishu + Obsidian
echo   2. Douyin - fetch account video list
echo   3. Douyin - extract transcript (CDP mode)
echo   4. Local audio/video - transcribe to text
echo   5. Sync JSON to Feishu
echo   6. Zhihu - keyword search + collect
echo   7. Xiaohongshu - keyword search + collect
echo   8. Sync JSON to Obsidian
echo   9. Batch transcribe videos - write back Obsidian
echo   0. Exit
echo.
echo ============================================
set /p choice="Select (0-9): "

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

REM =================================================================
:sph_feishu
cls
echo ============================================
echo   Shipinhao - Get content + Feishu + Obsidian
echo ============================================
echo.
echo Input WeChat Channel video ID (space-separated for multiple):
echo Example: AH9KmByTvv
echo.
set /p sph_input="Video IDs: "
if "%sph_input%"=="" goto menu

echo.
echo Fetching content + interact data + Feishu + Obsidian...
python scripts/sph_to_feishu.py --batch %sph_input% --to-obsidian
echo.
pause
goto menu

REM =================================================================
:douyin_videos
cls
echo ============================================
echo   Douyin - Fetch account video list
echo ============================================
echo.
echo Input Douyin user page URL:
echo Example: https://www.douyin.com/user/MS4wLjAB...
echo.
set /p douyin_url="URL: "
if "%douyin_url%"=="" goto menu

set /p max_count="Max videos (default 50): "
if "%max_count%"=="" set max_count=50

echo.
echo Fetching...
python scripts/douyin_account_videos.py "%douyin_url%" --max %max_count% -o douyin_videos.json
echo.
echo Sync to Obsidian? (y/n)
set /p douyin_obs="Sync Obsidian: "
if /i "%douyin_obs%"=="y" python scripts/sync_to_obsidian.py douyin_videos.json -p douyin

echo Sync to Feishu? (y/n)
set /p douyin_fs="Sync Feishu: "
if /i "%douyin_fs%"=="y" node scripts/sync-to-feishu.js --account-file=douyin_videos.json

echo.
echo Done! Output: douyin_videos.json
pause
goto menu

REM =================================================================
:dy_transcript
cls
echo ============================================
echo   Douyin - Extract transcript (CDP mode)
echo ============================================
echo.
echo PREREQUISITES:
echo   1. Close all Chrome windows
echo   2. Win+R, run: chrome.exe --remote-debugging-port=9222
echo   3. Login to Douyin in the opened Chrome
echo.
echo Input Douyin video URL:
echo Example: https://www.douyin.com/video/74123456789
echo.
set /p video_url="URL: "
if "%video_url%"=="" goto menu

echo.
echo Extracting transcript...
python scripts/dytranscript.py "%video_url%"
echo.
pause
goto menu

REM =================================================================
:transcribe
cls
echo ============================================
echo   Local audio/video - transcribe to text
echo ============================================
echo.
echo Select engine:
echo   1. Paraformer (online, best Chinese, needs API key)
echo   2. Whisper medium (offline, recommended)
echo   3. Whisper large-v3 (offline, best quality, slow)
echo.
set /p engine_choice="Engine (1/2/3): "

set engine=paraformer
set model=medium
if "%engine_choice%"=="2" set engine=whisper
if "%engine_choice%"=="3" set engine=whisper
if "%engine_choice%"=="3" set model=large-v3

echo.
echo Drag & drop video file here, or type path:
echo Supported: mp4/mp3/wav/m4a/aac/flac/ogg/mov/avi/mkv
echo.
set /p file_path="File: "
if "%file_path%"=="" goto menu

echo.
echo Transcribing (engine: %engine%)...
python scripts/transcribe_local.py "%file_path%" --engine %engine% -m %model% --lang zh -o transcript.txt
echo.
echo Done! Output: transcript.txt
pause
goto menu

REM =================================================================
:sync_feishu
cls
echo ============================================
echo   Sync JSON to Feishu
echo ============================================
echo.
echo Sync existing videos.json to Feishu Bitable.
echo.
set /p fs_file="JSON filename (default: douyin_videos.json): "
if "%fs_file%"=="" set fs_file=douyin_videos.json

echo Syncing to Feishu...
node scripts/sync-to-feishu.js --account-file=%fs_file%
echo.
pause
goto menu

REM =================================================================
:zhihu_collect
cls
echo ============================================
echo   Zhihu - Keyword search + collect
echo ============================================
echo.
echo NOTE: First time needs QR code login.
echo.

REM MediaCrawler will auto-launch Chrome in CDP mode

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: uv not found. Run setup.bat first.
    pause
    goto menu
)

if not exist media-crawler\main.py (
    echo ERROR: MediaCrawler not found. Run setup.bat first.
    pause
    goto menu
)

set /p zh_kw="Keywords (comma-separated): "
if "%zh_kw%"=="" goto menu
set /p zh_n="Max count (default 20): "
if "%zh_n%"=="" set zh_n=20

echo.
echo Starting MediaCrawler (QR code will pop up, scan with Zhihu app)...
cd media-crawler
uv run main.py --platform zhihu --lt qrcode --type search --keywords "%zh_kw%" --crawler_max_notes_count %zh_n% --save_data_option jsonl
cd ..

echo.
echo Converting + writing to Obsidian...
python scripts/media_crawler_bridge.py -p zhihu --auto -o zhihu_videos.json --to-obsidian

echo.
echo Sync to Feishu? (y/n)
set /p zh_fs="Sync Feishu: "
if /i "%zh_fs%"=="y" node scripts/sync-to-feishu.js --account-file=zhihu_videos.json

echo.
echo Done! Zhihu collection complete.
pause
goto menu

REM =================================================================
:xhs_collect
cls
echo ============================================
echo   Xiaohongshu - Keyword search + collect
echo ============================================
echo.
echo NOTE: First time needs QR code login.
echo.

REM MediaCrawler will auto-launch Chrome in CDP mode

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: uv not found. Run setup.bat first.
    pause
    goto menu
)

if not exist media-crawler\main.py (
    echo ERROR: MediaCrawler not found. Run setup.bat first.
    pause
    goto menu
)

set /p xhs_kw="Keywords (comma-separated): "
if "%xhs_kw%"=="" goto menu
set /p xhs_n="Max count (default 20): "
if "%xhs_n%"=="" set xhs_n=20

echo.
echo Starting MediaCrawler (QR code will pop up, scan with XHS app)...
cd media-crawler
uv run main.py --platform xhs --lt qrcode --type search --keywords "%xhs_kw%" --crawler_max_notes_count %xhs_n% --save_data_option jsonl
cd ..

echo.
echo Converting + writing to Obsidian...
python scripts/media_crawler_bridge.py -p xhs --auto -o xhs_videos.json --to-obsidian

echo.
echo Sync to Feishu? (y/n)
set /p xhs_fs="Sync Feishu: "
if /i "%xhs_fs%"=="y" node scripts/sync-to-feishu.js --account-file=xhs_videos.json

echo.
echo Done! XHS collection complete.
pause
goto menu

REM =================================================================
:obsidian_sync
cls
echo ============================================
echo   Sync JSON to Obsidian
echo ============================================
echo.
echo Write existing videos.json to Obsidian vault.
echo.
set /p obs_file="JSON file path (default: videos.json): "
if "%obs_file%"=="" set obs_file=videos.json

echo.
echo Platform: douyin / xhs / zhihu / bilibili / kuaishou / weibo / tieba / sph
set /p obs_plat="Platform: "
if "%obs_plat%"=="" set obs_plat=douyin

echo.
python scripts/sync_to_obsidian.py "%obs_file%" -p "%obs_plat%"
echo.
pause
goto menu

REM =================================================================
:batch_transcribe
cls
echo ============================================
echo   Batch transcribe - videos to transcript
echo ============================================
echo.
echo Scan downloaded videos -> Whisper transcribe -> write back Obsidian notes
echo.
echo Based on bridge output *_videos.json file.
echo.
set /p bt_file="JSON filename (default: zhihu_videos.json): "
if "%bt_file%"=="" set bt_file=zhihu_videos.json

echo Dry-run first? (y/n, default y)
set /p bt_dry="Preview: "
if "%bt_dry%"=="" set bt_dry=y

if /i "%bt_dry%"=="y" (
    python scripts/transcribe_batch.py "%bt_file%" --dry-run
) else (
    echo Starting transcription (this will take a while)...
    python scripts/transcribe_batch.py "%bt_file%"
)

echo.
pause
goto menu

REM =================================================================
:end
cls
echo.
echo Thanks for using Info Collector Toolkit!
echo GitHub: https://github.com/sanjin587/info-collector
echo.
timeout /t 2 >nul
