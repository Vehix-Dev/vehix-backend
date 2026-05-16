import 'dart:async';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'api_service.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // If you're going to use other Firebase services in the background, such as Firestore,
  // make sure you call `initializeApp` before using other Firebase services.
  print("📩 [RIDER] Handling a background message: ${message.messageId}");
  print("Payload: ${message.data}");
}

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;

    try {
      // 1. Set background handler
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      // 2. Request permissions (Required for Android 13+ and iOS)
      NotificationSettings settings = await _fcm.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        print('✅ [RIDER] User granted notification permission');
      } else {
        print('❌ [RIDER] User declined notification permission');
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
        print('🔔 [RIDER] Foreground Message received: ${message.notification?.title}');
      });

      // 6. Handle notification click
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        print('🚀 [RIDER] Notification clicked! Data: ${message.data}');
      });

      _initialized = true;
    } catch (e) {
      print('❌ [RIDER] NotificationService initialization error: $e');
    }
  }

  Future<void> _getTokenAndRegister() async {
    try {
      String? token = await _fcm.getToken();
      if (token != null) {
        print('🔑 [RIDER] FCM Token: $token');
        // Register with backend
        await ApiService.updateFcmToken(token);
      }

      // Listen for token refresh
      _fcm.onTokenRefresh.listen((newToken) async {
        print('🔑 [RIDER] FCM Token Refreshed: $newToken');
        await ApiService.updateFcmToken(newToken);
      });
    } catch (e) {
      print('❌ [RIDER] Error getting FCM token: $e');
    }
  }

  /// Manually trigger token refresh and registration (e.g. after login)
  Future<void> refreshRegistration() async {
    await _getTokenAndRegister();
  }
}
