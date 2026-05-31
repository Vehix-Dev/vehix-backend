package com.vehix.roadie_app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.MethodChannel.MethodCallHandler
import io.flutter.plugin.common.MethodChannel.Result

class OverlayPlugin : FlutterPlugin, MethodCallHandler {
    private var channel: MethodChannel? = null
    private var context: Context? = null

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channel = MethodChannel(binding.binaryMessenger, "vehix/overlay")
        channel?.setMethodCallHandler(this)
        context = binding.applicationContext
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channel?.setMethodCallHandler(null)
        channel = null
        context = null
    }

    override fun onMethodCall(call: MethodCall, result: Result) {
        val ctx = context
        if (ctx == null) {
            result.error("NO_CONTEXT", "Context is null", null)
            return
        }

        when (call.method) {
            "showOverlay" -> {
                val isOnline = call.argument<Boolean>("isOnline") ?: false
                val intent = Intent(ctx, BackgroundService::class.java)
                intent.action = "SHOW_OVERLAY"
                intent.putExtra("isOnline", isOnline)
                startServiceSafely(ctx, intent)
                result.success(true)
            }
            "hideOverlay" -> {
                val intent = Intent(ctx, BackgroundService::class.java)
                intent.action = "HIDE_OVERLAY"
                startServiceSafely(ctx, intent)
                result.success(true)
            }
            "updateStatus" -> {
                val isOnline = call.argument<Boolean>("isOnline") ?: false
                val intent = Intent(ctx, BackgroundService::class.java)
                intent.action = "UPDATE_OVERLAY_STATUS"
                intent.putExtra("isOnline", isOnline)
                startServiceSafely(ctx, intent)
                result.success(true)
            }
            "bringAppToFront" -> {
                try {
                    val intent = ctx.packageManager.getLaunchIntentForPackage(ctx.packageName)
                    intent?.let {
                        it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                        ctx.startActivity(it)
                        result.success(true)
                        return
                    }
                    result.error("FAILED", "Launch intent not found", null)
                } catch (e: Exception) {
                    result.error("FAILED", e.message, null)
                }
            }
            "checkPermission" -> {
                result.success(hasOverlayPermission(ctx))
            }
            "requestPermission" -> {
                requestOverlayPermission(ctx)
                result.success(true)
            }
            "showRequestAlert" -> {
                val title = call.argument<String>("title") ?: "New Request"
                val intent = Intent(ctx, BackgroundService::class.java)
                intent.action = "SHOW_ALERT"
                intent.putExtra("title", title)
                startServiceSafely(ctx, intent)
                result.success(true)
            }
            else -> result.notImplemented()
        }
    }

    private fun startServiceSafely(ctx: Context, intent: Intent) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ContextCompat.startForegroundService(ctx, intent)
            } else {
                ctx.startService(intent)
            }
        } catch (e: Exception) {
            try {
                ctx.startService(intent)
            } catch (ex: Exception) {
                // Fail-safe
            }
        }
    }

    private fun hasOverlayPermission(ctx: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(ctx)
        } else {
            true
        }
    }

    private fun requestOverlayPermission(ctx: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${ctx.packageName}")
            )
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            ctx.startActivity(intent)
        }
    }
}
