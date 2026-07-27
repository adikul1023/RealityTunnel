[Setup]
AppName=OverREALITY VPN
AppVersion=1.0.0
DefaultDirName={autopf}\OverREALITY
DefaultGroupName=OverREALITY VPN
UninstallDisplayIcon={app}\OverREALITY.UI.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.\Installer
OutputBaseFilename=OverREALITY-Setup
SetupIconFile=.\src\OverREALITY.UI\Assets\logo.ico
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
Source: ".\src\OverREALITY.UI\bin\Release\net8.0-windows\win-x64\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".\src\OverREALITY.Helper\bin\Release\net8.0-windows\win-x64\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".\artifacts\latest\sing-box.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\artifacts\latest\wintun.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\src\OverREALITY.UI\Assets\logo.ico"; DestDir: "{app}\Assets"; Flags: ignoreversion

[Icons]
Name: "{group}\OverREALITY VPN"; Filename: "{app}\OverREALITY.UI.exe"; IconFilename: "{app}\Assets\logo.ico"
Name: "{commondesktop}\OverREALITY VPN"; Filename: "{app}\OverREALITY.UI.exe"; IconFilename: "{app}\Assets\logo.ico"

[Run]
Filename: "{app}\OverREALITY.UI.exe"; Description: "Launch OverREALITY VPN"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
