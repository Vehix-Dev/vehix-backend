import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:io';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import 'services_selection_screen.dart';

class IDVerificationScreen extends StatefulWidget {
  final String role;
  const IDVerificationScreen({required this.role, super.key});

  @override
  State<IDVerificationScreen> createState() => _IDVerificationScreenState();
}

class _IDVerificationScreenState extends State<IDVerificationScreen> {
  final ImagePicker _picker = ImagePicker();
  
  File? _profileImage;
  File? _ninFrontImage;
  File? _ninBackImage;
  
  bool isLoading = false;

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          // Exit the app instead of going back to login
          SystemNavigator.pop();
        }
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF10223D),
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          title: const Text(
            'Identity Verification',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          iconTheme: const IconThemeData(color: Colors.white),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 16),
                const Text(
                  'Please upload your documents to complete verification',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 16,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 32),
                _buildImageUploadSection(
                  title: 'Profile Photo',
                  subtitle: 'Take a clear photo of your face',
                  image: _profileImage,
                  onTap: _pickProfileImage,
                  icon: Icons.person,
                ),
                const SizedBox(height: 20),
                _buildImageUploadSection(
                  title: 'NIN Front',
                  subtitle: 'Upload front side of your National ID',
                  image: _ninFrontImage,
                  onTap: _pickNINFront,
                  icon: Icons.badge,
                ),
                const SizedBox(height: 20),
                _buildImageUploadSection(
                  title: 'NIN Back',
                  subtitle: 'Upload back side of your National ID',
                  image: _ninBackImage,
                  onTap: _pickNINBack,
                  icon: Icons.badge_outlined,
                ),
                const SizedBox(height: 32),
                ElevatedButton(
                  onPressed: isLoading ? null : _submitVerification,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFF8C00),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: isLoading
                      ? const SizedBox(
                          height: 24,
                          width: 24,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : const Text(
                          'Submit Verification',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: TextButton(
                    onPressed: isLoading ? null : _skipForNow,
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.white70,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: BorderSide(color: Colors.white.withValues(alpha: 0.3)),
                      ),
                    ),
                    child: const Text(
                      'Skip for now',
                      style: TextStyle(
                        color: Colors.white70,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildImageUploadSection({
    required String title,
    required String subtitle,
    required File? image,
    required VoidCallback onTap,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1D3B63),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: image != null ? Colors.green : Colors.white.withAlpha(51),
          width: 2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                image != null ? Icons.check_circle : icon,
                color: image != null ? Colors.green : Colors.white70,
                size: 24,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              if (image != null)
                const Icon(
                  Icons.check_circle,
                  color: Colors.green,
                  size: 20,
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (image != null)
            Container(
              width: double.infinity,
              height: 150,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                image: DecorationImage(
                  image: FileImage(image),
                  fit: BoxFit.cover,
                ),
              ),
            )
          else
            GestureDetector(
              onTap: onTap,
              child: Container(
                width: double.infinity,
                height: 120,
                decoration: BoxDecoration(
                  color: Colors.white.withAlpha(26),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: Colors.white.withAlpha(77),
                    style: BorderStyle.solid,
                  ),
                ),
                child: const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.camera_alt_outlined,
                      color: Colors.white70,
                      size: 32,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Tap to upload',
                      style: TextStyle(
                        color: Colors.white70,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  bool _canSubmit() {
    return _profileImage != null &&
           _ninFrontImage != null &&
           _ninBackImage != null &&
           !isLoading;
  }

  Future<void> _pickProfileImage() async {
    await _showImagePickerDialog((source) async {
      final XFile? image = await _picker.pickImage(
        source: source,
        imageQuality: 80,
        maxWidth: 800,
        maxHeight: 800,
      );
      
      if (image != null) {
        setState(() {
          _profileImage = File(image.path);
        });
      }
    });
  }

  Future<void> _pickNINFront() async {
    await _showImagePickerDialog((source) async {
      final XFile? image = await _picker.pickImage(
        source: source,
        imageQuality: 80,
        maxWidth: 1200,
        maxHeight: 800,
      );
      
      if (image != null) {
        setState(() {
          _ninFrontImage = File(image.path);
        });
      }
    });
  }

  Future<void> _pickNINBack() async {
    await _showImagePickerDialog((source) async {
      final XFile? image = await _picker.pickImage(
        source: source,
        imageQuality: 80,
        maxWidth: 1200,
        maxHeight: 800,
      );
      
      if (image != null) {
        setState(() {
          _ninBackImage = File(image.path);
        });
      }
    });
  }

  Future<void> _showImagePickerDialog(Function(ImageSource) onPick) async {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1D3B63),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Choose Image Source',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _buildImageSourceOption(
                  icon: Icons.camera_alt,
                  label: 'Camera',
                  onTap: () {
                    Navigator.pop(context);
                    onPick(ImageSource.camera);
                  },
                ),
                _buildImageSourceOption(
                  icon: Icons.photo_library,
                  label: 'Gallery',
                  onTap: () {
                    Navigator.pop(context);
                    onPick(ImageSource.gallery);
                  },
                ),
              ],
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildImageSourceOption({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withAlpha(26),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(
              icon,
              color: Colors.white,
              size: 32,
            ),
            const SizedBox(height: 8),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitVerification() async {
    if (!_canSubmit()) return;

    setState(() => isLoading = true);

    try {
      // Upload profile photo
      if (_profileImage != null) {
        await ApiService.uploadUserImage(_profileImage!, 'PROFILE');
      }

      // Upload NIN front
      if (_ninFrontImage != null) {
        await ApiService.uploadUserImage(_ninFrontImage!, 'NIN_FRONT');
      }

      // Upload NIN back
      if (_ninBackImage != null) {
        await ApiService.uploadUserImage(_ninBackImage!, 'NIN_BACK');
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Documents uploaded successfully! Your documents will be reviewed by administrators.',
            ),
            backgroundColor: Colors.green,
          ),
        );
        
        // Navigate to services selection screen
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => ServicesSelectionScreen(role: widget.role, isOnboarding: true),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error uploading documents: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() => isLoading = false);
    }
  }

  void _skipForNow() async {
    // Mark ID verification as skipped so user isn't prompted again
    try {
      await ApiService.post("/me/", {"id_verification_skipped": true}, requiresAuth: true);
    } catch (e) {
      // Continue even if API call fails
      print("Failed to mark ID verification as skipped: $e");
    }
    
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ServicesSelectionScreen(role: widget.role, isOnboarding: true),
      ),
    );
  }
}
