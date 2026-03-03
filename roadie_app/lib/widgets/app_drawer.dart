import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../screens/login_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/referrals_screen.dart';
import '../screens/help_screen.dart';
import '../screens/wallet_screen.dart';
import '../screens/history_screen.dart';

class AppDrawer extends StatefulWidget {
  const AppDrawer({super.key});

  @override
  State<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends State<AppDrawer> {
  Map<String, dynamic>? userData;

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  Future<void> _loadUserData() async {
    final data = await ApiService.fetchUserInfo();
    if (mounted) setState(() => userData = data);
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
      child: Column(
        children: [
          UserAccountsDrawerHeader(
            decoration: const BoxDecoration(color: Color(0xFF10223D)),
            accountName: Text(displayName),
            accountEmail: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (email.isNotEmpty) Text(email),
                if (phone.isNotEmpty) Text(phone),
              ],
            ),
            currentAccountPicture: CircleAvatar(
              backgroundColor: Colors.white,
              backgroundImage: const AssetImage('assets/logo.jpeg'),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.person, color: Color(0xFF10223D)),
            title: const Text('Profile'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ProfileScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet),
            title: const Text('Wallet'),
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
            title: const Text('History'),
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
                MaterialPageRoute(builder: (_) => const ReferralsScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.help),
            title: const Text('Help'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const HelpScreen()),
              );
            },
          ),
          const Spacer(),
          ListTile(
            leading: const Icon(Icons.exit_to_app),
            title: const Text('Logout'),
            onTap: () async {
              final navigator = Navigator.of(context);
              navigator.pop();
              await ApiService.logout();
              if (!mounted) return;
              navigator.pushReplacement(
                MaterialPageRoute(
                  builder: (_) => const LoginScreen(role: "RODIE"),
                ),
              );
            },
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              'Version 1.0.0+2',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ),
        ],
      ),
    );
  }
}
