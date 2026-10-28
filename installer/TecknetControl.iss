; Inno Setup 6 script. Build with build.bat (it runs PyInstaller first).
; Installs for the current user only: no administrator rights needed.

#define AppExe "TecknetControl.exe"
#define AppVersion GetStringFileInfo("..\dist\TecknetControl\" + AppExe, "ProductVersion")

[Setup]
AppId={{8C0D6C5E-6B8E-4E7A-9C61-2F3B7F0A9C11}
AppName=Tecknet Control
AppVersion={#AppVersion}
AppVerName=Tecknet Control {#AppVersion}
AppPublisher=Tecknet Control contributors
DefaultDirName={localappdata}\Programs\Tecknet Control
DisableDirPage=yes
DisableProgramGroupPage=yes
DefaultGroupName=Tecknet Control
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=TecknetControl-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName=Tecknet Control
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "startup"; Description: "Start with Windows"

[InstallDelete]
; Old libraries from a previous version.
Type: filesandordirs; Name: "{app}\_internal"
; Without this flag the v1.6 AutoHotkey hotkeys stop working immediately.
Type: files; Name: "{userappdata}\TecknetControl\controls.enabled"

[Files]
Source: "..\dist\TecknetControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Tecknet Control"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\Tecknet Control"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TecknetControl"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open Tecknet Control"; Flags: nowait postinstall skipifsilent

[Code]
// Settings in %APPDATA%\TecknetControl are never removed, so a new install keeps them.

procedure CloseRunningApp();
var
  ResultCode: Integer;
begin
  // Ask a running v1.7+ to exit cleanly, then make sure no copy is left
  // (v1.6 and earlier did not listen for --exit).
  if FileExists(ExpandConstant('{app}\{#AppExe}')) then
  begin
    Exec(ExpandConstant('{app}\{#AppExe}'), '--exit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseRunningApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CloseRunningApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'TecknetControl');
end;
