import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:collection';

/// Error types for better categorization
enum ErrorType {
  network,
  authentication,
  validation,
  server,
  websocket,
  location,
  payment,
  unknown,
}

/// Error severity levels
enum ErrorSeverity {
  low,      // User can continue
  medium,   // Feature affected
  high,     // App functionality affected
  critical, // App unusable
}

/// User-friendly error messages
class ErrorMessages {
  static const Map<ErrorType, Map<String, String>> _messages = {
    ErrorType.network: {
      'no_internet': 'No internet connection. Please check your network settings.',
      'connection_timeout': 'Connection timeout. Please try again.',
      'connection_failed': 'Failed to connect to server. Please try again.',
      'slow_network': 'Slow network detected. Some features may be limited.',
    },
    ErrorType.authentication: {
      'token_expired': 'Your session has expired. Please log in again.',
      'invalid_credentials': 'Invalid email or password. Please try again.',
      'access_denied': 'Access denied. You don\'t have permission to perform this action.',
      'session_invalid': 'Invalid session. Please log in again.',
    },
    ErrorType.validation: {
      'invalid_email': 'Please enter a valid email address.',
      'invalid_phone': 'Please enter a valid phone number.',
      'required_field': 'This field is required.',
      'invalid_format': 'Invalid format. Please check your input.',
    },
    ErrorType.server: {
      'server_error': 'Server error. Please try again later.',
      'maintenance': 'Server is under maintenance. Please try again later.',
      'service_unavailable': 'Service temporarily unavailable. Please try again.',
      'rate_limit': 'Too many requests. Please wait and try again.',
    },
    ErrorType.websocket: {
      'connection_lost': 'Real-time connection lost. Reconnecting...',
      'connection_failed': 'Failed to establish real-time connection.',
      'message_failed': 'Failed to send message. Please try again.',
      'reconnected': 'Real-time connection restored.',
    },
    ErrorType.location: {
      'location_disabled': 'Location services are disabled. Please enable them in settings.',
      'location_permission_denied': 'Location permission denied. Please enable it in settings.',
      'location_unavailable': 'Unable to get your location. Please try again.',
      'gps_timeout': 'GPS timeout. Please ensure you have a clear view of the sky.',
    },
    ErrorType.payment: {
      'payment_failed': 'Payment failed. Please check your payment details.',
      'insufficient_funds': 'Insufficient funds. Please add money to your wallet.',
      'payment_cancelled': 'Payment was cancelled.',
      'payment_timeout': 'Payment timeout. Please try again.',
    },
    ErrorType.unknown: {
      'default': 'An unexpected error occurred. Please try again.',
    },
  };

  static String getMessage(ErrorType type, String code) {
    try {
      return _messages[type]?[code] ?? _messages[ErrorType.unknown]?['default'] ?? 'Unknown error occurred.';
    } catch (e) {
      return 'Error message not available.';
    }
  }
}

/// Comprehensive error handling service
class ErrorHandlingService {
  static final ErrorHandlingService _instance = ErrorHandlingService._internal();
  factory ErrorHandlingService() => _instance;
  ErrorHandlingService._internal();

  final Queue<AppError> _errorHistory = Queue<AppError>();
  final Map<ErrorType, int> _errorCounts = {};
  Timer? _errorReportTimer;
  
  static const int _maxErrorHistory = 100;
  static const Duration _errorReportInterval = Duration(minutes: 5);

  /// Initialize error handling
  void initialize() {
    _errorReportTimer = Timer.periodic(_errorReportInterval, (_) {
      _reportErrorStatistics();
    });
    debugPrint("🛡️ Error Handling: Initialized");
  }

  /// Handle and display error
  void handleError(
    dynamic error, {
    ErrorType? type,
    ErrorSeverity? severity,
    String? customMessage,
    StackTrace? stackTrace,
    BuildContext? context,
    VoidCallback? onRetry,
    bool showSnackbar = true,
    bool logToConsole = true,
  }) {
    final appError = AppError.fromError(
      error,
      type: type ?? _determineErrorType(error),
      severity: severity ?? _determineErrorSeverity(error),
      customMessage: customMessage,
      stackTrace: stackTrace,
    );

    _recordError(appError);

    if (logToConsole) {
      _logError(appError);
    }

    if (showSnackbar && context != null) {
      _showErrorSnackbar(context, appError, onRetry);
    }

    // Handle critical errors
    if (appError.severity == ErrorSeverity.critical) {
      _handleCriticalError(appError, context);
    }
  }

