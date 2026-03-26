<#
.SYNOPSIS
    Voice Dispatch System — ONE COMMAND BOOTSTRAP

    Paste this single command into PowerShell on your Windows PC:

    Set-ExecutionPolicy Bypass -Scope Process -Force; cd $HOME; git clone https://github.com/lozturner/personal-ai-system.git; cd personal-ai-system; git checkout claude/voice-dispatch-system-dmGlI; .\bootstrap.ps1 -ApiKey "YOUR_KEY_HERE"

    Or if repo already cloned:

    cd $HOME\personal-ai-system; git pull origin claude/voice-dispatch-system-dmGlI; .\bootstrap.ps1 -ApiKey "YOUR_KEY_HERE"

.DESCRIPTION
    Does EVERYTHING:
    1. Checks Python 3.12 (offers to download if missing)
    2. Creates venv
    3. Installs PyTorch (auto-detects NVIDIA GPU)
    4. Installs all dependencies
    5. Downloads AI models (Whisper, Silero VAD)
    6. Opens firewall ports
    7. Creates .env with your API key
    8. Creates desktop shortcut
    9. Starts the system
    10. System auto-calls your phone once Linphone connects

    Zero interaction required after launch (unless Python is missing).
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiKey = "",

    [switch]$CpuOnly,
    [string]$CudaVersion = "cu121",
    [string]$WhisperModel = "base",
    [switch]$NoStart,
    [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ═══════════════════════════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  VOICE DISPATCH — FULL AUTO BOOTSTRAP" -ForegroundColor Cyan
Write-Host "  Everything installs. Then it calls your phone." -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$startTime = Get-Date
$errors = @()

function Log-Step {
    param([string]$step, [string]$msg)
    Write-Host "[$step] $msg" -ForegroundColor Yellow
}

function Log-OK {
    param([string]$msg)
    Write-Host "  + $msg" -ForegroundColor Green
}

function Log-Warn {
    param([string]$msg)
    Write-Host "  ! $msg" -ForegroundColor Yellow
    $script:errors += $msg
}

function Log-Fail {
    param([string]$msg)
    Write-Host "  X $msg" -ForegroundColor Red
    $script:errors += $msg
}

# ═══════════════════════════════════════════════════════════════════
# STEP 1: PYTHON
# ═══════════════════════════════════════════════════════════════════
Log-Step "1/10" "Checking Python..."

$python = $null
$needsAudioopLts = $false

foreach ($cmd in @("python", "python3", "py -3.12", "py")) {
    try {
        $cmdParts = $cmd -split " "
        $ver = & $cmdParts[0] $cmdParts[1..($cmdParts.Length-1)] --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                $python = $cmd
                if ($minor -ge 13) { $needsAudioopLts = $true }
                Log-OK "Found $ver"
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Log-Fail "Python 3.10+ not found."
    Write-Host ""
    Write-Host "  Attempting automatic Python 3.12 install via winget..." -ForegroundColor Yellow

    try {
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $python = "py -3.12"
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        Log-OK "Python 3.12 installed via winget"
    } catch {
        Log-Fail "Could not auto-install Python. Install Python 3.12 from python.org and re-run."
        exit 1
    }
}

# ═══════════════════════════════════════════════════════════════════
# STEP 2: VIRTUAL ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════
Log-Step "2/10" "Creating virtual environment..."

$venvPath = Join-Path $ProjectRoot "venv"
$pythonVenv = Join-Path $venvPath "Scripts\python.exe"
$pip = Join-Path $venvPath "Scripts\pip.exe"

if (Test-Path $pythonVenv) {
    Log-OK "venv exists, reusing"
} else {
    $cmdParts = $python -split " "
    & $cmdParts[0] $cmdParts[1..($cmdParts.Length-1)] -m venv $venvPath
    if (-not (Test-Path $pythonVenv)) {
        Log-Fail "Failed to create venv"
        exit 1
    }
    Log-OK "Created venv"
}

& $pythonVenv -m pip install --upgrade pip --quiet 2>$null
Log-OK "pip upgraded"

# ═══════════════════════════════════════════════════════════════════
# STEP 3: DETECT GPU + INSTALL PYTORCH
# ═══════════════════════════════════════════════════════════════════
Log-Step "3/10" "Installing PyTorch..."

$hasGpu = $false
if (-not $CpuOnly) {
    try {
        $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }
        if ($gpu) {
            $hasGpu = $true
            Log-OK "NVIDIA GPU detected: $($gpu.Name)"
        }
    } catch {}
}

if ($hasGpu) {
    Write-Host "  Installing PyTorch with CUDA ($CudaVersion) — large download, be patient..." -ForegroundColor Gray
    & $pip install torch torchaudio --index-url "https://download.pytorch.org/whl/$CudaVersion" --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        Log-Warn "CUDA PyTorch failed, falling back to CPU"
        & $pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet 2>$null
    } else {
        Log-OK "PyTorch installed with CUDA"
    }
} else {
    Write-Host "  Installing CPU-only PyTorch..." -ForegroundColor Gray
    & $pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet 2>$null
    Log-OK "PyTorch installed (CPU)"
}

