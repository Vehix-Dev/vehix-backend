import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String baseUrl = "https://backend.vehix.ug/api";

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
    try {
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await saveToken(data["access"]);
        await saveRole("RODIE");
        return true;
      } else {
        return false;
      }
    } catch (e) {
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
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(body),
      );

      if (response.statusCode == 401) {
        await logout();
        return null;
      }

      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    } catch (e) {
      return null;
    }
  }

  static Future<dynamic> get(String endpoint) async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final response = await http.get(
        Uri.parse("$baseUrl$endpoint"),
        headers: {"Authorization": "Bearer $token"},
      );

      if (response.statusCode == 401) {
        await logout();
        return null;
      }

      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    } catch (e) {
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
}
