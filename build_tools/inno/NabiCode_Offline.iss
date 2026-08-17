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
  MasterPasswordSHA256 = 'f89df8c2689cb179a06efafecef653e12f99b525d12dbeb1ed3ff0484faebc57';

var
  DeleteAllUserData: Boolean;
  MaintenancePage: TInputOptionWizardPage;
  MaintenanceFinished: Boolean;
  OfficialInstallLocation: String;
  LegacyInstallLocation: String;
  OldInstallLocations: TStringList;

function NormalizeMasterPassword(const Value: String): String;
var
  Normalized: String;
begin
  Normalized := Lowercase(Trim(Value));
  while Pos('  ', Normalized) > 0 do
    StringChangeEx(Normalized, '  ', ' ', True);
  Result := Normalized;
end;

function VerifyMasterPassword(const Value: String): Boolean;
begin
  Result := CompareText(GetSHA256OfString(NormalizeMasterPassword(Value)),
    MasterPasswordSHA256) = 0;
end;

function RequestMasterPassword(): Boolean;
var
  Form: TSetupForm;
  Prompt: TNewStaticText;
  PasswordEdit: TPasswordEdit;
  OKButton: TNewButton;
  CancelButton: TNewButton;
  Password: String;
begin
  Form := CreateCustomForm(ScaleX(440), ScaleY(150), False, True);
  try
    Form.Caption := 'Autorização de segurança';
    Prompt := TNewStaticText.Create(Form);
    Prompt.Parent := Form;
    Prompt.Left := ScaleX(16);
    Prompt.Top := ScaleY(16);
    Prompt.Width := Form.ClientWidth - ScaleX(32);
    Prompt.Caption := 'Digite a senha mestra do NabiCode para confirmar a exclusão total:';

    PasswordEdit := TPasswordEdit.Create(Form);
    PasswordEdit.Parent := Form;
    PasswordEdit.Left := ScaleX(16);
    PasswordEdit.Top := Prompt.Top + Prompt.Height + ScaleY(12);
    PasswordEdit.Width := Form.ClientWidth - ScaleX(32);

    OKButton := TNewButton.Create(Form);
    OKButton.Parent := Form;
    OKButton.Caption := 'Confirmar';
    OKButton.Width := ScaleX(100);
    OKButton.Height := ScaleY(28);
    OKButton.Left := Form.ClientWidth - ScaleX(216);
    OKButton.Top := Form.ClientHeight - ScaleY(42);
    OKButton.ModalResult := mrOk;
    OKButton.Default := True;

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := 'Cancelar';
    CancelButton.Width := ScaleX(100);
    CancelButton.Height := ScaleY(28);
    CancelButton.Left := Form.ClientWidth - ScaleX(108);
    CancelButton.Top := OKButton.Top;
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    Form.ActiveControl := PasswordEdit;

    Result := Form.ShowModal() = mrOk;
    Password := PasswordEdit.Text;
    PasswordEdit.Text := '';
  finally
    Form.Free();
  end;
  if Result and not VerifyMasterPassword(Password) then
  begin
    MsgBox('Senha mestra incorreta. Nenhum dado foi apagado.', mbError, MB_OK);
    Result := False;
  end;
  Password := '';
end;

procedure DeleteAllNabiCodeData();
var
  Index: Integer;
begin
  { Somente raízes exatas pertencentes ao NabiCode; nunca apaga AppData/ProgramData genéricos. }
  DelTree(ExpandConstant('{userappdata}\NabiCode'), True, True, True);
  DelTree(ExpandConstant('{localappdata}\NabiCode'), True, True, True);
  DelTree(ExpandConstant('{commonappdata}\NabiCode'), True, True, True);
  if OfficialInstallLocation <> '' then
    DelTree(RemoveBackslashUnlessRoot(OfficialInstallLocation), True, True, True);
  if LegacyInstallLocation <> '' then
    DelTree(RemoveBackslashUnlessRoot(LegacyInstallLocation), True, True, True);
  if OldInstallLocations <> nil then
    for Index := 0 to OldInstallLocations.Count - 1 do
      DelTree(RemoveBackslashUnlessRoot(OldInstallLocations[Index]), True, True, True);
end;

function RunRegisteredUninstaller(const RegistryKey: String): Boolean;
var
  InstallLocation: String;
  Uninstaller: String;
  ResultCode: Integer;
