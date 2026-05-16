import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'requesting_screen.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';
import '../widgets/app_drawer.dart';

class ServiceDetailScreen extends StatefulWidget {
  final int serviceId;
  final String serviceName;
  final String description;
  final LatLng? currentLocation;
  final WebSocketService ws; // Add WebSocketService parameter

  const ServiceDetailScreen({
    super.key,
    required this.serviceId,
    required this.serviceName,
    required this.description,
    this.currentLocation,
    required this.ws,
  });

  @override
  State<ServiceDetailScreen> createState() => _ServiceDetailScreenState();
}

class _ServiceDetailScreenState extends State<ServiceDetailScreen> {
  final TextEditingController notesController = TextEditingController();
  bool _isRequesting = false;

  @override
  void dispose() {
    notesController.dispose();
    super.dispose();
  }

  Future<void> _requestService() async {
    setState(() => _isRequesting = true);

    try {
      // Get location - try passed location first, then fetch fresh
      LatLng? location = widget.currentLocation;
      
      if (location == null) {
        debugPrint("📍 [Rider] No cached location, fetching fresh...");
        try {
          final position = await Geolocator.getCurrentPosition(
            desiredAccuracy: LocationAccuracy.medium,
            timeLimit: const Duration(seconds: 15),
          );

          location = LatLng(position.latitude, position.longitude);
          debugPrint("✅ [Rider] Fresh location fetched: (${location.latitude.toStringAsFixed(4)}, ${location.longitude.toStringAsFixed(4)})");
        } catch (e) {
          debugPrint("⚠️ [Rider] Fresh location fetch failed: $e");
          // Try last known position
          try {
            final position = await Geolocator.getLastKnownPosition();
            if (position != null) {
              location = LatLng(position.latitude, position.longitude);
              debugPrint("✅ [Rider] Using last known location: (${location.latitude.toStringAsFixed(4)}, ${location.longitude.toStringAsFixed(4)})");
            }
          } catch (_) {}
        }
      }

      if (location == null) {
        debugPrint("❌ [Rider] Unable to get location");
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Unable to get your location. Please enable GPS and try again."),
              backgroundColor: Colors.red,
            ),
          );
        }
        setState(() => _isRequesting = false);
        return;
      }

      debugPrint("📝 [Rider] Creating request for service ID: ${widget.serviceId}");
      debugPrint("📍 [Rider] Location: (${location.latitude.toStringAsFixed(4)}, ${location.longitude.toStringAsFixed(4)})");
      
      final response = await ApiService.createRequest(
        serviceTypeId: widget.serviceId,
        riderLat: location.latitude,
        riderLng: location.longitude,
        notes: notesController.text.trim(),
      );

      debugPrint("📡 [Rider] Response received: $response");

      if (response == null ||
          (response is Map && response.containsKey('error'))) {
        debugPrint("❌ [Rider] Request creation failed: ${response is Map ? response['error'] : 'Unknown error'}");
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                (response is Map)
                    ? (response['error'] ?? response['detail'] ?? response['non_field_errors'] ?? 'Failed to create request')
                    : 'Failed to create request',
              ),
              backgroundColor: Colors.red,
            ),
          );
        }
        setState(() => _isRequesting = false);
        return;
      }

      debugPrint("✅ [Rider] Request created successfully with ID: ${response['id']}");
      
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => RequestingScreen(
              request: {
                "id": response['id'],
                "service_type": widget.serviceId,
                "service_type_name": widget.serviceName,
                "status": response['status'] ?? 'pending',
                "notes": notesController.text.trim(),
              },
              ws: widget.ws, // Pass WebSocket service
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Error: ${e.toString()}"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isRequesting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFF10223D),
        foregroundColor: Colors.white,
        title: Text(widget.serviceName),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      drawer: const AppDrawer(),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Service Name
              Hero(
                tag: 'service_${widget.serviceId}',
                child: Material(
                  color: Colors.transparent,
                  child: Text(
                    widget.serviceName,
                    style: const TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF10223D),
                      letterSpacing: -0.5,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Description
              Text(
                widget.description,
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.black54,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 24),

              // Location Info
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF10223D).withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(15),
                  border: Border.all(
                    color: const Color(0xFF10223D).withValues(alpha: 0.1),
                  ),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.location_on,
                      color: Color(0xFF10223D),
                      size: 28,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        widget.currentLocation != null
                            ? "📍 Current Location Found\nLat: ${widget.currentLocation!.latitude.toStringAsFixed(4)}, Lng: ${widget.currentLocation!.longitude.toStringAsFixed(4)}"
                            : "📍 Location not available",
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Notes Input
              const Text(
                "Additional Notes (Optional)",
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF10223D),
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: notesController,
                minLines: 3,
                maxLines: 5,
                decoration: InputDecoration(
                  hintText: "Describe your issue or add special requests...",
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(15),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(15),
                    borderSide: const BorderSide(
                      color: Color(0xFFFF8C00),
                      width: 2,
                    ),
                  ),
                  contentPadding: const EdgeInsets.all(15),
                ),
              ),
              const SizedBox(height: 32),

              // Request Now Button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isRequesting ? null : _requestService,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    backgroundColor: const Color(0xFFFF8C00),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                    elevation: 5,
                    shadowColor: const Color(0xFFFF8C00).withValues(alpha: 0.4),
                  ),
                  child: _isRequesting
                      ? const SizedBox(
                          height: 24,
                          width: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              Colors.white,
                            ),
                          ),
                        )
                      : const Text(
                          "Request Now",
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

