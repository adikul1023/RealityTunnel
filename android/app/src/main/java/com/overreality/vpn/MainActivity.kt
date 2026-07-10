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
    
    // Manual DI Wiring
    private val clientLogger by lazy { com.overreality.vpn.logging.ClientLogger(applicationContext) }
    private val apiClient by lazy { com.overreality.vpn.data.OracleApiClient() }
    private val secureStorage by lazy { com.overreality.vpn.data.SecureStorage(applicationContext) }
    private val tokenRepository by lazy { com.overreality.vpn.auth.TokenRepository(secureStorage) }
    private val licenseRepository by lazy { com.overreality.vpn.auth.LicenseRepository(secureStorage) }
    private val authManager by lazy { com.overreality.vpn.auth.AuthenticationManager(apiClient, tokenRepository, secureStorage, licenseRepository) }
    private val configProvider by lazy { com.overreality.vpn.data.ConfigurationProvider(applicationContext, licenseRepository, secureStorage, authManager, apiClient) }
    private val sessionManager by lazy { SessionManager(applicationContext, configProvider) }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }

    private val activationMutex = kotlinx.coroutines.sync.Mutex()

    private suspend fun processActivationIntent(intent: Intent?): Boolean {
        if (!activationMutex.tryLock()) {
            clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "DEEP_LINK", "Concurrent deep link activation attempt ignored")
            return false
        }
        try {
            val uri = intent?.data ?: return false
            val exchangeToken = uri.getQueryParameter("exchange_token") ?: return false
            clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "DEEP_LINK", "Processing exchange token from URI")
            val deviceGuid = secureStorage.getDeviceGuid()
            val res = apiClient.exchangeToken(exchangeToken, deviceGuid)
            return if (res is com.overreality.vpn.models.ExchangeResult.Success) {
                tokenRepository.updateTokens(res.tokens)
                clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "AUTH", "Exchange token redeemed successfully")
                true
            } else {
                clientLogger.log(com.overreality.vpn.logging.LogLevel.ERROR, "AUTH", "Exchange token redemption failed")
                false
            }
        } finally {
            activationMutex.unlock()
        }
    }

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
                    var currentNavState by remember { mutableStateOf(NavigationState.SPLASH) }
                    val uiState by VpnStatusStore.state.collectAsState()

                    LaunchedEffect(Unit) {
                        clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "STARTUP", "Starting explicit 6-step Android initialization sequence")
                        if (processActivationIntent(intent)) {
                            currentNavState = NavigationState.MAIN
                            return@LaunchedEffect
                        }

                        // 1. Read cached tokens
                        // 2. Read cached profile
                        val profile = configProvider.getVpnProfile()

                        // 3. Validate offline license
                        if (!authManager.isAuthenticated) {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "AUTH", "No valid authentication state found -> Login")
                            currentNavState = NavigationState.LOGIN
                            return@LaunchedEffect
                        }

                        val tokens = tokenRepository.getCurrentTokens()
                        if (tokens != null && System.currentTimeMillis() > tokens.expiresAt + 72L * 3600 * 1000) {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "AUTH", "Offline grace period (72 hours) expired -> Login")
                            tokenRepository.clearTokens()
                            currentNavState = NavigationState.LOGIN
                            return@LaunchedEffect
                        }

                        // 4. Refresh JWT if required (non-blocking)
                        launch(Dispatchers.IO) {
                            try { authManager.getValidAccessToken() }
                            catch (e: Exception) { clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "AUTH", "Background JWT refresh failed") }
                        }

                        // 5. Background profile refresh
                        launch(Dispatchers.IO) {
                            try { configProvider.refreshProfileBackground() }
                            catch (e: Exception) { clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "CONFIG", "Background profile refresh failed") }
                        }

                        // 6. Navigate with auto-recovery for missing cached profile
                        var activeProfile = profile
                        if (activeProfile == null) {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.WARN, "CONFIG", "Cached profile missing -> attempting network recovery")
                            activeProfile = kotlinx.coroutines.withContext(Dispatchers.IO) {
                                configProvider.fetchVpnProfile()
                            }
                        }
                        if (activeProfile != null) {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "NAV", "Authenticated and profile available -> Main")
                            currentNavState = NavigationState.MAIN
                        } else {
                            currentNavState = NavigationState.LOGIN
                        }
                    }

                    when (currentNavState) {
                        NavigationState.SPLASH -> {
                            SplashScreen()
                        }
                        NavigationState.LOGIN -> {
                            LoginScreen(
                                authManager = authManager,
                                tokenRepository = tokenRepository,
                                clientLogger = clientLogger,
                                onLoginSuccess = { currentNavState = NavigationState.MAIN }
                            )
                        }
                        NavigationState.MAIN -> {
                            MainScreen(
                                uiState = uiState,
                                onConnect = { profile -> requestAndStartVpn(profile) },
                                onDisconnect = { sessionManager.stopSession() },
                                onNavigateToProfile = { currentNavState = NavigationState.PROFILE }
                            )
                        }
                        NavigationState.PROFILE -> {
                            ProfileScreen(
                                onNavigateBack = { currentNavState = NavigationState.MAIN },
                                onLogout = {
                                    authManager.logout()
                                    sessionManager.stopSession()
                                    currentNavState = NavigationState.LOGIN
                                }
                            )
                        }
                        NavigationState.FIRST_TIME_MASTER_TOKEN -> {
                            SaveMasterTokenScreen(
                                onComplete = { currentNavState = NavigationState.MAIN }
                            )
                        }
                    }
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
                "Stealthy VPN",
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
                    lifecycleScope.launch(Dispatchers.IO) {
                        sessionManager.startSession(cleanServerIp)
                    }
                }
            }
        }
    }

    private val vpnPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                pendingServerIp?.let { ip ->
                    lifecycleScope.launch(Dispatchers.IO) {
                        sessionManager.startSession(ip)
                    }
                }
            } else {
                VpnStatusStore.setState(VpnConnectionState.ERROR, "VPN permission denied")
            }
            pendingServerIp = null
        }

    companion object {
        private const val PREFLIGHT_CACHE_WINDOW_MS = 90_000L
        private const val NOTIFICATION_CHANNEL_ID = "stealthy_vpn_channel"
    }
}

