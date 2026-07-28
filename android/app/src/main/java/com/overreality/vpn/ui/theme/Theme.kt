package com.overreality.vpn.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF8AA0FF),
    secondary = Color(0xFF71D4FF),
    background = Color(0xFF0A1226),
    surface = Color(0xFF121A33),
    onPrimary = Color(0xFF0A1226),
    onSecondary = Color.Black,
    onBackground = Color(0xFFF1F4FF),
    onSurface = Color(0xFFE4E9FF),
)

@Composable
fun OverREALITYTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = Typography,
        content = content,
    )
}
