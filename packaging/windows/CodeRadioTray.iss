; Inno Setup script — per-user install (no admin / not Program Files)
; Compile via scripts\build_windows.ps1 (passes /DMyAppVersion=…)

#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif

#define MyAppName "Code Radio Tray"
#define MyAppPublisher "coderadio-on-tray (unofficial)"
#define MyAppURL "https://github.com/pawprint0706/coderadio-on-tray"
#define MyAppExeName "CodeRadioTray.exe"

[Setup]
AppId={{A7C3E8F1-4B2D-4E9A-9C1F-CoderadioTray01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\CodeRadioTray
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user only — no UAC elevation, not under Program Files
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=CodeRadioTray-{#MyAppVersion}-win64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Entire PyInstaller onedir (exe + _internal + mpv)
Source: "..\..\dist\CodeRadioTray\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
