import 'package:flutter/material.dart';
import 'login_screen.dart';
import 'home_screen.dart';
import 'ride_screen.dart';
import '../services/api_service.dart';
import 'dart:async';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    try {
      await Future.delayed(const Duration(seconds: 2));
      if (!mounted) return;

      final token = await ApiService.getToken();
      if (token != null) {
        // Fetch active request for Roadie with timeout
        final activeRequests = await ApiService.getMyRequests(
          status: 'active',
        ).timeout(const Duration(seconds: 5), onTimeout: () => []);

        if (activeRequests.isNotEmpty && mounted) {
          final active = activeRequests.first;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => RideScreen(request: active)),
          );
          return;
        }

        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const HomeScreen(role: "RODIE")),
          );
        }
      } else {
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const LoginScreen(role: "RODIE")),
          );
        }
      }
    } catch (e) {
      debugPrint("Roadie session check error: $e");
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const LoginScreen(role: "RODIE")),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF10223D), // Dark Blue
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset(
              'assets/logo.jpeg',
              width: 150,
              errorBuilder: (context, error, stackTrace) => const Icon(
                Icons.local_shipping,
                size: 100,
                color: Color(0xFFFF8C00),
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              "Vehix",
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
