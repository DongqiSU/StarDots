#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Stardot"

[Setup]
AppId={{38AC61BA-D0EE-4E74-A108-8E2F80C5742B}
AppName=Stardot 星点
AppVersion={#AppVersion}
AppVerName=Stardot 星点 {#AppVersion}
DefaultDirName={localappdata}\Programs\Stardot
DefaultGroupName=Stardot
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\Stardot.exe
SetupIconFile=..\build\preview-assets\Stardot.ico
OutputDir=..\dist
OutputBaseFilename=Stardot-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
VersionInfoVersion=1.0.0.0
InfoBeforeFile=..\build-support\preview-notes.txt

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: unchecked

[Files]
Source: "..\dist\Stardot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Stardot"; Filename: "{app}\Stardot.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Stardot"; Filename: "{app}\Stardot.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Stardot.exe"; Description: "启动 Stardot 星点"; Flags: nowait postinstall skipifsilent

; User tasks live outside {app}. Uninstallation never deletes the task database.
