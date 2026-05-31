import 'dart:async';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';
import '../main.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  print("📩 [RODIE] Handling a background message: ${message.messageId}");
  print("Payload: ${message.data}");
  
  // IMMEDIATELY DRAW OVER OTHER APPS / POP UP REQUEST MODEL IF IT IS AN OFFER REQUEST
  if (message.data['type'] == 'OFFER_REQUEST') {
    try {
      // Save pending offer request and local receive time in SharedPreferences so main UI can calculate countdown perfectly
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('pending_offer_request_id', message.data['request_id']?.toString() ?? '');
      await prefs.setString('pending_offer_request_timestamp', message.data['timestamp']?.toString() ?? '');
      await prefs.setDouble('pending_offer_request_receive_time', DateTime.now().millisecondsSinceEpoch / 1000.0);
      
      const channel = MethodChannel('vehix/overlay');
      await channel.invokeMethod('bringAppToFront');
      print("🚀 [RODIE] Successfully brought app to front on background FCM OFFER_REQUEST");
    } catch (e) {
      print("❌ [RODIE] Failed to bring app to front from background FCM: $e");
    }
  }
}

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  static final StreamController<Map<String, dynamic>> _offerRequestStreamController = StreamController<Map<String, dynamic>>.broadcast();
  static Stream<Map<String, dynamic>> get offerRequestStream => _offerRequestStreamController.stream;

  FirebaseMessaging? get _fcm {
    try {
      return FirebaseMessaging.instance;
    } catch (e) {
      print("⚠️ [RODIE] FirebaseMessaging not initialized: $e");
      return null;
    }
  }
  
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;

    try {
      final fcmInstance = _fcm;
      if (fcmInstance == null) {
        print("⚠️ [RODIE] Skipping NotificationService initialization - Firebase not available");
        return;
      }

      // 1. Set background handler
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      // 2. Request permissions (Required for Android 13+ and iOS)
      NotificationSettings settings = await fcmInstance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        print('✅ [RODIE] User granted notification permission');
      } else {
        print('❌ [RODIE] User declined notification permission');
      }

      // 3. Configure foreground notification presentation (Crucial for testing!)
      await FirebaseMessaging.instance.setForegroundNotificationPresentationOptions(
        alert: true, // Required to display a heads-up notification
        badge: true,
        sound: true,
      );

      // 4. Get FCM Token and Register
      await _getTokenAndRegister();

      // 5. Setup foreground message handler
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        print('🔔 [RODIE] Foreground Message received: ${message.notification?.title}');
        if (message.data['type'] == 'OFFER_REQUEST') {
          _handleOfferRequestPush(message.data);
        } else {
          _showForegroundNotification(message);
        }
      });

      // 6. Handle notification click
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        print('🚀 [RODIE] Notification clicked! Data: ${message.data}');
        if (message.data['type'] == 'OFFER_REQUEST') {
          _handleOfferRequestPush(message.data);
        }
      });

      // 7. Handle initial message (terminated state launch)
      fcmInstance.getInitialMessage().then((RemoteMessage? message) {
        if (message != null) {
          print('🚀 [RODIE] App launched from initial message: ${message.data}');
          if (message.data['type'] == 'OFFER_REQUEST') {
            _handleOfferRequestPush(message.data);
          }
        }
      });

      _initialized = true;
    } catch (e) {
      print('❌ [RODIE] NotificationService initialization error: $e');
    }
  }

  void _handleOfferRequestPush(Map<String, dynamic> data) async {
    final requestIdStr = data['request_id'];
    if (requestIdStr == null) return;
    final requestId = int.tryParse(requestIdStr.toString());
    if (requestId == null) return;

    // Capture local receive time immediately to bypass any clock drifts
    final double receiveTime = DateTime.now().millisecondsSinceEpoch / 1000.0;
    
    // Add a short delay to ensure UI/home_screen has mounted and subscribed
    await Future.delayed(const Duration(milliseconds: 500));
    
    print('📦 [RODIE] Fetching details for request $requestId from push');
    final details = await ApiService.getRequestDetails(requestId);
    if (details != null) {
      details['local_receive_time'] = receiveTime;
      if (data['timestamp'] != null) {
        details['timestamp'] = data['timestamp'];
      }
      _offerRequestStreamController.add(details);
    }
  }

  Future<void> _getTokenAndRegister() async {
    try {
      final fcmInstance = _fcm;
      if (fcmInstance == null) return;

      String? token = await fcmInstance.getToken();
      if (token != null) {
        print('🔑 [RODIE] FCM Token: $token');
        await ApiService.updateFcmToken(token);
      }

      fcmInstance.onTokenRefresh.listen((newToken) async {
        print('🔑 [RODIE] FCM Token Refreshed: $newToken');
        await ApiService.updateFcmToken(newToken);
      });
    } catch (e) {
      print('❌ [RODIE] Error getting FCM token: $e');
    }
  }

  Future<void> refreshRegistration() async {
    await _getTokenAndRegister();
  }

  void _showForegroundNotification(RemoteMessage message) {
    final title = message.notification?.title ?? "Notification";
    final body = message.notification?.body ?? "";
    final context = navigatorKey.currentContext;
    if (context != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14)),
              const SizedBox(height: 4),
              Text(body, style: const TextStyle(color: Colors.white70, fontSize: 12)),
            ],
          ),
          backgroundColor: const Color(0xFF10223D),
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          action: SnackBarAction(
            label: "VIEW",
            textColor: const Color(0xFFFF8C00),
            onPressed: () {
              // Notification click handling if any custom routing is needed
            },
          ),
        ),
      );
    }
  }
}
