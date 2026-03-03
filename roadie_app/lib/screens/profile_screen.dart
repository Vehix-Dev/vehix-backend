import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  Map<String, dynamic>? user;
  bool _isLoading = true;
  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _loadUser();
  }

  Future<void> _loadUser() async {
    setState(() => _isLoading = true);
    final data = await ApiService.fetchUserInfo();
    if (mounted) {
      setState(() {
        user = data;
        _isLoading = false;
      });
    }
  }

  Future<void> _uploadImage(String type) async {
    final XFile? image = await _picker.pickImage(source: ImageSource.gallery);
    if (image == null) return;

    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text("Uploading $type...")));

    final response = await ApiService.uploadUserImage(File(image.path), type);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            response != null
                ? "Successfully uploaded $type"
                : "Failed to upload $type",
          ),
          backgroundColor: response != null ? Colors.green : Colors.red,
        ),
      );
      _loadUser(); // Refresh status
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Profile')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : user == null
          ? const Center(child: Text("Failed to load profile"))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: CircleAvatar(
                      radius: 50,
                      backgroundColor: Colors.blue.shade100,
                      child: const Icon(
                        Icons.person,
                        size: 50,
                        color: Colors.blue,
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _buildInfoSection("Personal Info", [
                    _buildInfoRow(Icons.person, "Username", user!['username']),
                    _buildInfoRow(Icons.email, "Email", user!['email']),
                    _buildInfoRow(Icons.phone, "Phone", user!['phone']),
                  ]),
                  const SizedBox(height: 24),
                  _buildInfoSection("Wallet", [
                    _buildInfoRow(
                      Icons.account_balance_wallet,
                      "Balance",
                      "UGX ${user!['wallet']?['balance'] ?? '0.00'}",
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: () {}, // Future: Wallet Screen
                            icon: const Icon(Icons.add),
                            label: const Text("Deposit"),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {}, // Future: Withdrawal
                            icon: const Icon(Icons.file_download),
                            label: const Text("Withdraw"),
                          ),
                        ),
                      ],
                    ),
                  ]),
                  const SizedBox(height: 24),
                  _buildInfoSection("KYC & Verification", [
                    _buildInfoRow(
                      Icons.verified_user,
                      "Status",
                      user!['is_approved'] == true
                          ? "Approved ✅"
                          : "Pending Approval ⏳",
                      color: user!['is_approved'] == true
                          ? Colors.green
                          : Colors.orange,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      "Upload Documents",
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: [
                        _buildUploadChip("NIN Front", "NIN_FRONT"),
                        _buildUploadChip("NIN Back", "NIN_BACK"),
                        _buildUploadChip("License", "LICENSE_FRONT"),
                      ],
                    ),
                  ]),
                  const SizedBox(height: 40),
                  Center(
                    child: TextButton.icon(
                      onPressed: () async {
                        final navigator = Navigator.of(context);
                        await ApiService.logout();
                        if (mounted) {
                          navigator.pushReplacementNamed('/login');
                        }
                      },
                      icon: const Icon(Icons.logout, color: Colors.red),
                      label: const Text(
                        "Logout",
                        style: TextStyle(color: Colors.red),
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildInfoSection(String title, List<Widget> children) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: Colors.blue,
          ),
        ),
        const Divider(),
        ...children,
      ],
    );
  }

  Widget _buildInfoRow(
    IconData icon,
    String label,
    String? value, {
    Color? color,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        children: [
          Icon(icon, size: 20, color: Colors.grey),
          const SizedBox(width: 12),
          Text("$label: ", style: const TextStyle(fontWeight: FontWeight.w500)),
          Expanded(
            child: Text(
              value ?? "N/A",
              style: TextStyle(
                color: color,
                fontWeight: color != null ? FontWeight.bold : null,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadChip(String label, String type) {
    return ActionChip(
      avatar: const Icon(Icons.upload_file, size: 16),
      label: Text(label),
      onPressed: () => _uploadImage(type),
    );
  }
}
