import 'package:flutter/material.dart';
import '../services/websocket_service.dart';
import 'ride_screen.dart';

class RequestingScreen extends StatefulWidget {
  final Map request;
  const RequestingScreen({required this.request, super.key});

  @override
  State<RequestingScreen> createState() => _RequestingScreenState();
}

class _RequestingScreenState extends State<RequestingScreen>
    with SingleTickerProviderStateMixin {
  final WebSocketService ws = WebSocketService();
  AnimationController? _controller;
  Animation<double>? _animation;

  @override
  void initState() {
    super.initState();

    // Airwaves animation
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.7, end: 1.3).animate(_controller!);

    // Listen for request updates
    ws.connect((data) {
      if (data["type"] == "REQUEST_UPDATE" && data["status"] == "ACCEPTED") {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => RideScreen(request: widget.request),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _controller?.dispose();
    ws.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final serviceName = widget.request["service_type_name"] ?? "Service";

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              "Requesting $serviceName...",
              style: const TextStyle(fontSize: 24),
            ),
            const SizedBox(height: 40),
            AnimatedBuilder(
              animation: _animation!,
              builder: (context, child) {
                return Transform.scale(
                  scale: _animation!.value,
                  child: const Icon(Icons.wifi, size: 80, color: Colors.blue),
                );
              },
            ),
            const SizedBox(height: 20),
            const Text(
              "Waiting for Roadie to accept...",
              style: TextStyle(fontSize: 18),
            ),
          ],
        ),
      ),
    );
  }
}
