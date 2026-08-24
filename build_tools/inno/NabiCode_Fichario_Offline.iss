#ifndef AppVersion
  #error AppVersion deve ser fornecida pelo build_fichario.py
#endif

#define AppName "NabiCode Fichario"
#define DistName "NabiCode_Fichario_v" + StringChange(AppVersion, ".", "_")
#define AppExe DistName + ".exe"
#ifndef DistSource
  #define DistSource "..\..\build_output\fichario\dist\" + DistName
#endif

[Setup]
AppId={{8A761427-FF35-4EC7-BAB4-7A09B9D72208}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NabiCode
DefaultDirName={autopf}\NabiCode Fichario
DefaultGroupName=NabiCode Fichario
OutputDir=..\..\build_output\fichario\installer
OutputBaseFilename=NabiCode_Fichario_{#AppVersion}_Setup_Offline
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
#ifdef AppIconFile
SetupIconFile={#AppIconFile}
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; Flags: unchecked

[Files]
Source: "{#DistSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\NabiCode Fichario"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\NabiCode Fichario"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Executar NabiCode Fichario"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  { Instalador integralmente offline. Dados ficam em AppData e sao preservados. }
  Result := True;
end;
