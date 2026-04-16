param(
    [string]$Python = "f:/LUMO/.venv/Scripts/python.exe",
    [string]$IconPath = "static/images/logo.ico",
    [string]$Launcher = "desktop/launcher.py",
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    throw "Python executable not found at: $Python"
}

if (-not (Test-Path $Launcher)) {
    throw "Launcher script not found at: $Launcher"
}

if ($Launcher -like "*launcher_qt.py") {
    Write-Warning "Qt launcher selected. If embeds fail to play, rebuild with -Launcher desktop/launcher.py"
}

Remove-Item -Recurse -Force "build\LUMO-Desktop" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist\LUMO-Desktop" -ErrorAction SilentlyContinue
Remove-Item -Force "dist\LUMO-Desktop.exe" -ErrorAction SilentlyContinue

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--log-level", "WARN",
    "--windowed",
    "--name", "LUMO-Desktop",
    "--add-data", "templates;templates",
    "--add-data", "static;static"
)

if (Test-Path ".env") {
    $pyInstallerArgs += @("--add-data", ".env;.")
    Write-Host "Including .env in desktop package"
} else {
    Write-Warning "No .env file found. Desktop build may miss runtime API keys."
}

if ($OneFile) {
    $pyInstallerArgs += "--onefile"
}

if ($IconPath -and (Test-Path $IconPath)) {
    $pyInstallerArgs += @("--icon", $IconPath)
} else {
    Write-Warning "Icon file not found at '$IconPath'. Building without custom icon."
}

$pyInstallerArgs += $Launcher

& $Python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if ($OneFile) {
    if (-not (Test-Path "dist\LUMO-Desktop.exe")) {
        throw "Build incomplete: dist/LUMO-Desktop.exe not found"
    }
    Write-Host "Build complete. Check dist/LUMO-Desktop.exe"
    Write-Host "Share this single EXE only when using -OneFile build."
} else {
    if (-not (Test-Path "dist\LUMO-Desktop\LUMO-Desktop.exe")) {
        throw "Build incomplete: dist/LUMO-Desktop/LUMO-Desktop.exe not found"
    }
    if (-not (Test-Path "dist\LUMO-Desktop\_internal\python312.dll")) {
        throw "Build incomplete: dist/LUMO-Desktop/_internal/python312.dll not found"
    }

    if (Test-Path ".env") {
        Copy-Item ".env" "dist\LUMO-Desktop\.env" -Force
        Write-Host "Copied .env into dist/LUMO-Desktop/.env"
    }

    $portableZip = "dist\LUMO-Desktop-portable.zip"
    Remove-Item -Force $portableZip -ErrorAction SilentlyContinue
    Compress-Archive -Path "dist\LUMO-Desktop\*" -DestinationPath $portableZip -Force
    Write-Host "Portable package created: $portableZip"

    Write-Host "Build complete. Check dist/LUMO-Desktop/LUMO-Desktop.exe"
    Write-Host "IMPORTANT: Do not share only the EXE from onedir build."
    Write-Host "Share either dist/LUMO-Desktop-portable.zip or the full dist/LUMO-Desktop folder."
}
