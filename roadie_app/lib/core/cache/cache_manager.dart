import 'package:hive_flutter/hive_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Singleton cache manager wrapping Hive for instant app startup.
/// Caches: last GPS location, user profile, services list.
class CacheManager {
  static final CacheManager _instance = CacheManager._();
  factory CacheManager() => _instance;
  CacheManager._();

  static const String _boxUser = 'user_box';
  static const String _boxCache = 'cache_box';
  static const String _keyLastLocation = 'last_location';
  static const String _keyUserProfile = 'user_profile';
  static const String _keyServices = 'cached_services';

  late Box _userBox;
  late Box _cacheBox;
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    await Hive.initFlutter();
    _userBox = await Hive.openBox(_boxUser);
    _cacheBox = await Hive.openBox(_boxCache);
    _initialized = true;
  }

  // ── Location ──
  Future<void> saveLastLocation(double lat, double lng) async {
    if (!_initialized) return;
    await _cacheBox.put(_keyLastLocation, {'lat': lat, 'lng': lng});
  }

  Map<String, double>? getLastLocation() {
    if (!_initialized) return null;
    final data = _cacheBox.get(_keyLastLocation);
    if (data == null) return null;
    return {
      'lat': (data['lat'] as num).toDouble(),
      'lng': (data['lng'] as num).toDouble(),
    };
  }

  // ── User Profile ──
  Future<void> saveUserProfile(Map<String, dynamic> profile) async {
    if (!_initialized) return;
    await _userBox.put(_keyUserProfile, profile);
    try {
      final prefs = await SharedPreferences.getInstance();
      final id = profile['id'];
      if (id != null) {
        await prefs.setString('logged_in_rodie_id', id.toString());
      }
    } catch (_) {}
  }

  Map<String, dynamic>? getUserProfile() {
    if (!_initialized) return null;
    final data = _userBox.get(_keyUserProfile);
    if (data == null) return null;
    return Map<String, dynamic>.from(data);
  }

  // ── Services ──
  Future<void> saveServices(List<dynamic> services) async {
    if (!_initialized) return;
    await _cacheBox.put(_keyServices, services);
  }

  List<dynamic>? getServices() {
    if (!_initialized) return null;
    final data = _cacheBox.get(_keyServices);
    if (data == null) return null;
    return List<dynamic>.from(data);
  }

  // ── Generic ──
  Future<void> clearAll() async {
    if (!_initialized) return;
    await _userBox.clear();
    await _cacheBox.delete(_keyLastLocation);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('logged_in_rodie_id');
    } catch (_) {}
  }
}
