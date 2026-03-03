import 'package:flutter/material.dart';
import '../services/api_service.dart';

class RatingScreen extends StatefulWidget {
  final Map request;
  const RatingScreen({required this.request, super.key});

  @override
  State<RatingScreen> createState() => _RatingScreenState();
}

class _RatingScreenState extends State<RatingScreen> {
  double rating = 5;

  void submitRating() async {
    // Example: POST to backend
    await ApiService.post("/requests/${widget.request["id"]}/rate/", {
      "rating": rating,
      "role": "RODIE",
    });

    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text("Rating submitted")));
    Navigator.popUntil(context, (route) => route.isFirst);
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
      appBar: AppBar(title: Text("Rate $name")),
      body: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text("Rate $name", style: const TextStyle(fontSize: 24)),
          Slider(
            value: rating,
            onChanged: (v) => setState(() => rating = v),
            min: 1,
            max: 5,
            divisions: 4,
            label: rating.toString(),
          ),
          ElevatedButton(onPressed: submitRating, child: const Text("Submit")),
        ],
      ),
    );
  }
}
