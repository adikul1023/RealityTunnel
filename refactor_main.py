import re

with open('android/app/src/main/java/com/overreality/vpn/MainActivity.kt', 'r') as f:
    content = f.read()

# Replace requestAndStartVpn signature and VpnConfigStore usage
content = re.sub(
    r'private fun requestAndStartVpn\(profile: VpnProfile, onlyTest: Boolean = false\) \{[\s\S]*?val cleanServerIp = profile\.serverIp',
    'private fun requestAndStartVpn(profile: com.overreality.vpn.models.VpnProfileDto, onlyTest: Boolean = false) {\n        val cleanServerIp = profile.server_ip',
    content
)

content = re.sub(
    r'val prefs = VpnConfigStore\.prefs\(this@MainActivity\)[\s\S]*?checkedAtMs = System\.currentTimeMillis\(\),\n                \)',
    'lastPreflightOk = PreflightCache(\n                    serverIp = cleanServerIp,\n                    uuid = profile.uuid,\n                    publicKey = profile.public_key,\n                    checkedAtMs = System.currentTimeMillis(),\n                )',
    content
)

content = re.sub(
    r'private fun hasRecentMatchingPreflight\(serverIp: String\): Boolean \{[\s\S]*?val cached = lastPreflightOk \?: return false',
    'private fun hasRecentMatchingPreflight(serverIp: String, profile: com.overreality.vpn.models.VpnProfileDto): Boolean {\n        val cached = lastPreflightOk ?: return false',
    content
)

content = re.sub(
    r'cached\.uuid == uuid &&\n            cached\.publicKey == publicKey',
    'cached.uuid == profile.uuid &&\n            cached.publicKey == profile.public_key',
    content
)

content = re.sub(
    r'val preflight = if \(!onlyTest && hasRecentMatchingPreflight\(cleanServerIp\)\) \{',
    'val preflight = if (!onlyTest && hasRecentMatchingPreflight(cleanServerIp, profile)) {',
    content
)

# Replace NavigationState.MAIN block
content = re.sub(
    r'NavigationState\.MAIN -> \{[\s\S]*?onNavigateToProfile = \{ currentNavState = NavigationState\.PROFILE \}\n                            \)\n                        \}',
    'NavigationState.MAIN -> {\n                            val activeProfile = secureStorage.getVpnProfile()\n                            MainScreen(\n                                uiState = uiState,\n                                activeProfile = activeProfile,\n                                onConnect = {\n                                    if (activeProfile != null) requestAndStartVpn(activeProfile)\n                                },\n                                onDisconnect = {\n                                    sessionManager.stopVpn()\n                                },\n                                onNavigateToProfile = { currentNavState = NavigationState.PROFILE }\n                            )\n                        }',
    content
)

# Replace MainScreen signature and body
mainscreen_regex = r'private fun MainScreen\([\s\S]*?if \(showSwitchSheet\) \{[\s\S]*?\}\n        \}\n    \}\n\}'
replacement = '''private fun MainScreen(
    uiState: VpnUiState,
    activeProfile: com.overreality.vpn.models.VpnProfileDto?,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onNavigateToProfile: () -> Unit = {}
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                brush = Brush.verticalGradient(
                    colors = listOf(Color(0xFF0A1226), Color(0xFF121933), Color(0xFF1B1740))
                )
            )
    ) {
        Scaffold(
            containerColor = Color.Transparent,
            topBar = {
                TopAppBar(
                    title = { Text( Stealthy) },
                    actions = {
                        TextButton(onClick = onNavigateToProfile) {
                            Text(??, fontSize = 20.sp)
                        }
                    }
                )
            }
        ) { innerPadding ->
            HomeScreen(
                modifier = Modifier.padding(innerPadding),
                uiState = uiState,
                activeProfile = activeProfile,
                onPrimaryAction = {
                    if (uiState.state == VpnConnectionState.CONNECTED ||
                        uiState.state == VpnConnectionState.CONNECTING
                    ) {
                        onDisconnect()
                    } else {
                        onConnect()
                    }
                }
            )
        }
    }
}'''
content = re.sub(mainscreen_regex, replacement, content)

# Replace HomeScreen signature
content = re.sub(
    r'private fun HomeScreen\(\n    modifier: Modifier = Modifier,\n    uiState: VpnUiState,\n    activeProfile: VpnProfile\?,\n    onPrimaryAction: \(\) -> Unit,\n\) \{',
    'private fun HomeScreen(\n    modifier: Modifier = Modifier,\n    uiState: VpnUiState,\n    activeProfile: com.overreality.vpn.models.VpnProfileDto?,\n    onPrimaryAction: () -> Unit,\n) {',
    content
)

# Replace activeProfile.name
content = re.sub(
    r'text = activeProfile\?\.name \?\: No Config,',
    'text = if (activeProfile != null) Stealthy Node else No Config,',
    content
)

# Replace activeProfile.serverIp
content = re.sub(
    r'text = activeProfile\?\.serverIp\.orEmpty\(\),',
    'text = activeProfile?.server_ip.orEmpty(),',
    content
)

with open('android/app/src/main/java/com/overreality/vpn/MainActivity.kt', 'w') as f:
    f.write(content)
