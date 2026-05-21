import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class NotificationDetailScreen extends StatelessWidget {
  final Map<String, dynamic> notification;
  final VoidCallback? onHide;

  const NotificationDetailScreen({
    super.key,
    required this.notification,
    this.onHide,
  });

  @override
  Widget build(BuildContext context) {
    final String title = notification['title'] ?? 'Notice';
    final String message = notification['message'] ?? '';
    final String? type = notification['notification_type'];
    final DateTime createdAt = DateTime.parse(notification['created_at']);
    final String formattedDate = DateFormat('MMMM d, yyyy • h:mm a').format(createdAt);

    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: const Text("Notification", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF10223D),
        elevation: 0.5,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Type badge + date
            Row(
              children: [
                _buildTypeBadge(type),
                const Spacer(),
                Text(
                  formattedDate,
                  style: TextStyle(color: Colors.grey[500], fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Title
            Text(
              title,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Color(0xFF10223D),
                height: 1.3,
              ),
            ),
            const SizedBox(height: 16),

            // Divider
            Container(
              height: 3,
              width: 40,
              decoration: BoxDecoration(
                color: const Color(0xFFFF8C00),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),

            // Full message content
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Text(
                message,
                style: TextStyle(
                  color: Colors.grey[800],
                  fontSize: 16,
                  height: 1.6,
                ),
              ),
            ),
            const SizedBox(height: 32),

            // Action buttons
            Row(
              children: [
                // OK button (go back)
                Expanded(
                  child: ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Okay'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10223D),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                // Hide button (hide from frontend only)
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      onHide?.call();
                      Navigator.pop(context, 'hidden');
                    },
                    child: const Text('Hide'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.red[600],
                      side: BorderSide(color: Colors.red[300]!),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypeBadge(String? type) {
    String label = 'General';
    Color color = const Color(0xFF10223D);
    IconData iconData = Icons.notifications;

    switch (type) {
      case 'URGENT':
        label = 'Urgent';
        iconData = Icons.warning_rounded;
        color = Colors.red;
        break;
      case 'PROMOTION':
        label = 'Promotion';
        iconData = Icons.local_offer_rounded;
        color = Colors.green;
        break;
      case 'SERVICE':
        label = 'Service';
        iconData = Icons.build_circle_rounded;
        color = const Color(0xFFFF8C00);
        break;
      case 'BULLETIN':
        label = 'Bulletin';
        iconData = Icons.newspaper_rounded;
        color = Colors.blue;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(iconData, color: color, size: 16),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}
