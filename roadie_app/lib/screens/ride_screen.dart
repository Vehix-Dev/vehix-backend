import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:geolocator/geolocator.dart';
import '../services/websocket_service.dart';
import '../services/api_service.dart';
import 'rating_screen.dart';

class RideScreen extends StatefulWidget {
  final Map request;
  const RideScreen({required this.request, super.key});

  @override
  State<RideScreen> createState() => _RideScreenState();
}

class _RideScreenState extends State<RideScreen> {
  LatLng riderLocation = const LatLng(0, 0);
  LatLng roadieLocation = const LatLng(0, 0);
  final WebSocketService ws = WebSocketService();
  final List<Map> messages = [];
  final TextEditingController chatController = TextEditingController();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  Timer? locationTimer;
  final MapController mapController = MapController();
  late Map currentRequest;
  bool _isConnected = false;
  bool _isChatOpen = false;

  @override
  void initState() {
    super.initState();
    currentRequest = Map.from(widget.request);
    _parseInitialLocations();
    connectWS();
    startSendingLocation();
  }

  void _parseInitialLocations() {
    try {
      if (currentRequest["rider_lat"] != null) {
        double lat =
            double.tryParse(currentRequest["rider_lat"].toString()) ?? 0.0;
        double lng =
            double.tryParse(currentRequest["rider_lng"].toString()) ?? 0.0;
        if (lat != 0) riderLocation = LatLng(lat, lng);
      }
      if (currentRequest["roadie_lat"] != null) {
        double lat =
            double.tryParse(currentRequest["roadie_lat"].toString()) ?? 0.0;
        double lng =
            double.tryParse(currentRequest["roadie_lng"].toString()) ?? 0.0;
        if (lat != 0) roadieLocation = LatLng(lat, lng);
      } else {
        roadieLocation = riderLocation;
      }
    } catch (e) {
      debugPrint("Error parsing initial locations: $e");
    }
  }

