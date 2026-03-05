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
        const SnackBar(content: Text("Rating submitted successfully!")),
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
          SnackBar(content: Text("Error: ${e.toString()}")),
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
      name = counterpart["first_name"];
    } else {
      name = widget.request["rider_name"]?.toString().split(" ")[0] ?? "Rider";
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF10223D),
        foregroundColor: Colors.white,
        title: const Text("Rate the Experience"),
        leading: null,
        automaticallyImplyLeading: false,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const SizedBox(height: 40),
            CircleAvatar(
              radius: 50,
              backgroundColor: const Color(0xFFFF8C00),
              child: Text(
                name[0].toUpperCase(),
                style: const TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              "How was your experience with $name?",
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 40),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(5, (index) {
                return GestureDetector(
                  onTap: () => setState(() => rating = (index + 1).toDouble()),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Icon(
                      Icons.star,
                      size: 48,
                      color: index < rating ? const Color(0xFFFF8C00) : Colors.grey,
                    ),
                  ),
                );
              }),
            ),
            const SizedBox(height: 12),
            Text(
              "${rating.toInt()} out of 5 stars",
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 60),
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : submitRating,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFF8C00),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
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
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 56,
              child: OutlinedButton(
                onPressed: goHome,
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: Color(0xFF10223D), width: 2),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  "Home",
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
    );
  }
}
