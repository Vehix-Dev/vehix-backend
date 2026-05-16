import 'package:flutter/material.dart';
import '../services/wake_lock_service.dart';

/// Wake Lock Settings Screen
/// 
/// Allows users to control the wake lock behavior
/// Professional UI designed for production use
class WakeLockSettingsScreen extends StatefulWidget {
  const WakeLockSettingsScreen({super.key});

  @override
  State<WakeLockSettingsScreen> createState() => _WakeLockSettingsScreenState();
}

class _WakeLockSettingsScreenState extends State<WakeLockSettingsScreen> {
  final WakeLockService _wakeLockService = WakeLockService();
  bool _isEnabled = false;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    setState(() => _isLoading = true);
    _isEnabled = _wakeLockService.isEnabled;
    setState(() => _isLoading = false);
  }

  Future<void> _toggleWakeLock(bool value) async {
    setState(() => _isLoading = true);
    
    try {
      await _wakeLockService.setEnabled(value);
      setState(() => _isEnabled = value);
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            value 
              ? 'Screen will stay awake during active services' 
              : 'Screen may turn off automatically'
          ),
          backgroundColor: value ? Colors.green : Colors.orange,
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to update setting: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'Display Settings',
          style: TextStyle(
            color: Color(0xFF10223D),
            fontWeight: FontWeight.bold,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF10223D)),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Main Setting Card
                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF10223D).withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Icon(
                                  Icons.screen_lock_portrait,
                                  color: Color(0xFF10223D),
                                  size: 24,
                                ),
                              ),
                              const SizedBox(width: 12),
                              const Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Keep Screen Awake',
                                      style: TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.bold,
                                        color: Color(0xFF10223D),
                                      ),
                                    ),
                                    SizedBox(height: 4),
                                    Text(
                                      'Prevent screen from turning off during active services',
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: Colors.grey,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Switch(
                                value: _isEnabled,
                                onChanged: _toggleWakeLock,
                                activeTrackColor: const Color(0xFFFF8C00),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Information Card
                  Card(
                    elevation: 1,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'How it works',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: Color(0xFF10223D),
                            ),
                          ),
                          const SizedBox(height: 12),
                          _buildInfoItem(
                            icon: Icons.check_circle,
                            title: 'During Active Services',
                            description: 'Screen stays on while you\'re providing or receiving assistance',
                            color: Colors.green,
                          ),
                          const SizedBox(height: 8),
                          _buildInfoItem(
                            icon: Icons.mobile_off,
                            title: 'When App is Backgrounded',
                            description: 'Screen can turn off when you switch to other apps',
                            color: Colors.orange,
                          ),
                          const SizedBox(height: 8),
                          _buildInfoItem(
                            icon: Icons.battery_charging_full,
                            title: 'Battery Smart',
                            description: 'Respects system battery settings and low battery mode',
                            color: Colors.blue,
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Status Card
                  Card(
                    elevation: 1,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Row(
                        children: [
                          Icon(
                            _isEnabled 
                              ? Icons.screen_lock_portrait 
                              : Icons.screen_lock_portrait_outlined,
                            color: _isEnabled 
                              ? Colors.green 
                              : Colors.grey,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _isEnabled 
                              ? 'Screen wake lock is currently active'
                              : 'Screen wake lock is inactive',
                            style: TextStyle(
                              color: _isEnabled 
                                ? Colors.green 
                                : Colors.grey,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 24),
                  
                  // Warning Note
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.orange.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.info_outline,
                          color: Colors.orange,
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text(
                            'Note: Keeping the screen awake may use more battery power. This feature only activates during active services to minimize battery impact.',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.orange,
                              height: 1.4,
                            ),
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

  Widget _buildInfoItem({
    required IconData icon,
    required String title,
    required String description,
    required Color color,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF10223D),
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                description,
                style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 12,
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

