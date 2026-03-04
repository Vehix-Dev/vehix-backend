import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:audioplayers/audioplayers.dart';
import '../services/websocket_service.dart';
import '../services/api_service.dart';
import 'ride_screen.dart';
import 'login_screen.dart';
import '../widgets/app_drawer.dart';

class HomeScreen extends StatefulWidget {
  final String role;
  const HomeScreen({required this.role, super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  LatLng? currentLocation;
  List<LatLng> roadieLocations = [];
  final WebSocketService ws = WebSocketService();
  String _loadingStatus = "Initializing...";
  bool _isReady = false;
  Map? activeOffer;
  Timer? _locationTimer;
  final AudioPlayer _audioPlayer = AudioPlayer();

  final String _tileTemplate = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

  @override
  void initState() {
    super.initState();
    _initializeScreen();
  }

  Future<void> _initializeScreen() async {
    try {
      await _initLocation();
      setState(() => _loadingStatus = "Connecting...");
      await _connectWS();
      if (mounted) {
        setState(() => _isReady = true);
        _sendInitialLocation();
        _startLocationBroadcast();
      }
    } on SessionInvalidatedException catch (e) {
      if (mounted) {
        _showSessionInvalidatedDialog(e.message);
      }
    } catch (e) {
      if (mounted) setState(() => _loadingStatus = "Error: $e");
    }
  }

  void _showSessionInvalidatedDialog(String message) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('Session Ended'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
              );
            },
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
  }