  /// Show success message
  void showSuccess(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 3),
    SnackBarAction? action,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.green,
        duration: duration,
        action: action,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Show info message
  void showInfo(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 3),
    SnackBarAction? action,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.info, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.blue,
        duration: duration,
        action: action,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Show warning message
  void showWarning(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 4),
    SnackBarAction? action,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.warning, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.orange,
        duration: duration,
        action: action,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Show loading dialog
  void showLoadingDialog(
    BuildContext context, {
    String message = 'Loading...',
    bool barrierDismissible = false,
  }) {
    showDialog(
      context: context,
      barrierDismissible: barrierDismissible,
      builder: (context) => PopScope(
        canPop: barrierDismissible,
        child: Dialog(
          backgroundColor: Colors.transparent,
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 16),
                Text(message),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Hide loading dialog
  void hideLoadingDialog(BuildContext context) {
    Navigator.of(context, rootNavigator: true).pop();
  }

  /// Determine error type from error object
  ErrorType _determineErrorType(dynamic error) {
    final errorString = error.toString().toLowerCase();
    
    if (errorString.contains('network') || 
        errorString.contains('socket') ||
        errorString.contains('connection')) {
      return ErrorType.network;
    } else if (errorString.contains('token') ||
               errorString.contains('unauthorized') ||
               errorString.contains('authentication')) {
      return ErrorType.authentication;
    } else if (errorString.contains('validation') ||
               errorString.contains('invalid') ||
               errorString.contains('required')) {
      return ErrorType.validation;
    } else if (errorString.contains('server') ||
               errorString.contains('500') ||
               errorString.contains('503')) {
      return ErrorType.server;
    } else if (errorString.contains('websocket') ||
               errorString.contains('ws')) {
      return ErrorType.websocket;
    } else if (errorString.contains('location') ||
               errorString.contains('gps')) {
      return ErrorType.location;
    } else if (errorString.contains('payment') ||
               errorString.contains('transaction')) {
      return ErrorType.payment;
    }
    
    return ErrorType.unknown;
  }

  /// Determine error severity
  ErrorSeverity _determineErrorSeverity(dynamic error) {
    final errorString = error.toString().toLowerCase();
    
    if (errorString.contains('critical') ||
        errorString.contains('fatal')) {
      return ErrorSeverity.critical;
    } else if (errorString.contains('server') ||
               errorString.contains('authentication')) {
      return ErrorSeverity.high;
    } else if (errorString.contains('network') ||
               errorString.contains('timeout')) {
      return ErrorSeverity.medium;
    }
    
    return ErrorSeverity.low;
  }

  /// Record error for analytics
  void _recordError(AppError error) {
    _errorHistory.add(error);
    
    // Maintain history size
    while (_errorHistory.length > _maxErrorHistory) {
      _errorHistory.removeFirst();
    }
    
    // Update error counts
    _errorCounts[error.type] = (_errorCounts[error.type] ?? 0) + 1;
  }

  /// Log error to console
  void _logError(AppError error) {
    debugPrint("🛡️ Error: ${error.type.name} - ${error.message}");
    if (error.stackTrace != null) {
      debugPrint("🛡️ StackTrace: ${error.stackTrace}");
    }
    debugPrint("🛡️ Severity: ${error.severity.name}");
    debugPrint("🛡️ Timestamp: ${error.timestamp}");
  }

  /// Show error snackbar
  void _showErrorSnackbar(
    BuildContext context,
    AppError error,
    VoidCallback? onRetry,
  ) {
    final color = _getSeverityColor(error.severity);
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(_getSeverityIcon(error.severity), color: Colors.white),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                error.userMessage,
                style: const TextStyle(fontSize: 14),
              ),
            ),
          ],
        ),
        backgroundColor: color,
        duration: _getDurationForSeverity(error.severity),
        action: onRetry != null ? SnackBarAction(
          label: 'Retry',
          textColor: Colors.white,
          onPressed: onRetry,
        ) : null,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Handle critical errors
  void _handleCriticalError(AppError error, BuildContext? context) {
    debugPrint("🚨 Critical Error: ${error.message}");
    
    // Show critical error dialog
    if (context != null) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.error, color: Colors.red),
              const SizedBox(width: 8),
              const Text('Critical Error'),
            ],
          ),
          content: Text(error.userMessage),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                // Optionally restart app or navigate to safe screen
              },
              child: const Text('OK'),
            ),
          ],
        ),
      );
    }
  }

  /// Get color for severity level
  Color _getSeverityColor(ErrorSeverity severity) {
    switch (severity) {
      case ErrorSeverity.low:
        return Colors.orange;
      case ErrorSeverity.medium:
        return Colors.deepOrange;
      case ErrorSeverity.high:
        return Colors.red;
      case ErrorSeverity.critical:
        return Colors.red[900] ?? Colors.red;
    }
  }

  /// Get icon for severity level
  IconData _getSeverityIcon(ErrorSeverity severity) {
    switch (severity) {
      case ErrorSeverity.low:
        return Icons.warning;
      case ErrorSeverity.medium:
        return Icons.error_outline;
      case ErrorSeverity.high:
        return Icons.error;
      case ErrorSeverity.critical:
        return Icons.dangerous;
    }
  }

  /// Get duration for severity level
  Duration _getDurationForSeverity(ErrorSeverity severity) {
    switch (severity) {
      case ErrorSeverity.low:
        return const Duration(seconds: 3);
      case ErrorSeverity.medium:
        return const Duration(seconds: 5);
      case ErrorSeverity.high:
        return const Duration(seconds: 8);
      case ErrorSeverity.critical:
        return const Duration(seconds: 10);
    }
  }

  /// Report error statistics
  void _reportErrorStatistics() {
    if (_errorHistory.isEmpty) return;
    
    debugPrint("📊 Error Statistics Report:");
    debugPrint("   Total Errors: ${_errorHistory.length}");
    
    for (final entry in _errorCounts.entries) {
      debugPrint("   ${entry.key.name}: ${entry.value}");
    }
    
    // Calculate error rate
    final recentErrors = _errorHistory.where(
      (error) => DateTime.now().difference(error.timestamp).inMinutes < 5
    ).length;
    
    if (recentErrors > 10) {
      debugPrint("⚠️ High error rate detected: $recentErrors errors in last 5 minutes");
    }
  }

  /// Get error statistics
  Map<String, dynamic> getErrorStatistics() {
    return {
      'totalErrors': _errorHistory.length,
      'errorCounts': Map.from(_errorCounts),
      'recentErrors': _errorHistory.where(
        (error) => DateTime.now().difference(error.timestamp).inMinutes < 5
      ).length,
      'criticalErrors': _errorHistory.where(
        (error) => error.severity == ErrorSeverity.critical
      ).length,
    };
  }

  /// Clear error history
  void clearErrorHistory() {
    _errorHistory.clear();
    _errorCounts.clear();
    debugPrint("🧹 Error history cleared");
  }

  /// Dispose resources
  void dispose() {
    _errorReportTimer?.cancel();
    clearErrorHistory();
  }
}