enum class NavigationState { SPLASH, LOGIN, MAIN, PROFILE, FIRST_TIME_MASTER_TOKEN }

@Composable
fun SplashScreen() {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Stealthy", fontSize = 28.sp, color = Color.White, fontWeight = FontWeight.Bold)
            Text("Checking session...", color = Color.Gray)
        }
    }
}

@Composable
fun LoginScreen(
    authManager: com.overreality.vpn.auth.AuthenticationManager,
    tokenRepository: com.overreality.vpn.auth.TokenRepository,
    clientLogger: com.overreality.vpn.logging.ClientLogger,
    onLoginSuccess: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = androidx.compose.runtime.rememberCoroutineScope()

    var accountId by remember { mutableStateOf("") }
    var masterToken by remember { mutableStateOf("") }
    var rememberDevice by remember { mutableStateOf(true) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    var show2FaDialog by remember { mutableStateOf(false) }
    var tempLoginToken by remember { mutableStateOf("") }
    var totpCode by remember { mutableStateOf("") }

    var showDeviceLimitDialog by remember { mutableStateOf<com.overreality.vpn.models.DeviceLimitDetails?>(null) }
    var showSubscriptionExpired by remember { mutableStateOf(false) }
    var showMandatoryUpdate by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Welcome to Stealthy", fontSize = 24.sp, color = Color.White, fontWeight = FontWeight.Bold)

            errorMessage?.let {
                Text(it, color = Color.Red, fontSize = 14.sp)
            }

            OutlinedTextField(
                value = accountId,
                onValueChange = { accountId = it },
                label = { Text("Account ID") },
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = masterToken,
                onValueChange = { masterToken = it },
                label = { Text("Master Token") },
                modifier = Modifier.fillMaxWidth()
            )

            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                androidx.compose.material3.Checkbox(
                    checked = rememberDevice,
                    onCheckedChange = { rememberDevice = it }
                )
                Text("Remember this device", color = Color.LightGray)
            }

            Button(
                onClick = {
                    if (accountId.isBlank() || masterToken.isBlank()) {
                        errorMessage = "Please enter both Account ID and Master Token."
                        return@Button
                    }
                    isLoading = true
                    errorMessage = null
                    coroutineScope.launch {
                        try {
                            clientLogger.log(com.overreality.vpn.logging.LogLevel.INFO, "AUTH", "Login attempt initiated")
                            val result = authManager.login(accountId.trim(), masterToken.trim())
                            when (result) {
                                is com.overreality.vpn.models.LoginResult.Success -> {
                                    if (!rememberDevice) {
                                        tokenRepository.updateTokensInMemoryOnly(result.tokens)
                                    }
                                    onLoginSuccess()
                                }
                                is com.overreality.vpn.models.LoginResult.Requires2FA -> {
                                    tempLoginToken = result.temporaryLoginToken
                                    show2FaDialog = true
                                }
                                is com.overreality.vpn.models.LoginResult.DeviceLimitExceeded -> {
                                    showDeviceLimitDialog = result.details
                                }
                                is com.overreality.vpn.models.LoginResult.ReplayDetected -> {
                                    authManager.logout()
                                    errorMessage = "Security Alert: A potential replay attack was detected. Session terminated."
                                }
                                is com.overreality.vpn.models.LoginResult.SubscriptionExpired -> {
                                    showSubscriptionExpired = true
                                }
                                is com.overreality.vpn.models.LoginResult.MandatoryUpdate -> {
                                    showMandatoryUpdate = true
                                }
                                is com.overreality.vpn.models.LoginResult.MaintenanceMode -> {
                                    errorMessage = if (result.retryAfterSeconds != null) {
                                        "Service undergoing scheduled maintenance. Try again in ${result.retryAfterSeconds}s."
                                    } else {
                                        "Service undergoing scheduled maintenance. Try again later."
                                    }
                                }
                                is com.overreality.vpn.models.LoginResult.Error -> {
                                    errorMessage = result.message
                                }
                                else -> {
                                    errorMessage = "Login failed."
                                }
                            }
                        } catch (e: Exception) {
                            errorMessage = "Connection error: ${e.message}"
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !isLoading
            ) {
                Text(if (isLoading) "Logging in..." else "Log In")
            }
        }
    }

    if (show2FaDialog) {
        AlertDialog(
            onDismissRequest = { show2FaDialog = false },
            title = { Text("Two-Factor Authentication") },
            text = {
                OutlinedTextField(
                    value = totpCode,
                    onValueChange = { totpCode = it },
                    label = { Text("6-digit code") }
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    coroutineScope.launch {
                        val verified = authManager.verify2Fa(tempLoginToken, totpCode)
                        if (verified) {
                            show2FaDialog = false
                            onLoginSuccess()
                        } else {
                            errorMessage = "Invalid 2FA code."
                            show2FaDialog = false
                        }
                    }
                }) { Text("Verify") }
            },
            dismissButton = {
                TextButton(onClick = { show2FaDialog = false }) { Text("Cancel") }
            }
        )
    }

    showDeviceLimitDialog?.let { details ->
        AlertDialog(
            onDismissRequest = { showDeviceLimitDialog = null },
            title = { Text("Device Limit Exceeded") },
            text = { Text("You have reached your device limit (${details.currentDevices} / ${details.maxDevices}). Please remove a device to continue.") },
            confirmButton = {
                TextButton(onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse(details.manageDevicesUrl))
                    context.startActivity(intent)
                    showDeviceLimitDialog = null
                }) { Text("Manage Devices") }
            },
            dismissButton = {
                TextButton(onClick = { showDeviceLimitDialog = null }) { Text("Cancel") }
            }
        )
    }

    if (showSubscriptionExpired) {
        AlertDialog(
            onDismissRequest = { showSubscriptionExpired = false },
            title = { Text("Subscription Expired") },
            text = { Text("Your VPN subscription has expired. Please renew to continue using the service.") },
            confirmButton = {
                TextButton(onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://stealthy.co.in/account/billing"))
                    context.startActivity(intent)
                    showSubscriptionExpired = false
                }) { Text("Renew") }
            },
            dismissButton = {
                TextButton(onClick = { showSubscriptionExpired = false }) { Text("Cancel") }
            }
        )
    }

    if (showMandatoryUpdate) {
        AlertDialog(
            onDismissRequest = { showMandatoryUpdate = false },
            title = { Text("Mandatory Update Required") },
            text = { Text("A critical security update is required to connect.") },
            confirmButton = {
                TextButton(onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://stealthy.co.in/download"))
                    context.startActivity(intent)
                    showMandatoryUpdate = false
                }) { Text("Download") }
            },
            dismissButton = {
                TextButton(onClick = { showMandatoryUpdate = false }) { Text("Close") }
            }
        )
    }
}

