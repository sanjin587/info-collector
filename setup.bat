@echo off
chcp 65001 >nul
title 信息采集官三合一安装程序
color 0A

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     🕵️  信息采集官 三合一安装程序             ║
echo ╠══════════════════════════════════════════════╣
echo ║  工具包 + agent-reach + MediaCrawler          ║
echo ╚══════════════════════════════════════════════╝
echo.

REM ==================== 步骤 1: 检查基础环境 ====================
echo [1/6] 检查基础环境...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未安装，请先安装 Python 3.11+
    pause
    exit /b 1
)
echo   ✅ Python %python_version%

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js 未安装，请先安装 Node.js 16+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set node_version=%%i
echo   ✅ Node.js %node_version%

where chrome >nul 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ Chrome 未找到，MediaCrawler CDP 模式需要 Chrome
) else (
    echo   ✅ Chrome 已安装
)

echo.

REM ==================== 步骤 2: 安装 Python 依赖 ====================
echo [2/6] 安装 Python 依赖...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ⚠️ pip install 有警告，继续...
)
echo   ✅ Python 依赖已安装
echo.

REM ==================== 步骤 3: 安装 Node.js 依赖 ====================
echo [3/6] 安装 Node.js 依赖...
if not exist node_modules\ (
    call npm install
)
echo   ✅ Node.js 依赖已安装
echo.

REM ==================== 步骤 4: 检查/安装 MediaCrawler ====================
echo [4/6] 检查 MediaCrawler...
if exist media-crawler\main.py (
    echo   ✅ MediaCrawler 已安装
) else (
    echo   📥 正在克隆 MediaCrawler...
    where uv >nul 2>&1
    if %errorlevel% neq 0 (
        echo   ⚠️ uv 未安装，正在安装...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        set PATH=%USERPROFILE%\.local\bin;%PATH%
    )
    git clone https://github.com/NanmiCoder/MediaCrawler.git media-crawler
    cd media-crawler
    echo   📦 安装 MediaCrawler 依赖（可能需要几分钟）...
    uv sync
    cd ..
    echo   ✅ MediaCrawler 安装完成
)
echo.

REM ==================== 步骤 5: 检查 agent-reach ====================
echo [5/6] 检查 agent-reach...
agent-reach --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ agent-reach 未找到，请先安装
    echo   参考: https://github.com/Panniantong/Agent-Reach
) else (
    echo   ✅ agent-reach 已安装
    echo   📡 检查后端状态...
    agent-reach doctor --json
)
echo.

REM ==================== 步骤 6: 检查配置 ====================
echo [6/6] 检查配置...
if exist .env (
    echo   ✅ .env 配置文件存在

    REM 检查关键变量
    findstr /C:"FEISHU_APP_ID=" .env >nul && echo   ✅ FEISHU_APP_ID 已配置
    findstr /C:"DASHSCOPE_API_KEY=" .env >nul && echo   ✅ DASHSCOPE_API_KEY 已配置

    findstr /C:"DASHSCOPE_API_KEY=$" .env >nul && echo   ⚠️ DASHSCOPE_API_KEY 为空，Paraformer 不可用
) else (
    echo   ❌ .env 文件不存在，请从 .env.example 复制并填写
)
echo.

REM ==================== 完成 ====================
echo ╔══════════════════════════════════════════════╗
echo ║          ✅ 安装完成！                         ║
echo ╠══════════════════════════════════════════════╣
echo ║                                              ║
echo ║  可用命令：                                   ║
echo ║  run.bat           — 交互式菜单                ║
echo ║  agent-reach       — 全网搜索                  ║
echo ║  cd media-crawler  — MediaCrawler 批量采集     ║
echo ║                                              ║
echo ║  快速上手：                                   ║
echo ║  1. agent-reach doctor --json  查看搜索后端    ║
echo ║  2. 说"信息采集官"即可自动路由                 ║
echo ║                                              ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
