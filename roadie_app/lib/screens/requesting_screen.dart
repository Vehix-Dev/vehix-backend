import 'package:flutter/material.dart';
import 'dart:async';
import '../services/websocket_service.dart';
import 'ride_screen.dart';
import 'home_screen.dart';

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

  int _remainingSeconds = 15; // 15 seconds to accept offer
  Timer? _countdownTimer;

  @override
  void initState() {
    super.initState();

    // Airwaves animation
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.7, end: 1.3).animate(_controller!);

    // Start countdown timer
    _startCountdown();

    // Listen for request updates
    _initializeWebSocket();
  }

  void _startCountdown() {
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _remainingSeconds--;
      });
      if (_remainingSeconds <= 0) {
        timer.cancel();
      }
    });
  }

  Future<void> _initializeWebSocket() async {
    try {
      await ws.connect("RODIE", (data) {
        if (!mounted) return;
        
        if (data["type"] == "REQUEST_UPDATE") {
          if (data["status"] == "ACCEPTED") {
            _countdownTimer?.cancel();
            // Use updated request data if available, otherwise use original
            final updatedRequest = data["request"] ?? widget.request;
            
            Navigator.pushReplacement(
              context,
              PageRouteBuilder(
                pageBuilder: (context, animation, secondaryAnimation) =>
                    RideScreen(request: updatedRequest),
                transitionsBuilder:
                    (context, animation, secondaryAnimation, child) {
                  return FadeTransition(opacity: animation, child: child);
                },
                transitionDuration: const Duration(milliseconds: 600),
              ),
            );
          } else if (data["status"] == "EXPIRED") {
            // Offer expired because another roadie accepted or timeout
            _countdownTimer?.cancel();
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text("This offer is no longer available"),
                  duration: Duration(seconds: 2),
                ),
              );
              Future.delayed(const Duration(seconds: 1), () {
                if (mounted) {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const HomeScreen(role: "RODIE"),
                    ),
                  );
                }
              });
            }
          }
        }
      });
      ws.send({"type": "JOIN_REQUEST", "request_id": widget.request["id"]});
    } catch (e) {
      debugPrint("WebSocket initialization error: $e");
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    _countdownTimer?.cancel();
    ws.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final serviceName = widget.request["service_type_name"] ?? "Service";
    final progressPercent = _remainingSeconds / 15.0;

    return Scaffold(
      body: PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, result) {
          if (didPop) return;
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Please accept or decline the offer."),
            ),
          );
        },
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                "Awaiting for Rider...",
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                serviceName,
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 40),
              AnimatedBuilder(
                animation: _animation!,
                builder: (context, child) {
                  if (_animation == null) return const SizedBox(height: 80);
                  return Transform.scale(
                    scale: _animation!.value,
                    child: const Icon(
                      Icons.wifi,
                      size: 80,
                      color: Colors.blue,
                    ),
                  );
                },
              ),
              const SizedBox(height: 40),
              // Countdown timer with progress bar (15 seconds to accept)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                decoration: BoxDecoration(
                  color: Colors.orange.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.orange, width: 2),
                ),
                child: Column(
                  children: [
                    Text(
                      "Time to accept: $_remainingSeconds seconds",
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.orange,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: LinearProgressIndicator(
                        value: progressPercent,
                        minHeight: 8,
                        backgroundColor: Colors.grey[300],
                        valueColor: AlwaysStoppedAnimation(
                          _remainingSeconds <= 3
                              ? Colors.red
                              : Colors.orange,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                "Waiting for rider to confirm...",
                style: TextStyle(fontSize: 16),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
