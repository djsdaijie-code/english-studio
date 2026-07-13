#define MyAppName "English Studio"
#define MyAppVersion GetEnv("ENGLISH_STUDIO_RELEASE_VERSION")
#define MyAppPublisher "English Studio Contributors"
#define MyAppExeName "EnglishStudio.exe"
#define MyAppSource GetEnv("ENGLISH_STUDIO_APP_SOURCE")

[Setup]
AppId={{7A25B33E-5B8F-4B4E-91D0-E2C07CD5D90F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\English Studio
DefaultGroupName=English Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=EnglishStudio-{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=English Studio

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\English Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\English Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,English Studio}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\EnglishStudio"; Check: ShouldRemoveUserData

[Code]
function ShouldRemoveUserData(): Boolean;
begin
  Result := ExpandConstant('{param:purgedata|0}') = '1';
end;
