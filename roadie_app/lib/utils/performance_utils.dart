import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'dart:async';

class PerformanceUtils {
  // Initialize ScreenUtil for responsive design
  static void initScreenUtil(BuildContext context) {
    ScreenUtil.init(context, designSize: const Size(375, 812));
  }

  // Smooth page transitions using built-in Flutter routes
  static Future<T?> navigateTo<T>(
    BuildContext context,
    Widget page, {
    Duration duration = const Duration(milliseconds: 300),
    Curve curve = Curves.easeInOutCubic,
  }) {
    return Navigator.push<T>(
      context,
      PageRouteBuilder(
        pageBuilder: (context, animation, secondaryAnimation) => page,
        transitionDuration: duration,
        transitionsBuilder: (context, anim, secondaryAnim, child) {
          return SlideTransition(
            position: Tween(begin: const Offset(1, 0), end: Offset.zero)
                .chain(CurveTween(curve: curve))
                .animate(anim),
            child: FadeTransition(opacity: anim, child: child),
          );
        },
      ),
    );
  }

  static Future<T?> navigateToModal<T>(
    BuildContext context,
    Widget page, {
    Duration duration = const Duration(milliseconds: 250),
    Curve curve = Curves.easeOutCubic,
  }) {
    return Navigator.push<T>(
      context,
      PageRouteBuilder(
        pageBuilder: (context, animation, secondaryAnimation) => page,
        transitionDuration: duration,
        fullscreenDialog: true,
        transitionsBuilder: (context, anim, secondaryAnim, child) {
          return SlideTransition(
            position: Tween(begin: const Offset(0, 1), end: Offset.zero)
                .chain(CurveTween(curve: curve))
                .animate(anim),
            child: child,
          );
        },
      ),
    );
  }

  static Future<T?> navigateWithFade<T>(
    BuildContext context,
    Widget page, {
    Duration duration = const Duration(milliseconds: 200),
    Curve curve = Curves.easeInOut,
  }) {
    return Navigator.push<T>(
      context,
      PageRouteBuilder(
        pageBuilder: (context, animation, secondaryAnimation) => page,
        transitionDuration: duration,
        transitionsBuilder: (context, anim, secondaryAnim, child) {
          return FadeTransition(opacity: anim, child: child);
        },
      ),
    );
  }

  static void navigateBack<T>(BuildContext context, [T? result]) {
    Navigator.pop<T>(context, result);
  }

  // Responsive sizing with ScreenUtil
  static double setWidth(double width) => width.w;
  static double setHeight(double height) => height.h;
  static double setFont(double fontSize) => fontSize.sp;
  static double setRadius(double radius) => radius.r;
  static EdgeInsets setPadding({
    double all = 0,
    double horizontal = 0,
    double vertical = 0,
    double top = 0,
    double bottom = 0,
    double left = 0,
    double right = 0,
  }) {
    return EdgeInsets.only(
      left: left > 0 ? left.w : (horizontal > 0 ? horizontal.w : (all > 0 ? all.w : 0)),
      right: right > 0 ? right.w : (horizontal > 0 ? horizontal.w : (all > 0 ? all.w : 0)),
      top: top > 0 ? top.h : (vertical > 0 ? vertical.h : (all > 0 ? all.h : 0)),
      bottom: bottom > 0 ? bottom.h : (vertical > 0 ? vertical.h : (all > 0 ? all.h : 0)),
    );
  }

  // Performance-optimized widgets
  static Widget buildOptimizedImage(
    String imageUrl, {
    double? width,
    double? height,
    BoxFit fit = BoxFit.cover,
    Widget? placeholder,
    Widget? errorWidget,
  }) {
    return CachedNetworkImage(
      imageUrl: imageUrl,
      width: width,
      height: height,
      fit: fit,
      placeholder: (context, url) => placeholder ?? _buildDefaultPlaceholder(),
      errorWidget: (context, url, error) => errorWidget ?? _buildDefaultError(),
      memCacheWidth: width?.toInt(),
      memCacheHeight: height?.toInt(),
    );
  }

  static Widget _buildDefaultPlaceholder() {
    return Container(
      color: Colors.grey[300],
      child: const Center(
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(Colors.grey),
        ),
      ),
    );
  }

  static Widget _buildDefaultError() {
    return Container(
      color: Colors.grey[300],
      child: const Center(
        child: Icon(Icons.error, color: Colors.grey),
      ),
    );
  }

  // Debounced function calls for performance
  static Function debounce(Function function, {Duration delay = const Duration(milliseconds: 300)}) {
    Timer? timer;
    return () {
      if (timer?.isActive ?? false) timer?.cancel();
      timer = Timer(delay, function as void Function());
    };
  }

  // Throttled function calls for performance
  static Function throttle(Function function, {Duration interval = const Duration(milliseconds: 300)}) {
    bool isThrottled = false;
    return () {
      if (!isThrottled) {
        function();
        isThrottled = true;
        Timer(interval, () => isThrottled = false);
      }
    };
  }

  // Optimized scroll physics
  static const ScrollPhysics defaultScrollPhysics = BouncingScrollPhysics(
    parent: AlwaysScrollableScrollPhysics(),
  );

  static const ScrollPhysics fixedScrollPhysics = ClampingScrollPhysics(
    parent: AlwaysScrollableScrollPhysics(),
  );

  // Performance monitoring utilities
  static void logPerformance(String operation, DateTime startTime) {
    final duration = DateTime.now().difference(startTime);
    debugPrint('Performance: $operation took ${duration.inMilliseconds}ms');
  }

  static DateTime startPerformanceTimer() => DateTime.now();

  // Memory optimization hints
  static void disposeResources(List<dynamic> resources) {
    for (final resource in resources) {
      if (resource is AnimationController) {
        resource.dispose();
      } else if (resource is TextEditingController) {
        resource.dispose();
      } else if (resource is FocusNode) {
        resource.dispose();
      } else if (resource is ScrollController) {
        resource.dispose();
      }
    }
  }

  // Optimized list view builder
  static Widget buildOptimizedListView({
    required int itemCount,
    required IndexedWidgetBuilder itemBuilder,
    ScrollPhysics? physics,
    EdgeInsets? padding,
    bool shrinkWrap = false,
    double? itemExtent,
  }) {
    return ListView.builder(
      physics: physics ?? defaultScrollPhysics,
      padding: padding,
      shrinkWrap: shrinkWrap,
      itemExtent: itemExtent,
      itemCount: itemCount,
      itemBuilder: (context, index) {
        return OptimizedWidget(
          index: index,
          child: itemBuilder(context, index),
        );
      },
    );
  }
}

// Optimized widget wrapper for better performance
class OptimizedWidget extends StatelessWidget {
  final int index;
  final Widget child;

  const OptimizedWidget({
    super.key,
    required this.index,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return KeyedSubtree(
      key: ValueKey(index),
      child: child,
    );
  }
}

// Custom performance-aware scroll physics
class SmoothScrollPhysics extends BouncingScrollPhysics {
  const SmoothScrollPhysics({super.parent});

  @override
  SmoothScrollPhysics applyTo(ScrollPhysics? ancestor) {
    return SmoothScrollPhysics(parent: buildParent(ancestor));
  }

  @override
  SpringDescription get spring => const SpringDescription(
    mass: 50,
    stiffness: 100,
    damping: 1,
  );
}
