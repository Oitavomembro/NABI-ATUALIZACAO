#ifndef AppVersion
  #error AppVersion deve ser fornecida por build_windows.py
#endif

#define AppName "NabiCode"
#define DistName "NabiCode_v" + StringChange(AppVersion, ".", "_")
#define AppExe DistName + ".exe"

[Setup]
AppId={{F186E71A-73A5-4E5E-B8B1-9C6488CF9267}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NabiCode
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
DefaultDirName={autopf}\NabiCode
DefaultGroupName=NabiCode
DisableProgramGroupPage=yes
OutputDir=..\..\build_output\installer
OutputBaseFilename=NabiCode_{#AppVersion}_Setup_Offline
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName=NabiCode {#AppVersion}
AppMutex=NabiCodeApplicationMutex
CloseApplications=yes
RestartApplications=no
UninstallLogMode=append
WizardStyle=modern
SetupLogging=yes
#ifdef AppIconFile
SetupIconFile={#AppIconFile}
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\..\build_output\dist\{#DistName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\NabiCode"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\NabiCode"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Executar NabiCode"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  { O setup é integralmente offline. Não há download, pip ou instalação de Python. }
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Dados operacionais do NabiCode em AppData são deliberadamente preservados. }
    Log('Dados operacionais do NabiCode preservados em AppData.');
  end;
end;
