package com.overreality.vpn

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.VpnService
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.overreality.vpn.ui.theme.OverREALITYTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private var pendingServerIp: String? = null

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    private data class PreflightCache(
        val serverIp: String,
        val uuid: String,
        val publicKey: String,
        val checkedAtMs: Long,
    )

    private var lastPreflightOk: PreflightCache? = null

    private fun hasRecentMatchingPreflight(serverIp: String): Boolean {
        val prefs = VpnConfigStore.prefs(this)
        val uuid = prefs.getString(VpnConfigStore.KEY_UUID, "")?.trim().orEmpty()
        val publicKey = prefs.getString(VpnConfigStore.KEY_PUBLIC_KEY, "")?.trim().orEmpty()
        val cached = lastPreflightOk ?: return false
        val fresh = System.currentTimeMillis() - cached.checkedAtMs <= PREFLIGHT_CACHE_WINDOW_MS
        return fresh &&
            cached.serverIp == serverIp &&
            cached.uuid == uuid &&
            cached.publicKey == publicKey
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        ensureNotificationChannel()
        requestNotificationPermissionIfNeeded()

        setContent {
            OverREALITYTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val uiState by VpnStatusStore.state.collectAsState()
                    MainScreen(
                        uiState = uiState,
                        onConnect = { profile -> requestAndStartVpn(profile) },
                        onDisconnect = { stopVpnService() },
                    )
                }
            }
        }
    }

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

        val nm = getSystemService(NotificationManager::class.java)
        val existing = nm.getNotificationChannel(NOTIFICATION_CHANNEL_ID)
        if (existing == null) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "OverREALITY VPN",
                NotificationManager.IMPORTANCE_DEFAULT,
            )
            nm.createNotificationChannel(channel)
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
            return
        }
        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    private fun requestAndStartVpn(profile: VpnProfile, onlyTest: Boolean = false) {
        VpnConfigStore.setActiveProfile(this, profile.id)

        val cleanServerIp = profile.serverIp
            .lineSequence()
            .firstOrNull()
            ?.trim()
            .orEmpty()

        VpnStatusStore.setState(VpnConnectionState.CONNECTING, "Running preflight checks...")

        lifecycleScope.launch(Dispatchers.IO) {
            val preflight = if (!onlyTest && hasRecentMatchingPreflight(cleanServerIp)) {
                VpnPreflight.Result(true, "Using recent preflight result")
            } else {
                VpnPreflight.run(this@MainActivity, cleanServerIp)
            }

            withContext(Dispatchers.Main) {
                if (!preflight.ok) {
                    VpnStatusStore.setState(VpnConnectionState.ERROR, preflight.message)
                    return@withContext
                }

                val prefs = VpnConfigStore.prefs(this@MainActivity)
                lastPreflightOk = PreflightCache(
                    serverIp = cleanServerIp,
                    uuid = prefs.getString(VpnConfigStore.KEY_UUID, "")?.trim().orEmpty(),
                    publicKey = prefs.getString(VpnConfigStore.KEY_PUBLIC_KEY, "")?.trim().orEmpty(),
                    checkedAtMs = System.currentTimeMillis(),
                )

                if (onlyTest) {
                    VpnStatusStore.setState(VpnConnectionState.DISCONNECTED, preflight.message)
                    return@withContext
                }

                val engine = AndroidVpnEngineProvider.create(this@MainActivity)
                if (!engine.isAvailable()) {
                    VpnStatusStore.setState(
                        VpnConnectionState.ERROR,
                        engine.unavailableReason() ?: "Android VPN engine unavailable"
                    )
                    return@withContext
                }

                pendingServerIp = cleanServerIp
                val intent: Intent? = VpnService.prepare(this@MainActivity)
                if (intent != null) {
                    vpnPermissionLauncher.launch(intent)
                } else {
                    startVpnService(cleanServerIp)
                }
            }
        }
    }

    private val vpnPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                pendingServerIp?.let { startVpnService(it) }
            } else {
                VpnStatusStore.setState(VpnConnectionState.ERROR, "VPN permission denied")
            }
            pendingServerIp = null
        }

    private fun startVpnService(serverIp: String) {
        val intent = Intent(this, OverRealityVpnService::class.java)
            .setAction(OverRealityVpnService.ACTION_START)
            .putExtra(OverRealityVpnService.EXTRA_SERVER_IP, serverIp)
        ContextCompat.startForegroundService(this, intent)
    }

    private fun stopVpnService() {
        val intent = Intent(this, OverRealityVpnService::class.java)
            .setAction(OverRealityVpnService.ACTION_STOP)
        startService(intent)
    }

    companion object {
        private const val PREFLIGHT_CACHE_WINDOW_MS = 90_000L
        private const val NOTIFICATION_CHANNEL_ID = "overreality_vpn_channel"
    }
}

