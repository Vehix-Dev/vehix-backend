import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class ServicesSelectionScreen extends StatefulWidget {
  final String role;
  final bool isOnboarding;
  const ServicesSelectionScreen({required this.role, this.isOnboarding = false, super.key});

  @override
  State<ServicesSelectionScreen> createState() =>
      _ServicesSelectionScreenState();
}

class _ServicesSelectionScreenState extends State<ServicesSelectionScreen> {
  List<dynamic> availableServices = [];
  Set<int> selectedServiceIds = {};
  bool isLoading = true;
  bool isSaving = false;

  Widget _buildServiceImage(Map<String, dynamic> service, {bool isSelected = false}) {
    final String? imageUrl = service['image'];
    final String serviceName = service['name']?.toString().toLowerCase() ?? '';
    
    // If image URL is available, try to load it
    if (imageUrl != null && imageUrl.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.network(
          imageUrl,
          width: 44,
          height: 44,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) {
            // Fallback to icon if image fails to load
            return _buildServiceIcon(serviceName, isSelected: isSelected);
          },
          loadingBuilder: (context, child, loadingProgress) {
            if (loadingProgress == null) return child;
            return Center(
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(
                  isSelected ? Colors.white70 : const Color(0xFFFF8C00).withValues(alpha: 0.5),
                ),
              ),
            );
          },
        ),
      );
    }
    
    // Fallback to icon based on service name
    return _buildServiceIcon(serviceName, isSelected: isSelected);
  }

  Widget _buildServiceIcon(String serviceName, {bool isSelected = false}) {
    IconData iconData;
    
    if (serviceName.contains('towing')) {
      iconData = Icons.local_shipping;
    } else if (serviceName.contains('battery') || serviceName.contains('jump')) {
      iconData = Icons.battery_charging_full;
    } else if (serviceName.contains('tire')) {
      iconData = Icons.tire_repair;
    } else if (serviceName.contains('fuel')) {
      iconData = Icons.local_gas_station;
    } else if (serviceName.contains('mechanic')) {
      iconData = Icons.build;
    } else if (serviceName.contains('locksmith')) {
      iconData = Icons.vpn_key;
    } else {
      iconData = Icons.handyman;
    }
    
    return Icon(
      iconData,
      size: 24,
      color: isSelected ? Colors.white : Colors.white70,
    );
  }

  @override
  void initState() {
    super.initState();
    _loadServices();
  }

  Future<void> _loadServices() async {
    try {
      // Load available services
      final services = await ApiService.getServices();
      debugPrint("🔍 Available services loaded: ${services.length} services");
      
      // Load user's currently selected services
      final userServices = await ApiService.getRodieServices();
      Set<int> currentlySelected = {};
      
      debugPrint("🔍 User services: $userServices");
      
      for (var service in userServices) {
        // Handle different API response formats
        int? serviceId;
        
        // Try different possible field structures
        if (service['service_id'] != null) {
          serviceId = service['service_id'] as int;
        } else if (service['service'] != null && service['service'] is Map) {
          // Nested service object
          serviceId = service['service']['id'] as int?;
        } else if (service['id'] != null) {
          // Direct id field (might be the RodieService record id, need to check)
          serviceId = service['id'] as int?;
        }
        
        if (serviceId != null) {
          currentlySelected.add(serviceId);
          debugPrint("✅ Added service ID: $serviceId");
        }
      }
      
      if (mounted) {
        setState(() {
          availableServices = services;
          selectedServiceIds = currentlySelected;
          isLoading = false;
        });
        debugPrint("✅ Services loaded: ${selectedServiceIds.length} selected");
      }
    } catch (e) {
      debugPrint("❌ Failed to load services: $e");
      if (mounted) {
        setState(() => isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Failed to load services: $e")),
        );
      }
    }
  }

  Future<void> _saveServices() async {
    if (selectedServiceIds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please select at least one service")),
      );
      return;
    }

    setState(() => isSaving = true);
    try {
      // Use the dedicated API method for saving services
      final response = await ApiService.saveRodieServices(selectedServiceIds.toList());

      if (response != null && mounted) {
        debugPrint("✅ Services saved successfully: $response");
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Services saved successfully!")),
        );
        
        // Navigate based on mode
        if (widget.isOnboarding) {
          // Onboarding mode - go to home
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => HomeScreen(role: widget.role),
            ),
          );
        } else {
          // Manage mode - just pop back with success flag
          Navigator.pop(context, true);
        }
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Failed to save services")),
        );
      }
    } catch (e) {
      debugPrint("❌ Error saving services: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Error saving services: $e")),
        );
      }
    } finally {
      if (mounted) setState(() => isSaving = false);
    }
  }


  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !widget.isOnboarding,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && widget.isOnboarding) {
          // Exit the app during onboarding
          SystemNavigator.pop();
        }
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF10223D),
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () {
              if (widget.isOnboarding) {
                // Exit app during onboarding
                SystemNavigator.pop();
              } else {
                // Normal back in manage mode
                Navigator.pop(context);
              }
            },
          ),
          title: Text(widget.isOnboarding ? "Select Service(s)" : "Manage Services"),
          backgroundColor: const Color(0xFF10223D),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF10223D), Color(0xFF1D3B63)],
          ),
        ),
        child: isLoading
            ? const Center(
                child: CircularProgressIndicator(color: Colors.white),
              )
            : SafeArea(
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              "Select Service(s)",
                              style: TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 24),
                            Text(
                              "${selectedServiceIds.length} selected",
                              style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFFFF8C00),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Services List
                      ListView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: availableServices.length,
                        itemBuilder: (context, index) {
                          final service = availableServices[index];
                          final serviceId = service['id'] as int;
                          final isSelected = selectedServiceIds.contains(serviceId);

                          return GestureDetector(
                            onTap: () {
                              setState(() {
                                if (isSelected) {
                                  selectedServiceIds.remove(serviceId);
                                } else {
                                  selectedServiceIds.add(serviceId);
                                }
                              });
                            },
                            child: Container(
                              margin: const EdgeInsets.only(bottom: 12),
                              decoration: BoxDecoration(
                                color: isSelected ? const Color(0xFFFF8C00).withValues(alpha: 0.1) : Colors.white.withValues(alpha: 0.1),
                                border: Border.all(
                                  color: isSelected ? const Color(0xFFFF8C00) : Colors.white.withValues(alpha: 0.3),
                                ),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: ListTile(
                                contentPadding: const EdgeInsets.all(16),
                                leading: Container(
                                  width: 50,
                                  height: 50,
                                  decoration: BoxDecoration(
                                    color: isSelected ? const Color(0xFFFF8C00) : Colors.white.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                      color: isSelected ? const Color(0xFFFF8C00) : Colors.white.withValues(alpha: 0.1),
                                      width: 1,
                                    ),
                                  ),
                                  child: _buildServiceImage(service as Map<String, dynamic>, isSelected: isSelected),
                                ),
                                title: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      service['name'] ?? 'Service',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 16,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    if (service['fixed_price'] != null)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 4),
                                        child: Text(
                                          "UGX ${service['fixed_price']}",
                                          style: const TextStyle(
                                            color: Color(0xFFFF8C00),
                                            fontSize: 12,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                trailing: Checkbox(
                                  value: isSelected,
                                  onChanged: (bool? value) {
                                    setState(() {
                                      if (value == true) {
                                        selectedServiceIds.add(service['id']);
                                      } else {
                                        selectedServiceIds.remove(service['id']);
                                      }
                                    });
                                  },
                                  activeColor: const Color(0xFFFF8C00),
                                  checkColor: Colors.white,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                      // Bottom Button Section with extra padding
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10223D),
                          border: Border(
                            top: BorderSide(
                              color: Colors.white.withValues(alpha: 0.1),
                            ),
                          ),
                        ),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: isSaving || selectedServiceIds.isEmpty
                                    ? null
                                    : _saveServices,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFFFF8C00),
                                  disabledBackgroundColor: const Color(0xFFFF8C00).withValues(alpha: 0.5),
                                  padding: const EdgeInsets.symmetric(vertical: 16),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                child: isSaving
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                        ),
                                      )
                                    : const Text(
                                        "Save",
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                              ),
                            ),
                            const SizedBox(height: 16),
                            // Skip button - only show during onboarding
                            if (widget.isOnboarding)
                              SizedBox(
                                width: double.infinity,
                                height: 48,
                                child: TextButton(
                                  onPressed: () {
                                    Navigator.pushReplacement(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => HomeScreen(role: widget.role),
                                      ),
                                    );
                                  },
                                  style: TextButton.styleFrom(
                                    foregroundColor: Colors.white70,
                                    padding: const EdgeInsets.symmetric(vertical: 12),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(8),
                                      side: BorderSide(color: Colors.white.withValues(alpha: 0.3)),
                                    ),
                                  ),
                                  child: const Text(
                                    "Skip for now",
                                    style: TextStyle(
                                      color: Colors.white70,
                                      fontSize: 16,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),
                              ),
                            // Extra bottom padding to ensure scrollability
                            const SizedBox(height: 20),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
      ),
      ),
    );
  }
}