# ═══════════════════════════════════════════════════════════════════
# STEP 4: INSTALL ALL DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════
Log-Step "4/10" "Installing dependencies..."

$reqFile = Join-Path $ProjectRoot "requirements.txt"
& $pip install -r $reqFile --quiet 2>$null

if ($needsAudioopLts) {
    & $pip install audioop-lts --quiet 2>$null
    Log-OK "Installed audioop-lts (Python 3.13+)"
}

# Verify critical packages
$criticalPackages = @("pyVoIP", "faster_whisper", "anthropic", "numpy")
$missingPkgs = @()
foreach ($pkg in $criticalPackages) {
    $check = & $pythonVenv -c "import $pkg" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $missingPkgs += $pkg
    }
}

if ($missingPkgs.Count -gt 0) {
    Log-Warn "Failed to import: $($missingPkgs -join ', ')"
} else {
    Log-OK "All critical packages verified"
}

# ═══════════════════════════════════════════════════════════════════
# STEP 5: PRE-DOWNLOAD AI MODELS
# ═══════════════════════════════════════════════════════════════════
Log-Step "5/10" "Pre-downloading AI models..."

# Whisper model
Write-Host "  Downloading Whisper '$WhisperModel' model..." -ForegroundColor Gray
& $pythonVenv -c "from faster_whisper import WhisperModel; WhisperModel('$WhisperModel', device='cpu', compute_type='int8'); print('OK')" 2>$null
if ($LASTEXITCODE -eq 0) {
    Log-OK "Whisper model cached"
} else {
    Log-Warn "Whisper download failed — will retry on first call"
}

# Silero VAD
Write-Host "  Downloading Silero VAD..." -ForegroundColor Gray
& $pythonVenv -c "
try:
    from silero_vad import load_silero_vad
    load_silero_vad()
except ImportError:
    import torch
    torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)
print('OK')
" 2>$null
if ($LASTEXITCODE -eq 0) {
    Log-OK "Silero VAD cached"
} else {
    Log-Warn "Silero VAD download failed — will retry on first call"
}

# ═══════════════════════════════════════════════════════════════════
# STEP 6: FIREWALL
# ═══════════════════════════════════════════════════════════════════
Log-Step "6/10" "Configuring firewall..."

