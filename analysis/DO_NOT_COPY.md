# DO NOT COPY

The following elements, patterns, and logic from the legacy codebase **MUST NOT** be ported over to the rewrite:

1. **Old UUID Authentication (`OldUUIDManager.cs` or similar manual inputs):**
   - Do not allow users to manually type a UUID to authenticate to the VPN. All auth must flow through the central API via Email/Password -> JWT -> Provisioning.

2. **Old VLESS Configuration (`config.template.json`):**
   - Do not use hardcoded or static JSON templates for sing-box routing. Configurations must be dynamically fetched from the `/api/client/config` endpoint and injected into the engine.

3. **Hardcoded URLs:**
   - Do not hardcode `api.stealthy.co.in` or `edge.stealthy.co.in` inside the C# logic. These must be configurable via `appsettings.json` or dynamic backend routing.

4. **Monolithic UI Logic:**
   - Do not port `MainWindow.xaml.cs` logic directly. The rewrite must strictly enforce MVVM. The View must not perform API calls or manage the VPN state directly.

5. **Legacy Installer Custom Logic (`setup.csproj`):**
   - Do not use a C# console app to zip and install the payload. Use a robust, industry-standard setup tool (like WiX, InnoSetup, or MSIX) to handle service registration and UAC correctly.

6. **Temporary Hacks & Dead Code:**
   - Do not port over any scratch scripts, testing hacks (e.g., bypassing UAC for WinUI via manifest downgrading), or unused `.xaml` test pages.

7. **Insecure Storage:**
   - Do not write credentials or active UUIDs to plain text `.json` files on disk. Pass configurations directly to the helper via secure IPC or store them in encrypted DPAPI vaults.
