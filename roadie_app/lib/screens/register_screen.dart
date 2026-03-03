import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class RegisterScreen extends StatefulWidget {
  final String role;
  const RegisterScreen({required this.role, super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final usernameController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final firstNameController = TextEditingController();
  final lastNameController = TextEditingController();
  final phoneController = TextEditingController();
  final ninController = TextEditingController();
  bool isLoading = false;
  bool isPasswordVisible = false;

  void _register() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => isLoading = true);

    final success = await ApiService.signup(
      username: usernameController.text,
      email: emailController.text,
      password: passwordController.text,
      firstName: firstNameController.text,
      lastName: lastNameController.text,
      phone: phoneController.text,
      role: widget.role,
      nin: ninController.text,
    );

    setState(() => isLoading = false);

    if (success && mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => HomeScreen(role: widget.role)),
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            "Registration failed. Try a different username or email.",
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF10223D), Color(0xFF1D3B63), Color(0xFF10223D)],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 20),
                  const Text(
                    "Join Vehix",
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                      letterSpacing: 1.2,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "Create your ${widget.role.toLowerCase()} account",
                    style: const TextStyle(
                      fontSize: 16,
                      color: Colors.white70,
                      fontWeight: FontWeight.w300,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 40),
                  _buildField(
                    firstNameController,
                    "First Name",
                    Icons.person_outline,
                  ),
                  const SizedBox(height: 16),
                  _buildField(
                    lastNameController,
                    "Last Name",
                    Icons.person_outline,
                  ),
                  const SizedBox(height: 16),
                  _buildField(
                    usernameController,
                    "Username",
                    Icons.account_circle_outlined,
                  ),
                  const SizedBox(height: 16),
                  _buildField(
                    emailController,
                    "Email",
                    Icons.email_outlined,
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 16),
                  _buildField(
                    phoneController,
                    "Phone Number",
                    Icons.phone_outlined,
                    keyboardType: TextInputType.phone,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: ninController,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: "NIN (14 Characters)",
                      labelStyle: const TextStyle(color: Colors.white70),
                      prefixIcon: const Icon(
                        Icons.badge_outlined,
                        color: Colors.white70,
                      ),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.1),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide(
                          color: Colors.white.withValues(alpha: 0.2),
                        ),
                      ),
                    ),
                    validator: (v) => (v == null || v.length != 14)
                        ? "NIN must be 14 characters"
                        : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: passwordController,
                    obscureText: !isPasswordVisible,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: "Password",
                      labelStyle: const TextStyle(color: Colors.white70),
                      prefixIcon: const Icon(
                        Icons.lock_outline,
                        color: Colors.white70,
                      ),
                      suffixIcon: IconButton(
                        icon: Icon(
                          isPasswordVisible
                              ? Icons.visibility
                              : Icons.visibility_off,
                          color: Colors.white70,
                        ),
                        onPressed: () => setState(
                          () => isPasswordVisible = !isPasswordVisible,
                        ),
                      ),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.1),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide(
                          color: Colors.white.withValues(alpha: 0.2),
                        ),
                      ),
                    ),
                    validator: (v) =>
                        v!.length < 6 ? "Password too short" : null,
                  ),
                  const SizedBox(height: 40),
                  ElevatedButton(
                    onPressed: isLoading ? null : _register,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFF8C00),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.all(18),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                      elevation: 8,
                    ),
                    child: isLoading
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text(
                            "CREATE ACCOUNT",
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1,
                            ),
                          ),
                  ),
                  const SizedBox(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text(
                        "Already have an account? ",
                        style: TextStyle(color: Colors.white70),
                      ),
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text(
                          "Sign In",
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
      ),
    );
  }

  Widget _buildField(
    TextEditingController controller,
    String label,
    IconData icon, {
    TextInputType? keyboardType,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white70),
        prefixIcon: Icon(icon, color: Colors.white70),
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.1),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.2)),
        ),
      ),
      validator: (v) => v!.isEmpty ? "Required" : null,
    );
  }
}
