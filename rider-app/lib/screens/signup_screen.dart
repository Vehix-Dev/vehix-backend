import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'login_screen.dart';

class SignupScreen extends StatefulWidget {
  final String role;
  const SignupScreen({required this.role, super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  // Controllers
  final firstNameController = TextEditingController();
  final lastNameController = TextEditingController();
  final usernameController = TextEditingController();
  final emailController = TextEditingController();
  final phoneController = TextEditingController();
  final passwordController = TextEditingController();
  final ninController = TextEditingController();
  final referralCodeController = TextEditingController();

  // Form key for validation
  final _formKey = GlobalKey<FormState>();

  bool loading = false;
  bool obscurePassword = true;

  @override
  void dispose() {
    // Dispose controllers to prevent memory leaks
    firstNameController.dispose();
    lastNameController.dispose();
    usernameController.dispose();
    emailController.dispose();
    phoneController.dispose();
    passwordController.dispose();
    ninController.dispose();
    referralCodeController.dispose();
    super.dispose();
  }

  Future<void> signup() async {
    // Validate form
    if (!_formKey.currentState!.validate()) return;

    setState(() => loading = true);

    final payload = {
      "first_name": firstNameController.text.trim(),
      "last_name": lastNameController.text.trim(),
      "username": usernameController.text.trim(),
      "email": emailController.text.trim(),
      "phone": phoneController.text.trim(),
      "password": passwordController.text,
      "role": widget.role,
    };
    
    // Only add NIN if provided (optional for riders)
    if (ninController.text.trim().isNotEmpty) {
      payload["nin"] = ninController.text.trim();
    }
    
    // Only add referral code if provided (optional)
    if (referralCodeController.text.trim().isNotEmpty) {
      payload["referred_by_code"] = referralCodeController.text.trim();
    }

    // print removed

    try {
      final response = await ApiService.post(
        "/register/",
        payload,
        requiresAuth: false,
      );

      // print removed

      // Check if response has an error field
      if (response is Map && response.containsKey('error')) {
        throw Exception(response['error']);
      }

      // Check for success (adjust based on your API response structure)
      if (response["id"] != null ||
          response["user"] != null ||
          response["success"] == true) {
        _showSnackBar("Registration successful! Please log in.", isError: false);

        // Navigate to login screen after short delay
        Future.delayed(const Duration(seconds: 1), () {
          if (mounted) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => LoginScreen(role: widget.role)),
            );
          }
        });
      } else {
        // Show specific error from API if available
        String errorMsg =
            response["detail"] ??
            response["message"] ??
            response["error"] ??
            "Registration failed";
        _showSnackBar(errorMsg);
      }
    } catch (e) {
      // print removed
      _showSnackBar("Error: ${e.toString().replaceAll('Exception:', '')}");
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _showSnackBar(String message, {bool isError = true}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(10),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF10223D),
        title: Text("${widget.role} Signup"),
        centerTitle: true,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF10223D)),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 20),

                // First Name
                _buildInputField(
                  controller: firstNameController,
                  label: "First Name",
                  icon: Icons.person_outline,
                ),
                const SizedBox(height: 15),

                // Last Name
                _buildInputField(
                  controller: lastNameController,
                  label: "Last Name",
                  icon: Icons.person_outline,
                ),
                const SizedBox(height: 15),

                // Username
                _buildInputField(
                  controller: usernameController,
                  label: "Username",
                  icon: Icons.badge_outlined,
                ),
                const SizedBox(height: 15),

                // Email
                _buildInputField(
                  controller: emailController,
                  label: "Email",
                  icon: Icons.email_outlined,
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 15),

                // Phone
                _buildInputField(
                  controller: phoneController,
                  label: "Phone",
                  icon: Icons.phone_outlined,
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 15),

                // Password
                _buildInputField(
                  controller: passwordController,
                  label: "Password",
                  icon: Icons.lock_outline,
                  isPassword: true,
                ),
                const SizedBox(height: 15),

                // NIN (Optional for Riders)
                _buildInputField(
                  controller: ninController,
                  label: "NIN (National ID) - Optional",
                  icon: Icons.credit_card_outlined,
                ),
                const SizedBox(height: 15),

                // Referral Code (Optional)
                _buildInputField(
                  controller: referralCodeController,
                  label: "Referral Code - Optional",
                  icon: Icons.card_giftcard_outlined,
                ),
                const SizedBox(height: 30),

                // Signup Button
                loading
                    ? const Center(child: CircularProgressIndicator())
                    : SizedBox(
                        height: 56,
                        child: ElevatedButton(
                          onPressed: signup,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFF8C00),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            elevation: 0,
                          ),
                          child: const Text(
                            "Sign Up",
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),

                const SizedBox(height: 15),

                // Login link
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text("Already have an account? ", style: TextStyle(color: Colors.grey)),
                    TextButton(
                      onPressed: () {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                            builder: (_) => LoginScreen(role: widget.role),
                          ),
                        );
                      },
                      child: const Text(
                        "Log In",
                        style: TextStyle(
                          color: Color(0xFFFF8C00),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInputField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    TextInputType? keyboardType,
    bool isPassword = false,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.grey.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.withValues(alpha: 0.1)),
      ),
      child: TextFormField(
        controller: controller,
        obscureText: isPassword && obscurePassword,
        keyboardType: keyboardType,
        style: const TextStyle(color: Color(0xFF10223D)),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: TextStyle(color: Colors.grey.withValues(alpha: 0.7)),
          prefixIcon: Icon(icon, color: Colors.grey.withValues(alpha: 0.7)),
          suffixIcon: isPassword
              ? IconButton(
                  icon: Icon(
                    obscurePassword ? Icons.visibility : Icons.visibility_off,
                    color: Colors.grey.withValues(alpha: 0.7),
                  ),
                  onPressed: () => setState(() => obscurePassword = !obscurePassword),
                )
              : null,
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 16,
          ),
        ),
        validator: (value) {
          if (label.contains("Optional")) return null;
          if (value == null || value.trim().isEmpty) {
            return "$label is required";
          }
          if (label == "Password" && value.length < 6) {
            return "Password must be at least 6 characters";
          }
          if (label == "Username" && value.length < 3) {
            return "Username must be at least 3 characters";
          }
          return null;
        },
      ),
    );
  }
}

