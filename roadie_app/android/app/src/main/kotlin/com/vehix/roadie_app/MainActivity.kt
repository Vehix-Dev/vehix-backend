package com.vehix.roadie_app

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val OVERLAY_CHANNEL = "vehix/overlay"
    private val BACKGROUND_CHANNEL = "vehix/background"
    private val REQUEST_OVERLAY_PERMISSION = 1001

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Unified MethodChannel implementation routing everything through BackgroundService
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, OVERLAY_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "showOverlay" -> {
                    val isOnline = call.argument<Boolean>("isOnline") ?: false
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.action = "SHOW_OVERLAY"
                    intent.putExtra("isOnline", isOnline)
                    startServiceSafely(intent)
                    result.success(true)
                }
                "hideOverlay" -> {
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.action = "HIDE_OVERLAY"
                    startServiceSafely(intent)
                    result.success(true)
                }
                "updateStatus" -> {
                    val isOnline = call.argument<Boolean>("isOnline") ?: false
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.action = "UPDATE_OVERLAY_STATUS"
                    intent.putExtra("isOnline", isOnline)
                    startServiceSafely(intent)
                    result.success(true)
                }
                "bringAppToFront" -> {
                    bringAppToFront()
                    result.success(true)
                }
                "checkPermission" -> {
                    result.success(hasOverlayPermission())
                }
                "requestPermission" -> {
                    requestOverlayPermission()
                    result.success(true)
                }
                "showRequestAlert" -> {
                    val title = call.argument<String>("title") ?: "New Request"
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.action = "SHOW_ALERT"
                    intent.putExtra("title", title)
                    startServiceSafely(intent)
                    result.success(true)
                }
                else -> result.notImplemented()
            }
        }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, BACKGROUND_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "initializeService" -> {
                    val title = call.argument<String>("notificationTitle") ?: "Vehix Roadie"
                    val text = call.argument<String>("notificationText") ?: "Online and ready"
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.putExtra("title", title)
                    intent.putExtra("text", text)
                    startServiceSafely(intent)
                    result.success(true)
                }
                "updateStatus" -> {
                    // This is handled by overlay update as well, but can be used for notification updates
                    val isOnline = call.argument<Boolean>("isOnline") ?: false
                    val intent = Intent(this, BackgroundService::class.java)
                    intent.putExtra("isOnline", isOnline)
                    startServiceSafely(intent)
                    result.success(true)
                }
                "stopService" -> {
                    stopService(Intent(this, BackgroundService::class.java))
                    result.success(true)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun startServiceSafely(intent: Intent) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ContextCompat.startForegroundService(this, intent)
            } else {
                startService(intent)
            }
        } catch (e: Exception) {
            // Fallback for some weird background restrictions
            try {
                startService(intent)
            } catch (ex: Exception) {
                // Last resort
            }
        }
    }

    private fun hasOverlayPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else {
            true
        }
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, REQUEST_OVERLAY_PERMISSION)
        }
    }

    private fun bringAppToFront() {
        val intent = Intent(this, MainActivity::class.java)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        startActivity(intent)
    }
}
