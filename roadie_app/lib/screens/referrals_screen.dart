import 'package:flutter/material.dart';

class ReferralsScreen extends StatelessWidget {
  const ReferralsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Referrals & Promotions')),
      body: const Padding(
        padding: EdgeInsets.all(16.0),
        child: Text(
          'Share your referral code with friends and earn rewards!\n(Feature coming soon)',
          style: TextStyle(fontSize: 16),
        ),
      ),
    );
  }
}
