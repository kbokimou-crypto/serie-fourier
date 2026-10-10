; Script Inno Setup : crée SerieFourier_Setup.exe (installateur Windows)
[Setup]
AppName=Série de Fourier
AppVersion=1.0
DefaultDirName={autopf}\SerieFourier
DefaultGroupName=Série de Fourier
OutputBaseFilename=SerieFourier_Setup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Icônes :"

[Files]
Source: "dist\SerieFourier.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "exemple_suite.csv"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Série de Fourier"; Filename: "{app}\SerieFourier.exe"
Name: "{group}\Désinstaller"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Série de Fourier"; Filename: "{app}\SerieFourier.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SerieFourier.exe"; Description: "Lancer Série de Fourier"; Flags: nowait postinstall skipifsilent
