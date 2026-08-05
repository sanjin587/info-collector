@echo off
chcp 65001 >nul
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title 信息采集官 · 全自动流水线

if "%~1"=="" (
    echo.
    echo ╔══════════════════════════════════════════════╗
    echo ║     🕵️  信息采集官 · 全自动流水线              ║
    echo ╠══════════════════════════════════════════════╣
    echo ║                                            ║
    echo ║  用法:                                      ║
    echo ║  collector ^<链接^>                          ║
    echo ║  collector ^<文件路径^>                       ║
    echo ║  collector --dry-run ^<链接^>   预览         ║
    echo ║  collector --model medium ^<链接^>           ║
    echo ║                                            ║
    echo ║  示例:                                      ║
    echo ║  collector https://v.douyin.com/xxxxx/      ║
    echo ║  collector https://www.bilibili.com/video/BV║
    echo ║  collector C:\Users\...\视频.mp4             ║
    echo ║                                            ║
    echo ║  支持: 抖音 B站 YouTube 小红书 快手 视频号    ║
    echo ║  输出: Obsidian 逐字稿                       ║
    echo ║                                            ║
    echo ╚══════════════════════════════════════════════╝
    echo.
    set /p input="🔗 请输入视频链接或文件路径: "
    if "%input%"=="" exit /b
    python scripts/collector.py pipeline "%input%" %*
    goto :end
)

REM 有参数时直接传给 collector.py
if "%~1"=="--dry-run" (
    python scripts/collector.py pipeline %*
) else if "%~1"=="transcribe" (
    python scripts/collector.py %*
) else if "%~1"=="detect" (
    python scripts/collector.py %*
) else if "%~1"=="sync" (
    python scripts/collector.py %*
) else (
    python scripts/collector.py pipeline %*
)

:end
echo.
pause
