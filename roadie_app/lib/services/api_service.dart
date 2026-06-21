import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../core/cache/cache_manager.dart';
import '../config/app_config.dart';


class SessionInvalidatedException implements Exception {
  final String message;
  SessionInvalidatedException(this.message);
  @override
  String toString() => message;
}

class ApiService {
  static String get baseUrl => AppConfig.apiBaseUrl;
  
  // Stream to notify UI about session invalidation (multiple device login)
  static final StreamController<String> _sessionController = StreamController<String>.broadcast();
  static Stream<String> get sessionInvalidatedStream => _sessionController.stream;

  static const Duration requestTimeout = Duration(seconds: 15);
  static const int maxRetries = 3;
  static const Duration retryDelay = Duration(seconds: 2);

  static const _tokenKey = 'access';
  static const _refreshTokenKey = 'refresh';

  static Future<void> saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString("access", token);
  }

  static Future<void> saveRole(String role) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString("role", role);
  }

  static Future<String?> getRole() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("role");
  }

  static Future<bool> updateFcmToken(String token) async {
    try {
      final result = await patch("/profile/", {"fcm_token": token});
      if (result != null) {
        print("✅ FCM token updated on backend");
        return true;
      }
      return false;
    } catch (e) {
      print("❌ Failed to update FCM token: $e");
      return false;
    }
  }

  static Map<String, dynamic>? _parseJwtPayload(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return null;
      final payload = parts[1];
      var normalized = base64Url.normalize(payload);
      final decoded = utf8.decode(base64Url.decode(normalized));
      return jsonDecode(decoded) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  static Future<Map<String, dynamic>?> getUserData() async {
    final token = await getToken();
    if (token == null) return null;
    return _parseJwtPayload(token);
  }

  /// Corrected: Backend uses /api/me/ for profile information
  static Future<Map<String, dynamic>?> fetchUserInfo() async {
    try {
      final result = await get("/me/");
      if (result is Map<String, dynamic>) {
        return result;
      }
      // print removed
      return null;
    } catch (e) {
      // print removed
      return null;
    }
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("access");
    await prefs.remove("refresh"); // Clear refresh token to prevent auto-login after logout
    await prefs.remove("role");
    
    // Clear Hive cache to prevent UI resume with old data
    try {
      await CacheManager().clearAll();
    } catch (e) {
      debugPrint("Cache clear error: $e");
    }
  }


  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("access");
  }

  /// Alias for getToken for WebSocket service compatibility
  static Future<String?> getAuthToken() async {
    return await getToken();
  }

  /// Helper method to retry failed network requests
  static Future<http.Response?> _retryablePost(
    Uri url,
    Map<String, String> headers,
    String body,
  ) async {
    int retries = 0;
    while (retries < maxRetries) {
      try {
        print("📤 POST attempt ${retries + 1}/$maxRetries to: $url");
        final response = await http.post(
          url,
          headers: headers,
          body: body,
        ).timeout(requestTimeout, onTimeout: () {
          throw TimeoutException("Request timeout after $requestTimeout");
        });
        print("📥 Response received: ${response.statusCode}");
        return response;
      } on SocketException catch (e) {
        print("⚠️ Network error (attempt ${retries + 1}): $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(retryDelay);
        }
      } on TimeoutException catch (e) {
        print("⏱️ Timeout (attempt ${retries + 1}): $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(retryDelay);
        }
      }
    }
    return null;
  }

  /// Helper method to retry failed GET requests
  static Future<http.Response?> _retryableGet(
    Uri url,
    Map<String, String> headers,
  ) async {
    int retries = 0;
    while (retries < maxRetries) {
      try {
        print("📤 GET attempt ${retries + 1}/$maxRetries to: $url");
        final response = await http.get(
          url,
          headers: headers,
        ).timeout(requestTimeout, onTimeout: () {
          throw TimeoutException("Request timeout after $requestTimeout");
        });
        print("📥 Response received: ${response.statusCode}");
        return response;
      } on SocketException catch (e) {
        print("⚠️ Network error (attempt ${retries + 1}): $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(retryDelay);
        }
      } on TimeoutException catch (e) {
        print("⏱️ Timeout (attempt ${retries + 1}): $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(retryDelay);
        }
      }
    }
    return null;
  }

  static Future<dynamic> signup({
    required String username,
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required String phone,
    required String role,
    String? nin, // Made optional (nullable)
    String? referredByCode,
  }) async {
    try {
      final Map<String, dynamic> data = {
        "username": username,
        "email": email,
        "password": password,
        "first_name": firstName,
        "last_name": lastName,
        "phone": phone,
        "role": role,
      };
      
      // Add NIN if provided
      if (nin != null && nin.isNotEmpty) {
        data["nin"] = nin;
      }
      
      // Add referral code if provided
      if (referredByCode != null && referredByCode.isNotEmpty) {
        data["referred_by_code"] = referredByCode;
      }
      
      final response = await post("/register/", data);
      if (response != null && response["id"] != null) {
        return await login(username, password);
      } else if (response != null && response is Map) {
        // Return validation errors if any
        print("❌ Registration failed with errors: $response");
        return response; // Return the error map for handling in UI
      } else {
        print("❌ Registration failed: No valid response");
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  static Future<bool> login(String username, String password) async {
    final url = Uri.parse("$baseUrl/login/roadie/");
    print("🔐 Roadie login attempt: user=$username, url=$url");
    try {
      final response = await _retryablePost(
        url,
        {"Content-Type": "application/json"},
        jsonEncode({"username": username, "password": password}),
      );

      if (response == null) {
        print("❌ Login failed: No response after retries");
        return false;
      }

      print("📨 Login response: status=${response.statusCode}");
      print("📦 Response body: ${response.body}");
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await saveToken(data["access"]);
        // Save refresh token if present
        if (data["refresh"] != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(_refreshTokenKey, data["refresh"]);
        }
        await saveRole("RODIE");
        print("✅ Roadie login successful!");
        return true;
      } else {
        print("❌ Login failed with status ${response.statusCode}");
        if (response.body.isNotEmpty) {
          try {
            final errorData = jsonDecode(response.body);
            print("❌ Error details: $errorData");
          } catch (_) {}
        }
        return false;
      }
    } catch (e) {
      print("❌ Login exception: $e");
      return false;
    }
  }

  /// Refresh JWT token if needed
  static Future<bool> refreshTokenIfNeeded() async {
    final prefs = await SharedPreferences.getInstance();
    final refreshToken = prefs.getString(_refreshTokenKey);
    if (refreshToken == null) {
      print("⚠️ No refresh token available");
      return false;
    }
    
    try {
      final url = Uri.parse("$baseUrl/refresh/");
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"refresh": refreshToken}),
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await prefs.setString(_tokenKey, data["access"]);
        print("✅ Token refreshed successfully");
        return true;
      } else {
        print("❌ Token refresh failed: ${response.statusCode}");
        return false;
      }
    } catch (e) {
      print("❌ Token refresh error: $e");
      return false;
    }
  }

  /// Internal helper to check for and handle session invalidation or natural expiration
  static Future<bool> _handleSessionInvalidation(http.Response response) async {
    if (response.statusCode == 401) {
      if (response.body.isNotEmpty) {
        try {
          final errorData = jsonDecode(response.body);
          final detail = errorData['detail'] ?? '';
          final code = errorData['code'] ?? '';
          
          // Case 1: Multiple device login (Manual invalidation)
          if (detail.contains('session is no longer valid') || 
              detail.contains('Another device') ||
              code == 'session_invalidated') {
            print("🔓 Session invalidated - another device logged in");
            _sessionController.add('You have been logged out because you logged in on another device.');
            await logout();
            return true; // Stop here, session is dead
          }
          
          // Case 2: Natural token expiration
          if (code == 'token_not_valid' || detail.contains('given token has expired')) {
            print("🔄 Access token expired. Attempting silent refresh...");
            final refreshed = await refreshTokenIfNeeded();
            if (refreshed) {
              return false; // Return false but caller should check if we just refreshed
            }
          }
        } catch (e) {
          print("Error parsing 401 response: $e");
        }
      }
      
      // Fallback: If we couldn't refresh or it's a hard 401, logout
      await logout();
    }
    return false;
  }

  static Future<dynamic> post(
    String endpoint,
    Map body, {
    bool requiresAuth = false,
  }) async {
    final url = Uri.parse("$baseUrl$endpoint");
    try {
      Future<http.Response?> makeCall() async {
        Map<String, String> headers = {"Content-Type": "application/json"};
        if (requiresAuth) {
          final token = await getToken();
          if (token != null) headers["Authorization"] = "Bearer $token";
        }
        return await _retryablePost(url, headers, jsonEncode(body));
      }

      var response = await makeCall();
      if (response != null && response.statusCode == 401) {
        if (await _handleSessionInvalidation(response)) {
          throw SessionInvalidatedException('You have been logged out because you logged in on another device.');
        }
        // If it wasn't a hard invalidation, it was likely an expired token that was just refreshed. Retry once.
        response = await makeCall();
      }

      if (response == null) {
        print("❌ Networking error: No response received");
        return null;
      }
      
      if (response.statusCode >= 400) {
        print("❌ API error ${response.statusCode} on $endpoint");
        if (response.body.isNotEmpty) {
          try {
            final errorBody = jsonDecode(response.body);
            print("❌ Error body: $errorBody");
            return errorBody; // Return error body for validation handling
          } catch (e) {
            print("❌ Failed to decode error body: $e");
          }
        }
        return null;
      }

      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    } catch (e) {
      if (e is SessionInvalidatedException) rethrow;
      print("❌ POST error: $e");
      return null;
    }
  }

  static Future<dynamic> patch(
    String endpoint,
    Map body, {
    bool requiresAuth = true,
  }) async {
    final url = Uri.parse("$baseUrl$endpoint");
    try {
      Future<http.Response?> makeCall() async {
        Map<String, String> headers = {"Content-Type": "application/json"};
        if (requiresAuth) {
          final token = await getToken();
          if (token != null) headers["Authorization"] = "Bearer $token";
        }
        return await _retryablePatch(url, headers, jsonEncode(body));
      }

      var response = await makeCall();
      if (response != null && response.statusCode == 401) {
        if (await _handleSessionInvalidation(response)) {
          throw SessionInvalidatedException('You have been logged out because you logged in on another device.');
        }
        response = await makeCall();
      }

      if (response == null) return null;
      
      if (response.statusCode >= 400) {
        if (response.body.isNotEmpty) {
          try {
            return jsonDecode(response.body);
          } catch (e) {
            print("❌ Failed to decode JSON from PATCH error body: $e");
          }
        }
        return null;
      }

      if (response.body.isEmpty) return null;
      try {
        return jsonDecode(response.body);
      } catch (e) {
        print("❌ Failed to decode JSON from PATCH response: $e");
        return null;
      }
    } catch (e) {
      if (e is SessionInvalidatedException) rethrow;
      print("❌ PATCH error: $e");
      return null;
    }
  }

  static Future<dynamic> get(String endpoint) async {
    final url = Uri.parse("$baseUrl$endpoint");
    try {
      Future<http.Response?> makeCall() async {
        final token = await getToken();
        if (token == null) return null;
        return await _retryableGet(url, {"Authorization": "Bearer $token"});
      }

      var response = await makeCall();
      if (response != null && response.statusCode == 401) {
        if (await _handleSessionInvalidation(response)) {
          throw SessionInvalidatedException('You have been logged out because you logged in on another device.');
        }
        response = await makeCall();
      }

      if (response == null || response.statusCode >= 400) return null;
      if (response.body.isEmpty) return null;
      try {
        return jsonDecode(response.body);
      } catch (e) {
        print("❌ Failed to decode JSON from GET response: $e");
        return null;
      }
    } catch (e) {
      if (e is SessionInvalidatedException) rethrow;
      print("❌ GET error: $e");
      return null;
    }
  }

  /// Helper method to retry failed PATCH requests
  static Future<http.Response?> _retryablePatch(
    Uri url,
    Map<String, String> headers,
    String body,
  ) async {
    int retries = 0;
    while (retries < maxRetries) {
      try {
        print("📤 PATCH attempt ${retries + 1}/$maxRetries to: $url");
        final response = await http.patch(
          url,
          headers: headers,
          body: body,
        ).timeout(const Duration(seconds: 15), onTimeout: () {
          throw TimeoutException("Request timeout after 15 seconds");
        });
        print("📥 Response received: ${response.statusCode}");
        return response;
      } on SocketException catch (e) {
        print("⚠️ Network error (attempt ${retries + 1}): $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(const Duration(seconds: 2));
        }
      } catch (e) {
        print("❌ PATCH attempt ${retries + 1} failed: $e");
        retries++;
        if (retries < maxRetries) {
          await Future.delayed(const Duration(seconds: 2));
        }
      }
    }
    return null;
  }


  /// Corrected: Backend uses /api/services/ for general service listing
  static Future<List<dynamic>> getServices() async {
    try {
      final response = await get("/services/");
      if (response is List) return response;
      if (response is Map && response.containsKey('results')) {
        return response['results'];
      }
      return [];
    } catch (e) {
      // print removed
      return [];
    }
  }

  /// Wallet APIs
  static Future<Map<String, dynamic>?> getWallet() async {
    final response = await get("/wallet/");
    return response is Map<String, dynamic> ? response : null;
  }

  static Future<Map<String, dynamic>?> getRoadiePayments() async {
    final response = await get("/roadie/payments/");
    return response is Map<String, dynamic> ? response : null;
  }

  static Future<Map<String, dynamic>?> depositFunds(double amount) async {
    try {
      final response = await post("/wallet/deposit/", {"amount": amount}, requiresAuth: true);
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      print("❌ [ROADIE] Deposit error: $e");
      return null;
    }
  }

  static Future<Map<String, dynamic>?> checkPaymentStatus(String reference) async {
    try {
      print("🔍 [ROADIE] Checking payment status for: $reference");
      final response = await get("/payments/status/$reference/");
      print("📥 [ROADIE] Payment status response: $response");
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      print("❌ [ROADIE] Payment status check error: $e");
      return null;
    }
  }

  static Future<Map<String, dynamic>?> withdrawFunds(
    double amount,
    String phoneNumber,
  ) async {
    final Map<String, dynamic> data = {
      "amount": amount,
      "phone_number": phoneNumber,
    };
    
    print("💸 [ROADIE] Initiating withdrawal:");
    print("   Amount: $amount");
    print("   Phone: $phoneNumber");
    
    try {
      final response = await post("/wallet/withdraw/", data, requiresAuth: true);
      print("📥 [ROADIE] Withdrawal response: $response");
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      print("❌ [ROADIE] Withdrawal error: $e");
      return null;
    }
  }

  /// Image Upload API (KYC)
  static Future<dynamic> uploadUserImage(File image, String type) async {
    final token = await getToken();
    if (token == null) return null;

    var request = http.MultipartRequest(
      'POST',
      Uri.parse("$baseUrl/images/user-images/"),
    );
    request.headers['Authorization'] = "Bearer $token";
    request.fields['image_type'] = type;
    request.files.add(await http.MultipartFile.fromPath('image', image.path));

    try {
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode >= 400) {
        print("❌ Upload failed: ${response.statusCode} - ${response.reasonPhrase}");
        try {
          return jsonDecode(response.body);
        } catch (_) {
          throw Exception("Server returned ${response.statusCode}. The file might be too large or the server is encountering an error.");
        }
      }

      return jsonDecode(response.body);
    } catch (e) {
      if (e is FormatException) {
        throw Exception("Server returned an invalid response. The file might be too large.");
      }
      rethrow;
    }
  }

  /// History APIs
  static Future<List<dynamic>> getMyRequests({String? status}) async {
    final endpoint = status != null
        ? "/requests/roadie/?status=$status"
        : "/requests/roadie/";
    final response = await get(endpoint);
    return response is List ? response : [];
  }

  /// Nearby search
  static Future<List<dynamic>> searchNearbyRoadies(
    double lat,
    double lng,
    int serviceId,
  ) async {
    final endpoint =
        "/requests/nearby/?lat=$lat&lng=$lng&service_id=$serviceId";
    final response = await get(endpoint);
    return response is List ? response : [];
  }

  static Future<dynamic> createRequest({
    required int serviceTypeId,
    required double riderLat,
    required double riderLng,
    String notes = "",
  }) async {
    return await post("/requests/create/", {
      "service_type": serviceTypeId,
      "rider_lat": double.parse(riderLat.toStringAsFixed(6)),
      "rider_lng": double.parse(riderLng.toStringAsFixed(6)),
      "notes": notes,
    }, requiresAuth: true);
  }

  static Future<dynamic> acceptRequest(int requestId, {double? lat, double? lng}) async {
    final Map<String, dynamic> data = {};
    if (lat != null) data['lat'] = lat;
    if (lng != null) data['lng'] = lng;
    
    return await post("/requests/$requestId/accept/", data, requiresAuth: true);
  }

  static Future<dynamic> declineRequest(int requestId) async {
    return await post("/requests/$requestId/decline/", {}, requiresAuth: true);
  }

  static Future<Map<String, dynamic>?> getRequestDetails(int requestId) async {
    final response = await get("/requests/$requestId/");
    if (response is Map) {
      return Map<String, dynamic>.from(response);
    }
    return null;
  }

  static Future<List<dynamic>> fetchChatHistory(int requestId) async {
    final response = await get("/requests/$requestId/chat/");
    return response is List ? response : [];
  }

  /// Referral APIs
  static Future<List<dynamic>> getReferrals() async {
    final response = await get("/referrals/");
    return response is List ? response : [];
  }

  /// Notification APIs
  static Future<List<dynamic>> getNotifications() async {
    final response = await get("/notifications/");
    return response is List ? response : [];
  }

  static Future<bool> markNotificationAsRead(int notificationId) async {
    final response = await patch("/notifications/$notificationId/", {"is_read": true});
    return response != null;
  }

  /// Rodie Status APIs
  static Future<dynamic> updateRodieStatus(bool isOnline) async {
    return await post(
      "/roadie/status/",
      {"is_online": isOnline},
      requiresAuth: true,
    );
  }

  /// Rodie Services APIs
  static Future<dynamic> saveRodieServices(List<int> serviceIds) async {
    return await post(
      "/auth/rodie/services/",
      {"service_ids": serviceIds},
      requiresAuth: true,
    );
  }

  static Future<List<dynamic>> getRodieServices() async {
    final response = await get("/auth/rodie/services/");
    // Backend returns {'services': [...], 'services_selected': bool}
    if (response is Map && response.containsKey('services')) {
      return response['services'] as List;
    }
    if (response is List) {
      return response;
    }
    return [];
  }

  /// Forgot Password APIs
  static Future<Map<String, dynamic>?> sendPasswordResetCode(String email, String role) async {
    try {
      final response = await post("/auth/password-reset/", {
        "email": email,
        "role": role,
      });
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      debugPrint("❌ [ROADIE] Reset code request error: $e");
      return null;
    }
  }

  static Future<Map<String, dynamic>?> confirmPasswordReset({
    required String email,
    required String role,
    required String code,
    required String newPassword,
  }) async {
    try {
      final response = await post("/auth/password-reset/confirm/", {
        "email": email,
        "role": role,
        "code": code,
        "new_password": newPassword,
      });
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      debugPrint("❌ [ROADIE] Password confirm error: $e");
      return null;
    }
  }

  /// Change password (POST /api/profile/change-password/)
  static Future<Map<String, dynamic>?> changePassword(String currentPassword, String newPassword) async {
    final token = await getToken();
    if (token == null) return null;
    
    try {
      final response = await post(
        "/profile/change-password/", 
        {
          "current_password": currentPassword,
          "new_password": newPassword,
        },
        requiresAuth: true
      );

      if (response != null && response['success'] == true) {
        return response;
      } else if (response != null) {
        // Return structured error if present
        return {
          'success': false,
          'error': response['error'] ?? response['message'] ?? 'Failed to change password',
        };
      }
      return null;
    } catch (e) {
      print("Change password error: $e");
      return null;
    }
  }

  /// Account Deletion APIs
  static Future<Map<String, dynamic>?> checkDeletionEligibility() async {
    return await get("/profile/deletion-eligibility/");
  }

  static Future<Map<String, dynamic>?> requestAccountDeletion(String reason) async {
    return await post("/profile/request-deletion/", {"reason": reason}, requiresAuth: true);
  }

  static Future<Map<String, dynamic>?> submitFeedback(String message, {String type = 'app_feedback'}) async {
    try {
      final response = await post("/feedback/", {
        "message": message,
        "type": type,
      }, requiresAuth: true);
      return response is Map<String, dynamic> ? response : null;
    } catch (e) {
      debugPrint("❌ [ROADIE] Feedback submission error: $e");
      return null;
    }
  }
}
