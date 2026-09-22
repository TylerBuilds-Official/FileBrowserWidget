; File Browser installer. Build with tools\build.ps1, or compile this directly with
;   ISCC.exe /DMyAppVersion=0.1.1 installer\FileBrowser.iss
; after PyInstaller has produced dist\FileBrowser.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.1"
#endif
#define MyAppName "File Browser"
#define MyAppPublisher "TylerBuilds"
#define MyAppExeName "FileBrowser.exe"
#define MyAppUrl "https://github.com/TylerBuilds-Official/FileBrowserWidget"

[Setup]
; Keep this GUID: it is how Windows recognises an upgrade rather than a second copy.
AppId={{8F5B1C42-3A7D-4E96-9C1B-2D6A0F4E7B31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}
AppUpdatesURL={#MyAppUrl}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; The app keeps its startup entry and settings under HKCU, so it installs per user without
; a UAC prompt. Anyone who wants it for the whole machine can still elevate in the dialog.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The app sits in the tray, so an upgrade has to ask it to close before replacing its files.
CloseApplications=yes
RestartApplications=no
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#SourcePath}\..\src\assets\logo\fb_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir={#SourcePath}\Output
OutputBaseFilename=FileBrowserSetup-{#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourcePath}\..\dist\FileBrowser\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\dist\FileBrowser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Settings -> Start with Windows writes this value itself; clear it when the app goes away,
; so an uninstalled app cannot leave a startup entry pointing at nothing.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "FileBrowserWidget"; ValueType: none; Flags: dontcreatekey uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"; ValueName: "FileBrowserWidget"; ValueType: none; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
