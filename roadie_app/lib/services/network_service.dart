import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'websocket_service.dart';
import '../main.dart' show navigatorKey;

class NetworkService {
  static final NetworkService _instance = NetworkService._internal();
  factory NetworkService() => _instance;
  NetworkService._internal();

  bool _isConnected = true;
  bool _isDialogShowing = false;
  int _failureCount = 0;
  static const int _maxFailuresBeforeDisconnect = 2; // Failures * interval = total grace period
  Timer? _connectionCheckTimer;
  final StreamController<bool> _connectionController = StreamController<bool>.broadcast();
  WebSocketService? _webSocketService;
  
  Stream<bool> get connectionStream => _connectionController.stream;
  bool get isConnected => _isConnected;

  /// Set WebSocket service reference for auto-reconnection
  void setWebSocketService(WebSocketService webSocketService) {
    _webSocketService = webSocketService;
  }

  Future<void> initialize() async {
    debugPrint("🌐 NetworkService: Initializing...");
    
    // Check initial connection status
    await _checkConnection();
    
    // Start periodic network monitoring (every 2 seconds for ~4-5s response)
    _connectionCheckTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _checkConnection();
    });
    
    debugPrint("🌐 NetworkService: Initialization complete. Connected: $_isConnected");
  }

  Future<void> _checkConnection() async {
    bool currentCheckPassed = false;
    
    try {
      // Method 1: Try HTTP request to multiple reliable endpoints
      final urls = [
        'https://www.google.com',
        'https://www.cloudflare.com',
        'https://www.github.com',
      ];
      
      for (String url in urls) {
        try {
          final response = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 3));
          if (response.statusCode >= 200 && response.statusCode < 300) {
            currentCheckPassed = true;
            debugPrint("🌐 NetworkService: Connectivity check passed via $url");
            break;
          }
        } catch (e) {
          continue;
        }
      }
      
      // Method 2: Fallback to DNS lookup if HTTP fails
      if (!currentCheckPassed) {
        try {
          final result = await InternetAddress.lookup('google.com').timeout(const Duration(seconds: 2));
          if (result.isNotEmpty && result[0].rawAddress.isNotEmpty) {
            currentCheckPassed = true;
            debugPrint("🌐 NetworkService: Connectivity check passed via DNS lookup");
          }
        } catch (e) {
          debugPrint("🌐 NetworkService: DNS fallback lookup failed: $e");
        }
      }
      
    } catch (e) {
      currentCheckPassed = false;
    }
    
    if (currentCheckPassed) {
      _failureCount = 0;
      _updateConnectionStatus(true);
    } else {
      _failureCount++;
      debugPrint("🌐 NetworkService: Check failed ($_failureCount/$_maxFailuresBeforeDisconnect)");
      
      // Only mark as disconnected after multiple consecutive failures
      if (_failureCount >= _maxFailuresBeforeDisconnect) {
        _updateConnectionStatus(false);
      } else {
        // If we were connected, stay connected during the grace period
        debugPrint("🌐 NetworkService: Failure within grace period, maintaining previous status");
      }
    }

    // Also check for stale WebSocket even when network status hasn't changed
    if (_isConnected && _webSocketService != null && 
        !_webSocketService!.isConnected && !_webSocketService!.isConnecting) {
      debugPrint("🌐 NetworkService: Network up but WebSocket dead, triggering reconnect");
      _webSocketService!.reconnect();
    }
  }

  void _updateConnectionStatus(bool connected) {
    if (_isConnected != connected) {
      debugPrint("🌐 NetworkService: Status changed from $_isConnected to $connected");
      _isConnected = connected;
      _connectionController.add(connected);
      
      if (!connected && !_isDialogShowing) {
        debugPrint("🌐 NetworkService: Showing no network dialog");
        _showNoNetworkDialog();
      } else if (connected) {
        if (_isDialogShowing) {
          debugPrint("🌐 NetworkService: Hiding no network dialog");
          _hideNoNetworkDialog();
        }
        // Always reconnect WebSocket when network is restored
        if (_webSocketService != null && !_webSocketService!.isConnected) {
          debugPrint("🌐 NetworkService: Reconnecting WebSocket after network restoration");
          _webSocketService!.reconnect();
        }
      }
    }
  }

  void _showNoNetworkDialog() {
    _isDialogShowing = true;
    debugPrint("🌐 NetworkService: Attempting to show dialog...");
    
    // Use a delay to ensure the app is fully loaded
    Future.delayed(const Duration(milliseconds: 500), () {
      if (_isDialogShowing && navigatorKey.currentState != null && navigatorKey.currentState!.overlay != null) {
        try {
          showDialog(
            context: navigatorKey.currentState!.overlay!.context,
            barrierDismissible: false,
            builder: (context) => PopScope(
              canPop: false,
              child: AlertDialog(
                icon: Icon(
                  Icons.wifi_off,
                  color: Colors.red[600],
                  size: 48,
                ),
                title: const Text(
                  "No Network Connection",
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                content: const Text(
                  "Internet access is required for the app to function properly. Please check your mobile data, Wi-Fi connection, or data balance.",
                  style: TextStyle(fontSize: 14),
                ),
                actions: [
                  TextButton(
                    onPressed: () {
                      // Retry connection check
                      _hideNoNetworkDialog();
                      _checkConnection();
                    },
                    child: const Text(
                      "Retry",
                      style: TextStyle(color: Color(0xFFFF8C00)),
                    ),
                  ),
                ],
              ),
            ),
          );
          debugPrint("🌐 NetworkService: Dialog shown successfully");
        } catch (e) {
          debugPrint("🌐 NetworkService: Error showing dialog - $e");
        }
      } else {
        debugPrint("🌐 NetworkService: Cannot show dialog - navigator not ready");
      }
    });
  }

  void _hideNoNetworkDialog() {
    if (_isDialogShowing && navigatorKey.currentState != null) {
      try {
        _isDialogShowing = false;
        navigatorKey.currentState!.pop();
        debugPrint("🌐 NetworkService: Dialog hidden");
      } catch (e) {
        debugPrint("🌐 NetworkService: Error hiding dialog - $e");
      }
    }
  }

  void dispose() {
    debugPrint("🌐 NetworkService: Disposing...");
    _connectionCheckTimer?.cancel();
    _connectionController.close();
  }
}

// The navigatorKey is imported from main.dart at the top of this file to ensure consistency
