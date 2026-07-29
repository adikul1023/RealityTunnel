# OverREALITY Android (Kotlin)

This folder contains the Android starter app built with Kotlin + Jetpack Compose.

## Status

- Project scaffold created
- UI starter screen created
- `VpnService` lifecycle implemented (start/stop + TUN establish)
- VPN permission flow wired
- Service state store wired to UI
- Runtime config template added (`config.android.template.json`)
- sing-box process manager added (asset extraction + process launch)
- Foreground `VpnService` notification implemented (Android 14/15/16 compatible)
- Service declared as `foregroundServiceType="specialUse"`

## Open in Android Studio

1. Open Android Studio
2. Choose **Open**
3. Select this folder: `android/`
4. Let Gradle sync

## Build

Use Android Studio (recommended), or from terminal:

```bash
./gradlew :app:assembleDebug
```

## Next implementation steps

1. Bundle Android `sing-box` binary as `app/src/main/assets/sing-box`
2. Pass real tunnel fd/config integration expected by sing-box Android mode
3. Add secure key storage UX (encrypted storage)
4. Add background/foreground service notification handling for long-running VPN

## Notes

- Android uses `VpnService`; this is different from desktop route commands.
- Runtime root is not required for VpnService-based tunnel apps.
- Current app expects credentials to be saved from UI (UUID + REALITY public key).
- If `assets/sing-box` is missing, connect will fail with a clear error.
- Android 14+ requires proper foreground service typing; this project uses `specialUse` with VPN subtype.
