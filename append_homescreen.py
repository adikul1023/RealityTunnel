with open('android/app/src/main/java/com/overreality/vpn/MainActivity.kt', 'a') as f:
    f.write(r'''
@Composable
private fun HomeScreen(
    modifier: Modifier = Modifier,
    uiState: VpnUiState,
    activeProfile: com.overreality.vpn.models.VpnProfileDto?,
    onPrimaryAction: () -> Unit,
) {
    val statusLabel = when (uiState.state) {
        VpnConnectionState.CONNECTED ->  Connected
        VpnConnectionState.CONNECTING -> Connecting
        VpnConnectionState.ERROR -> Problem
        VpnConnectionState.DISCONNECTED -> Ready
    }
    val detail = userFacingMessage(uiState)

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp, vertical = 28.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = if (activeProfile != null) Stealthy Node else No Config,
            color = Color.White,
            fontSize = 30.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = activeProfile?.server_ip.orEmpty(),
            color = Color(0xFFB8C3FF),
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(modifier = Modifier.height(32.dp))
        Button(
            onClick = onPrimaryAction,
            enabled = activeProfile != null,
            shape = RoundedCornerShape(22.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (uiState.state == VpnConnectionState.CONNECTED) Color(0xFFFF5252) else Color(0xFF4285F4)
            ),
            modifier = Modifier.size(200.dp, 60.dp)
        ) {
            Text(
                text = if (uiState.state == VpnConnectionState.CONNECTED) Disconnect else Connect,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = statusLabel,
            color = Color.White,
            fontSize = 18.sp,
            fontWeight = FontWeight.Medium
        )
        if (detail.isNotBlank()) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = detail,
                color = if (uiState.state == VpnConnectionState.ERROR) Color(0xFFFF7A7A) else Color(0xFF9FB2FF),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
''')
