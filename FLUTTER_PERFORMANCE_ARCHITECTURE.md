# Vehix Flutter Performance Architecture

## Recommended Folder Structure (UI-Focused)

```
lib/
├── main_v2.dart                    # App entry — ProviderScope + Hive init
│
├── core/
│   ├── theme/
│   │   └── app_theme.dart          # Colors, spacing, radius, shadows, curves, ThemeData
│   ├── constants/
│   │   └── app_constants.dart      # API URLs, timing, cache keys, distances
│   ├── cache/
│   │   └── cache_manager.dart      # Hive wrapper — location, profile, job state
│   ├── utils/
│   │   ├── debouncer.dart          # Debouncer + Throttler classes
│   │   └── isolate_helpers.dart    # JSON parsing, distance filtering in isolates
│   └── providers/
│       ├── auth_provider.dart      # AuthNotifier — tokens, profile, login state
│       ├── socket_provider.dart    # SocketNotifier — WS connection, messages, offers
│       ├── map_provider.dart       # MapNotifier — camera, markers, polylines, animation
│       ├── ui_provider.dart        # UiNotifier — buttons, phases, loading, errors
│       └── location_provider.dart  # LocationNotifier — GPS, tracking, caching
│
├── widgets/
│   ├── optimized_map.dart          # GoogleMap built ONCE + 60fps marker ticker
│   ├── skeleton_loader.dart        # Shimmer skeletons (card, list, home)
│   ├── animated_service_card.dart  # Staggered entrance + selection animation (Rider)
│   ├── premium_bottom_sheet.dart   # Searching panel + matched roadie panel (Rider)
│   ├── connection_banner.dart      # Animated WS status banner
│   ├── offer_dialog.dart           # Countdown timer + audio + vibration (Roadie)
│   └── online_toggle.dart          # Glow effect online/offline toggle (Roadie)
│
├── screens/
│   ├── home_screen_v2.dart         # Main screen — map + overlays + bottom panel
│   ├── ... (existing screens)
│
└── services/
    └── api_service.dart            # Existing — fully compatible with new architecture
```

---

## Architecture: Separated State Concerns

| Provider | Scope | What It Holds | Rebuild Trigger |
|----------|-------|---------------|-----------------|
| `authProvider` | Global | Tokens, user profile, login state | Login/logout, profile fetch |
| `socketProvider` | Global | WS connection, raw messages, offers | Every WS message (throttled) |
| `mapProvider` | Global | Markers, polylines, camera, controller | Location updates (debounced) |
| `uiProvider` | Global | Loading, phases, selection, errors | User interaction only |
| `locationProvider` | Global | GPS position, tracking status | GPS stream |

### Derived Providers (Scoped Rebuilds)

```dart
// Only rebuilds when request phase changes — not on every socket message
final requestPhaseProvider = Provider<RequestPhase>((ref) {
  return ref.watch(uiProvider.select((s) => s.requestPhase));
});

// Only rebuilds when online status changes
final isOnlineProvider = Provider<bool>((ref) {
  return ref.watch(uiProvider.select((s) => s.isOnline));
});

// Only rebuilds when an offer arrives/clears
final activeOfferProvider = Provider<Map<String, dynamic>?>((ref) {
  return ref.watch(socketProvider.select((s) => s.activeOffer));
});
```

---

## Performance Patterns Applied

### 1. Map Optimization
- **GoogleMap built once** — `OptimizedMapWidget` uses `select()` to only watch markers/polylines
- **Marker updates are differential** — only changed markers are replaced, not the full set
- **Smooth marker interpolation** — `Ticker` at 60fps with ease-out cubic curve
- **Preloaded BitmapDescriptor** — assets loaded once at init, reused for all markers
- **Dark map style** — JSON style applied directly, no runtime processing

### 2. Debounce/Throttle
- **Location updates throttled** at 500ms — max 2 updates/sec to UI
- **Marker rebuilds debounced** at 300ms — batches rapid socket messages
- **State changes** only fire when values actually differ

### 3. RepaintBoundary Isolation
Applied to:
- `OptimizedMapWidget` — map repaints don't cascade to overlays
- `ConnectionBanner` — status changes don't repaint map
- `_TopBarOverlay` — greeting/latency isolated from bottom panel
- `OnlineToggle` — toggle animation isolated from parent
- `OfferDialog` — countdown timer isolated from map

