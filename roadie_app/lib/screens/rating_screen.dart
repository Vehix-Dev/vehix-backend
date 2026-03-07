import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class RatingScreen extends StatefulWidget {
  final Map request;
  const RatingScreen({required this.request, super.key});

  @override
  State<RatingScreen> createState() => _RatingScreenState();
}

class _RatingScreenState extends State<RatingScreen> {
  double rating = 5;
  bool _isSubmitting = false;

  void submitRating() async {
    setState(() => _isSubmitting = true);
    try {
      await ApiService.post("/requests/${widget.request["id"]}/rate/", {
        "rating": rating,
        "role": "RODIE",
      });

      if (!mounted) return;
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Rating submitted successfully!"),
          backgroundColor: Colors.green,
        ),
      );
      
      // Navigate to HomeScreen
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const HomeScreen(role: 'RODIE')),
        (route) => false,
      );
    } catch (e) {
      setState(() => _isSubmitting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Error: ${e.toString()}"),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void goHome() {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const HomeScreen(role: 'RODIE')),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final counterpart = widget.request["rider"];

    String name = "Rider";
    if (counterpart is Map && counterpart["first_name"] != null) {
      name = "${counterpart["first_name"]} ${counterpart["last_name"] ?? ""}".trim();
    } else {
      name = widget.request["rider_name"]?.toString() ?? "Rider";
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF10223D),
        elevation: 0,
        title: const Text(
          "Rate the Experience",
          style: TextStyle(
            color: Color(0xFF10223D),
            fontWeight: FontWeight.bold,
          ),
        ),
        leading: null,
        automaticallyImplyLeading: false,
        actions: [
          TextButton.icon(
            onPressed: goHome,
            icon: const Icon(Icons.home, color: Color(0xFF10223D)),
            label: const Text(
              "Home",
              style: TextStyle(
                color: Color(0xFF10223D),
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(height: 40),
              
              // Profile Avatar
              Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF10223D).withValues(alpha: 0.3),
                    width: 4,
                  ),
                ),
                child: CircleAvatar(
                  radius: 50,
                  backgroundColor: const Color(0xFF10223D),
                  child: Text(
                    name.isNotEmpty ? name[0].toUpperCase() : "?",
                    style: const TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              
              const SizedBox(height: 24),
              
              // User Name and Service
              Text(
                name,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF10223D),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                "Service: ${widget.request["service_type_name"] ?? "Assist"}",
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.grey.withValues(alpha: 0.7),
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
              
              const SizedBox(height: 40),
              
              // Rating Question
              const Text(
                "How was your experience?",
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF10223D),
                ),
                textAlign: TextAlign.center,
              ),
              
              const SizedBox(height: 30),
              
              // Star Rating
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(5, (index) {
                  return GestureDetector(
                    onTap: () => setState(() => rating = (index + 1).toDouble()),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Icon(
                        index < rating ? Icons.star : Icons.star_border,
                        size: 56,
                        color: index < rating ? const Color(0xFFFF8C00) : Colors.grey.withValues(alpha: 0.3),
                      ),
                    ),
                  );
                }),
              ),
              
              const SizedBox(height: 16),
              
              // Rating Text
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                child: Text(
                  "${rating.toInt()} out of 5 stars",
                  key: ValueKey(rating),
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: rating <= 2 ? Colors.red : rating <= 3 ? Colors.orange : Colors.green,
                  ),
                ),
              ),
              
              // Rating Description
              const SizedBox(height: 8),
              Text(
                _getRatingDescription(rating.toInt()),
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey.withValues(alpha: 0.7),
                  fontStyle: FontStyle.italic,
                ),
                textAlign: TextAlign.center,
              ),
              
              const SizedBox(height: 60),
              
              // Submit Button
              SizedBox(
                width: double.infinity,
                height: 56,
                child: ElevatedButton(
                  onPressed: _isSubmitting ? null : submitRating,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFF8C00),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    elevation: 4,
                    shadowColor: const Color(0xFFFF8C00).withValues(alpha: 0.3),
                  ),
                  child: _isSubmitting
                      ? const SizedBox(
                          height: 24,
                          width: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Text(
                          "Submit Rating",
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Skip Button
              SizedBox(
                width: double.infinity,
                height: 56,
                child: OutlinedButton(
                  onPressed: goHome,
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Color(0xFF10223D), width: 2),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Text(
                    "Skip for Now",
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF10223D),
                    ),
                  ),
                ),
              ),
              
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  String _getRatingDescription(int rating) {
    switch (rating) {
      case 1:
        return "Very Poor - Not satisfied at all";
      case 2:
        return "Poor - Below expectations";
      case 3:
        return "Average - Met basic expectations";
      case 4:
        return "Good - Above expectations";
      case 5:
        return "Excellent - Outstanding service!";
      default:
        return "";
    }
  }
}
