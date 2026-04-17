#define MyAppName "Format Foundry"
#define MyAppVersion "1.8.16"
#define MyAppPublisher "Format Foundry"
#define MyAppExeName "FormatFoundry.exe"
#define MyUpdaterExeName "FormatFoundry_Updater.exe"

[Setup]
AppId={{33D7E9DA-6CF5-44F7-84E8-06DF57C05495}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Format Foundry
UsePreviousAppDir=yes
DisableDirPage=auto
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
AppMutex=Local\UniversalFileUtilitySuite_SingleInstanceMutex,Local\UniversalFileUtilitySuiteUpdater_SingleInstanceMutex,Local\UniversalConversionHubHCB_SingleInstanceMutex,Local\UniversalConversionHubHCBUpdater_SingleInstanceMutex,Local\UniversalConversionHubUCH_SingleInstanceMutex,Local\UniversalConversionHubUCHUpdater_SingleInstanceMutex,Local\FormatFoundry_SingleInstanceMutex,Local\FormatFoundryUpdater_SingleInstanceMutex
OutputDir=..\installer_output
OutputBaseFilename=FormatFoundry_Setup
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
Source: "..\dist\FormatFoundry.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\FormatFoundry_Updater.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PROJECT_PLAN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\update_manifest.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Format Foundry"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Format Foundry Updater"; Filename: "{app}\{#MyUpdaterExeName}"
Name: "{autoprograms}\Uninstall Format Foundry"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Format Foundry"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Format Foundry"; Flags: nowait postinstall skipifsilent