if ($SkipFirewall) {
    Log-OK "Skipped (flag set)"
} else {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if ($isAdmin) {
        $rules = @(
            @{Name="VoiceDispatch-SIP"; Port="5060"; Desc="SIP signaling"},
            @{Name="VoiceDispatch-SIP2"; Port="5062"; Desc="pyVoIP endpoint"},
            @{Name="VoiceDispatch-RTP"; Port="10000-20000"; Desc="RTP audio"}
        )
        foreach ($rule in $rules) {
            $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
            if (-not $existing) {
                New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol UDP -LocalPort $rule.Port -Action Allow -Description $rule.Desc | Out-Null
                Log-OK "Firewall: $($rule.Name) ($($rule.Port) UDP)"
            } else {
                Log-OK "Firewall: $($rule.Name) exists"
            }
        }
    } else {
        Log-Warn "Not admin — run these manually in admin PowerShell:"
        Write-Host '  netsh advfirewall firewall add rule name="VD-SIP" dir=in action=allow protocol=UDP localport=5060' -ForegroundColor Gray
        Write-Host '  netsh advfirewall firewall add rule name="VD-SIP2" dir=in action=allow protocol=UDP localport=5062' -ForegroundColor Gray
        Write-Host '  netsh advfirewall firewall add rule name="VD-RTP" dir=in action=allow protocol=UDP localport=10000-20000' -ForegroundColor Gray
    }
}

# ═══════════════════════════════════════════════════════════════════
# STEP 7: DETECT LAN IP
# ═══════════════════════════════════════════════════════════════════
Log-Step "7/10" "Detecting network..."

$lanIP = & $pythonVenv -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>$null
if (-not $lanIP) { $lanIP = "UNKNOWN" }
Log-OK "LAN IP: $lanIP"

# ═══════════════════════════════════════════════════════════════════
# STEP 8: CREATE .env
# ═══════════════════════════════════════════════════════════════════
Log-Step "8/10" "Configuring .env..."

$envFile = Join-Path $ProjectRoot ".env"

if ($ApiKey) {
    # API key provided as parameter — write it
    $envContent = @"
# Voice Dispatch System Configuration
# Auto-generated by bootstrap.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm")
ANTHROPIC_API_KEY=$ApiKey
WHISPER_MODEL=$WhisperModel
WHISPER_DEVICE=$(if ($hasGpu) { "cuda" } else { "cpu" })
WHISPER_COMPUTE=$(if ($hasGpu) { "float16" } else { "int8" })
CLAUDE_MODEL=claude-sonnet-4-6
AUTO_CALL=true
SAVE_AUDIO=true
DISPATCH_LAN_IP=$lanIP
"@
    $envContent | Out-File -FilePath $envFile -Encoding UTF8 -Force
    Log-OK ".env created with API key"
} elseif (Test-Path $envFile) {
    Log-OK ".env exists, keeping"
} else {
    Log-Warn "No API key provided. Set it: .\bootstrap.ps1 -ApiKey sk-ant-..."
    # Create .env anyway with placeholder
    $envContent = @"
# Voice Dispatch System Configuration
# SET YOUR API KEY BELOW:
ANTHROPIC_API_KEY=
WHISPER_MODEL=$WhisperModel
WHISPER_DEVICE=$(if ($hasGpu) { "cuda" } else { "cpu" })
CLAUDE_MODEL=claude-sonnet-4-6
AUTO_CALL=true
SAVE_AUDIO=true
DISPATCH_LAN_IP=$lanIP
"@
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
}

# ═══════════════════════════════════════════════════════════════════
# STEP 9: DESKTOP SHORTCUT + RUN.BAT
# ═══════════════════════════════════════════════════════════════════
Log-Step "9/10" "Creating launcher..."

# Ensure run.bat exists
$runBat = Join-Path $ProjectRoot "run.bat"
if (-not (Test-Path $runBat)) {
    @"
@echo off
title Voice Dispatch System
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m voice_dispatch.watchdog_runner
pause
"@ | Out-File -FilePath $runBat -Encoding ASCII
}
Log-OK "run.bat ready"

# Desktop shortcut
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Voice Dispatch.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $runBat
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = "Start Voice Dispatch System"
    $shortcut.Save()
    Log-OK "Desktop shortcut created"
} catch {
    Log-Warn "Desktop shortcut failed (non-critical)"
}

# ═══════════════════════════════════════════════════════════════════
# STEP 10: QUICK SELF-TEST
# ═══════════════════════════════════════════════════════════════════
Log-Step "10/10" "Running self-test..."

$testScript = @'
import sys
results = []