/// App error model
class AppError {
  final ErrorType type;
  final ErrorSeverity severity;
  final String message;
  final String userMessage;
  final DateTime timestamp;
  final StackTrace? stackTrace;

  AppError({
    required this.type,
    required this.severity,
    required this.message,
    required this.userMessage,
    required this.timestamp,
    this.stackTrace,
  });

  factory AppError.fromError(
    dynamic error, {
    required ErrorType type,
    required ErrorSeverity severity,
    String? customMessage,
    StackTrace? stackTrace,
  }) {
    final message = error.toString();
    final userMessage = customMessage ?? ErrorMessages.getMessage(type, _getErrorCode(message));
    
    return AppError(
      type: type,
      severity: severity,
      message: message,
      userMessage: userMessage,
      timestamp: DateTime.now(),
      stackTrace: stackTrace,
    );
  }

  static String _getErrorCode(String message) {
    final lowerMessage = message.toLowerCase();
    
    if (lowerMessage.contains('no internet')) return 'no_internet';
    if (lowerMessage.contains('timeout')) return 'connection_timeout';
    if (lowerMessage.contains('connection failed')) return 'connection_failed';
    if (lowerMessage.contains('slow')) return 'slow_network';
    if (lowerMessage.contains('token expired')) return 'token_expired';
    if (lowerMessage.contains('invalid credentials')) return 'invalid_credentials';
    if (lowerMessage.contains('access denied')) return 'access_denied';
    if (lowerMessage.contains('invalid email')) return 'invalid_email';
    if (lowerMessage.contains('invalid phone')) return 'invalid_phone';
    if (lowerMessage.contains('required')) return 'required_field';
    if (lowerMessage.contains('server error')) return 'server_error';
    if (lowerMessage.contains('maintenance')) return 'maintenance';
    if (lowerMessage.contains('unavailable')) return 'service_unavailable';
    if (lowerMessage.contains('rate limit')) return 'rate_limit';
    if (lowerMessage.contains('connection lost')) return 'connection_lost';
    if (lowerMessage.contains('location disabled')) return 'location_disabled';
    if (lowerMessage.contains('permission denied')) return 'location_permission_denied';
    if (lowerMessage.contains('payment failed')) return 'payment_failed';
    if (lowerMessage.contains('insufficient')) return 'insufficient_funds';
    
    return 'default';
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type.name,
      'severity': severity.name,
      'message': message,
      'userMessage': userMessage,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}

/// Global error handling service instance
final errorHandlingService = ErrorHandlingService();
