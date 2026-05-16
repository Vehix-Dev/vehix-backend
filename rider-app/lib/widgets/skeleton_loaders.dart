import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../utils/performance_utils.dart';

class SkeletonLoader extends StatelessWidget {
  final double width;
  final double height;
  final BorderRadius? borderRadius;

  const SkeletonLoader({
    super.key,
    required this.width,
    required this.height,
    this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: Colors.grey[300]!,
      highlightColor: Colors.grey[100]!,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: borderRadius ?? BorderRadius.circular(8),
        ),
      ),
    );
  }
}

class ServiceCardSkeleton extends StatelessWidget {
  const ServiceCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: PerformanceUtils.setPadding(horizontal: 16, vertical: 8),
      padding: PerformanceUtils.setPadding(all: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(25),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SkeletonLoader(
                width: PerformanceUtils.setWidth(48),
                height: PerformanceUtils.setHeight(48),
                borderRadius: BorderRadius.circular(24),
              ),
              SizedBox(width: PerformanceUtils.setWidth(12)),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SkeletonLoader(
                      width: PerformanceUtils.setWidth(120),
                      height: PerformanceUtils.setHeight(16),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    SizedBox(height: PerformanceUtils.setHeight(8)),
                    SkeletonLoader(
                      width: PerformanceUtils.setWidth(80),
                      height: PerformanceUtils.setHeight(12),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ],
                ),
              ),
            ],
          ),
          SizedBox(height: PerformanceUtils.setHeight(12)),
          SkeletonLoader(
            width: double.infinity,
            height: PerformanceUtils.setHeight(12),
            borderRadius: BorderRadius.circular(4),
          ),
          SizedBox(height: PerformanceUtils.setHeight(8)),
          SkeletonLoader(
            width: PerformanceUtils.setWidth(200),
            height: PerformanceUtils.setHeight(12),
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      ),
    );
  }
}

