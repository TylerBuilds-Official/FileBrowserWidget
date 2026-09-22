<#
.SYNOPSIS
    Build File Browser: compile the Qt resources, freeze the app, and package the installer.

.DESCRIPTION
    PyQt6 ships no resource compiler, so the resources are compiled with PySide6's rcc and the
    generated module is repointed at PyQt6 (qRegisterResourceData exists in both bindings).
    PySide6 is installed into a throwaway virtual environment and thrown away with it, so it can
    never end up inside the frozen app: two Qt bindings in one bundle break the build.
#>
param(
    [string]$Version,
    [string]$Iscc,
    [switch]$SkipResources,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Create the project .venv first: $python is missing." }
if (-not $Version) {
    $match = Select-String -LiteralPath (Join-Path $root 'src\version.py') -Pattern 'VERSION = "([^"]+)"'
    if (-not $match) { throw 'src\version.py has no VERSION = "x.y.z" line.' }
    $Version = $match.Matches[0].Groups[1].Value
}

if (-not $SkipResources) {
    Write-Host '== Compiling Qt resources ==' -ForegroundColor Cyan
    $rccVenv = Join-Path $env:TEMP "filebrowser-rcc-$([guid]::NewGuid().ToString('N').Substring(0,8))"
    try {
        & $python -m venv $rccVenv
        & (Join-Path $rccVenv 'Scripts\python.exe') -m pip install --quiet --disable-pip-version-check PySide6-Essentials
        $generated = Join-Path $root 'src\assets\resources_rc.py'
        & (Join-Path $rccVenv 'Scripts\pyside6-rcc.exe') (Join-Path $root 'src\assets\resources.qrc') -o $generated
        if (-not (Test-Path -LiteralPath $generated)) { throw 'pyside6-rcc produced no output.' }

        # Repoint the generated module at PyQt6 so the app has one Qt binding, not two.
        $text = Get-Content -LiteralPath $generated -Raw
        if ($text -notmatch 'from PySide6 import QtCore') { throw 'Unexpected rcc output: no PySide6 import to repoint.' }
        $note = @"
#
# Generated with pyside6-rcc, because PyQt6 ships no resource compiler, then repointed
# at PyQt6: qRegisterResourceData/qUnregisterResourceData exist in both bindings.
# Regenerate with tools/build.ps1, which patches this import again.

from PyQt6 import QtCore
"@
        # rcc writes CRLF on Windows; match the line whatever ends it, and prove the swap happened.
        $text = [regex]::Replace($text, '(?m)^from PySide6 import QtCore?$', $note.TrimEnd())
        if ($text -match 'from PySide6') { throw 'resources_rc.py still imports PySide6 after repointing.' }
        if ($text -notmatch 'from PyQt6 import QtCore') { throw 'resources_rc.py has no PyQt6 import after repointing.' }
        [System.IO.File]::WriteAllText($generated, $text, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "   resources_rc.py regenerated and repointed at PyQt6"
    }
    finally {
        # The PySide6 binaries go away with the venv, before PyInstaller ever looks around.
        Remove-Item -LiteralPath $rccVenv -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host '== Building the icon and wizard images ==' -ForegroundColor Cyan
& $python -B (Join-Path $root 'tools\build-icon.py')
if ($LASTEXITCODE -ne 0) { throw "build-icon.py exited with $LASTEXITCODE" }

# Task Manager names a process by its FileDescription; without one it shows FileBrowser.exe.
$versionFile = Join-Path $root 'build\FileBrowser.version'
New-Item -ItemType Directory -Force (Split-Path $versionFile) | Out-Null
$parts = @($Version -split '\.') + @('0', '0', '0', '0')
$tuple = "($($parts[0]), $($parts[1]), $($parts[2]), $($parts[3]))"
$versionText = @"
# Version resource for FileBrowser.exe, written by tools/build.ps1 from src/version.py.
VSVersionInfo(
  ffi=FixedFileInfo(filevers=$tuple, prodvers=$tuple, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'TylerBuilds'),
      StringStruct('FileDescription', 'File Browser'),
      StringStruct('FileVersion', '$Version'),
      StringStruct('InternalName', 'FileBrowser'),
      StringStruct('OriginalFilename', 'FileBrowser.exe'),
      StringStruct('ProductName', 'File Browser'),
      StringStruct('ProductVersion', '$Version')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
[System.IO.File]::WriteAllText($versionFile, $versionText, (New-Object System.Text.UTF8Encoding $false))

Write-Host '== Freezing the app ==' -ForegroundColor Cyan
Push-Location $root
try {
    & $python -m PyInstaller --noconfirm --clean --windowed --name FileBrowser `
        --icon src\assets\logo\fb_icon.ico `
        --version-file $versionFile `
        --exclude-module PySide6 --exclude-module PySide2 --exclude-module PyQt5 `
        --exclude-module tkinter --exclude-module pytest `
        launch.pyw
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller exited with $LASTEXITCODE" }
}
finally { Pop-Location }

$leaked = Get-ChildItem (Join-Path $root 'dist') -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'pyside|shiboken' }
if ($leaked) { throw "PySide6 leaked into the bundle: $($leaked[0].FullName)" }
Write-Host "   dist\FileBrowser built, no second Qt binding inside"

if ($SkipInstaller) { return }

Write-Host '== Packaging the installer ==' -ForegroundColor Cyan
if (-not $Iscc) {
    $candidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
        'A:\DevTools\Inno Setup 7\ISCC.exe',
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if (-not $Iscc) { throw 'ISCC.exe not found. Pass -Iscc <path> or add Inno Setup to PATH.' }

& $Iscc "/DMyAppVersion=$Version" (Join-Path $root 'installer\FileBrowser.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC exited with $LASTEXITCODE" }
Write-Host "   installer\Output\FileBrowserSetup-$Version.exe" -ForegroundColor Green
