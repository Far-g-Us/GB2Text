[Setup]
AppName=GB Text Extraction Framework
AppVersion=1.0.0
DefaultDirName={pf}\GB Text Extraction Framework
DefaultGroupName=GB Text Extraction Framework
OutputDir=userdocs:Inno Setup Examples Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\gb2text\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GB Text Extraction Framework"; Filename: "{app}\gb2text.exe"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\gb2text.exe"; Description: "Запустить GB Text Extraction Framework"; Flags: nowait postinstall skipifsilent