### 4. Isolate Offloading
- `parseJsonInIsolate()` — large JSON responses parsed off main thread
- `filterNearbyInIsolate()` — haversine distance filtering for bulk roadie lists
- Keeps main thread free for 60fps rendering

### 5. Hive Caching (Instant Startup)
Cached on every update:
- Last known location → map shows instantly on launch
- User profile → greeting shows instantly
- Services list → cards show instantly from cache, refresh in background
- Online status (Roadie) → toggle state preserved across restarts
- Job state → active job UI restored on crash recovery

### 6. Widget Optimization
- `const` constructors on all stateless leaf widgets
- `AnimatedSwitcher` instead of conditional widget swaps
- `ListView.builder` for scrollable lists (lazy rendering)
- No `Opacity` widgets — use `Color.withOpacity()` instead
- No unnecessary `ClipRRect` — use `BoxDecoration` with borderRadius

### 7. Animation Strategy
- `flutter_animate` for staggered entrances and micro-interactions
- `AnimatedContainer` for smooth property transitions (color, size, border)
- `AnimatedSwitcher` for content swaps with fade/slide
- `Ticker` for 60fps marker interpolation (not `Timer`)
- All animations use `Curves.easeOutCubic` for premium feel

---

## Production Checklist

### Before Release
- [ ] Add Google Maps API key to `AndroidManifest.xml` and `AppDelegate.swift`
- [ ] Add marker icon assets: `assets/icons/roadie_marker.png`, `rider_marker.png`, `roadie_selected_marker.png`
- [ ] Add sound asset: `assets/sounds/offer_alert.mp3`
- [ ] Run `flutter pub get` in both apps
- [ ] Test with `flutter run --profile` to check frame times
- [ ] Enable Flutter DevTools performance overlay during QA

### Performance Targets
- [ ] Startup to interactive: < 2 seconds (cached data shows immediately)
- [ ] Map render: < 500ms (preloaded icons, single build)
- [ ] Marker update latency: < 300ms (debounced, differential)
- [ ] Frame budget: < 16ms per frame (60fps target)
- [ ] WebSocket reconnect: < 5s with exponential backoff
- [ ] Memory: No leaked subscriptions (all cancelled in dispose)

### Frame Rate Validation
```bash
# Profile mode — check for janky frames
flutter run --profile

# In DevTools, check:
# - Build phase: < 8ms
# - Paint phase: < 4ms  
# - No red frames in timeline
```

### Memory Leak Prevention
- All `StreamSubscription` cancelled in `dispose()`
- All `Timer` cancelled in `dispose()`
- All `Ticker` disposed in `dispose()`
- `Debouncer.dispose()` called in notifier dispose
- `GoogleMapController.dispose()` called in MapNotifier dispose
- `AudioPlayer.dispose()` called in OfferDialog dispose

---

## Migration Guide

### Step 1: Update Dependencies
Both `pubspec.yaml` files already updated. Run:
```bash
cd rider-app && flutter pub get
cd ../roadie_app && flutter pub get
```

### Step 2: Add Google Maps API Key

**Android** — `android/app/src/main/AndroidManifest.xml`:
```xml
<meta-data
    android:name="com.google.android.geo.API_KEY"
    android:value="YOUR_GOOGLE_MAPS_API_KEY"/>
```

**iOS** — `ios/Runner/AppDelegate.swift`:
```swift
GMSServices.provideAPIKey("YOUR_GOOGLE_MAPS_API_KEY")
```

### Step 3: Add Assets
Create these files:
```
assets/icons/roadie_marker.png    (40x40, 2x, 3x)
assets/icons/rider_marker.png     (44x44, 2x, 3x)
assets/icons/roadie_selected_marker.png (48x48, 2x, 3x)
assets/sounds/offer_alert.mp3
```

Update `pubspec.yaml`:
```yaml
flutter:
  assets:
    - assets/icons/
    - assets/sounds/
```

### Step 4: Switch Entry Point
Change `main.dart` imports to use `main_v2.dart`, or rename:
```bash
# Option A: Update launch config to use main_v2.dart
# Option B: Replace main.dart with main_v2.dart content
```

### Step 5: Gradual Screen Migration
Existing screens continue to work. Migrate one at a time:
1. Replace `flutter_map` with `OptimizedMapWidget` in each screen
2. Replace `setState` calls with `ref.read(provider.notifier).method()`
3. Replace `FutureBuilder` with `ref.watch(asyncProvider)`
4. Add `RepaintBoundary` around heavy widgets

---

## Key Files Created

### Rider App (rider-app/lib/) — 22 files

