import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';

class WalletScreen extends StatefulWidget {
  const WalletScreen({super.key});

  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  Map<String, dynamic>? wallet;
  Map<String, dynamic>? userData;
  List<dynamic> transactions = [];
  bool _isLoading = true;
  bool _isProcessingDeposit = false;
  bool _isProcessingWithdrawal = false;

  static const int _minWithdrawal = 5000;

  @override
  void initState() {
    super.initState();
    _loadWallet();
  }

  Future<void> _loadWallet() async {
    setState(() => _isLoading = true);
    final userInfo = await ApiService.fetchUserInfo();
    final paymentsResponse = await ApiService.getRoadiePayments();

    if (mounted) {
      setState(() {
        userData = userInfo;
        // Use the specialized roadie payments response which has summary + history
        if (paymentsResponse != null) {
          wallet = paymentsResponse['summary'];
          transactions = paymentsResponse['transactions'] ?? [];
        }
        _isLoading = false;
      });
    }
  }

  // ─── DEPOSIT ────────────────────────────────────────────────────────────────
  // No form needed. Tap "Deposit" → hit backend → open Pesapal page in browser.

  Future<void> _initiateDeposit() async {
    final amountController = TextEditingController();
    
    final double? amount = await showDialog<double>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Deposit Funds'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Enter the amount you wish to deposit into your wallet (UGX).'),
            const SizedBox(height: 16),
            TextField(
              controller: amountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              autofocus: true,
              decoration: InputDecoration(
                labelText: 'Amount (UGX)',
                prefixText: 'UGX ',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFFF8C00), foregroundColor: Colors.white),
            onPressed: () {
              final val = double.tryParse(amountController.text.trim());
              if (val != null && val > 0) {
                Navigator.pop(ctx, val);
              } else {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please enter a valid amount.')));
              }
            },
            child: const Text('Next'),
          ),
        ],
      ),
    );

    if (amount == null) return;

    setState(() => _isProcessingDeposit = true);
    try {
      final response = await ApiService.depositFunds(amount);
      if (!mounted) return;

      if (response != null && response['redirect_url'] != null) {
        final url = Uri.parse(response['redirect_url'].toString());
        if (await canLaunchUrl(url)) {
          await launchUrl(url, mode: LaunchMode.externalApplication);
          // After the user returns, offer to check status
          if (mounted) _showCheckStatusDialog(response['reference']?.toString() ?? '');
        } else {
          _showError('Could not open payment page. Please try again.');
        }
      } else {
        String errMsg = response?['error']?.toString() ?? 'Failed to create payment link.';
        if (response != null && response['pesapal_response'] != null) {
          final pRes = response['pesapal_response'];
          if (pRes['error'] != null && pRes['error']['message'] != null) {
            errMsg = pRes['error']['message'];
          }
        }
        _showError(errMsg);
      }
    } catch (e) {
      _showError('Deposit error: $e');
    } finally {
      if (mounted) setState(() => _isProcessingDeposit = false);
    }
  }

  void _showCheckStatusDialog(String reference) {
    if (reference.isEmpty) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Payment Completed?'),
        content: const Text('After completing payment on the Pesapal page, tap "Check Status" to update your balance.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Later')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFF8C00),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              _checkPaymentStatus(reference);
            },
            child: const Text('Check Status'),
          ),
        ],
      ),
    );
  }

  Future<void> _checkPaymentStatus(String reference) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const AlertDialog(
        content: Row(children: [
          CircularProgressIndicator(),
          SizedBox(width: 16),
          Text('Checking payment…'),
        ]),
      ),
    );
    try {
      final result = await ApiService.checkPaymentStatus(reference);
      if (mounted) Navigator.pop(context);
      if (result != null && result['success'] == true) {
        final st = result['payment']?['status'] ?? '';
        if (st == 'COMPLETED') {
          _showSuccess('Payment completed! Your wallet has been updated.');
          _loadWallet();
        } else if (st == 'FAILED') {
          _showError('Payment failed. Please try again.');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Payment status: $st. Check back shortly.'), backgroundColor: Colors.orange),
          );
        }
      } else {
        _showError('Could not check payment status. Please try again.');
      }
    } catch (e) {
      if (mounted) Navigator.pop(context);
      _showError('Error: $e');
    }
  }

  // ─── WITHDRAW ───────────────────────────────────────────────────────────────

  void _showWithdrawModal() {
    final amountController = TextEditingController();
    final phoneController = TextEditingController(text: userData?['phone'] ?? '');
    String? errorMessage;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
            left: 24, right: 24, top: 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 40, height: 4,
                  decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2)),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Withdraw Funds', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF10223D))),
                  IconButton(onPressed: () => Navigator.pop(ctx), icon: const Icon(Icons.close)),
                ],
              ),
              const SizedBox(height: 4),

              // ⚠️ Min limit notice
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.amber.shade300),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.amber.shade800, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Minimum withdrawal is UGX ${_minWithdrawal.toString().replaceAllMapped(RegExp(r"(\d{1,3})(?=(\d{3})+(?!\d))"), (Match m) => "${m[1]},")} per transaction.',
                        style: TextStyle(color: Colors.amber.shade900, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              
              // ℹ️ Manual processing notice
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.blue.shade300),
                ),
                child: Row(
                  children: [
                    Icon(Icons.access_time_outlined, color: Colors.blue.shade800, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Withdrawals are processed manually by our team. Please allow up to 24 hours for funds to reflect on your mobile money account.',
                        style: TextStyle(color: Colors.blue.shade900, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Available balance
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFF10223D).withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.account_balance_wallet_outlined, color: Color(0xFF10223D), size: 20),
                    const SizedBox(width: 10),
                    Text(
                      'Available: UGX ${double.parse(wallet?['current_balance']?.toString() ?? '0').toStringAsFixed(0).replaceAllMapped(RegExp(r"(\d{1,3})(?=(\d{3})+(?!\d))"), (Match m) => "${m[1]},")}',
                      style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF10223D), fontSize: 15),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              if (errorMessage != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.red.shade200),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: Colors.red.shade700, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          errorMessage!,
                          style: TextStyle(color: Colors.red.shade900, fontSize: 13, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // Amount input
              TextField(
                controller: amountController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'Amount (UGX) — min 5,000',
                  prefixText: 'UGX ',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  filled: true,
                  fillColor: Colors.grey.shade50,
                ),
              ),
              const SizedBox(height: 12),

              // Phone input
              TextField(
                controller: phoneController,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(
                  labelText: 'Mobile Money Phone Number',
                  hintText: '2567XXXXXXXX',
                  prefixIcon: const Icon(Icons.phone_android_outlined),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  filled: true,
                  fillColor: Colors.grey.shade50,
                ),
              ),
              const SizedBox(height: 20),

              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _isProcessingWithdrawal ? null : () async {
                    final amount = double.tryParse(amountController.text.trim());
                    final phone = phoneController.text.trim();

                    if (amount == null || amount <= 0) {
                      setS(() => errorMessage = 'Enter a valid amount.'); return;
                    }
                    if (amount < _minWithdrawal) {
                      setS(() => errorMessage = 'Minimum withdrawal is UGX 5,000 per transaction.'); return;
                    }
                    final balance = double.tryParse(wallet?['current_balance']?.toString() ?? '0') ?? 0;
                    if (amount > balance) {
                      setS(() => errorMessage = 'Insufficient balance. Available: UGX ${balance.toStringAsFixed(0)}'); return;
                    }
                    if (phone.isEmpty || phone.length < 10) {
                      setS(() => errorMessage = 'Enter a valid phone number.'); return;
                    }

                    setS(() {
                      _isProcessingWithdrawal = true;
                      errorMessage = null;
                    });
                    try {
                      final result = await ApiService.withdrawFunds(amount, phone);
                      if (!mounted) return;
                      if (result != null && result['success'] == true) {
                        Navigator.pop(ctx);
                        _showSuccess('Withdrawal submitted! It will be reviewed and processed within 24 hours. Ref: ${result['reference']}');
                        _loadWallet();
                      } else {
                        setS(() => errorMessage = _parseErrorMessage(result) ?? 'Withdrawal failed. Please try again.');
                      }
                    } catch (e) {
                      setS(() => errorMessage = 'Error: $e');
                    } finally {
                      if (mounted) setS(() => _isProcessingWithdrawal = false);
                    }
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red.shade600,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    elevation: 0,
                  ),
                  child: _isProcessingWithdrawal
                      ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation<Color>(Colors.white)))
                      : const Text('Submit Withdrawal', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── HELPERS ────────────────────────────────────────────────────────────────

  String? _parseErrorMessage(dynamic result) {
    if (result == null) return null;
    if (result is! Map) return null;
    // Top-level error string
    if (result['error'] is String) return result['error'];
    // DRF field-level errors: {"field": ["message", ...]}
    for (final value in result.values) {
      if (value is List && value.isNotEmpty) return value.first.toString();
      if (value is String) return value;
    }
    return null;
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red.shade700));
  }

  void _showSuccess(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.green, duration: const Duration(seconds: 5)));
  }

  // ─── BUILD ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text('My Wallet', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF10223D),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadWallet,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildBalanceCard(),
                  const SizedBox(height: 16),
                  _buildStatsRow(),
                  const SizedBox(height: 24),
                  _buildTrialBanner(),
                  const Text('Transaction History', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Color(0xFF10223D))),
                  const SizedBox(height: 12),
                  if (transactions.isEmpty)
                    _buildEmptyState()
                  else
                    ...transactions.map(_buildTransactionTile),
                  const SizedBox(height: 32),
                ],
              ),
            ),
    );
  }

  Widget _buildBalanceCard() {
    final rawBalance = wallet?['current_balance'] ?? '0';
    final balance = double.parse(rawBalance.toString()).toStringAsFixed(0).replaceAllMapped(RegExp(r"(\d{1,3})(?=(\d{3})+(?!\d))"), (Match m) => "${m[1]},");
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF10223D), Color(0xFF1D3C6A)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [BoxShadow(color: const Color(0xFF10223D).withValues(alpha: 0.35), blurRadius: 24, offset: const Offset(0, 10))],
      ),
      child: Column(
        children: [
          const Text('Available Balance', style: TextStyle(color: Colors.white70, fontSize: 15, letterSpacing: 0.4)),
          const SizedBox(height: 8),
          Text('UGX $balance', style: const TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold, letterSpacing: -0.5)),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildActionButton(
                icon: _isProcessingDeposit ? null : Icons.arrow_downward_rounded,
                label: 'Deposit',
                color: Colors.greenAccent.shade700,
                onTap: _isProcessingDeposit ? null : _initiateDeposit,
                isLoading: _isProcessingDeposit,
              ),
              Container(width: 1, height: 48, color: Colors.white24),
              _buildActionButton(
                icon: Icons.arrow_upward_rounded,
                label: 'Withdraw',
                color: Colors.redAccent.shade200,
                onTap: _showWithdrawModal,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton({IconData? icon, required String label, required Color color, VoidCallback? onTap, bool isLoading = false}) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: 52, height: 52,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.15), shape: BoxShape.circle, border: Border.all(color: color.withValues(alpha: 0.4))),
            child: isLoading
                ? Padding(padding: const EdgeInsets.all(14), child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation<Color>(color)))
                : Icon(icon, color: color, size: 24),
          ),
          const SizedBox(height: 6),
          Text(label, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildStatsRow() {
    final totalDep = double.parse(wallet?['total_earned']?.toString() ?? '0').toStringAsFixed(0);
    final totalWth = double.parse(wallet?['total_withdrawn']?.toString() ?? '0').toStringAsFixed(0);
    final pendingDep = double.parse(wallet?['pending_deposits']?.toString() ?? '0');
    final pendingWth = double.parse(wallet?['pending_withdrawals']?.toString() ?? '0');
    
    final totalPending = (pendingDep + pendingWth).toStringAsFixed(0);
    
    return Row(
      children: [
        Expanded(child: _buildStatCard('Earned', 'UGX $totalDep', Colors.green)),
        const SizedBox(width: 8),
        Expanded(child: _buildStatCard('Withdrawn', 'UGX $totalWth', Colors.red)),
        const SizedBox(width: 8),
        Expanded(child: _buildStatCard('Pending', 'UGX $totalPending', Colors.orange)),
      ],
    );
  }

  Widget _buildStatCard(String title, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.2)),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(fontSize: 11, color: Colors.grey.shade600, fontWeight: FontWeight.w500)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }

  Widget _buildTrialBanner() {
    final String? endDate = userData?['trial_end_date'];
    final int trialDays = userData?['trial_days_left'] ?? 0;
    if (endDate == null || endDate.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: trialDays > 0 ? Colors.green.shade50 : Colors.orange.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: trialDays > 0 ? Colors.green.shade200 : Colors.orange.shade200),
      ),
      child: Row(
        children: [
          Icon(trialDays > 0 ? Icons.timer_outlined : Icons.warning_amber_rounded,
              color: trialDays > 0 ? Colors.green : Colors.orange, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              trialDays > 0 ? 'Free Trial: $trialDays days left — commission-free jobs!' : 'Free trial ended. Commission now applies.',
              style: TextStyle(color: trialDays > 0 ? Colors.green.shade800 : Colors.orange.shade900, fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 48),
        child: Column(
          children: [
            Icon(Icons.receipt_long_outlined, size: 64, color: Colors.grey.shade300),
            const SizedBox(height: 16),
            Text('No transactions yet', style: TextStyle(color: Colors.grey.shade400, fontSize: 16)),
            const SizedBox(height: 8),
            Text('Your deposits and withdrawals will appear here.', style: TextStyle(color: Colors.grey.shade400, fontSize: 13), textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  Widget _buildTransactionTile(dynamic tx) {
    final amount = double.tryParse(tx['amount'].toString()) ?? 0.0;
    final isNeg = amount < 0 || tx['transaction_type'] == 'WITHDRAWAL';
    final txStatus = (tx['status'] ?? 'COMPLETED').toString().toUpperCase();
    final label = tx['reason'] ?? tx['transaction_type'] ?? 'Transaction';
    final date = tx['created_at']?.toString().split('T')[0] ?? '';

    Color statusColor = Colors.green;
    if (txStatus == 'PENDING') statusColor = Colors.orange;
    if (txStatus == 'FAILED') statusColor = Colors.red;
    if (txStatus == 'CANCELLED') statusColor = Colors.grey;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: isNeg ? Colors.red.shade50 : Colors.green.shade50,
          child: Icon(isNeg ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
              color: isNeg ? Colors.red.shade600 : Colors.green.shade600, size: 20),
        ),
        title: Text(label.toString(), style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: Color(0xFF10223D))),
        subtitle: Text(date, style: TextStyle(color: Colors.grey.shade500, fontSize: 12)),
        trailing: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '${isNeg ? '-' : '+'} UGX ${amount.abs().toStringAsFixed(0)}',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: isNeg ? Colors.red.shade600 : Colors.green.shade700),
            ),
            Container(
              margin: const EdgeInsets.only(top: 3),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(4)),
              child: Text(txStatus, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: statusColor)),
            ),
            if (txStatus == 'PENDING')
              Padding(
                padding: const EdgeInsets.only(top: 4.0),
                child: GestureDetector(
                  onTap: () => _checkPaymentStatus(tx['reference'] ?? ''),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: const Color(0xFF10223D), borderRadius: BorderRadius.circular(4)),
                    child: const Text('Verify', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
