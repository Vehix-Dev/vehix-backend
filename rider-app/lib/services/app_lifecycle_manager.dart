import 'package:flutter/widgets.dart';
import 'wake_lock_service.dart';

/// App Lifecycle Manager for Wake Lock Service
/// 
/// Automatically manages wake lock based on app lifecycle events
/// This ensures the wake lock is properly enabled/disabled
/// when the app goes to foreground/background
class AppLifecycleManager extends WidgetsBindingObserver {
  static final AppLifecycleManager _instance = AppLifecycleManager._internal();
  factory AppLifecycleManager() => _instance;
  AppLifecycleManager._internal();

  final WakeLockService _wakeLockService = WakeLockService();
  bool _isInitialized = false;

  /// Initialize the lifecycle manager
  void initialize() {
    if (_isInitialized) return;
    
    WidgetsBinding.instance.addObserver(this);
    _isInitialized = true;
    print('🔄 AppLifecycleManager initialized');
  }

  /// Dispose the lifecycle manager
  void dispose() {
    if (!_isInitialized) return;
    
    WidgetsBinding.instance.removeObserver(this);
    _isInitialized = false;
    print('🔄 AppLifecycleManager disposed');
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    
    switch (state) {
      case AppLifecycleState.resumed:
        print('🔄 App resumed');
        _wakeLockService.onAppResumed();
        break;
        
      case AppLifecycleState.paused:
        print('🔄 App paused');
        _wakeLockService.onAppPaused();
        break;
        
      case AppLifecycleState.detached:
        print('🔄 App detached');
        _wakeLockService.dispose();
        break;
        
      case AppLifecycleState.inactive:
        print('🔄 App inactive');
        // App is transitioning, no action needed
        break;
        
      case AppLifecycleState.hidden:
        print('🔄 App hidden');
        _wakeLockService.onAppPaused();
        break;
    }
  }
}
