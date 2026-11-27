; AutoClicker Windows installer (Inno Setup 6.5+)
; Build from repository root with scripts/build_installer.ps1.
#ifndef MyAppVersion
  #define MyAppVersion "5.0.0"
#endif

#define MyAppName "AutoClicker"
#define MyAppPublisher "YJH9999"
#define MyAppURL "https://github.com/YJH9999/Autoclick"
#define MyAppExeName "AutoClicker.exe"

[Setup]
AppId={{57E7D6B1-3D2F-4D55-9C7E-AC10D0C50001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\AutoClicker
DefaultGroupName=AutoClicker
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=AutoClicker-{#MyAppVersion}-Windows-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\AutoClicker.exe
UninstallDisplayName=AutoClicker
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\AutoClicker_SingleInstance_V5
CloseApplications=yes
CloseApplicationsFilter=AutoClicker.exe
RestartApplications=no
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=AutoClicker Windows Setup
VersionInfoProductName=AutoClicker
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (c) 2026 AutoClicker contributors

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "startmenuicon"; Description: "创建开始菜单快捷方式(&S)"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; PyInstaller onedir: the root EXE is the single entry point; Python modules,
; dependency DLLs and resources are loaded from _internal at runtime.
Source: "..\dist\AutoClicker\AutoClicker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\AutoClicker\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\AutoClicker"; Filename: "{app}\AutoClicker.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\AutoClicker"; Filename: "{app}\AutoClicker.exe"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autoprograms}\卸载 AutoClicker"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
Filename: "{app}\AutoClicker.exe"; Description: "{cm:LaunchProgram,AutoClicker}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