@Composable
fun ProfileScreen(onNavigateBack: () -> Unit, onLogout: () -> Unit) {
    val context = LocalContext.current
    
    Box(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Profile", fontSize = 24.sp, color = Color.White, fontWeight = FontWeight.Bold)
            
            Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color(0x1AFFFFFF))) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Plan: Premium", color = Color.White, fontWeight = FontWeight.Bold)
                    Text("Devices: 1 / 5", color = Color.LightGray)
                }
            }

            Button(
                onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://stealthy.co.in/account"))
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Manage Subscription")
            }

            Button(
                onClick = { onLogout() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = Color.Red.copy(alpha = 0.5f))
            ) {
                Text("Log Out")
            }

            TextButton(onClick = onNavigateBack) {
                Text("Back to Main")
            }
        }
    }
}

@Composable
fun SaveMasterTokenScreen(onComplete: () -> Unit) {
    val context = LocalContext.current as android.app.Activity
    
    // Clear FLAG_SECURE on dispose
    androidx.compose.runtime.DisposableEffect(Unit) {
        context.window.setFlags(
            android.view.WindowManager.LayoutParams.FLAG_SECURE,
            android.view.WindowManager.LayoutParams.FLAG_SECURE
        )
        onDispose {
            context.window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    Box(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Save Your Master Token", fontSize = 24.sp, color = Color.White, fontWeight = FontWeight.Bold)
            Text(
                "This token is generated once and will never be shown again. Save it securely.",
                color = Color.LightGray
            )
            
            Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color(0x1AFFFFFF))) {
                Text("xoxb-...", modifier = Modifier.padding(16.dp), color = Color.White, fontWeight = FontWeight.Bold)
            }

            Button(onClick = onComplete, modifier = Modifier.fillMaxWidth()) {
                Text("I have saved it")
            }
        }
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
    onNavigateToProfile: () -> Unit = {}
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
                        title = { Text("Stealthy") },
                        actions = {
                            TextButton(onClick = onNavigateToProfile) {
                                Text("👤", fontSize = 20.sp)
                            }
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
            text = "Set Up Stealthy",
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
