import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> requests = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoading = true);
    final data = await ApiService.getMyRequests();
    if (mounted) {
      setState(() {
        requests = data;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Request History")),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadHistory,
              child: requests.isEmpty
                  ? const Center(child: Text("No service requests found"))
                  : ListView.builder(
                      padding: const EdgeInsets.all(8),
                      itemCount: requests.length,
                      itemBuilder: (context, index) {
                        final req = requests[index];
                        return _buildRequestCard(req);
                      },
                    ),
            ),
    );
  }

  Widget _buildRequestCard(Map<String, dynamic> req) {
    final status = req['status'] ?? 'UNKNOWN';
    final color = _getStatusColor(status);
    final riderName = req['rider_name'] ?? "No Rider info";
    final riderPhone = req['rider_phone'] ?? "";

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  req['service_type_name'] ?? "Service",
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: color),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.person, size: 16, color: Color(0xFF10223D)),
                const SizedBox(width: 8),
                Text("Rider: $riderName"),
              ],
            ),
            if (riderPhone.isNotEmpty) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.phone, size: 16, color: Color(0xFF10223D)),
                  const SizedBox(width: 8),
                  Text("Phone: $riderPhone"),
                ],
              ),
            ],
            const SizedBox(height: 12),
            Text(
              "ID: #${req['id']} • Date: ${req['created_at']?.split('T')[0] ?? ''}",
              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'COMPLETED':
        return Colors.green;
      case 'CANCELLED':
        return Colors.red;
      case 'REQUESTED':
        return Colors.orange;
      case 'ACCEPTED':
      case 'EN_ROUTE':
      case 'STARTED':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }
}
