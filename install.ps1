<#
Voice Dispatch System — Windows Auto-Installer
Run: powershell -ExecutionPolicy Bypass -File install.ps1
#>

param(
    [switch]$CpuOnly,
    [string]$CudaVersion = "cu121"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    VOICE DISPATCH — WINDOWS INSTALLER        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Check Python
# ---------------------------------------------------------------------------
Write-Host "[1/8] Checking Python..." -ForegroundColor Yellow

$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10 -and $minor -le 12) {
                $python = $cmd
                Write-Host "  Found $ver ($cmd)" -ForegroundColor Green
                break
            } elseif ($major -eq 3 -and $minor -ge 13) {
                Write-Host "  Found $ver — Python 3.13+ detected." -ForegroundColor Yellow
                Write-Host "  audioop was removed in 3.13. Will install audioop-lts." -ForegroundColor Yellow
                $python = $cmd
                $needsAudioopLts = $true
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Host "  ERROR: Python 3.10-3.12 not found." -ForegroundColor Red
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  Recommended: Python 3.12.x" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Create virtual environment
# ---------------------------------------------------------------------------
Write-Host "[2/8] Creating virtual environment..." -ForegroundColor Yellow

$venvPath = Join-Path $ProjectRoot "venv"
if (Test-Path $venvPath) {
    Write-Host "  venv already exists, reusing" -ForegroundColor Green
} else {
    & $python -m venv $venvPath
    Write-Host "  Created venv at $venvPath" -ForegroundColor Green
}

# Activate
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
} else {
    $env:PATH = "$(Join-Path $venvPath 'Scripts');$env:PATH"
}

$pip = Join-Path $venvPath "Scripts\pip.exe"
$pythonVenv = Join-Path $venvPath "Scripts\python.exe"

# Upgrade pip
Write-Host "  Upgrading pip..." -ForegroundColor Gray
& $pythonVenv -m pip install --upgrade pip --quiet

# ---------------------------------------------------------------------------
# 3. Install PyTorch
# ---------------------------------------------------------------------------
Write-Host "[3/8] Installing PyTorch..." -ForegroundColor Yellow

if ($CpuOnly) {
    Write-Host "  Installing CPU-only PyTorch..." -ForegroundColor Gray
    & $pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
} else {
    Write-Host "  Installing PyTorch with CUDA ($CudaVersion)..." -ForegroundColor Gray
    Write-Host "  (This is a large download ~2GB, be patient)" -ForegroundColor Gray
    & $pip install torch torchaudio --index-url "https://download.pytorch.org/whl/$CudaVersion" --quiet
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "  PyTorch install failed. Trying CPU-only..." -ForegroundColor Yellow
    & $pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
}

Write-Host "  PyTorch installed" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Install other dependencies
# ---------------------------------------------------------------------------
Write-Host "[4/8] Installing dependencies..." -ForegroundColor Yellow

& $pip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet

if ($needsAudioopLts) {
    Write-Host "  Installing audioop-lts for Python 3.13+..." -ForegroundColor Gray
    & $pip install audioop-lts --quiet
}

Write-Host "  Dependencies installed" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 5. Download faster-whisper model
# ---------------------------------------------------------------------------
Write-Host "[5/8] Pre-downloading Whisper model..." -ForegroundColor Yellow

& $pythonVenv -c "from faster_whisper import WhisperModel; m = WhisperModel('base', device='cpu', compute_type='int8'); print('  Whisper model cached')"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Whisper model download failed — will download on first call" -ForegroundColor Yellow
} else {
    Write-Host "  Whisper model ready" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 6. Configure firewall
# ---------------------------------------------------------------------------
Write-Host "[6/8] Configuring Windows Firewall..." -ForegroundColor Yellow

$rules = @(
    @{Name="VoiceDispatch-SIP"; Port="5060"; Protocol="UDP"},
    @{Name="VoiceDispatch-SIP2"; Port="5062"; Protocol="UDP"},
    @{Name="VoiceDispatch-RTP"; Port="10000-20000"; Protocol="UDP"}
)

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    foreach ($rule in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
        if (-not $existing) {
            New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol $rule.Protocol -LocalPort $rule.Port -Action Allow | Out-Null
            Write-Host "  Created firewall rule: $($rule.Name) ($($rule.Port))" -ForegroundColor Green
        } else {
            Write-Host "  Firewall rule exists: $($rule.Name)" -ForegroundColor Green
        }
    }
} else {
    Write-Host "  Not running as admin — skipping firewall setup" -ForegroundColor Yellow
    Write-Host "  Run this as admin OR manually allow UDP ports 5060, 5062, 10000-20000" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 7. Create .env file
# ---------------------------------------------------------------------------
Write-Host "[7/8] Setting up configuration..." -ForegroundColor Yellow

$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    $apiKey = Read-Host "  Enter your Anthropic API key (or press Enter to set later)"

    $envContent = @"
# Voice Dispatch System Configuration
ANTHROPIC_API_KEY=$apiKey

# Whisper model: tiny, base, small, medium, large-v3
WHISPER_MODEL=base

# Device for inference: cpu or cuda
WHISPER_DEVICE=cpu

# Claude model
CLAUDE_MODEL=claude-sonnet-4-6

# Auto-call your phone when system starts
AUTO_CALL=true

# Save call recordings
SAVE_AUDIO=true
"@
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "  Created .env file" -ForegroundColor Green

    if (-not $apiKey) {
        Write-Host "  ⚠ Set your API key in .env before running!" -ForegroundColor Yellow
    }
} else {
    Write-Host "  .env already exists" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 8. Create desktop shortcut + run.bat
# ---------------------------------------------------------------------------
Write-Host "[8/8] Creating launcher..." -ForegroundColor Yellow

$runBat = Join-Path $ProjectRoot "run.bat"
$runContent = @"
@echo off
title Voice Dispatch System
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m voice_dispatch.watchdog_runner
pause
"@
$runContent | Out-File -FilePath $runBat -Encoding ASCII
Write-Host "  Created run.bat" -ForegroundColor Green

# Desktop shortcut
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Voice Dispatch.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $runBat
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = "Start Voice Dispatch System"
    $shortcut.IconLocation = "imageres.dll,101"
    $shortcut.Save()
    Write-Host "  Created desktop shortcut: Voice Dispatch" -ForegroundColor Green
} catch {
    Write-Host "  Could not create desktop shortcut (non-critical)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         INSTALLATION COMPLETE                ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Detect LAN IP
$lanIP = & $pythonVenv -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>$null
if (-not $lanIP) { $lanIP = "YOUR_PC_IP" }

Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Set your API key in .env (if you haven't)" -ForegroundColor White
Write-Host "  2. Install Obi Linphone on your Android phone" -ForegroundColor White
Write-Host "  3. Configure Linphone:" -ForegroundColor White
Write-Host "     - SIP server: $lanIP" -ForegroundColor Cyan
Write-Host "     - Username: 200" -ForegroundColor Cyan
Write-Host "     - Password: phone123" -ForegroundColor Cyan
Write-Host "     - Transport: UDP" -ForegroundColor Cyan
Write-Host "  4. Double-click 'Voice Dispatch' on your desktop" -ForegroundColor White
Write-Host "  5. Call extension 100 from Linphone" -ForegroundColor White
Write-Host ""
Write-Host "  Or just double-click run.bat and the system will call YOU." -ForegroundColor Green
Write-Host ""
