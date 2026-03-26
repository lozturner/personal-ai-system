<#
Voice Dispatch — Control Panel
Double-click run.bat or run this directly.
Handles: kill old instances, start fresh, restart, auto-call.
#>

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonVenv = Join-Path $ProjectRoot "venv\Scripts\python.exe"

function Kill-OldInstances {
    # Kill any existing voice dispatch processes and free ports
    $procs = Get-Process python*, powershell* -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -ne $PID }

    # Find processes using our SIP ports
    $portUsers = netstat -ano 2>$null | Select-String ":5060 |:5062 " |
        ForEach-Object {
            if ($_ -match '\s+(\d+)\s*$') { [int]$Matches[1] }
        } | Sort-Object -Unique | Where-Object { $_ -ne 0 -and $_ -ne $PID }

    foreach ($pid in $portUsers) {
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Killing old process: $($proc.Name) (PID $pid)" -ForegroundColor Gray
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }

    # Wait a moment for ports to free
    Start-Sleep -Seconds 2
}

function Start-VoiceDispatch {
    Kill-OldInstances

    Write-Host ""
    Write-Host "  Starting Voice Dispatch..." -ForegroundColor Green
    Write-Host ""

    $script:dispatchProcess = Start-Process -FilePath $pythonVenv `
        -ArgumentList "-m", "voice_dispatch.main" `
        -WorkingDirectory $ProjectRoot `
        -NoNewWindow -PassThru

    return $script:dispatchProcess
}

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
Clear-Host
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  VOICE DISPATCH — CONTROL PANEL" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Commands (type anytime):" -ForegroundColor White
Write-Host "    R  = Restart the system" -ForegroundColor Yellow
Write-Host "    S  = Stop the system" -ForegroundColor Yellow
Write-Host "    Q  = Quit everything" -ForegroundColor Yellow
Write-Host "    U  = Update code (git pull) + restart" -ForegroundColor Yellow
Write-Host ""

# Start it
$proc = Start-VoiceDispatch

# Monitor loop — check for user input and process health
while ($true) {
    # Check if process died
    if ($proc.HasExited) {
        Write-Host ""
        Write-Host "  System crashed (exit code $($proc.ExitCode)). Auto-restarting in 3s..." -ForegroundColor Red
        Write-Host "  Press Q to quit instead, or wait..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
        $proc = Start-VoiceDispatch
    }

    # Check for keypress (non-blocking)
    if ([Console]::KeyAvailable) {
        $key = [Console]::ReadKey($true).KeyChar.ToString().ToUpper()

        switch ($key) {
            "R" {
                Write-Host ""
                Write-Host "  >>> RESTARTING <<<" -ForegroundColor Yellow
                try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
                Start-Sleep -Seconds 1
                $proc = Start-VoiceDispatch
            }
            "S" {
                Write-Host ""
                Write-Host "  >>> STOPPED <<<" -ForegroundColor Yellow
                try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
                Write-Host "  Press R to restart, Q to quit." -ForegroundColor Gray
            }
            "U" {
                Write-Host ""
                Write-Host "  >>> UPDATING + RESTARTING <<<" -ForegroundColor Yellow
                try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
                Start-Sleep -Seconds 1
                Push-Location $ProjectRoot
                git pull
                Pop-Location
                Start-Sleep -Seconds 1
                $proc = Start-VoiceDispatch
            }
            "Q" {
                Write-Host ""
                Write-Host "  >>> QUITTING <<<" -ForegroundColor Yellow
                try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
                Kill-OldInstances
                Write-Host "  Goodbye." -ForegroundColor Green
                exit 0
            }
        }
    }

    Start-Sleep -Milliseconds 500
}
