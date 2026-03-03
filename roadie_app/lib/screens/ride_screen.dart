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
  Timer? locationTimer;
  final MapController mapController = MapController();

  @override
  void initState() {
    super.initState();
    _parseInitialLocations();
    connectWS();
    startSendingLocation();
  }

  void _parseInitialLocations() {
    try {
      if (widget.request["rider_lat"] != null) {
        double lat =
            double.tryParse(widget.request["rider_lat"].toString()) ?? 0.0;
        double lng =
            double.tryParse(widget.request["rider_lng"].toString()) ?? 0.0;
        if (lat != 0) riderLocation = LatLng(lat, lng);
      }
      if (widget.request["roadie_lat"] != null) {
        double lat =
            double.tryParse(widget.request["roadie_lat"].toString()) ?? 0.0;
        double lng =
            double.tryParse(widget.request["roadie_lng"].toString()) ?? 0.0;
        if (lat != 0) roadieLocation = LatLng(lat, lng);
      } else {
        roadieLocation = riderLocation;
      }
    } catch (e) {
      debugPrint("Error parsing initial locations: $e");
    }
  }

  void connectWS() async {
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
        if (data["status"] == "STARTED") {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text("Assist has started")));
        }
        if (data["status"] == "COMPLETED") {
          if (!mounted) return;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => RatingScreen(request: widget.request),
            ),
          );
        }
      }
    });
    ws.send({"type": "JOIN_REQUEST", "request_id": widget.request["id"]});
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
      "request_id": widget.request["id"],
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
      "/requests/${widget.request["id"]}/start/",
      {},
      requiresAuth: true,
    );
  }

  void completeAssist() async {
    await ApiService.post(
      "/requests/${widget.request["id"]}/complete/",
      {},
      requiresAuth: true,
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

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Finish or cancel the ride first.")),
        );
      },
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: const Color(0xFF10223D),
          foregroundColor: Colors.white,
          title: Text(name),
          actions: [
            IconButton(
              icon: const Icon(Icons.phone),
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
          ],
        ),
        body: Column(
          children: [
            Expanded(
              flex: 3,
              child: FlutterMap(
                mapController: mapController,
                options: MapOptions(initialCenter: center, initialZoom: 15),
                children: [
                  TileLayer(
                    urlTemplate:
                        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    userAgentPackageName: 'com.vehix.roadie',
                  ),
                  MarkerLayer(
                    markers: [
                      Marker(
                        point: riderLocation,
                        width: 40,
                        height: 40,
                        child: const Icon(
                          Icons.person_pin_circle,
                          size: 40,
                          color: Color(0xFF10223D),
                        ),
                      ),
                      Marker(
                        point: roadieLocation,
                        width: 40,
                        height: 40,
                        child: const Icon(
                          Icons.local_shipping,
                          size: 40,
                          color: Color(0xFFFF8C00),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(8.0),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        ElevatedButton(
                          onPressed: startAssist,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF10223D),
                            foregroundColor: Colors.white,
                          ),
                          child: const Text("Start Assist"),
                        ),
                        ElevatedButton(
                          onPressed: completeAssist,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFF8C00),
                            foregroundColor: Colors.white,
                          ),
                          child: const Text("Complete Assist"),
                        ),
                      ],
                    ),
                    const Divider(),
                    Expanded(
                      child: ListView.builder(
                        reverse: true,
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
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: isMe
                                    ? const Color(0xFFFF8C00)
                                    : const Color(0xFF10223D),
                                borderRadius: BorderRadius.circular(15),
                              ),
                              child: Text(
                                msg["text"] ?? "",
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: chatController,
                            decoration: InputDecoration(
                              hintText: "Type a message...",
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(20),
                              ),
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: 16,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        CircleAvatar(
                          backgroundColor: const Color(0xFFFF8C00),
                          child: IconButton(
                            icon: const Icon(
                              Icons.send,
                              color: Colors.white,
                              size: 20,
                            ),
                            onPressed: sendChat,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
