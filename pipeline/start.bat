@echo off
chcp 65001 >nul
title 飞书 → 视频链接 → 逐字稿 → 知识库

echo.
echo ╔══════════════════════════════════════════╗
echo ║  🎬 飞书 → 逐字稿 → 知识库 流水线      ║
echo ╠══════════════════════════════════════════╣
echo ║  发视频链接到飞书机器人 → 自动处理      ║
echo ║  支持: 抖音 B站 视频号 YouTube 小红书    ║
echo ║  引擎: 妙记(免费) → 本地Whisper(兜底)   ║
echo ║  存档: Obsidian 知识库                   ║
echo ╚══════════════════════════════════════════╝
echo.
echo 按 Ctrl+C 停止
echo.

cd /d "%~dp0"
node feishu-link-transcribe.js

pause
