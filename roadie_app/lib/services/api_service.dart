import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class SessionInvalidatedException implements Exception {
  final String message;
  SessionInvalidatedException(this.message);
  @override
  String toString() => message;
}

class ApiService {
  static const String baseUrl = "https://backend.vehix.ug/api";
  static const Duration requestTimeout = Duration(seconds: 15);
  static const int maxRetries = 3;
  static const Duration retryDelay = Duration(seconds: 2);

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
    await prefs.remove("role");
  }

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("access");
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

  static Future<bool> signup({
    required String username,
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required String phone,
    required String role,
    required String nin,
  }) async {
    try {
      final response = await post("/register/", {
        "username": username,
        "email": email,
        "password": password,
        "first_name": firstName,
        "last_name": lastName,
        "phone": phone,
        "role": role,
        "nin": nin,
      });
      if (response != null && response["id"] != null) {
        return await login(username, password);
      }
      return false;
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

  static Future<dynamic> post(
    String endpoint,
    Map body, {
    bool requiresAuth = false,
  }) async {
    final url = Uri.parse("$baseUrl$endpoint");
    try {
      Map<String, String> headers = {"Content-Type": "application/json"};
      if (requiresAuth) {
        final token = await getToken();
        if (token != null) headers["Authorization"] = "Bearer $token";
      }
      
      final response = await _retryablePost(
        url,
        headers,
        jsonEncode(body),
      );

      if (response == null) {
        print("⚠️ POST $endpoint failed after retries");
        return null;
      }

      if (response.statusCode == 401) {
        print("🔓 Unauthorized (401)");
        // Check if it's a session invalidation (logged in elsewhere)
        if (response.body.isNotEmpty) {
          try {
            final errorData = jsonDecode(response.body);
            final detail = errorData['detail'] ?? '';
            if (detail.contains('session is no longer valid') || 
                detail.contains('Another device') ||
                errorData['code'] == 'multiple_device_login') {
              print("🔓 Session invalidated - another device logged in");
              await logout();
              throw SessionInvalidatedException(
                'You have been logged out because you logged in on another device.'
              );
            }
          } catch (e) {
            if (e is SessionInvalidatedException) rethrow;
          }
        }
        await logout();
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

  static Future<dynamic> get(String endpoint) async {
    final token = await getToken();
    if (token == null) {
      print("⚠️ No token available for GET $endpoint");
      return null;
    }
    try {
      final url = Uri.parse("$baseUrl$endpoint");
      final response = await _retryableGet(
        url,
        {"Authorization": "Bearer $token"},
      );

      if (response == null) {
        print("⚠️ GET $endpoint failed after retries");
        return null;
      }

      if (response.statusCode == 401) {
        print("🔓 Unauthorized (401)");
        // Check if it's a session invalidation (logged in elsewhere)
        if (response.body.isNotEmpty) {
          try {
            final errorData = jsonDecode(response.body);
            final detail = errorData['detail'] ?? '';
            if (detail.contains('session is no longer valid') || 
                detail.contains('Another device') ||
                errorData['code'] == 'multiple_device_login') {
              print("🔓 Session invalidated - another device logged in");
              await logout();
              throw SessionInvalidatedException(
                'You have been logged out because you logged in on another device.'
              );
            }
          } catch (e) {
            if (e is SessionInvalidatedException) rethrow;
          }
        }
        await logout();
        return null;
      }

      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    } catch (e) {
      print("❌ GET error: $e");
      return null;
    }
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

  static Future<dynamic> depositFunds(
    double amount,
    String? phoneNumber,
  ) async {
    final Map<String, dynamic> data = <String, dynamic>{"amount": amount};
    if (phoneNumber != null) data["phone_number"] = phoneNumber;
    return await post("/wallet/deposit/", data, requiresAuth: true);
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

    var streamedResponse = await request.send();
    var response = await http.Response.fromStream(streamedResponse);
    return jsonDecode(response.body);
  }

  /// History APIs
  static Future<List<dynamic>> getMyRequests({String? status}) async {
    final endpoint = status != null
        ? "/requests/my/?status=$status"
        : "/requests/my/";
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

  static Future<dynamic> acceptRequest(int requestId) async {
    return await post("/requests/$requestId/accept/", {}, requiresAuth: true);
  }

  static Future<dynamic> declineRequest(int requestId) async {
    return await post("/requests/$requestId/decline/", {}, requiresAuth: true);
  }

  /// Referral APIs
  static Future<List<dynamic>> getReferrals() async {
    final response = await get("/users/referrals/");
    return response is List ? response : [];
  }

  /// Rodie Status APIs
  static Future<dynamic> updateRodieStatus(bool isOnline) async {
    return await post(
      "/roadie/status/",
      {"is_online": isOnline},
      requiresAuth: true,
    );
  }
}