  Future<void> _initLocation() async {
    try {
      setState(() => _loadingStatus = "Getting location...");
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );
      if (mounted) {
        setState(() {
          currentLocation = LatLng(position.latitude, position.longitude);
        });
      }
    } catch (e) {
      debugPrint("Location error: $e");
    }
  }

  Future<void> _connectWS() async {
    await ws.connect((data) {
      if (data["type"] == "OFFER_REQUEST") {
        if (mounted) {
          _playNotificationSound();
          _showOfferDialog(data["request"]);
        }
      } else if (data["type"] == "RODIE_LOCATION" ||
          data["type"] == "NEARBY_LIST") {
        if (mounted) {
          setState(() {
            if (data["type"] == "RODIE_LOCATION") {
              roadieLocations = [LatLng(data["lat"], data["lng"])];
            }
          });
        }
      }
    });
  }

  Future<void> _playNotificationSound() async {
    try {
      await _audioPlayer.play(AssetSource('Sound.mpeg'));
    } catch (e) {
      debugPrint("Error playing sound: $e");
    }
  }

  Future<void> _sendInitialLocation() async {
    try {
      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      ws.sendLocation(lat: position.latitude, lng: position.longitude);
    } catch (e) {
      // ignore
    }
  }

  void _startLocationBroadcast() {
    _locationTimer?.cancel();
    _locationTimer = Timer.periodic(const Duration(seconds: 10), (timer) async {
      if (!mounted || !_isReady) {
        timer.cancel();
        return;
      }
      try {
        Position position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );
        ws.sendLocation(lat: position.latitude, lng: position.longitude);
      } catch (e) {
        // Silently fail in background
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (!_isReady || currentLocation == null) {
      return Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF10223D), Color(0xFF1D3B63)],
            ),
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const CircularProgressIndicator(color: Colors.white),
                const SizedBox(height: 24),
                Text(
                  _loadingStatus,
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: const Color(0xFF10223D),
        title: const Text(
          "Roadie Portal",
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            decoration: const BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
            ),
            child: IconButton(
              icon: const Icon(
                Icons.notifications_none,
                color: Color(0xFF10223D),
              ),
              onPressed: () {},
            ),
          ),
        ],
      ),
      drawer: const AppDrawer(),
      body: Stack(
        children: [
          FlutterMap(
            options: MapOptions(
              initialCenter: currentLocation!,
              initialZoom: 15,
            ),
            children: [
              TileLayer(
                urlTemplate: _tileTemplate,
                userAgentPackageName: 'com.vehix.roadie',
              ),
              MarkerLayer(
                markers: [
                  Marker(
                    point: currentLocation!,
                    width: 50,
                    height: 50,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF8C00).withValues(alpha: 0.2),
                        shape: BoxShape.circle,
                      ),
                      child: const Center(
                        child: Icon(
                          Icons.my_location,
                          color: Color(0xFFFF8C00),
                          size: 30,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          Positioned(
            top: 100,
            left: 20,
            right: 20,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.1),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.green.withValues(alpha: 0.1),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.online_prediction,
                      color: Colors.green,
                    ),
                  ),
                  const SizedBox(width: 16),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "Status: Online",
                          style: TextStyle(
                            fontWeight: FontWeight.w900,
                            color: Color(0xFF10223D),
                          ),
                        ),
                        Text(
                          "Ready for requests",
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
                  Switch(
                    value: true,
                    activeThumbColor: const Color(0xFFFF8C00),
                    onChanged: (v) {},
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showOfferDialog(Map request) {
    int timeLeft = 10;
    Timer? dialogTimer;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          dialogTimer ??= Timer.periodic(const Duration(seconds: 1), (timer) {
            if (timeLeft > 0) {
              setDialogState(() => timeLeft--);
            } else {
              timer.cancel();
              if (Navigator.canPop(context)) Navigator.pop(context);
            }
          });

          return Dialog(
            backgroundColor: Colors.transparent,
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(32),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    height: 120,
                    width: double.infinity,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [Color(0xFF10223D), Color(0xFF1D3B63)],
                      ),
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(32),
                        topRight: Radius.circular(32),
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(
                          Icons.flash_on,
                          color: Color(0xFFFF8C00),
                          size: 40,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          "NEW REQUEST",
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.9),
                            fontWeight: FontWeight.w900,
                            letterSpacing: 2,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              request['service_type_name'] ?? "Assist",
                              style: const TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w900,
                                color: Color(0xFF10223D),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 6,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.red.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                "${timeLeft}s",
                                style: const TextStyle(
                                  color: Colors.red,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 20),
                        _buildInfoRow(
                          Icons.location_on,
                          "Distance",
                          "${request['distance_km'] ?? '?'} km",
                        ),
                        const SizedBox(height: 12),
                        _buildInfoRow(
                          Icons.payments,
                          "Potential Fee",
                          "KES ${request['fee'] ?? '15,000'}",
                        ),
                        const SizedBox(height: 24),
                        Row(
                          children: [
                            Expanded(
                              child: TextButton(
                                onPressed: () async {
                                  dialogTimer?.cancel();
                                  Navigator.pop(context);
                                  await ApiService.declineRequest(
                                    request['id'],
                                  );
                                },
                                style: TextButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 16,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                ),
                                child: const Text(
                                  "Decline",
                                  style: TextStyle(
                                    color: Colors.grey,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: ElevatedButton(
                                onPressed: () async {
                                  dialogTimer?.cancel();
                                  final nav = Navigator.of(context);
                                  nav.pop();
                                  final response =
                                      await ApiService.acceptRequest(
                                        request['id'],
                                      );
                                  if (response != null && mounted) {
                                    nav.push(
                                      MaterialPageRoute(
                                        builder: (_) =>
                                            RideScreen(request: request),
                                      ),
                                    );
                                  }
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFFFF8C00),
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 16,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  elevation: 5,
                                ),
                                child: const Text(
                                  "ACCEPT",
                                  style: TextStyle(
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 1.5,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    ).then((_) => dialogTimer?.cancel());
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 20, color: const Color(0xFF1D3B63)),
        const SizedBox(width: 12),
        Text("$label: ", style: const TextStyle(color: Colors.grey)),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Color(0xFF10223D),
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    ws.disconnect();
    _locationTimer?.cancel();
    _audioPlayer.dispose();
    super.dispose();
  }
}
