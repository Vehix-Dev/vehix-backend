import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import 'package:intl/intl.dart';
import 'notification_detail_screen.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<dynamic> _notifications = [];
  Set<int> _hiddenIds = {};
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHiddenIds().then((_) => _fetchNotifications());
  }

  Future<void> _loadHiddenIds() async {
    final prefs = await SharedPreferences.getInstance();
    final hidden = prefs.getStringList('hidden_notification_ids') ?? [];
    setState(() {
      _hiddenIds = hidden.map((e) => int.parse(e)).toSet();
    });
  }

  Future<void> _hideNotification(int id) async {
    final prefs = await SharedPreferences.getInstance();
    _hiddenIds.add(id);
    await prefs.setStringList(
      'hidden_notification_ids',
      _hiddenIds.map((e) => e.toString()).toList(),
    );
    if (mounted) setState(() {});
  }

  Future<void> _fetchNotifications() async {
    try {
      final results = await ApiService.getNotifications();
      if (mounted) {
        setState(() {
          _notifications = results;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _markAsRead(int id) async {
    await ApiService.markNotificationAsRead(id);
    _fetchNotifications();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: const Text("Notifications", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF10223D),
        elevation: 0.5,
      ),
      body: RefreshIndicator(
        onRefresh: _fetchNotifications,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _visibleNotifications.isEmpty
                ? _buildEmptyState()
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _visibleNotifications.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final notif = _visibleNotifications[index];
                      return _buildNotificationCard(notif);
                    },
                  ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.notifications_off_outlined, size: 80, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            "No notifications yet",
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: Colors.grey[600]),
          ),
          const SizedBox(height: 8),
          Text(
            "We'll notify you about updates and job offers.",
            style: TextStyle(color: Colors.grey[500]),
          ),
        ],
      ),
    );
  }

  List<dynamic> get _visibleNotifications =>
      _notifications.where((n) => !_hiddenIds.contains(n['id'])).toList();

  Widget _buildNotificationCard(dynamic notif) {
    final bool isRead = notif['is_read'] ?? false;
    final DateTime createdAt = DateTime.parse(notif['created_at']);
    final String timeAgo = _formatTimeAgo(createdAt);

    return Dismissible(
      key: Key('notif_${notif['id']}'),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(
          color: Colors.red[50],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('🗑️', style: TextStyle(fontSize: 18)),
            const SizedBox(width: 4),
            Text('Hide', style: TextStyle(color: Colors.red[600], fontWeight: FontWeight.w600)),
          ],
        ),
      ),
      onDismissed: (_) => _hideNotification(notif['id']),
      child: InkWell(
      onTap: () async {
        if (!isRead) _markAsRead(notif['id']);
        final result = await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => NotificationDetailScreen(
              notification: Map<String, dynamic>.from(notif),
              onHide: () => _hideNotification(notif['id']),
            ),
          ),
        );
        if (result == 'hidden' && mounted) setState(() {});
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: isRead ? null : Border.all(color: const Color(0xFFFF8C00).withValues(alpha: 0.3), width: 1),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _getIconForType(notif['notification_type']),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          notif['title'] ?? 'Notice',
                          style: TextStyle(
                            fontWeight: isRead ? FontWeight.w600 : FontWeight.bold,
                            fontSize: 16,
                            color: const Color(0xFF10223D),
                          ),
                        ),
                      ),
                      if (!isRead)
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            color: Color(0xFFFF8C00),
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    notif['message'] ?? '',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Colors.grey[700],
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    timeAgo,
                    style: TextStyle(color: Colors.grey[500], fontSize: 12),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
    );
  }

  Widget _getIconForType(String? type) {
    IconData iconData = Icons.notifications;
    Color color = const Color(0xFF10223D);

    switch (type) {
      case 'URGENT':
        iconData = Icons.warning_rounded;
        color = Colors.red;
        break;
      case 'PROMOTION':
        iconData = Icons.local_offer_rounded;
        color = Colors.green;
        break;
      case 'SERVICE':
        iconData = Icons.build_circle_rounded;
        color = const Color(0xFFFF8C00);
        break;
      case 'BULLETIN':
        iconData = Icons.newspaper_rounded;
        color = Colors.blue;
        break;
    }

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        shape: BoxShape.circle,
      ),
      child: Icon(iconData, color: color, size: 24),
    );
  }

  String _formatTimeAgo(DateTime dateTime) {
    final Duration diff = DateTime.now().difference(dateTime);
    if (diff.inDays > 7) return DateFormat('MMM d, yyyy').format(dateTime);
    if (diff.inDays >= 1) return "${diff.inDays}d ago";
    if (diff.inHours >= 1) return "${diff.inHours}h ago";
    if (diff.inMinutes >= 1) return "${diff.inMinutes}m ago";
    return "Just now";
  }
}
