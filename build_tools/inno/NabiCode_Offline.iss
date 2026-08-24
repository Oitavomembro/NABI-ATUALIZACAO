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
UninstallDisplayIcon={app}\NabiCode.ico
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
Name: "{autoprograms}\NabiCode"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\NabiCode.ico"; IconIndex: 0
Name: "{autodesktop}\NabiCode"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\NabiCode.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Executar NabiCode"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
const
  LegacyR6UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{D8DD09BC-A699-4E77-A011-786A02A19596}_is1';
  OfficialUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F186E71A-73A5-4E5E-B8B1-9C6488CF9267}_is1';

var
  MaintenancePage: TInputOptionWizardPage;
  MaintenanceFinished: Boolean;
  OfficialInstallLocation: String;
  LegacyInstallLocation: String;
  OldInstallLocations: TStringList;

function RunRegisteredUninstaller(const RootKey: Integer; const RegistryKey: String): Boolean;
var
  InstallLocation: String;
  Uninstaller: String;
  ResultCode: Integer;
begin
  Result := True;
  if not RegQueryStringValue(RootKey, RegistryKey, 'InstallLocation', InstallLocation) then
    Exit;
  Uninstaller := AddBackslash(InstallLocation) + 'unins000.exe';
  if not FileExists(Uninstaller) then
  begin
    Result := False;
    Exit;
  end;
  Result := Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

procedure RemoveRegisteredNabiCodeInstallsAtRoot(const RootKey: Integer);
var
  Names: TArrayOfString;
  Index: Integer;
  RegistryKey: String;
  DisplayName: String;
  Publisher: String;
  InstallLocation: String;
begin
  if not RegGetSubkeyNames(RootKey,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall', Names) then
    Exit;
  for Index := 0 to GetArrayLength(Names) - 1 do
  begin
    RegistryKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + Names[Index];
    if (RootKey = HKLM64) and (CompareText(RegistryKey, OfficialUninstallKey) = 0) then
      Continue;
    DisplayName := '';
    Publisher := '';
    RegQueryStringValue(RootKey, RegistryKey, 'DisplayName', DisplayName);
    RegQueryStringValue(RootKey, RegistryKey, 'Publisher', Publisher);
    if (Pos('NABICODE', Uppercase(DisplayName)) = 1) and
      (CompareText(Publisher, 'NabiCode') = 0) then
    begin
      InstallLocation := '';
      if RegQueryStringValue(RootKey, RegistryKey, 'InstallLocation', InstallLocation) and
        (InstallLocation <> '') then
        OldInstallLocations.Add(InstallLocation);
      if not RunRegisteredUninstaller(RootKey, RegistryKey) then
        RegDeleteKeyIncludingSubkeys(RootKey, RegistryKey);
    end;
  end;
end;

procedure RemoveOtherRegisteredNabiCodeInstalls();
begin
  { Cobre instalações por máquina, por usuário e legados registrados em 32 bits. }
  RemoveRegisteredNabiCodeInstallsAtRoot(HKLM64);
  RemoveRegisteredNabiCodeInstallsAtRoot(HKLM32);
  RemoveRegisteredNabiCodeInstallsAtRoot(HKCU);
end;

procedure RemoveLegacyShortcuts();
begin
  { Remove atalhos de qualquer revisão anterior; o instalador recria somente o oficial. }
  DelTree(ExpandConstant('{commonprograms}\NabiCode*.lnk'), False, True, False);
  DelTree(ExpandConstant('{userprograms}\NabiCode*.lnk'), False, True, False);
  DelTree(ExpandConstant('{commondesktop}\NabiCode*.lnk'), False, True, False);
  DelTree(ExpandConstant('{userdesktop}\NabiCode*.lnk'), False, True, False);
  DeleteFile(ExpandConstant('{commonprograms}\NabiCode TESTE R6.lnk'));
  DeleteFile(ExpandConstant('{userprograms}\NabiCode TESTE R6.lnk'));
  DeleteFile(ExpandConstant('{commondesktop}\NabiCode TESTE R6.lnk'));
  DeleteFile(ExpandConstant('{userdesktop}\NabiCode TESTE R6.lnk'));
end;

function RemoveLegacyR6(): String;
var
  InstallLocation: String;
  Uninstaller: String;
  ResultCode: Integer;
begin
  Result := '';
  if not RegQueryStringValue(HKLM64, LegacyR6UninstallKey, 'InstallLocation', InstallLocation) then
  begin
    RemoveLegacyShortcuts();
    Exit;
  end;

  Uninstaller := AddBackslash(InstallLocation) + 'unins000.exe';
  if FileExists(Uninstaller) then
  begin
    Log('Removendo instalação legada NabiCode TESTE R6 antes da atualização.');
    if not Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode) then
    begin
      Result := 'Não foi possível iniciar a remoção da instalação antiga do NabiCode.';
      Exit;
    end;
    if ResultCode <> 0 then
    begin
      Result := 'A instalação antiga do NabiCode não pôde ser removida. Código: ' + IntToStr(ResultCode) + '.';
      Exit;
    end;
  end
  else
  begin
    { Entrada legada quebrada: remove somente o registro conhecido; dados e pasta são preservados. }
    RegDeleteKeyIncludingSubkeys(HKLM64, LegacyR6UninstallKey);
  end;
  RemoveLegacyShortcuts();
