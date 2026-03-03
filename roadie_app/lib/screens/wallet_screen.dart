import 'package:flutter/material.dart';
import '../services/api_service.dart';

class WalletScreen extends StatefulWidget {
  const WalletScreen({super.key});

  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  Map<String, dynamic>? wallet;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadWallet();
  }

  Future<void> _loadWallet() async {
    setState(() => _isLoading = true);
    final data = await ApiService.getWallet();
    if (mounted) {
      setState(() {
        wallet = data;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("My Wallet")),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadWallet,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildBalanceCard(),
                  const SizedBox(height: 24),
                  const Text(
                    "Transaction History",
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const Divider(),
                  if (wallet?['transactions'] == null ||
                      (wallet!['transactions'] as List).isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(32.0),
                        child: Text("No transactions yet"),
                      ),
                    )
                  else
                    ...((wallet!['transactions'] as List).map(
                      (tx) => _buildTransactionItem(tx),
                    )),
                ],
              ),
            ),
    );
  }

  Widget _buildBalanceCard() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      color: Colors.blue,
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            const Text(
              "Current Balance",
              style: TextStyle(color: Colors.white70, fontSize: 16),
            ),
            const SizedBox(height: 8),
            Text(
              "UGX ${wallet?['balance'] ?? '0.00'}",
              style: const TextStyle(
                color: Colors.white,
                fontSize: 32,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildCompactAction(Icons.add, "Deposit"),
                _buildCompactAction(Icons.file_download, "Withdraw"),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCompactAction(IconData icon, String label) {
    return Column(
      children: [
        CircleAvatar(
          backgroundColor: Colors.white24,
          child: Icon(icon, color: Colors.white),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: Colors.white, fontSize: 12)),
      ],
    );
  }

  Widget _buildTransactionItem(Map<String, dynamic> tx) {
    final amount = double.tryParse(tx['amount'].toString()) ?? 0.0;
    final isNegative = amount < 0;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isNegative ? Colors.red.shade50 : Colors.green.shade50,
        child: Icon(
          isNegative ? Icons.remove : Icons.add,
          color: isNegative ? Colors.red : Colors.green,
        ),
      ),
      title: Text(tx['reason'] ?? "Transfer"),
      subtitle: Text(tx['created_at']?.split('T')[0] ?? ""),
      trailing: Text(
        "${isNegative ? '-' : '+'} ${amount.abs().toStringAsFixed(2)}",
        style: TextStyle(
          fontWeight: FontWeight.bold,
          color: isNegative ? Colors.red : Colors.green,
        ),
      ),
    );
  }
}
