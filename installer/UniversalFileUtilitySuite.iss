#define MyAppName "Universal File Utility Suite"
#define MyAppVersion "0.4.10"
#define MyAppPublisher "Universal File Utility Suite"
#define MyAppExeName "UniversalFileUtilitySuite.exe"

[Setup]
AppId={{33D7E9DA-6CF5-44F7-84E8-06DF57C05495}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Universal File Utility Suite
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=UniversalFileUtilitySuite_Setup
SetupIconFile=..\assets\universal_file_utility_suite.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\UniversalFileUtilitySuite.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PROJECT_PLAN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\update_manifest.example.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Universal File Utility Suite"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Universal File Utility Suite"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Universal File Utility Suite"; Flags: nowait postinstall skipifsilent