  void connectWS() async {
    try {
      await ws.connect((data) {
        if (!mounted) return;
        
        if (data["type"] == "RODIE_LOCATION") {
          setState(() {
            roadieLocation = LatLng(
              double.parse(data["lat"].toString()),
              double.parse(data["lng"].toString()),
            );
          });
          _moveMap();
        } else if (data["type"] == "RIDER_LOCATION") {
          setState(() {
            riderLocation = LatLng(
              double.parse(data["lat"].toString()),
              double.parse(data["lng"].toString()),
            );
          });
          _moveMap();
        } else if (data["type"] == "CHAT_MESSAGE") {
          setState(() => messages.add(data));
        } else if (data["type"] == "REQUEST_UPDATE") {
          debugPrint("🔄 [Roadie] Received REQUEST_UPDATE: $data");
          // Update request data if provided
          if (data["request"] != null) {
            setState(() => currentRequest = data["request"]);
          }
          
          final status = data["request"]?["status"] ?? data["status"];
          final cancelledBy = data["request"]?["cancelled_by"] ?? data["cancelled_by"] ?? "Someone";
          
          if (status == "STARTED") {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text("Assist has started")),
            );
          }
          if (status == "COMPLETED") {
            if (!mounted) return;
            Navigator.pushReplacement(
              context,
              PageRouteBuilder(
                pageBuilder: (context, animation, secondaryAnimation) =>
                    RatingScreen(
                      request: currentRequest,
                    ),
                transitionsBuilder:
                    (context, animation, secondaryAnimation, child) {
                  return FadeTransition(opacity: animation, child: child);
                },
                transitionDuration: const Duration(milliseconds: 600),
              ),
            );
          }
          if (status == "CANCELLED") {
            debugPrint("❌ [Roadie] Received CANCELLATION: $data");
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text("$cancelledBy cancelled the request"),
                backgroundColor: Colors.red,
              ),
            );
            
            // Simply pop back to previous screen without reloading
            Future.delayed(const Duration(milliseconds: 1500), () {
              if (mounted && Navigator.canPop(context)) {
                Navigator.pop(context);
              }
            });
          }
        }
      });
      if (mounted) {
        setState(() => _isConnected = true);
        ws.send({"type": "JOIN_REQUEST", "request_id": currentRequest["id"]});
      }
    } catch (e) {
      debugPrint("WebSocket connection error: $e");
    }
  }

  void startSendingLocation() {
    locationTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      try {
        Position position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );
        ws.sendLocation(lat: position.latitude, lng: position.longitude);
        if (mounted) {
          setState(() {
            roadieLocation = LatLng(position.latitude, position.longitude);
          });
        }
      } catch (e) {
        debugPrint("Roadie location update error: $e");
      }
    });
  }

  void sendChat() {
    if (chatController.text.isEmpty) return;
    ws.send({
      "type": "CHAT",
      "request_id": currentRequest["id"],
      "text": chatController.text,
    });
    chatController.clear();
  }

  void _moveMap() {
    try {
      if (riderLocation.latitude != 0 && roadieLocation.latitude != 0) {
        final center = LatLng(
          (riderLocation.latitude + roadieLocation.latitude) / 2,
          (riderLocation.longitude + roadieLocation.longitude) / 2,
        );
        mapController.move(center, mapController.camera.zoom);
      }
    } catch (e) {
      // Map might not be ready yet
    }
  }

  void startAssist() async {
    await ApiService.post(
      "/requests/${currentRequest["id"]}/start/",
      {},
      requiresAuth: true,
    );
  }

  void completeAssist() async {
    await ApiService.post(
      "/requests/${currentRequest["id"]}/complete/",
      {},
      requiresAuth: true,
    );
  }

  void cancelRequest() async {
    // Get current roadie location
    final lat = roadieLocation.latitude;
    final lng = roadieLocation.longitude;

    if (!mounted) return;
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Cancel Request"),
        content: const Text("Are you sure you want to cancel this assist request?"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("No"),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              final result = await ApiService.post(
                "/requests/${currentRequest["id"]}/cancel/",
                {
                  "current_lat": lat,
                  "current_lng": lng,
                },
                requiresAuth: true,
              );

              if (!mounted) return;

              if (result != null && result is Map) {
                if (result.containsKey("detail")) {
                  String message = result["detail"] ?? "Request cancelled";
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(message)),
                  );
                  
                  // If cancellation was successful, pop back
                  if (message.contains("successfully")) {
                    Navigator.pop(context);
                  }
                }
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("Error cancelling request")),
                );
              }
            },
            child: const Text("Yes, Cancel"),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    locationTimer?.cancel();
    ws.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final center = LatLng(
      (riderLocation.latitude + roadieLocation.latitude) / 2,
      (riderLocation.longitude + roadieLocation.longitude) / 2,
    );
    final counterpart = widget.request["rider"];

    String name = "Assist in Progress";
    if (counterpart is Map) {
      name =
          "${counterpart["first_name"] ?? ""} ${counterpart["last_name"] ?? ""}"
              .trim();
    }
    if (name.isEmpty) {
      name = widget.request["rider_name"] ?? "Rider";
    }

    return WillPopScope(
      onWillPop: () async {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Finish or cancel the ride first.")),
        );
        return false;
      },
      child: Scaffold(
        key: _scaffoldKey,
        endDrawer: _buildChatDrawer(),
        body: Stack(
          children: [
            Column(
              children: [
                // Modern Header
                Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF10223D), Color(0xFF1D3B63)],
                    ),
                    borderRadius: BorderRadius.only(
                      bottomLeft: Radius.circular(24),
                      bottomRight: Radius.circular(24),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black26,
                        blurRadius: 10,
                        offset: Offset(0, 4),
                      ),
                    ],
                  ),
                  child: SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.assistant_navigation,
                                  color: Colors.white,
                                  size: 24,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      name,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 20,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    const Text(
                                      "Assisting Rider",
                                      style: TextStyle(
                                        color: Colors.white70,
                                        fontSize: 14,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Container(
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: IconButton(
                                  icon: const Icon(Icons.phone, color: Colors.white),
                                  onPressed: () async {
                                    String? phone = (counterpart is Map)
                                        ? counterpart["phone"]
                                        : widget.request["rider_phone"];
                                    if (phone == null || phone.isEmpty) return;
                                    final phoneUrl = 'tel:$phone';
                                    if (await canLaunchUrl(Uri.parse(phoneUrl))) {
                                      await launchUrl(Uri.parse(phoneUrl));
                                    }
                                  },
                                ),
                              ),
                            ],
                          ),
                          
                          // Status Indicator
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                    color: Colors.green,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  _isConnected ? "Connected" : "Connecting...",
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const Spacer(),
                                Text(
                                  "Service: ${widget.request["service_type_name"] ?? "Assist"}",
                                  style: const TextStyle(
                                    color: Color(0xFFFF8C00),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                
                // Map Section
                Expanded(
                  flex: 3,
                  child: Container(
                    margin: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.1),
                          blurRadius: 15,
                          offset: const Offset(0, 5),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: FlutterMap(
                        mapController: mapController,
                        options: MapOptions(initialCenter: center, initialZoom: 15),
                        children: [
                          TileLayer(
                            urlTemplate:
                                "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
                            subdomains: const ['a', 'b', 'c', 'd'],
                            retinaMode: RetinaMode.isHighDensity(context),
                            userAgentPackageName: 'com.vehix.roadie',
                          ),
                          MarkerLayer(
                            markers: [
                              // Rider Marker
                              Marker(
                                point: riderLocation,
                                width: 60,
                                height: 60,
                                child: Stack(
                                  alignment: Alignment.center,
                                  children: [
                                    Container(
                                      width: 60,
                                      height: 60,
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF10223D).withValues(alpha: 0.2),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF10223D),
                                        shape: BoxShape.circle,
                                        border: Border.all(color: Colors.white, width: 3),
                                        boxShadow: [
                                          BoxShadow(
                                            color: const Color(0xFF10223D).withValues(alpha: 0.3),
                                            blurRadius: 8,
                                            spreadRadius: 2,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              // Roadie Marker
                              Marker(
                                point: roadieLocation,
                                width: 60,
                                height: 60,
                                child: Stack(
                                  alignment: Alignment.center,
                                  children: [
                                    Container(
                                      width: 60,
                                      height: 60,
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFFF8C00).withValues(alpha: 0.2),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFFF8C00),
                                        shape: BoxShape.circle,
                                        border: Border.all(color: Colors.white, width: 3),
                                        boxShadow: [
                                          BoxShadow(
                                            color: const Color(0xFFFF8C00).withValues(alpha: 0.3),
                                            blurRadius: 8,
                                            spreadRadius: 2,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                
                // Bottom Section - Roadie Action Slider
                Expanded(
                  flex: 1,
                  child: Container(
                    margin: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.1),
                          blurRadius: 15,
                          offset: const Offset(0, 5),
                        ),
                      ],
                    ),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      child: _buildRoadieActionSlider(),
                    ),
                  ),
                ),
              ],
            ),
            
            // Floating Chat Button - Hide when chat is open
            ...(!_isChatOpen ? [
              Positioned(
                bottom: 100,
                right: 20,
                child: FloatingActionButton(
                  backgroundColor: const Color(0xFF10223D),
                  onPressed: () {
                    setState(() => _isChatOpen = true);
                    _scaffoldKey.currentState?.openEndDrawer();
                  },
                  child: Stack(
                    children: [
                      const Icon(Icons.chat, color: Colors.white),
                      if (messages.isNotEmpty)
                        Positioned(
                          right: 0,
                          top: 0,
                          child: Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: Colors.red,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ] : []),
            
            // Chat overlay that shows when drawer is open
            ...(_isChatOpen ? [
              Positioned.fill(
                child: GestureDetector(
                  onTap: () {
                    setState(() => _isChatOpen = false);
                    _scaffoldKey.currentState?.closeEndDrawer();
                  },
                  child: Container(
                    color: Colors.black.withValues(alpha: 0.5),
                  ),
                ),
              ),
            ] : []),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton(String text, IconData icon, Color color, VoidCallback onPressed) {
    return Container(
      height: 50,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onPressed,
          child: Center(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: Colors.white, size: 18),
                const SizedBox(width: 6),
                Text(
                  text,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRoadieActionSlider() {
    return Column(
      children: [
        Text(
          currentRequest["status"] == "STARTED" 
              ? "Slide to Complete Assist" 
              : "Slide to Start Assist",
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Color(0xFF10223D),
          ),
        ),
        const SizedBox(height: 12),
        Container(
          height: 50,
          decoration: BoxDecoration(
            color: Colors.grey.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(25),
          ),
          child: Stack(
            children: [
              Container(
                width: double.infinity,
                height: double.infinity,
                alignment: Alignment.center,
                child: Text(
                  currentRequest["status"] == "STARTED" 
                      ? "→ Complete →" 
                      : "→ Start →",
                  style: TextStyle(
                    color: Colors.grey.withValues(alpha: 0.6),
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Positioned.fill(
                child: SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    trackHeight: 50,
                    thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 20),
                    overlayShape: const RoundSliderOverlayShape(overlayRadius: 25),
                    activeTrackColor: Colors.transparent,
                    inactiveTrackColor: Colors.transparent,
                    thumbColor: currentRequest["status"] == "STARTED" 
                        ? const Color(0xFFFF8C00) 
                        : const Color(0xFF10223D),
                  ),
                  child: Slider(
                    value: 0,
                    min: 0,
                    max: 100,
                    onChanged: (value) {
                      if (value >= 95) {
                        if (currentRequest["status"] == "STARTED") {
                          completeAssist();
                        } else {
                          startAssist();
                        }
                      }
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
        // Only show cancel button if assist hasn't started
        if (currentRequest["status"] != "STARTED") ...[
          const SizedBox(height: 8),
          TextButton(
            onPressed: cancelRequest,
            child: const Text(
              "Cancel Request",
              style: TextStyle(
                color: Colors.red,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildChatDrawer() {
    return Drawer(
      width: MediaQuery.of(context).size.width,
      child: Container(
        color: Colors.white,
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                color: Color(0xFF10223D),
              ),
              child: SafeArea(
                bottom: false,
                child: Row(
                  children: [
                    const Icon(Icons.chat, color: Colors.white),
                    const SizedBox(width: 8),
                    const Text(
                      "Chat",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed: () {
                        setState(() => _isChatOpen = false);
                        Navigator.pop(context);
                      },
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: Column(
                children: [
                  Expanded(
                    child: ListView.builder(
                      reverse: true,
                      padding: const EdgeInsets.all(8),
                      itemCount: messages.length,
                      itemBuilder: (context, index) {
                        final msg = messages[messages.length - 1 - index];
                        final isMe = msg["sender_role"] == "RODIE";
                        return Align(
                          alignment: isMe
                              ? Alignment.centerRight
                              : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.symmetric(
                              vertical: 4,
                              horizontal: 8,
                            ),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 10,
                            ),
                            decoration: BoxDecoration(
                              color: isMe
                                  ? const Color(0xFFFF8C00)
                                  : const Color(0xFF10223D),
                              borderRadius: BorderRadius.only(
                                topLeft: const Radius.circular(20),
                                topRight: const Radius.circular(20),
                                bottomLeft: isMe
                                    ? const Radius.circular(20)
                                    : const Radius.circular(4),
                                bottomRight: isMe
                                    ? const Radius.circular(4)
                                    : const Radius.circular(20),
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.1),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            child: Text(
                              msg["text"] ?? "",
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  // Message Input with safe area
                  Container(
                    padding: EdgeInsets.only(
                      left: 16,
                      right: 16,
                      top: 16,
                      bottom: 16 + MediaQuery.of(context).padding.bottom,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.grey.withValues(alpha: 0.05),
                      border: Border(
                        top: BorderSide(
                          color: Colors.grey.withValues(alpha: 0.2),
                        ),
                      ),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(25),
                              border: Border.all(
                                color: Colors.grey.withValues(alpha: 0.3),
                              ),
                            ),
                            child: TextField(
                              controller: chatController,
                              decoration: const InputDecoration(
                                hintText: "Type a message...",
                                border: InputBorder.none,
                                contentPadding: EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 12,
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          decoration: const BoxDecoration(
                            color: Color(0xFFFF8C00),
                            shape: BoxShape.circle,
                          ),
                          child: IconButton(
                            icon: const Icon(Icons.send, color: Colors.white),
                            onPressed: sendChat,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