end;

function InitializeSetup(): Boolean;
begin
  { O setup é integralmente offline. Não há download, pip ou instalação de Python. }
  Result := True;
end;

procedure InitializeWizard();
begin
  MaintenanceFinished := False;
  OldInstallLocations := TStringList.Create;
  RegQueryStringValue(HKLM64, OfficialUninstallKey, 'InstallLocation', OfficialInstallLocation);
  RegQueryStringValue(HKLM64, LegacyR6UninstallKey, 'InstallLocation', LegacyInstallLocation);
  if RegKeyExists(HKLM64, OfficialUninstallKey) then
  begin
    MaintenancePage := CreateInputOptionPage(wpWelcome,
      'Manutenção do NabiCode', 'O NabiCode já está instalado neste computador.',
      'Escolha o que deseja fazer e clique em Avançar:', True, False);
    MaintenancePage.Add('Atualizar ou reparar o NabiCode (mantém todos os dados)');
    MaintenancePage.Add('Desinstalar o programa e manter banco, backups e configurações');
    MaintenancePage.SelectedValueIndex := 0;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (MaintenancePage = nil) or (CurPageID <> MaintenancePage.ID) or
    (MaintenancePage.SelectedValueIndex = 0) then
    Exit;

  if not RunRegisteredUninstaller(HKLM64, OfficialUninstallKey) then
  begin
    MsgBox('Não foi possível executar o desinstalador oficial do NabiCode.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  RemoveLegacyR6();
  RemoveOtherRegisteredNabiCodeInstalls();
  RemoveLegacyShortcuts();
  MaintenanceFinished := True;
  MsgBox('Manutenção concluída com sucesso.', mbInformation, MB_OK);
  WizardForm.Close;
  Result := False;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if MaintenanceFinished then
  begin
    Cancel := True;
    Confirm := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { Revisões atuais compartilham o AppId oficial; esta ponte é somente para o instalador R6 isolado. }
  Result := RemoveLegacyR6();
  if Result = '' then
    RemoveOtherRegisteredNabiCodeInstalls();
end;

function InitializeUninstall(): Boolean;
var
  Choice: Integer;
begin
  if UninstallSilent then
  begin
    { Atualizações e remoções silenciosas nunca apagam dados operacionais. }
    Result := True;
    Exit;
  end;

  Choice := SuppressibleMsgBox(
    'Como deseja desinstalar o NabiCode?' + #13#10 + #13#10 +
    'SIM — Desinstalar o programa e manter banco, backups e configurações.' + #13#10 +
    'NÃO — Não desinstalar.' + #13#10 +
    'CANCELAR — Não desinstalar.',
    mbConfirmation, MB_YESNOCANCEL or MB_DEFBUTTON2, IDNO);
  if (Choice = IDCANCEL) or (Choice = IDNO) then
  begin
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    Log('Dados operacionais do NabiCode preservados em AppData.');
end;
