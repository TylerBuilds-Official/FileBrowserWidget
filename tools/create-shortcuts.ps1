param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\launchers')
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$launcherPath = Join-Path $projectRoot 'launch.pyw'
$iconPath = Join-Path $projectRoot 'src\assets\filter.ico'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create the project .venv and install PyQt6 before creating shortcuts.'
}
$shortcutDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $shortcutDirectory -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
foreach ($entry in @(
    @{ Name = 'File Browser.lnk'; Arguments = ''; Description = 'Open File Browser (Alt+B while running)' },
    @{ Name = 'File Browser (Startup).lnk'; Arguments = ' --background'; Description = 'Start File Browser quietly in the system tray' }
)) {
    $shortcutPath = Join-Path $shortcutDirectory $entry.Name
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonPath
    $shortcut.Arguments = '"' + $launcherPath + '"' + $entry.Arguments
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = $iconPath + ',0'
    $shortcut.Description = $entry.Description
    $shortcut.Save()
    Write-Output $shortcutPath
}