class RequestCardSkeleton extends StatelessWidget {
  const RequestCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: PerformanceUtils.setPadding(horizontal: 16, vertical: 8),
      padding: PerformanceUtils.setPadding(all: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              SkeletonLoader(
                width: PerformanceUtils.setWidth(100),
                height: PerformanceUtils.setHeight(14),
                borderRadius: BorderRadius.circular(4),
              ),
              SkeletonLoader(
                width: PerformanceUtils.setWidth(60),
                height: PerformanceUtils.setHeight(20),
                borderRadius: BorderRadius.circular(10),
              ),
            ],
          ),
          SizedBox(height: PerformanceUtils.setHeight(12)),
          SkeletonLoader(
            width: double.infinity,
            height: PerformanceUtils.setHeight(14),
            borderRadius: BorderRadius.circular(4),
          ),
          SizedBox(height: PerformanceUtils.setHeight(8)),
          SkeletonLoader(
            width: PerformanceUtils.setWidth(150),
            height: PerformanceUtils.setHeight(12),
            borderRadius: BorderRadius.circular(4),
          ),
          SizedBox(height: PerformanceUtils.setHeight(16)),
          Row(
            children: [
              Expanded(
                child: SkeletonLoader(
                  width: double.infinity,
                  height: PerformanceUtils.setHeight(40),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              SizedBox(width: PerformanceUtils.setWidth(12)),
              Expanded(
                child: SkeletonLoader(
                  width: double.infinity,
                  height: PerformanceUtils.setHeight(40),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class MapSkeleton extends StatelessWidget {
  const MapSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: PerformanceUtils.setHeight(300),
      margin: PerformanceUtils.setPadding(all: 16),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
      ),
      child: Shimmer.fromColors(
        baseColor: Colors.grey[300]!,
        highlightColor: Colors.grey[100]!,
        child: Stack(
          children: [
            // Map background skeleton
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.grey[200],
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
            // Location markers skeleton
            Positioned(
              top: PerformanceUtils.setHeight(80),
              left: PerformanceUtils.setWidth(100),
              child: SkeletonLoader(
                width: PerformanceUtils.setWidth(40),
                height: PerformanceUtils.setHeight(40),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
            Positioned(
              top: PerformanceUtils.setHeight(150),
              right: PerformanceUtils.setWidth(80),
              child: SkeletonLoader(
                width: PerformanceUtils.setWidth(40),
                height: PerformanceUtils.setHeight(40),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
            // Loading indicator
            const Center(
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.grey),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ProfileSkeleton extends StatelessWidget {
  const ProfileSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Avatar skeleton
        SkeletonLoader(
          width: PerformanceUtils.setWidth(100),
          height: PerformanceUtils.setHeight(100),
          borderRadius: BorderRadius.circular(50),
        ),
        SizedBox(height: PerformanceUtils.setHeight(16)),
        // Name skeleton
        SkeletonLoader(
          width: PerformanceUtils.setWidth(120),
          height: PerformanceUtils.setHeight(18),
          borderRadius: BorderRadius.circular(4),
        ),
        SizedBox(height: PerformanceUtils.setHeight(8)),
        // Email skeleton
        SkeletonLoader(
          width: PerformanceUtils.setWidth(180),
          height: PerformanceUtils.setHeight(14),
          borderRadius: BorderRadius.circular(4),
        ),
        SizedBox(height: PerformanceUtils.setHeight(24)),
        // Stats skeleton
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            Column(
              children: [
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(40),
                  height: PerformanceUtils.setHeight(20),
                  borderRadius: BorderRadius.circular(4),
                ),
                SizedBox(height: PerformanceUtils.setHeight(4)),
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(60),
                  height: PerformanceUtils.setHeight(12),
                  borderRadius: BorderRadius.circular(4),
                ),
              ],
            ),
            Column(
              children: [
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(40),
                  height: PerformanceUtils.setHeight(20),
                  borderRadius: BorderRadius.circular(4),
                ),
                SizedBox(height: PerformanceUtils.setHeight(4)),
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(60),
                  height: PerformanceUtils.setHeight(12),
                  borderRadius: BorderRadius.circular(4),
                ),
              ],
            ),
            Column(
              children: [
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(40),
                  height: PerformanceUtils.setHeight(20),
                  borderRadius: BorderRadius.circular(4),
                ),
                SizedBox(height: PerformanceUtils.setHeight(4)),
                SkeletonLoader(
                  width: PerformanceUtils.setWidth(60),
                  height: PerformanceUtils.setHeight(12),
                  borderRadius: BorderRadius.circular(4),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }
}

class ChatSkeleton extends StatelessWidget {
  const ChatSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Received message skeleton
        Row(
          children: [
            SkeletonLoader(
              width: PerformanceUtils.setWidth(32),
              height: PerformanceUtils.setHeight(32),
              borderRadius: BorderRadius.circular(16),
            ),
            SizedBox(width: PerformanceUtils.setWidth(8)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SkeletonLoader(
                    width: PerformanceUtils.setWidth(200),
                    height: PerformanceUtils.setHeight(40),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(20),
                      topRight: Radius.circular(20),
                      bottomRight: Radius.circular(20),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        SizedBox(height: PerformanceUtils.setHeight(12)),
        // Sent message skeleton
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  SkeletonLoader(
                    width: PerformanceUtils.setWidth(180),
                    height: PerformanceUtils.setHeight(40),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(20),
                      topRight: Radius.circular(20),
                      bottomLeft: Radius.circular(20),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(width: PerformanceUtils.setWidth(8)),
            SkeletonLoader(
              width: PerformanceUtils.setWidth(32),
              height: PerformanceUtils.setHeight(32),
              borderRadius: BorderRadius.circular(16),
            ),
          ],
        ),
      ],
    );
  }
}

class LoadingOverlay extends StatelessWidget {
  final bool isLoading;
  final Widget child;
  final String? message;

  const LoadingOverlay({
    super.key,
    required this.isLoading,
    required this.child,
    this.message,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,
        if (isLoading)
          Container(
            color: Colors.black.withValues(alpha: 0.3),
            child: Center(
              child: Card(
                child: Padding(
                  padding: PerformanceUtils.setPadding(all: 24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(),
                      if (message != null) ...[
                        SizedBox(height: PerformanceUtils.setHeight(16)),
                        Text(
                          message!,
                          style: TextStyle(
                            fontSize: PerformanceUtils.setFont(14),
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
