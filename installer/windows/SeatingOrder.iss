; Inno Setup script for SeatingOrder
; Requires built executable at dist\SeatingOrder.exe

#define MyAppName "SeatingOrder"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Classroom"
#define MyAppExeName "SeatingOrder.exe"

[Setup]
AppId={{D5D8E8DA-2A6F-4EE7-8E6A-6C2A711B6B5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist-installer
OutputBaseFilename=SeatingOrder-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Files]
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Spustit {#MyAppName}"; Flags: nowait postinstall skipifsilent
