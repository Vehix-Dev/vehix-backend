import 'dart:async';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'api_service.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  print("📩 [RODIE] Handling a background message: ${message.messageId}");
  print("Payload: ${message.data}");
}

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

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
      });

      // 6. Handle notification click
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        print('🚀 [RODIE] Notification clicked! Data: ${message.data}');
      });

      _initialized = true;
    } catch (e) {
      print('❌ [RODIE] NotificationService initialization error: $e');
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
}
