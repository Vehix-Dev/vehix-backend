import 'package:flutter/material.dart';

class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Help & Support')),
      body: const Padding(
        padding: EdgeInsets.all(16.0),
        child: Text(
          'For assistance, please contact support@vehix.ug or call +256 123 456789.\nThank you for using Vehix!',
          style: TextStyle(fontSize: 16),
        ),
      ),
    );
  }
}