private data class ProfileEditorState(
    val profile: VpnProfile?,
    val isCreate: Boolean,
    val isSetup: Boolean,
)

private data class DeleteProfileState(
    val id: String,
    val name: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainScreen(
    uiState: VpnUiState,
    onConnect: (VpnProfile) -> Unit,
    onDisconnect: () -> Unit,
) {
    val context = LocalContext.current

    var profiles by remember { mutableStateOf(VpnConfigStore.listProfiles(context)) }
    var activeProfileId by remember { mutableStateOf(VpnConfigStore.getActiveProfile(context)?.id) }
    var menuExpanded by remember { mutableStateOf(false) }
    var showSwitchSheet by remember { mutableStateOf(false) }
    var editorState by remember { mutableStateOf<ProfileEditorState?>(null) }
    var deleteState by remember { mutableStateOf<DeleteProfileState?>(null) }

    fun refreshProfiles() {
        profiles = VpnConfigStore.listProfiles(context)
        activeProfileId = VpnConfigStore.getActiveProfile(context)?.id
    }

    val activeProfile = profiles.firstOrNull { it.id == activeProfileId } ?: profiles.firstOrNull()
    val setupRequired = !VpnConfigStore.hasCompletedSetup(context) || activeProfile == null

    LaunchedEffect(setupRequired, activeProfile?.id) {
        if (setupRequired && editorState == null) {
            editorState = ProfileEditorState(
                profile = activeProfile,
                isCreate = activeProfile == null,
                isSetup = true,
            )
        }
    }

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
                if (!setupRequired) {
                    TopAppBar(
                        title = { Text("OverREALITY") },
                        actions = {
                            Box {
                                TextButton(onClick = { menuExpanded = true }) {
                                    Text("⋮", fontSize = 24.sp)
                                }
                                DropdownMenu(
                                    expanded = menuExpanded,
                                    onDismissRequest = { menuExpanded = false },
                                ) {
                                    DropdownMenuItem(
                                        text = { Text("Switch Config") },
                                        onClick = {
                                            menuExpanded = false
                                            showSwitchSheet = true
                                        }
                                    )
                                    DropdownMenuItem(
                                        text = { Text("Edit Current Config") },
                                        onClick = {
                                            menuExpanded = false
                                            editorState = ProfileEditorState(
                                                profile = activeProfile,
                                                isCreate = false,
                                                isSetup = false,
                                            )
                                        }
                                    )
                                    DropdownMenuItem(
                                        text = { Text("Create New Config") },
                                        onClick = {
                                            menuExpanded = false
                                            editorState = ProfileEditorState(
                                                profile = null,
                                                isCreate = true,
                                                isSetup = false,
                                            )
                                        }
                                    )
                                }
                            }
                        }
                    )
                }
            }
        ) { innerPadding ->
            if (setupRequired) {
                ProfileSetupScreen(
                    modifier = Modifier.padding(innerPadding),
                    uiState = uiState,
                    initialProfile = activeProfile,
                    onSave = { profile ->
                        VpnConfigStore.saveProfile(context, profile, makeActive = true)
                        refreshProfiles()
                        editorState = null
                    }
                )
            } else {
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
                            onConnect(activeProfile)
                        }
                    }
                )
            }
        }

        if (showSwitchSheet) {
            ModalBottomSheet(
                onDismissRequest = { showSwitchSheet = false },
                containerColor = Color(0xFF101831),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(horizontal = 20.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = "Switch Config",
                        color = Color.White,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "Choose which profile the big button should use.",
                        color = Color(0xFF9FB2FF),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    profiles.forEach { profile ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    VpnConfigStore.setActiveProfile(context, profile.id)
                                    refreshProfiles()
                                    showSwitchSheet = false
                                },
                            colors = CardDefaults.cardColors(
                                containerColor = if (profile.id == activeProfile?.id) {
                                    Color(0xFF1D356F)
                                } else {
                                    Color(0x1AFFFFFF)
                                }
                            ),
                            shape = RoundedCornerShape(22.dp),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 16.dp, vertical = 14.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(
                                    selected = profile.id == activeProfile?.id,
                                    onClick = {
                                        VpnConfigStore.setActiveProfile(context, profile.id)
                                        refreshProfiles()
                                        showSwitchSheet = false
                                    }
                                )
                                Column(modifier = Modifier.padding(start = 8.dp)) {
                                    Text(profile.name, color = Color.White, fontWeight = FontWeight.SemiBold)
                                    Text(profile.serverIp, color = Color(0xFF9FB2FF), style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }

        editorState?.takeIf { !it.isSetup }?.let { state ->
            ProfileEditorDialog(
                state = state,
                onDismiss = { editorState = null },
                onSave = { profile ->
                    VpnConfigStore.saveProfile(context, profile, makeActive = true)
                    refreshProfiles()
                    editorState = null
                },
                onDelete = { profile ->
                    editorState = null
                    deleteState = DeleteProfileState(profile.id, profile.name)
                }
            )
        }

        deleteState?.let { state ->
            AlertDialog(
                onDismissRequest = { deleteState = null },
                title = { Text("Delete Config") },
                text = { Text("Delete ${state.name}? This can be recreated later.") },
                confirmButton = {
                    TextButton(
                        onClick = {
                            VpnConfigStore.deleteProfile(context, state.id)
                            refreshProfiles()
                            deleteState = null
                            if (profiles.isEmpty()) {
                                editorState = ProfileEditorState(null, isCreate = true, isSetup = true)
                            }
                        }
                    ) {
                        Text("Delete")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { deleteState = null }) {
                        Text("Cancel")
                    }
                }
            )
        }
    }
}

@Composable
private fun HomeScreen(
    modifier: Modifier = Modifier,
    uiState: VpnUiState,
    activeProfile: VpnProfile?,
    onPrimaryAction: () -> Unit,
) {
    val statusLabel = when (uiState.state) {
        VpnConnectionState.CONNECTED -> "Connected"
        VpnConnectionState.CONNECTING -> "Connecting"
        VpnConnectionState.ERROR -> "Problem"
        VpnConnectionState.DISCONNECTED -> "Ready"
    }
    val detail = userFacingMessage(uiState)

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp, vertical = 28.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(28.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0x19000000)),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 22.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = activeProfile?.name ?: "No Config",
                    color = Color.White,
                    fontSize = 30.sp,
                    fontWeight = FontWeight.SemiBold,
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = activeProfile?.serverIp.orEmpty(),
                    color = Color(0xFFB8C3FF),
                    style = MaterialTheme.typography.bodyMedium,
                )

                Spacer(modifier = Modifier.height(18.dp))

                Card(
                    shape = RoundedCornerShape(999.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = when (uiState.state) {
                            VpnConnectionState.CONNECTED -> Color(0x2636D982)
                            VpnConnectionState.CONNECTING -> Color(0x26F2B84B)
                            VpnConnectionState.ERROR -> Color(0x26FF6D6D)
                            VpnConnectionState.DISCONNECTED -> Color(0x26A1B4FF)
                        }
                    )
                ) {
                    Text(
                        text = statusLabel,
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                        color = when (uiState.state) {
                            VpnConnectionState.CONNECTED -> Color(0xFF73E37A)
                            VpnConnectionState.CONNECTING -> Color(0xFFFFCC66)
                            VpnConnectionState.ERROR -> Color(0xFFFF7A7A)
                            else -> Color(0xFFB8C3FF)
                        },
                        fontWeight = FontWeight.Medium,
                    )
                }

                if (detail.isNotBlank()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = detail,
                        color = Color(0xFFD6DEFF),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

                Spacer(modifier = Modifier.height(22.dp))

                Button(
                    onClick = onPrimaryAction,
                    enabled = activeProfile != null,
                    shape = RoundedCornerShape(22.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (uiState.state == VpnConnectionState.CONNECTED ||
                            uiState.state == VpnConnectionState.CONNECTING
                        ) Color(0xFF7B2533) else Color(0xFF2E5BFF)
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(76.dp),
                ) {
                    Text(
                        text = if (uiState.state == VpnConnectionState.CONNECTED ||
                            uiState.state == VpnConnectionState.CONNECTING
                        ) "Disconnect" else "Connect",
                        fontSize = 24.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
private fun ProfileSetupScreen(
    modifier: Modifier = Modifier,
    uiState: VpnUiState,
    initialProfile: VpnProfile?,
    onSave: (VpnProfile) -> Unit,
) {
    val detail = userFacingMessage(uiState)

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp, vertical = 28.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Top,
    ) {
        Text(
            text = "Set Up OverREALITY",
            color = Color.White,
            fontSize = 28.sp,
            fontWeight = FontWeight.SemiBold,
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "This appears only the first time. Later you only see Connect/Disconnect.",
            color = Color(0xFFB8C3FF),
            style = MaterialTheme.typography.bodyMedium,
        )

        Spacer(modifier = Modifier.height(12.dp))

        if (detail.isNotBlank()) {
            Text(
                text = detail,
                color = if (uiState.state == VpnConnectionState.ERROR) Color(0xFFFF7A7A) else Color(0xFF9FB2FF),
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        ProfileForm(
            initialProfile = initialProfile,
            submitLabel = "Save Setup",
            onSave = onSave,
        )
    }
}

@Composable
private fun ProfileEditorDialog(
    state: ProfileEditorState,
    onDismiss: () -> Unit,
    onSave: (VpnProfile) -> Unit,
    onDelete: (VpnProfile) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (state.isCreate) "Create Config" else "Edit Config") },
        text = {
            ProfileForm(
                initialProfile = state.profile,
                submitLabel = if (state.isCreate) "Create" else "Save",
                onSave = onSave,
                onDelete = onDelete,
            )
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Composable
private fun ProfileForm(
    initialProfile: VpnProfile?,
    submitLabel: String,
    onSave: (VpnProfile) -> Unit,
    onDelete: ((VpnProfile) -> Unit)? = null,
) {
    var name by rememberSaveable(initialProfile?.id) { mutableStateOf(initialProfile?.name.orEmpty()) }
    var serverIp by rememberSaveable(initialProfile?.id) { mutableStateOf(initialProfile?.serverIp.orEmpty()) }
    var uuid by rememberSaveable(initialProfile?.id) { mutableStateOf(initialProfile?.uuid.orEmpty()) }
    var publicKey by rememberSaveable(initialProfile?.id) { mutableStateOf(initialProfile?.publicKey.orEmpty()) }
    var sni by rememberSaveable(initialProfile?.id) {
        mutableStateOf(initialProfile?.sni?.ifBlank { "www.microsoft.com" } ?: "www.microsoft.com")
    }
    var shortId by rememberSaveable(initialProfile?.id) { mutableStateOf(initialProfile?.shortId.orEmpty()) }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Config Name") },
            placeholder = { Text("Primary") }
        )

        OutlinedTextField(
            value = serverIp,
            onValueChange = { serverIp = it.trim() },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Server IP") },
            placeholder = { Text("144.24.153.180") }
        )

        OutlinedTextField(
            value = uuid,
            onValueChange = { uuid = it.trim() },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("UUID") },
            placeholder = { Text("vless uuid") }
        )

        OutlinedTextField(
            value = publicKey,
            onValueChange = { publicKey = it.trim() },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("REALITY Public Key") },
            placeholder = { Text("public key") }
        )

        OutlinedTextField(
            value = sni,
            onValueChange = { sni = it.trim() },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("SNI") },
            placeholder = { Text("www.microsoft.com") }
        )

        OutlinedTextField(
            value = shortId,
            onValueChange = { shortId = it.trim() },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Short ID") },
            placeholder = { Text("optional") }
        )

        Spacer(modifier = Modifier.height(6.dp))

        Button(
            onClick = {
                onSave(
                    VpnProfile(
                        id = initialProfile?.id.orEmpty(),
                        name = name,
                        serverIp = serverIp,
                        uuid = uuid,
                        publicKey = publicKey,
                        sni = sni.ifBlank { "www.microsoft.com" },
                        shortId = shortId,
                    )
                )
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = serverIp.isNotBlank() && uuid.isNotBlank() && publicKey.isNotBlank(),
        ) {
            Text(submitLabel)
        }

        if (initialProfile != null && onDelete != null) {
            HorizontalDivider(color = Color(0x22FFFFFF))
            TextButton(
                onClick = { onDelete(initialProfile) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Delete Config", color = Color(0xFFFF8C8C))
            }
        }
    }
}

private fun userFacingMessage(uiState: VpnUiState): String {
    return when (uiState.state) {
        VpnConnectionState.CONNECTED -> ""
        VpnConnectionState.CONNECTING -> "Connecting..."
        VpnConnectionState.DISCONNECTED -> ""
        VpnConnectionState.ERROR -> uiState.message
            .replace(Regex("\\[[^]]+\\]\\s*"), "")
            .replace("libbox start failed:", "")
            .replace("startup failed:", "")
            .replace("Android VPN engine unavailable", "VPN unavailable")
            .replace(Regex("\\s+"), " ")
            .trim()
    }
}
