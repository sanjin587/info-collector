@echo off
chcp 65001 >nul
title 信息采集官 一键安装
color 0A

REM 添加 uv 路径
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     🕵️  信息采集官 一键安装                   ║
echo ╠══════════════════════════════════════════════╣
echo ║  Python + Node.js + Playwright + Whisper      ║
echo ║  + MediaCrawler + agent-reach                ║
echo ╚══════════════════════════════════════════════╝
echo.

REM ==================== 1. 检查基础环境 ====================
echo [1/8] 检查基础环境...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ❌ Python 未安装，请先安装 Python 3.11+
    echo      下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set py_ver=%%i
echo   ✅ %py_ver%

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ❌ Node.js 未安装，请先安装 Node.js 16+
    echo      下载: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set node_ver=%%i
echo   ✅ Node.js %node_ver%

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ Git 未找到，MediaCrawler 克隆需要 Git
    echo      下载: https://git-scm.com/
) else (
    echo   ✅ Git 已安装
)

where chrome >nul 2>&1
if %errorlevel% neq 0 (
    where "C:\Program Files\Google\Chrome\Application\chrome.exe" >nul 2>&1
    if %errorlevel% neq 0 (
        echo   ⚠️ Chrome 未找到（MediaCrawler CDP 模式需要）
    ) else (
        echo   ✅ Chrome 已安装
    )
) else (
    echo   ✅ Chrome 已安装
)

echo.

REM ==================== 2. Python 依赖 ====================
echo [2/8] 安装 Python 依赖...
pip install -r requirements.txt --quiet 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ pip install 有警告，尝试继续...
)
echo   ✅ Python 依赖已安装
echo.

REM ==================== 3. Node.js 依赖 ====================
echo [3/8] 安装 Node.js 依赖...
if not exist node_modules\ (
    call npm install --silent 2>&1
)
echo   ✅ Node.js 依赖已安装
echo.

REM ==================== 4. Playwright 浏览器 ====================
echo [4/8] 安装 Playwright 浏览器引擎...
python -m playwright install chromium 2>&1
echo   ✅ Playwright Chromium 已安装
echo.

REM ==================== 5. 检查 uv ====================
echo [5/8] 检查 uv 包管理器...
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo   📥 正在安装 uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>&1
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    echo   ✅ uv 安装完成
) else (
    echo   ✅ uv 已安装
)
echo.

REM ==================== 6. MediaCrawler ====================
echo [6/8] 检查 MediaCrawler...
if exist media-crawler\main.py (
    echo   ✅ MediaCrawler 已安装
) else (
    echo   📥 正在克隆 MediaCrawler（57K stars，7平台批量采集引擎）...
    git clone --depth 1 https://github.com/NanmiCoder/MediaCrawler.git media-crawler 2>&1
    if %errorlevel% neq 0 (
        echo   ❌ 克隆失败，请检查网络或手动克隆
        echo      git clone https://github.com/NanmiCoder/MediaCrawler.git media-crawler
    ) else (
        echo   📦 安装 MediaCrawler 依赖（首次需下载约 500MB，请耐心等待）...
        cd media-crawler
        call uv sync 2>&1
        cd ..
        echo   ✅ MediaCrawler 安装完成
    )
)
echo.

REM ==================== 7. agent-reach ====================
echo [7/8] 检查 agent-reach...
agent-reach --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   📥 正在安装 agent-reach（15平台全网搜索引擎）...
    pip install agent-reach --quiet 2>&1
    if %errorlevel% neq 0 (
        echo   ⚠️ agent-reach 安装失败，手动安装：
        echo      pip install agent-reach
        echo      参考: https://github.com/Panniantong/Agent-Reach
    ) else (
        echo   ✅ agent-reach 安装完成
    )
) else (
    for /f "tokens=*" %%i in ('agent-reach --version 2^>^&1') do echo   ✅ agent-reach %%i
)
echo.

REM ==================== 8. 配置文件 ====================
echo [8/8] 检查配置...
if not exist .env (
    echo   📝 正在从模板创建 .env 文件...
    copy .env.example .env >nul 2>&1
    echo   ⚠️ 请编辑 .env 填入你的飞书凭证和 API Key
) else (
    echo   ✅ .env 已存在
    findstr /C:"FEISHU_APP_ID=cli_" .env >nul 2>&1
    if %errorlevel% neq 0 (
        echo   ⚠️ FEISHU_APP_ID 似乎未配置
    ) else (
        echo   ✅ FEISHU_APP_ID 已配置
    )
    findstr /C:"DASHSCOPE_API_KEY=sk-" .env >nul 2>&1
    if %errorlevel% neq 0 (
        echo   ⚠️ DASHSCOPE_API_KEY 未配置（只能用 Whisper，不能用 Paraformer）
    ) else (
        echo   ✅ DASHSCOPE_API_KEY 已配置
    )
)
echo.

REM ==================== 完成 ====================
echo ╔══════════════════════════════════════════════╗
echo ║          ✅ 安装完成！                         ║
echo ╠══════════════════════════════════════════════╣
echo ║                                              ║
echo ║  🚀 快速上手：                                ║
echo ║  run.bat            交互式菜单                 ║
echo ║  说"信息采集官"     AI Agent 自动路由          ║
echo ║                                              ║
echo ║  📺 视频号采集                                 ║
echo ║  py scripts/sph_to_feishu.py 视频ID            ║
echo ║                                              ║
echo ║  📦 批量采集（需首次扫码登录）                  ║
echo ║  cd media-crawler                             ║
echo ║  uv run main.py --platform zhihu --type       ║
echo ║     search --keywords "关键词"             ║
echo ║                                              ║
echo ║  🔍 全网搜索                                   ║
echo ║  agent-reach doctor --json                    ║
echo ║                                              ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
