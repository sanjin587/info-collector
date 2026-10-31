[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Url,

    [string]$DownloaderSkillDir,

    [string]$OutputRoot,

    [ValidateSet('tiny', 'base', 'small', 'medium', 'large-v3')]
    [string]$Model = 'base',

    [ValidateRange(30, 600)]
    [int]$LoginWait = 600
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $PSScriptRoot '..\downloads\wechat-channels'
}

if ($Url -notmatch '(?i)https?://weixin\.qq\.com/sph/\S+') {
    throw '请输入包含 weixin.qq.com/sph/ 分享链接的 URL 或分享文案。'
}

$toolkitRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    $outputBase = [System.IO.Path]::GetFullPath($OutputRoot)
} else {
    $outputBase = [System.IO.Path]::GetFullPath((Join-Path $toolkitRoot $OutputRoot))
}

$skillDirectories = @()
if (-not [string]::IsNullOrWhiteSpace($DownloaderSkillDir)) {
    $skillDirectories += $DownloaderSkillDir
} else {
    if (-not [string]::IsNullOrWhiteSpace($env:SANJIN_WXVIDEO_SKILL_DIR)) {
        $skillDirectories += $env:SANJIN_WXVIDEO_SKILL_DIR
    }
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        $skillDirectories += (Join-Path $env:CODEX_HOME 'agents\skills\sanjin-yuanbao-wxvideo')
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $skillDirectories += (Join-Path $env:USERPROFILE '.agents\skills\sanjin-yuanbao-wxvideo')
        $skillDirectories += (Join-Path $env:USERPROFILE '.codex\skills\sanjin-yuanbao-wxvideo')
        $skillDirectories += (Join-Path $env:USERPROFILE '.workbuddy\skills\sanjin-yuanbao-wxvideo')
    }
}
$downloader = $null
foreach ($skillDirectory in $skillDirectories) {
    $candidate = Join-Path $skillDirectory 'scripts\run.ps1'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $downloader = $candidate
        break
    }
}
$transcriber = Join-Path $PSScriptRoot 'transcribe_local.py'
if ([string]::IsNullOrWhiteSpace($downloader) -or -not (Test-Path -LiteralPath $downloader -PathType Leaf)) {
    throw '找不到元宝视频号下载器。请传入 -DownloaderSkillDir，或设置 SANJIN_WXVIDEO_SKILL_DIR 指向原始 Skill 目录。'
}
if (-not (Test-Path -LiteralPath $transcriber -PathType Leaf)) {
    throw "找不到本地转写脚本：$transcriber"
}
$ffprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffprobeCommand) {
    throw '当前环境没有 ffprobe；为确保 MP4 媒体轨有效，本次没有开始下载或转写。'
}

if (Test-Path -LiteralPath $outputBase -PathType Leaf) {
    throw "输出根路径已经是文件：$outputBase"
}
if (-not (Test-Path -LiteralPath $outputBase -PathType Container)) {
    New-Item -ItemType Directory -Path $outputBase -Force | Out-Null
}

$runName = 'run_{0}_{1}' -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'), ([Guid]::NewGuid().ToString('N').Substring(0, 8))
$runDirectory = Join-Path $outputBase $runName
if (Test-Path -LiteralPath $runDirectory) {
    throw "本次运行目录已存在，为保护已有文件而停止：$runDirectory"
}
New-Item -ItemType Directory -Path $runDirectory | Out-Null

Write-Host '若元宝专用浏览器提示登录，请三哥本人在该窗口扫码；程序会等待并在识别登录后继续。'

$savedErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $downloadOutput = & $downloader 'download' $Url '--output-dir' $runDirectory '--codec' 'h264' '--login-wait' "$LoginWait"
    $downloadExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedErrorActionPreference
}

try {
    $downloadResult = ConvertFrom-Json -InputObject ($downloadOutput -join [Environment]::NewLine)
} catch {
    throw "下载器结果无法解析；请检查本次运行目录中的安全报告：$runDirectory"
}

if ($downloadExitCode -ne 0 -or $downloadResult.status -ne 'success') {
    $codes = @($downloadResult.results | Where-Object { $_.status -eq 'failed' } | ForEach-Object { $_.code } | Select-Object -Unique)
    $codeText = if ($codes.Count) { $codes -join ', ' } else { '下载未完成' }
    throw "视频下载未通过（$codeText）；未启动转写。保留本次目录：$runDirectory"
}

