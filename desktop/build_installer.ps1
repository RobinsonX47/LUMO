param(
    [string]$Python = "f:/LUMO/.venv/Scripts/python.exe",
    [string]$IconPath = "static/images/logo.ico"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    throw "Python executable not found at: $Python"
}

$iexpress = Get-Command iexpress.exe -ErrorAction SilentlyContinue
if (-not $iexpress) {
    throw "IExpress (iexpress.exe) was not found on this machine."
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $projectRoot

if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "desktop/installer/work") { Remove-Item -Recurse -Force "desktop/installer/work" }

New-Item -ItemType Directory -Path "dist" | Out-Null
New-Item -ItemType Directory -Path "desktop/installer/work" | Out-Null

powershell -ExecutionPolicy Bypass -File "desktop/build_desktop.ps1" -Python $Python -IconPath $IconPath

$distAppDir = Join-Path $projectRoot "dist/LUMO-Desktop"
if (-not (Test-Path $distAppDir)) {
    throw "Expected onedir output missing: $distAppDir"
}

$workDir = Join-Path $projectRoot "desktop/installer/work"
Copy-Item "desktop/installer/install.cmd" (Join-Path $workDir "install.cmd") -Force
Compress-Archive -Path (Join-Path $distAppDir "*") -DestinationPath (Join-Path $workDir "app.zip") -Force

$setupExe = Join-Path $projectRoot "dist/LUMO-Installer.exe"
$sedPath = Join-Path $workDir "lumo-installer.sed"
$sourceDirEscaped = ($workDir + "\").Replace("\", "\\")
$targetEscaped = $setupExe.Replace("\", "\\")

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=1
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$targetEscaped
FriendlyName=LUMO Desktop Installer
AppLaunched=cmd /c install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=cmd /c install.cmd
UserQuietInstCmd=cmd /c install.cmd
SourceFiles=SourceFiles
[Strings]
FILE0=install.cmd
FILE1=app.zip
[SourceFiles]
SourceFiles0=$sourceDirEscaped
[SourceFiles0]
%FILE0%=
%FILE1%=
"@

Set-Content -Path $sedPath -Value $sed -Encoding ASCII

& $iexpress.Source /N $sedPath
if ($LASTEXITCODE -ne 0) {
    throw "IExpress failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $setupExe)) {
    throw "Installer was not created at $setupExe"
}

Write-Host "Installer build complete: dist/LUMO-Installer.exe"