begin
  Result := True;
  if not RegQueryStringValue(HKLM64, RegistryKey, 'InstallLocation', InstallLocation) then
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

procedure RemoveOtherRegisteredNabiCodeInstalls();
var
  Names: TArrayOfString;
  Index: Integer;
  RegistryKey: String;
  DisplayName: String;
  Publisher: String;
  InstallLocation: String;
begin
  if not RegGetSubkeyNames(HKLM64,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall', Names) then
    Exit;
  for Index := 0 to GetArrayLength(Names) - 1 do
  begin
    RegistryKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + Names[Index];
    if CompareText(RegistryKey, OfficialUninstallKey) = 0 then
      Continue;
    DisplayName := '';
    Publisher := '';
    RegQueryStringValue(HKLM64, RegistryKey, 'DisplayName', DisplayName);
    RegQueryStringValue(HKLM64, RegistryKey, 'Publisher', Publisher);
    if (Pos('NABICODE', Uppercase(DisplayName)) = 1) and
      (CompareText(Publisher, 'NabiCode') = 0) then
    begin
      InstallLocation := '';
      if RegQueryStringValue(HKLM64, RegistryKey, 'InstallLocation', InstallLocation) and
        (InstallLocation <> '') then
        OldInstallLocations.Add(InstallLocation);
      if not RunRegisteredUninstaller(RegistryKey) then
        RegDeleteKeyIncludingSubkeys(HKLM64, RegistryKey);
    end;
  end;
end;

procedure RemoveLegacyShortcuts();
begin
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
    MaintenancePage.Add('Desinstalar e apagar completamente os dados deste usuário');
    MaintenancePage.SelectedValueIndex := 0;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  DeleteData: Boolean;
begin
  Result := True;
  if (MaintenancePage = nil) or (CurPageID <> MaintenancePage.ID) or
    (MaintenancePage.SelectedValueIndex = 0) then
    Exit;

  DeleteData := MaintenancePage.SelectedValueIndex = 2;
  if DeleteData and
    (SuppressibleMsgBox(
      'ATENÇÃO: banco de dados, backups, relatórios e configurações serão apagados definitivamente.' + #13#10 +
      'Confirma que deseja APAGAR TUDO?', mbCriticalError,
      MB_YESNO or MB_DEFBUTTON2, IDNO) <> IDYES) then
  begin
    Result := False;
    Exit;
  end;
  if DeleteData and not RequestMasterPassword() then
  begin
    Result := False;
    Exit;
  end;

  if not RunRegisteredUninstaller(OfficialUninstallKey) then
  begin
    MsgBox('Não foi possível executar o desinstalador oficial do NabiCode.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  RemoveLegacyR6();
  RemoveOtherRegisteredNabiCodeInstalls();
  RemoveLegacyShortcuts();
  if DeleteData then
    DeleteAllNabiCodeData();
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
  DeleteAllUserData := False;
  if UninstallSilent then
  begin
    { Atualizações e remoções silenciosas nunca apagam dados operacionais. }
    Result := True;
    Exit;
  end;

  Choice := SuppressibleMsgBox(
    'Como deseja desinstalar o NabiCode?' + #13#10 + #13#10 +
    'SIM — Apagar o programa e todos os dados deste usuário.' + #13#10 +
    'NÃO — Apagar somente o programa e manter banco, backups e configurações.' + #13#10 +
    'CANCELAR — Não desinstalar.',
    mbConfirmation, MB_YESNOCANCEL or MB_DEFBUTTON2, IDNO);
  if Choice = IDCANCEL then
  begin
    Result := False;
    Exit;
  end;
  if Choice = IDYES then
  begin
    DeleteAllUserData :=
      SuppressibleMsgBox(
        'ATENÇÃO: banco de dados, backups, relatórios e configurações serão apagados definitivamente.' + #13#10 +
        'Confirma que deseja APAGAR TUDO?',
        mbCriticalError, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
    if not DeleteAllUserData then
    begin
      Result := False;
      Exit;
    end;
    if not RequestMasterPassword() then
    begin
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteAllUserData then
    begin
      OfficialInstallLocation := ExpandConstant('{app}');
      DeleteAllNabiCodeData();
      Log('Dados operacionais do usuário removidos por escolha explícita.');
    end
    else
      Log('Dados operacionais do NabiCode preservados em AppData.');
  end;
end;
