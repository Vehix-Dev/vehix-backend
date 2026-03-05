import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'api_service.dart';

typedef WSCallback = void Function(Map<String, dynamic> data);

class WebSocketService {
  WebSocketChannel? _channel;
  late String _role;
  WSCallback? _callback;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;
  bool _isManuallyDisconnected = false;

  bool get isConnected => _channel != null;

  /// Connect to WebSocket with authentication
  Future<void> connect(WSCallback onMessage) async {
    final token = await ApiService.getToken();
    const role = "RODIE";

    _role = role.toUpperCase(); // "RIDER" or "RODIE"
    _callback = onMessage;

    try {
      if (token == null || token.isEmpty) {
        debugPrint("❌ No token available for WebSocket connection");
        return;
      }

      // Close any existing connection first
      _channel?.sink.close();
      _channel = null;

      // Map role to Django endpoint: RIDER -> rider, RODIE -> rodie, DRIVER -> rodie
      final roleEndpoint = _role == "RIDER" ? "rider" : "rodie";
      final url = "wss://backend.vehix.ug:443/ws/$roleEndpoint/?token=$token";
      
      debugPrint("🔌 WebSocket connecting to: wss://backend.vehix.ug:443/ws/$roleEndpoint/?token=***");

      final uri = Uri.parse(url);
      debugPrint("🔌 Parsed URI: $url");

      _channel = WebSocketChannel.connect(uri);

      _channel!.stream.listen(
        (event) {
          try {
            final data = jsonDecode(event);
            _callback?.call(data);
          } catch (e) {
            debugPrint("❌ Error decoding WebSocket message: $e");
          }
        },
        onDone: () {
          debugPrint("⚠️ WebSocket connection closed by server");
          _reconnect();
        },
        onError: (error) {
          debugPrint("❌ WebSocket error: $error");
          debugPrint("   Error type: ${error.runtimeType}");
          _reconnect();
        },
      );

      _pingTimer = Timer.periodic(const Duration(seconds: 25), (_) {
        sendPing();
      });

      // Reset reconnect attempts after successful connection
      _reconnectAttempts = 0;
      debugPrint("✅ WebSocket connected successfully");
    } catch (e) {
      debugPrint("❌ WebSocket connection error: $e");
      _reconnect();
    }
  }

  /// Reconnect with exponential backoff
  void _reconnect() {
    if (_isManuallyDisconnected) {
      return;
    }

    if (_reconnectAttempts >= _maxReconnectAttempts) {
      return;
    }

    _reconnectAttempts++;
    final delaySeconds = 5 * _reconnectAttempts;

    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      if (_role.isNotEmpty && _callback != null && !_isManuallyDisconnected) {
        connect(_callback!);
      }
    });
  }

  /// Close connection gracefully
  void disconnect() {
    _isManuallyDisconnected = true;
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _reconnectAttempts = 0;
  }

  /// Send ping
  void sendPing() {
    if (_channel != null) {
      _channel!.sink.add(jsonEncode({"type": "PING"}));
    }
  }

  /// Send location updates
  void sendLocation({required double lat, required double lng}) {
    if (_channel != null) {
      // Round to 6 decimal places
      final roundedLat = double.parse(lat.toStringAsFixed(6));
      final roundedLng = double.parse(lng.toStringAsFixed(6));

      final message = {
        "type": "LOCATION",
        "lat": roundedLat,
        "lng": roundedLng,
      };
      _channel!.sink.add(jsonEncode(message));
    }
  }

  /// Send chat message
  void sendChat(int requestId, String text) {
    if (_channel != null) {
      final message = {"type": "CHAT", "request_id": requestId, "text": text};
      _channel!.sink.add(jsonEncode(message));
    }
  }

  /// Send arbitrary custom data
  void send(Map<String, dynamic> data) {
    if (_channel != null) {
      _channel!.sink.add(jsonEncode(data));
    }
  }
}
