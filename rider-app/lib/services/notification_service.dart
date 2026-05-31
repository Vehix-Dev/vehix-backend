import 'dart:async';
import 'dart:io' show Platform;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:permission_handler/permission_handler.dart';
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

  FirebaseMessaging? get _fcm {
    try {
      return FirebaseMessaging.instance;
    } catch (e) {
      print("⚠️ [RIDER] FirebaseMessaging not initialized: $e");
      return null;
    }
  }
  
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;

    try {
      final fcmInstance = _fcm;
      if (fcmInstance == null) {
        print("⚠️ [RIDER] Skipping NotificationService initialization - Firebase not available");
        return;
      }

      // 1. Set background handler
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      // 2. Request permissions (Required for Android 13+ and iOS)
      if (Platform.isAndroid) {
        final status = await Permission.notification.status;
        if (!status.isGranted) {
          await Permission.notification.request();
        }
      }

      NotificationSettings settings = await fcmInstance.requestPermission(
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
      final fcmInstance = _fcm;
      if (fcmInstance == null) return;

      String? token = await fcmInstance.getToken();
      if (token != null) {
        print('🔑 [RIDER] FCM Token: $token');
        // Register with backend
        await ApiService.updateFcmToken(token);
      }

      // Listen for token refresh
      fcmInstance.onTokenRefresh.listen((newToken) async {
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