# Test 1: Config loads
try:
    from voice_dispatch.config import LAN_IP, SIP_PORT
    results.append(f"OK config (LAN={LAN_IP})")
except Exception as e:
    results.append(f"FAIL config: {e}")

# Test 2: Audio utils
try:
    from voice_dispatch.audio_utils import sip_to_pcm16, tts_float_to_sip
    sip_to_pcm16(bytes([128]*160))
    results.append("OK audio_utils")
except Exception as e:
    results.append(f"FAIL audio_utils: {e}")

# Test 3: SIP registrar
try:
    from voice_dispatch.sip_registrar import SIPRegistrar
    r = SIPRegistrar(host="127.0.0.1", port=0, lan_ip="127.0.0.1")
    results.append("OK sip_registrar")
except Exception as e:
    results.append(f"FAIL sip_registrar: {e}")

# Test 4: Anthropic SDK
try:
    import anthropic
    results.append("OK anthropic SDK")
except Exception as e:
    results.append(f"FAIL anthropic: {e}")

# Test 5: PyTorch
try:
    import torch
    cuda = "CUDA" if torch.cuda.is_available() else "CPU"
    results.append(f"OK torch ({cuda})")
except Exception as e:
    results.append(f"FAIL torch: {e}")

# Test 6: pyVoIP
try:
    import pyVoIP
    results.append(f"OK pyVoIP v{pyVoIP.__version__}")
except Exception as e:
    results.append(f"FAIL pyVoIP: {e}")

for r in results:
    print(f"  {r}")

fails = [r for r in results if r.startswith("FAIL")]
sys.exit(len(fails))
'@

& $pythonVenv -c $testScript
$testFails = $LASTEXITCODE

if ($testFails -eq 0) {
    Log-OK "All self-tests passed"
} else {
    Log-Warn "$testFails test(s) failed — check above"
}

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
$elapsed = (Get-Date) - $startTime

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor $(if ($errors.Count -eq 0) { "Green" } else { "Yellow" })

if ($errors.Count -eq 0) {
    Write-Host "  SETUP COMPLETE — zero errors" -ForegroundColor Green
} else {
    Write-Host "  SETUP COMPLETE — $($errors.Count) warning(s)" -ForegroundColor Yellow
    foreach ($e in $errors) {
        Write-Host "    - $e" -ForegroundColor Yellow
    }
}

Write-Host "  Time: $([math]::Round($elapsed.TotalMinutes, 1)) minutes" -ForegroundColor Gray
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor $(if ($errors.Count -eq 0) { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "  Your PC's IP: $lanIP" -ForegroundColor White
Write-Host ""
Write-Host "  PHONE SETUP (Linphone app):" -ForegroundColor White
Write-Host "    SIP server:  $lanIP" -ForegroundColor Cyan
Write-Host "    Username:    200" -ForegroundColor Cyan
Write-Host "    Password:    phone123" -ForegroundColor Cyan
Write-Host "    Transport:   UDP" -ForegroundColor Cyan
Write-Host ""

# ═══════════════════════════════════════════════════════════════════
# AUTO-START
# ═══════════════════════════════════════════════════════════════════
if ($NoStart) {
    Write-Host "  To start: double-click run.bat or 'Voice Dispatch' on desktop" -ForegroundColor White
} else {
    if (-not $ApiKey) {
        Write-Host "  No API key set — cannot start yet." -ForegroundColor Yellow
        Write-Host "  Re-run with: .\bootstrap.ps1 -ApiKey sk-ant-..." -ForegroundColor Yellow
    } else {
        Write-Host "  Starting Voice Dispatch in 3 seconds..." -ForegroundColor Green
        Write-Host "  Set up Linphone on your phone NOW with the details above." -ForegroundColor Green
        Write-Host "  When your phone connects, IT WILL RING." -ForegroundColor Green
        Write-Host ""
        Start-Sleep -Seconds 3

        # Start the system
        & $pythonVenv -m voice_dispatch.main
    }
}
