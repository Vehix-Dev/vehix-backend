import 'dart:convert';
import 'dart:async';
import 'dart:collection';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'api_service.dart';
import '../config/app_config.dart';

typedef WSCallback = void Function(Map<String, dynamic> data);

class WebSocketService {
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  WebSocketChannel? _channel;
  late String _role;
  WSCallback? _callback;
  final List<WSCallback> _handlers = [];
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  Timer? _connectionTimeoutTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const int _connectionTimeoutSeconds = 10;
  bool _isManuallyDisconnected = false;
  bool _isAlive = false;
  bool _isConnecting = false;
  bool _hasConnectedBefore = false;
  DateTime? _lastMessageTime;

  int _messageCount = 0;
  
  // Performance monitoring
  final Queue<DateTime> _messageTimestamps = Queue();
  
  // Connection quality metrics
  double _averageLatency = 0.0;
  final List<double> _latencyMeasurements = [];
  
  bool get isConnected => _channel != null && _isAlive && !_isConnecting;
  bool get isConnecting => _isConnecting;
  double get averageLatency => _averageLatency;
  int get messageCount => _messageCount;
  DateTime? get lastMessageTime => _lastMessageTime;

  /// Connect to WebSocket with authentication and performance optimizations
  Future<void> connect(String role, WSCallback onMessage) async {
    if (_isConnecting) {
      debugPrint("🔌 WebSocket: Already connecting, skipping duplicate request");
      return;
    }

    debugPrint("🚀 WebSocket: Connecting for Roadie");
    _role = role;
    _callback = onMessage;
    _isManuallyDisconnected = false;
    await _performConnection();
  }

  /// Perform the actual WebSocket connection
  Future<void> _performConnection() async {
    try {
      _isConnecting = true;
      
      // Get auth token
      final token = await ApiService.getAuthToken();
      if (token == null) {
        debugPrint("❌ WebSocket: No auth token available");
        _isConnecting = false;
        return;
      }

      final baseWsUrl = AppConfig.getWsUrl(_role.toLowerCase());
      final wsUrl = Uri.parse('$baseWsUrl?token=$token');
      debugPrint("🔗 Connecting to WebSocket: ${wsUrl.toString().replaceAll(RegExp(r'token=[^&]*'), 'token=***')}");

      _channel = WebSocketChannel.connect(wsUrl);
      
      // Set connection timeout
      _connectionTimeoutTimer = Timer(const Duration(seconds: _connectionTimeoutSeconds), () {
        if (_isConnecting) {
          debugPrint("⏰ WebSocket connection timeout");
          _isConnecting = false;
          _reconnect();
        }
      });

      try {
        await _channel!.ready.timeout(const Duration(seconds: 5));
      } catch (e) {
        debugPrint("❌ WebSocket Handshake Failed: $e");
        _isAlive = false;
        _isConnecting = false;
        _reconnect();
        return;
      }
      
      _connectionTimeoutTimer?.cancel();
      _isConnecting = false;

      // 🛡️ Fix 'Stream already listened to' by ensuring we listen to the stream safely
      _channel!.stream.listen(
        _handleMessage,
        onDone: _handleConnectionClosed,
        onError: _handleConnectionError,
        cancelOnError: true, // Automatically cancel on error to prevent zombie streams
      );

      _pingTimer = Timer.periodic(const Duration(seconds: 15), (_) {
        _sendLatencyPing();
      });

      // Reset reconnect attempts after successful connection
      _reconnectAttempts = 0;
      _isAlive = true;
      debugPrint("✅ WebSocket connected successfully");

      // Notify handlers of reconnection (skip on first connect)
      if (_hasConnectedBefore) {
        final reconnectEvent = {"type": "WS_RECONNECTED"};
        if (_callback != null) _callback!(reconnectEvent);
        for (final handler in _handlers) {
          handler(reconnectEvent);
        }
      }
      _hasConnectedBefore = true;
    } catch (e) {
      debugPrint("❌ WebSocket connection error: $e");
      _isConnecting = false;
      _reconnect();
    }
  }

