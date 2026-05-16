import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:roadie_app/services/api_service.dart';
import 'package:roadie_app/services/websocket_service.dart';
import 'package:roadie_app/screens/profile_screen.dart';
import 'package:roadie_app/screens/wallet_screen.dart';
import 'package:roadie_app/screens/history_screen.dart';
import 'package:roadie_app/screens/support_screen.dart';
import 'package:roadie_app/screens/services_selection_screen.dart';
import 'package:roadie_app/screens/referrals_screen.dart';

import 'package:roadie_app/screens/login_screen.dart';
import 'package:roadie_app/core/cache/cache_manager.dart';


class AppDrawer extends StatefulWidget {
  final Map<String, dynamic>? userData;
  final VoidCallback? onRefresh;
  
  const AppDrawer({super.key, this.userData, this.onRefresh});

  @override
  State<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends State<AppDrawer> {
  Map<String, dynamic>? userData;

  @override
  void initState() {
    super.initState();
    // Use the most reliable source immediately
    userData = widget.userData ?? CacheManager().getUserProfile();
    
    // Background refresh without triggering a "pop-in"
    _syncUserData();
  }

  Future<void> _syncUserData() async {
    final freshData = await ApiService.fetchUserInfo();
    if (freshData != null && mounted) {
      // Only trigger a UI update if the trial data has actually changed
      if (freshData['trial_days_left'] != userData?['trial_days_left'] ||
          freshData['trial_end_date'] != userData?['trial_end_date']) {
        setState(() => userData = freshData);
      } else {
        // Just update the reference quietly
        userData = freshData;
      }
      CacheManager().saveUserProfile(freshData);
    }
  }

  Widget? _buildFreeTrialSection() {
    final String? role = userData?['role'];
    final bool isApproved = userData?['is_approved'] == true;
    
    if (role != 'RODIE' && role != 'MECHANIC' || !isApproved) return null;

    final String? endDateStr = userData?['trial_end_date'];
    // If no trial_end_date set, no trial has been configured — hide this section
    if (endDateStr == null || endDateStr.isEmpty) return null;

    final int trialDays = userData?['trial_days_left'] ?? 0;
    final bool isExpired = trialDays <= 0;
    
    String dateFormatted = 'N/A';
    try {
      final date = DateTime.parse(endDateStr);
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      dateFormatted = '${date.day} ${months[date.month - 1]} ${date.year}';
    } catch (e) {
      dateFormatted = endDateStr.split('T')[0];
    }
    
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: (isExpired ? Colors.orange : Colors.green).withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: (isExpired ? Colors.orange : Colors.green).withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(
            isExpired ? Icons.warning_amber_rounded : Icons.timer_outlined, 
            color: isExpired ? Colors.orange[800] : Colors.green, 
            size: 20
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isExpired ? 'Free Trial Ended' : 'Trial: $trialDays days left',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: isExpired ? Colors.orange[900] : Colors.green,
                    fontSize: 14,
                  ),
                ),
                Text(
                  isExpired ? 'Charges now apply per job' : 'Commission-free until $dateFormatted',
                  style: TextStyle(
                    color: isExpired ? Colors.orange[800] : Colors.green,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    String displayName =
        userData?['first_name']?.toString().trim().isNotEmpty == true
        ? userData!['first_name']
        : (userData?['username'] ?? 'User');
    String email = userData?['email'] ?? '';
    String phone = userData?['phone'] ?? '';

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: const BoxDecoration(color: Color(0xFF10223D)),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                CircleAvatar(
                  radius: 35,
                  backgroundColor: Colors.white,
                  backgroundImage: (userData?['profile_photo'] != null && userData!['profile_photo'].toString().startsWith('http'))
                      ? NetworkImage(userData!['profile_photo'])
                      : null,
                  child: (userData?['profile_photo'] == null || !userData!['profile_photo'].toString().startsWith('http'))
                      ? const Icon(Icons.person, size: 35, color: Colors.grey)
                      : null,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        displayName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (email.isNotEmpty)
                        Text(
                          email,
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.8),
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      if (phone.isNotEmpty)
                        Text(
                          phone,
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.8),
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (_buildFreeTrialSection() != null) _buildFreeTrialSection()!,
          ListTile(
            leading: const Icon(Icons.person, color: Color(0xFF10223D)),
            title: const Text('My Profile'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ProfileScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.build, color: Color(0xFF10223D)),
            title: const Text('Manage Services'),
            onTap: () async {
              Navigator.pop(context);
              final result = await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => ServicesSelectionScreen(role: 'RODIE'),
                ),
              );
              
              if (result == true && widget.onRefresh != null) {
                widget.onRefresh!();
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet),
            title: const Text('My Wallet'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const WalletScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.history),
            title: const Text('Job History'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const HistoryScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.group),
            title: const Text('Referrals'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ReferralsScreen()),
              );
            },
          ),


          ListTile(
            leading: const Icon(Icons.support, color: Color(0xFF10223D)),
            title: const Text('Support'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SupportScreen()),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.privacy_tip, color: Color(0xFF10223D)),
            title: const Text('Privacy Policy'),
            onTap: () async {
              final url = Uri.parse('https://vehix.ug/privacy-policy/');
              if (await canLaunchUrl(url)) {
                await launchUrl(url, mode: LaunchMode.externalApplication);
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.description, color: Color(0xFF10223D)),
            title: const Text('Terms of Service'),
            onTap: () async {
              final url = Uri.parse('https://vehix.ug/terms-of-service/');
              if (await canLaunchUrl(url)) {
                await launchUrl(url, mode: LaunchMode.externalApplication);
              }
            },
          ),
          const SizedBox(height: 32),
          ListTile(
            leading: const Icon(Icons.exit_to_app),
            title: const Text('Logout'),
            onTap: () async {
              // Ensure roadie is offline before logging out
              try {
                await ApiService.updateRodieStatus(false);
              } catch (e) {
                debugPrint("Error going offline during logout: $e");
              }
              
              final ws = WebSocketService();
              ws.disconnect();
              final navigator = Navigator.of(context);
              navigator.pop();
              String? role = await ApiService.getRole();
              await ApiService.logout();
              if (!mounted) return;
              navigator.pushReplacement(
                MaterialPageRoute(
                  builder: (_) => LoginScreen(role: role ?? "RODIE"),
                ),
              );
            },
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              'Version 1.0',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ),
        ],
      ),
    );
  }
}