$files = @($downloadResult.results | Where-Object { $_.status -eq 'success' } | ForEach-Object { $_.files })
if ($files.Count -ne 1) {
    throw "预期下载 1 个 MP4，实际得到 $($files.Count) 个；未启动转写。保留本次目录：$runDirectory"
}

$record = $files[0]
$mediaPath = [System.IO.Path]::GetFullPath([string]$record.file_path)
if (-not (Test-Path -LiteralPath $mediaPath -PathType Leaf)) {
    throw "下载报告指向的 MP4 不存在：$mediaPath"
}
$mediaFile = Get-Item -LiteralPath $mediaPath
if ($mediaFile.Length -le 0 -or $mediaFile.Length -ne [int64]$record.bytes) {
    throw "MP4 实际字节数与下载报告不一致；保留文件供检查：$mediaPath"
}

$probeOutput = & $ffprobeCommand.Source -v error -show_entries 'stream=codec_type:format=duration,size' -of json $mediaPath 2>$null
$probeExitCode = $LASTEXITCODE
if ($probeExitCode -ne 0) {
    throw "ffprobe 未能验证 MP4；未启动转写。保留文件：$mediaPath"
}
try {
    $probe = ConvertFrom-Json -InputObject ($probeOutput -join [Environment]::NewLine)
} catch {
    throw "ffprobe 返回内容无法解析；未启动转写。保留文件：$mediaPath"
}
$streamTypes = @($probe.streams | ForEach-Object { [string]$_.codec_type })
if ($streamTypes -notcontains 'video' -or $streamTypes -notcontains 'audio') {
    throw "ffprobe 未找到有效视频轨和音频轨；未启动转写。保留文件：$mediaPath"
}
$duration = [double]::Parse([string]$probe.format.duration, [Globalization.CultureInfo]::InvariantCulture)
if ($duration -le 0) {
    throw "ffprobe 未返回有效时长；未启动转写。保留文件：$mediaPath"
}

$transcriptPath = [System.IO.Path]::ChangeExtension($mediaPath, '.transcript.txt')
if (Test-Path -LiteralPath $transcriptPath) {
    throw "逐字稿已存在，为保护已有文件而停止：$transcriptPath"
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pythonArgs = @()
if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "MP4 已下载并通过 ffprobe；但找不到 Python 来运行本地转写。媒体保留在：$mediaPath"
    }
    $pythonArgs += '-3'
}
$pythonArgs += @($transcriber, $mediaPath, '--engine', 'whisper', '--model', $Model, '--lang', 'zh', '--output', $transcriptPath)

$savedErrorActionPreference = $ErrorActionPreference
$savedPythonPath = $env:PYTHONPATH
try {
    $ErrorActionPreference = 'Continue'
    if ([string]::IsNullOrWhiteSpace($savedPythonPath)) {
        $env:PYTHONPATH = $toolkitRoot
    } else {
        $env:PYTHONPATH = "$toolkitRoot;$savedPythonPath"
    }
    $transcribeOutput = & $pythonCommand.Source @pythonArgs 2>&1
    $transcribeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedErrorActionPreference
    $env:PYTHONPATH = $savedPythonPath
}

if ($transcribeExitCode -ne 0 -or -not (Test-Path -LiteralPath $transcriptPath -PathType Leaf)) {
    throw "MP4 已下载且通过 ffprobe，但转写失败；媒体和报告保留在：$runDirectory"
}
$transcriptText = [System.IO.File]::ReadAllText($transcriptPath, [System.Text.Encoding]::UTF8)
if ($transcriptText -notmatch '(?im)^引擎:\s*whisper\s*$') {
    throw "MP4 已下载，但输出文件未确认 Whisper 转写结果；媒体和文件均保留在：$runDirectory"
}
$separator = '=' * 60
$lastSeparator = $transcriptText.LastIndexOf($separator, [System.StringComparison]::Ordinal)
$transcriptBody = if ($lastSeparator -ge 0) { $transcriptText.Substring($lastSeparator + $separator.Length).Trim() } else { '' }
if ([string]::IsNullOrWhiteSpace($transcriptBody)) {
    throw "MP4 已下载，但逐字稿正文为空；媒体和文件均保留在：$runDirectory"
}

Write-Host ("下载并校验完成：{0:N0} bytes；ffprobe 视频/音频轨通过，时长 {1:N1} 秒。" -f $mediaFile.Length, $duration)
Write-Host "MP4：$mediaPath"
Write-Host ("机器逐字稿：{0}（Whisper $Model，{1} 字，未人工校对）" -f $transcriptPath, $transcriptBody.Length)
if ($downloadResult.report_path) {
    Write-Host "下载报告：$($downloadResult.report_path)"
}