  void _handleConnectionClosed() {
    debugPrint("🔌 WebSocket connection closed");
    _isAlive = false;
    _reconnect();
  }

  void _handleConnectionError(dynamic error) {
    debugPrint("❌ WebSocket stream error: $error");
    _isAlive = false;
    _reconnect();
  }

  /// Reconnect with exponential backoff and jitter
  void _reconnect() async {
    if (_isManuallyDisconnected || _isConnecting) return;
    
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      debugPrint("🚫 WebSocket: Max reconnection attempts reached. Forcing fresh start...");
      _reconnectAttempts = 0; // Reset to keep trying forever in production
    }
    
    _reconnectAttempts++;
    
    final delaySeconds = _reconnectAttempts < 5 ? 2 : 5;

    debugPrint("🔄 WebSocket: Reconnecting in ${delaySeconds}s (attempt $_reconnectAttempts)");

    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () async {
      debugPrint("🔄 WebSocket: Refreshing token and performing hard reconnect...");
      await ApiService.refreshTokenIfNeeded();
      await _performConnection();
    });
  }

  /// Handle incoming WebSocket messages
  void _handleMessage(dynamic data) {
    try {
      final messageData = jsonDecode(data) as Map<String, dynamic>;
      _lastMessageTime = DateTime.now();
      _messageCount++;

      // Handle pong response for latency measurement
      if (messageData['type'] == 'PONG' || messageData['type'] == 'pong') {
        _calculateLatency();
        return;
      }

      // Update performance metrics
      _updatePerformanceMetrics();

      // 🚨 CANCELLATION HANDLER: If request is cancelled, notify UI to go home
      final type = messageData["type"];
      if (type == "REQUEST_CANCELLED" || (type == "REQUEST_UPDATE" && messageData["status"] == "CANCELLED")) {
        debugPrint("🚫 WebSocket: Request was CANCELLED. Notifying handlers...");
      }

      if (_callback != null) _callback!(messageData);
      for (final handler in _handlers) {
        handler(messageData);
      }
    } catch (e) {
      debugPrint("❌ Error parsing WebSocket message: $e");
    }
  }

  void _updatePerformanceMetrics() {
    final now = DateTime.now();
    _messageTimestamps.add(now);
    final oneSecondAgo = now.subtract(const Duration(seconds: 1));
    while (_messageTimestamps.isNotEmpty && _messageTimestamps.first.isBefore(oneSecondAgo)) {
      _messageTimestamps.removeFirst();
    }
  }

  DateTime? _lastPingTime;

  void _sendLatencyPing() {
    if (_isAlive && _channel != null) {
      _lastPingTime = DateTime.now();
      send({'type': 'PING', 'timestamp': _lastPingTime!.millisecondsSinceEpoch});
    }
  }

  void _calculateLatency() {
    if (_lastPingTime != null) {
      final latency = DateTime.now().difference(_lastPingTime!).inMilliseconds.toDouble();
      _latencyMeasurements.add(latency);
      if (_latencyMeasurements.length > 10) _latencyMeasurements.removeAt(0);
      _averageLatency = _latencyMeasurements.reduce((a, b) => a + b) / _latencyMeasurements.length;
      
      if (kDebugMode) {
        debugPrint("📊 WebSocket Latency: ${latency}ms (avg: ${_averageLatency.toStringAsFixed(1)}ms)");
      }
    }
  }

  /// Send data to WebSocket
  void send(Map<String, dynamic> data) {
    if (!isConnected) {
      // Quietly skip if not connected to avoid log spam
      return;
    }
    final message = Map<String, dynamic>.from(data);
    message['timestamp'] = DateTime.now().millisecondsSinceEpoch;
    _channel!.sink.add(jsonEncode(message));
  }

  Future<void> _closeConnection() async {
    _pingTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    
    try {
      _isAlive = false;
      if (_channel != null) {
        debugPrint("🔌 WebSocket: Closing channel...");
        await _channel!.sink.close();
        _channel = null; // CRITICAL: Nullify to allow fresh stream on reconnect
      }
    } catch (e) {
      debugPrint("⚠️ WebSocket: Error closing connection: $e");
    }
    
    // Do NOT set _isConnecting = false here, as it breaks the _reconnect flow state.
  }

  /// Disconnect gracefully
  Future<void> disconnect() async {
    debugPrint("🔌 WebSocket: Manual disconnect requested");
    _isManuallyDisconnected = true;
    _reconnectTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    await _closeConnection();
    _reconnectAttempts = 0;
    _handlers.clear();
    _latencyMeasurements.clear();
    _averageLatency = 0.0;
  }

  /// Manual reconnect when network is restored
  Future<void> reconnect() async {
    if (_isConnecting) {
      debugPrint("🔌 WebSocket: Already reconnecting, skipping");
      return;
    }
    
    debugPrint("🔌 WebSocket: Manual reconnect requested");
    _isConnecting = true; // Set immediately to prevent race conditions during refresh/close
    _reconnectAttempts = 0;
    _isManuallyDisconnected = false;
    _reconnectTimer?.cancel();
    
    try {
      // Close stale channel before reconnecting
      await _closeConnection();
      
      if (_role.isNotEmpty && _callback != null) {
        // Refresh token before reconnecting to avoid 401
        debugPrint("🔄 Refreshing token for manual reconnect...");
        await ApiService.refreshTokenIfNeeded();
        await _performConnection();
      }
    } catch (e) {
      debugPrint("❌ Manual reconnect error: $e");
    } finally {
      // Note: _isConnecting will be set to false inside _performConnection() 
      // or if it fails before getting there.
      if (!_isAlive) {
        _isConnecting = false;
      }
    }
  }

  /// Send location updates with targeted rider relay support
  void sendLocation({required double lat, required double lng, int? riderId}) {
    if (!isConnected) {
      // Quietly skip if not connected to avoid log spam
      return;
    }

    final roundedLat = double.parse(lat.toStringAsFixed(6));
    final roundedLng = double.parse(lng.toStringAsFixed(6));

    final message = {
      "type": "LOCATION",
      "lat": roundedLat,
      "lng": roundedLng,
      if (riderId != null) "rider_id": riderId,
      "timestamp": DateTime.now().millisecondsSinceEpoch,
    };

    _channel!.sink.add(jsonEncode(message));
  }

  /// Send chat message with delivery confirmation
  void sendChat(int requestId, String text) {
    if (!isConnected) {
      debugPrint("❌ WebSocket: Cannot send chat - not connected");
      return;
    }

    final message = {
      "type": "CHAT",
      "request_id": requestId,
      "text": text,
      "timestamp": DateTime.now().millisecondsSinceEpoch,
    };

    _channel!.sink.add(jsonEncode(message));
  }

  /// Add additional message handler
  void addHandler(WSCallback handler) {
    _handlers.add(handler);
  }

  /// Remove message handler
  void removeHandler(WSCallback handler) {
    _handlers.remove(handler);
  }

  /// Get connection quality metrics
  Map<String, dynamic> getConnectionMetrics() {
    return {
      'isConnected': isConnected,
      'averageLatency': _averageLatency,
      'messageCount': _messageCount,
      'lastMessageTime': _lastMessageTime?.toIso8601String(),
      'reconnectAttempts': _reconnectAttempts,
      'uptime': _lastMessageTime != null 
          ? DateTime.now().difference(_lastMessageTime!).inSeconds 
          : 0,
    };
  }

  /// Clear message history for memory management
  void clearMessageHistory() {
    _messageCount = 0;
    _lastMessageTime = null;
    debugPrint("🧹 WebSocket: Message history cleared");
  }
}
