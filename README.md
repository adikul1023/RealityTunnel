# RealityTunnel

A minimal WinUI 3 desktop application for managing xray connections on Windows.

## Features

- Requires Administrator privileges
- Simple modern UI
- Configure server IP
- Connect/Disconnect buttons
- Connection status display
- Automatic config.json generation from template
- Manages xray.exe process

## Requirements

- Windows 10/11 (version 19041 or higher)
- .NET 8 Runtime
- xray.exe in the same directory as the application

## Building

### Prerequisites
- Visual Studio 2022 with:
  - .NET Desktop Development workload
  - Windows App SDK C# Templates

### Build Commands

Debug build:
```powershell
dotnet build OverREALITY.sln
```

Release build (self-contained):
```powershell
dotnet publish OverREALITY.sln -c Release -r win-x64 --self-contained
```

The output will be in `bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish\`

## Setup

1. Build the application using the commands above
2. Copy `xray.exe` to the publish directory
3. Edit `config.template.json` to configure your VLESS settings:
   - Replace `your-uuid-here` with your user ID
   - Replace `your-public-key-here` with your Reality public key
   - Replace `your-short-id-here` with your Reality short ID
   - Adjust other settings as needed (port, serverName, etc.)

## Usage

1. Run `RealityTunnel.exe` as Administrator (the app will prompt for elevation)
2. Enter the server IP address
3. Click "Connect" to start the VPN tunnel
4. Click "Disconnect" to stop the tunnel

## Configuration Template

The `config.template.json` file contains the xray configuration with a `{{SERVER_IP}}` placeholder. When you click Connect, the app:
1. Reads `config.template.json`
2. Replaces `{{SERVER_IP}}` with the entered IP address
3. Saves the result as `config.json`
4. Launches `xray.exe run -config config.json`

## Project Structure

```
RealityTunnel/
├── App.xaml                    # Application XAML
├── App.xaml.cs                 # Application code-behind
├── MainWindow.xaml             # Main window UI
├── MainWindow.xaml.cs          # Main window logic
├── XrayController.cs           # Xray process controller
├── config.template.json        # Xray configuration template
├── app.manifest                # Administrator privilege manifest
├── Package.appxmanifest        # WinUI 3 package manifest
├── RealityTunnel.csproj        # Project file
└── Assets/                     # Application assets
```

## Notes

- The application requires Administrator privileges to create TUN interfaces
- Place xray.exe in the same directory as RealityTunnel.exe
- config.json is generated at runtime and can be deleted after use
- The xray process runs without a visible window