#### Core Architecture
| File | Purpose |
|------|---------|
| `core/theme/app_theme.dart` | Premium dark theme (blue accent) |
| `core/constants/app_constants.dart` | API URLs, timing, cache keys |
| `core/utils/debouncer.dart` | Debouncer + Throttler |
| `core/utils/isolate_helpers.dart` | JSON parsing + distance in isolates |
| `core/cache/cache_manager.dart` | Hive wrapper for instant startup |
| `core/providers/auth_provider.dart` | JWT auth + cached profile |
| `core/providers/socket_provider.dart` | WebSocket with throttled updates |
| `core/providers/map_provider.dart` | Markers with smooth interpolation |
| `core/providers/ui_provider.dart` | UI-only state (phases, loading) |
| `core/providers/location_provider.dart` | GPS + auto-cache |
| `core/providers/providers.dart` | Barrel export for all providers |

#### Widgets
| File | Purpose |
|------|---------|
| `widgets/optimized_map.dart` | Google Maps — built once, 60fps ticker |
| `widgets/skeleton_loader.dart` | Shimmer skeletons (card, list, home) |
| `widgets/animated_service_card.dart` | Staggered service cards |
| `widgets/premium_bottom_sheet.dart` | Searching + matched roadie panels |
| `widgets/connection_banner.dart` | WS status banner |
| `widgets/ride_tracking_panel.dart` | ETA tracker, progress stepper, action bar |
| `widgets/chat_widget.dart` | Real-time chat with smooth animations |
| `widgets/rating_widget.dart` | Animated star rating + feedback |
| `widgets/app_drawer_v2.dart` | Premium navigation drawer |

#### Screens
| File | Purpose |
|------|---------|
| `screens/home_screen_v2.dart` | Full home screen rewrite (map + overlays) |
| `screens/wallet_screen_v2.dart` | Premium wallet with balance + transactions |
| `screens/history_screen_v2.dart` | Ride history with filters + animations |
| `screens/notifications_screen_v2.dart` | Animated notification list |
| `screens/profile_screen_v2.dart` | Premium profile with stats + actions |
| `main_v2.dart` | App entry with Riverpod + Hive |

### Roadie App (roadie_app/lib/) — 23 files

#### Core Architecture
| File | Purpose |
|------|---------|
| `core/theme/app_theme.dart` | Premium dark theme (green accent) |
| `core/constants/app_constants.dart` | API URLs, timing, cache keys |
| `core/utils/debouncer.dart` | Debouncer + Throttler |
| `core/utils/isolate_helpers.dart` | JSON parsing + distance in isolates |
| `core/cache/cache_manager.dart` | Hive wrapper + online status cache |
| `core/providers/auth_provider.dart` | JWT auth + cached profile |
| `core/providers/socket_provider.dart` | WebSocket with offer handling |
| `core/providers/map_provider.dart` | Markers with rider interpolation |
| `core/providers/ui_provider.dart` | UI state with job phases |
| `core/providers/location_provider.dart` | GPS + continuous tracking |
| `core/providers/providers.dart` | Barrel export for all providers |

#### Widgets
| File | Purpose |
|------|---------|
| `widgets/optimized_map.dart` | Google Maps — built once, 60fps ticker |
| `widgets/skeleton_loader.dart` | Shimmer skeletons |
| `widgets/connection_banner.dart` | WS status banner |
| `widgets/offer_dialog.dart` | Animated offer with countdown + audio |
| `widgets/online_toggle.dart` | Glowing online/offline toggle |
| `widgets/ride_tracking_panel.dart` | ETA tracker, stepper, earnings summary |
| `widgets/chat_widget.dart` | Real-time chat with smooth animations |
| `widgets/rating_widget.dart` | Animated star rating + feedback |
| `widgets/app_drawer_v2.dart` | Premium drawer with online badge |

#### Screens
| File | Purpose |
|------|---------|
| `screens/home_screen_v2.dart` | Full home screen rewrite (map + offers) |
| `screens/wallet_screen_v2.dart` | Premium wallet with deposit/withdraw |
| `screens/history_screen_v2.dart` | Job history with filters + animations |
| `screens/notifications_screen_v2.dart` | Animated notification list |
| `screens/profile_screen_v2.dart` | Premium profile with services + stats |
| `main_v2.dart` | App entry with Riverpod + Hive |

### Shared
| File | Purpose |
|------|---------|
| `FLUTTER_PERFORMANCE_ARCHITECTURE.md` | This document |
