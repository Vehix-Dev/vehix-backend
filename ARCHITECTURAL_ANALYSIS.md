# VEHIX Ride-Sharing Platform - Complete Architectural Analysis

**Generated:** March 3, 2026  
**Scope:** Django Backend + Flutter Rider App + Flutter Roadie/Driver App

---

## TABLE OF CONTENTS
1. [Backend Architecture](#backend-architecture)
2. [API Endpoints](#api-endpoints)
3. [Authentication & Authorization](#authentication--authorization)
4. [Rider App Architecture](#rider-app-architecture)
5. [Roadie/Driver App Architecture](#roadiedriver-app-architecture)
6. [Integration Points](#integration-points)
7. [Critical Issues & Bugs](#critical-issues--bugs)
8. [Missing Features](#missing-features)
9. [Data/API Mismatches](#dataapi-mismatches)
10. [Recommendations](#recommendations)

---

## BACKEND ARCHITECTURE

### Database Models & Relationships

#### **Authentication & Users**
- **User** (`users/models.py:1-135`)
  - Fields: `username`, `email`, `password`, `phone`, `role`, `first_name`, `last_name`, `is_active`, `is_deleted`, `is_online`, `is_approved`, `nin`, `external_id`, `referral_code`, `lat`, `lng`, `current_login_id`
  - Roles: `RIDER`, `RODIE`, `MECHANIC`, `ADMIN`
  - Auto-generates: `external_id` (R001, BS001, IT001), `referral_code` (VX001)
  - **Single device login enforcement** via `current_login_id` UUID field
  - Status: created_at, updated_at (auto-tracked)

- **RiderAvailabilityLog** (`users/models.py:136-152`)
  - Tracks when riders go online/offline
  - Fields: `went_online_at`, `went_offline_at`, `device_type` (IOS, ANDROID)
  - **Note:** No corresponding RodieAvailabilityLog model exists

#### **Wallet & Payments**
- **Wallet** (`users/models.py:153-158`)
  - One-to-One with User
  - Fields: `balance` (Decimal)
  - **Default:** 0 balance

- **WalletTransaction** (`users/models.py:166-172`)
  - Tracks all wallet movements
  - Fields: `amount`, `reason`, `created_at`
  - Links all money movements to audit trail

- **Payment** (`users/models.py:219-241`)
  - Handles deposits/withdrawals
  - Types: `DEPOSIT`, `WITHDRAWAL`
  - Status: `PENDING`, `COMPLETED`, `FAILED`, `CANCELLED`
  - Integration: Pesapal (processor_id stores tracking ID)
  - **Issue:** Incomplete callback handling for payment status updates

#### **Service & Request Management**
- **ServiceType** (`services/models.py:1-22`)
  - Fields: `name`, `code`, `category` (BASIC, MECHANIC), `fixed_price`, `image`, `is_active`
  - Available services offered on platform

- **RodieService** (`services/models.py:24-40`)
  - Many-to-Many relationship between Rodie and ServiceType
  - Denormalization of services each roadie offers
  - Unique constraint: (rodie, service)

- **ServiceRequest** (`requests/models.py:1-75`)
  - Core request model
  - **Status Workflow:** REQUESTED → ACCEPTED → EN_ROUTE → STARTED → COMPLETED (or CANCELLED/EXPIRED)
  - Fields:
    - Rider FK (required)
    - Rodie FK (nullable, set on acceptance)
    - Service Type FK
    - Location: `rider_lat`, `rider_lng`
    - Timestamps: `created_at`, `accepted_at`, `en_route_at`, `started_at`, `completed_at`
    - Payment: `fee_charged`, `is_paid`
  - **Validation:** Checks wallet balance prevents creating requests below max_negative_balance
  - **Signal Handler:** Auto-charges rodie service fee on COMPLETED status

- **ChatMessage** (`requests/models_chat.py:1-10`)
  - FK to ServiceRequest
  - FK to User (sender)
  - Text message with created_at timestamp
  - **No history pagination:** Frontend loads without endpoint for full history

#### **Location Services**
- **RodieLocation** (`locations/models.py:1-10`)
  - One-to-One with Rodie User
  - Fields: `lat`, `lng`, `updated_at`
  - **Fallback strategy:** Backend also stores lat/lng in User model
  - **Cache layer:** Redis cache at `rodie_loc:{user_id}` with 5-min TTL

#### **Business Onboarding**
- **Garage** (`garages/models.py:1-199`)
  - Comprehensive business registration model
  - **Verification Workflow:** SUBMITTED → UNDER_REVIEW → VERIFIED (or REJECTED/SUSPENDED)
  - Fields (65+):
    - Business identity: name, type, address, coordinates, operating_hours (JSON)
    - Owner details: name, national_id, contact, ID photos, emergency contact
    - Manager details (optional)
    - Legal documents: registration cert, TIN, trading license, authority letter
    - Photos: exterior, interior workshop, tools/equipment
    - Services: vehicle_types, services_offered, services_not_offered (JSON arrays)
    - Pricing: pricing_info (JSON), negotiable flag
    - Staff: mechanics_count, certifications, skills
    - Policies: warranty, turnaround time, emergency service, working days, cancellation policy
    - Payments: method (MOBILE_MONEY, BANK_TRANSFER), account details, settlement preference
    - Compliance: terms acceptance, IP tracking
    - Admin: verification_by (FK to User), verified_at, rejection_reason
  - **Submission tracking:** Application tracking ID, completion percentage
  - **Note:** Business onboarding exists but no API endpoints visible in urls.py

#### **Notifications & Referrals**
- **Notification** (`users/models.py:159-174`)
  - User-specific or broadcast
  - Fields: `title`, `body`, `data` (JSON), `read`, `broadcast`, `target_role`
  - Real-time delivery via WebSocket

- **Referral** (`users/models.py:175-180`)
  - Tracks referrer → referred relationships
  - Amount field tracks referral bonus

- **PlatformConfig** (`users/models.py:204-216`)
  - Singleton-like configuration
  - **Settings:**
    - `max_negative_balance`: Minimum balance allowed (prevents poor users from requesting)
    - `service_fee`: Fee charged to rodie on service completion
    - `trial_days`: Free trial period for trial_days from registration
    - Mechanic transition documents (JSON list)
  - Updated dynamically via admin API

#### **Images/KYC**
- **UserImage** (`images/models.py:1-90`)
  - Types: PROFILE, NIN_FRONT, NIN_BACK, LICENSE, VEHICLE, OTHER
  - Stores original and thumbnail
  - Status: APPROVED, REJECTED
  - Metadata: file_size, width, height, mime_type, storage_path

### Architecture Patterns

**Authentication:**
- JWT tokens (simplejwt) with custom serializer
- Token includes `login_id` for single-device enforcement
- Very long expiry (50 years) for mobile apps
- Role-based custom tokens: RiderTokenObtainPairSerializer, RoadieTokenObtainPairSerializer

**Real-time Communication:**
- Django Channels with Redis backend
- WebSocket consumers for: RodieConsumer, RiderConsumer, AdminConsumer
- Groups: `rodie_{user_id}`, `rider_{user_id}`, `admin_monitoring`, `role_{role}`, `request_{request_id}`

**Caching Strategy:**
- Redis for ephemeral data:
  - `rodie_loc:{user_id}` - location (5 min TTL)
  - `rider_loc:{user_id}` - location (5 min TTL)
  - `active_offer:{user_id}` - pending request offer
  - `request_status:{request_id}` - request status (3600 sec TTL)
  - `request_status:{request_id}` - decline status (300 sec)

**Notification Delivery:**
- Database-backed (Notification model)
- Channel-based push via WebSocket
- Broadcast capability for admin announcements

---

## API ENDPOINTS

### Authentication Endpoints
```
POST   /api/register/                              - Register new user
POST   /api/login/                                 - Generic login (role must match)
POST   /api/login/rider/                           - Rider-specific login (enforces RIDER role)
POST   /api/login/roadie/                          - Rodie-specific login (enforces RODIE role)
POST   /api/refresh/                               - Refresh JWT token
GET    /api/me/                                    - Get current user profile
POST   /api/auth/admin/login/                      - Admin login
POST   /api/auth/admin/register/                   - Register admin (auth only)
```

**Issue:** There is NO /api/login/<role>/ endpoint - apps call `/login/rider/` and `/login/roadie/` but these are not in urls.py. Looking at tokens.py, these classes exist but URLs are missing from urls.py at lines 50-51!

### User Management Endpoints
```
GET    /api/me/                                    - Current user info
GET    /api/wallet/                                - Get wallet (MyWalletView)
POST   /api/wallet/deposit/                        - Initiate deposit (DepositView)
POST   /api/wallet/withdraw/                       - Initiate withdrawal (WithdrawView)
POST   /api/payments/pesapal/ipn/                  - Pesapal webhook (IPN)
GET    /api/referrals/                             - My referrals (MyReferralsView)
POST   /api/roadie/status/                         - Update rodie online/offline status
```

### Rodie Status & Services
```
POST   /api/roadie/status/                         - Set is_online (true/false)
GET    /api/auth/rodie/services/                   - Get rodie's available services
POST   /api/auth/rodie/services/                   - Update rodie's services (accepts service_ids array)
```

### Service Management (Admin & Riders)
```
GET    /api/services/                              - List active services (ServiceTypeListView)
GET    /api/auth/admin/services/                   - Create/list (admin)
PUT    /api/auth/admin/services/<id>/              - Update service
DELETE /api/auth/admin/services/<id>/              - Delete service
GET    /api/auth/admin/rodie-services/             - List all rodie service assignments
POST   /api/auth/admin/rodie-services/             - Create assignment
PUT    /api/auth/admin/rodie-services/<id>/        - Update
DELETE /api/auth/admin/rodie-services/<id>/        - Delete
```

### Service Request Endpoints (Core Feature)
```
POST   /api/requests/create/                       - Create new request (rider)
GET    /api/requests/my/                           - Get rider's requests
GET    /api/requests/roadie/                       - Get rodie's assigned requests
GET    /api/requests/nearby/?lat=&lng=&service_id= - Find nearby rodies (rider)
POST   /api/requests/<id>/accept/                  - Accept request (rodie)
POST   /api/requests/<id>/decline/                 - Decline request (rodie)
POST   /api/requests/<id>/cancel/                  - Cancel request (rider/rodie)
POST   /api/requests/<id>/enroute/                 - Mark en-route (rodie)
POST   /api/requests/<id>/start/                   - Start service (rodie)
POST   /api/requests/<id>/complete/                - Complete service (rodie)
POST   /api/requests/<id>/chat/                    - Send chat message
POST   /api/requests/<id>/assign/                  - Admin assign rodie
GET    /api/requests/<id>/route/                   - Get route info
```

**Issue:** Rider app calls `/requests/create/` but backend pattern matches only `/create/` under `/api/requests/` prefix in urls.py

### Chat
```
POST   /api/requests/<id>/chat/                    - Broadcast chat message
```
**Issue:** No GET endpoint for chat history! Chats are only pushed via WebSocket, not retrievable via REST API

### Notification Endpoints
```
GET    /api/notifications/                         - List my notifications
POST   /api/notifications/                         - Create notification
GET    /api/notifications/<id>/                    - Retrieve notification
PUT    /api/notifications/<id>/                    - Update (mark read)
DELETE /api/notifications/<id>/                    - Delete
POST   /api/auth/admin/notifications/              - Admin create broadcast
```

### Image Upload/KYC
```
POST   /api/images/user-images/                    - Upload user image (multipart)
```
**Note:** Endpoint not found in urls.py! Rider app expects this but it's not routed.

### Platform Configuration
```
GET    /api/auth/platform/config/                  - Get platform config (public)
POST   /api/auth/platform/config/                  - Update config (admin)
```

### Admin Endpoints
```
GET    /api/auth/admin/riders/                     - List all riders
POST   /api/auth/admin/riders/                     - Create rider
GET    /api/auth/admin/riders/<id>/                - Get rider
PUT    /api/auth/admin/riders/<id>/                - Update rider
DELETE /api/auth/admin/riders/<id>/                - Delete rider

GET    /api/auth/admin/roadies/                    - List all rodies
POST   /api/auth/admin/roadies/                    - Create rodie
GET    /api/auth/admin/roadies/<id>/               - Get rodie
PUT    /api/auth/admin/roadies/<id>/               - Update rodie
DELETE /api/auth/admin/roadies/<id>/               - Delete rodie

GET    /api/auth/admin/users/                      - List all users
GET    /api/auth/admin/users/deleted/              - List deleted users
POST   /api/auth/admin/users/<id>/restore/         - Restore soft-deleted user

GET    /api/auth/admin/requests/                   - List all requests
POST   /api/auth/admin/requests/<id>/assign/       - Assign rodie to request

GET    /api/auth/admin/wallets/                    - Wallet management
POST   /api/auth/admin/wallets/                    - Create wallet
GET    /api/auth/admin/referrals/                  - Referral management

GET    /api/auth/admin/riders/realtime/            - Real-time rider locations (Admin)
GET    /api/auth/admin/requests/realtime/          - Real-time request tracking (Admin)
GET    /api/auth/admin/requests/realtime/map/      - Map view of requests (Admin)
GET    /api/auth/admin/locations/realtime/         - Realtime locations (Admin)
GET    /api/auth/admin/locations/realtime/map/     - Map view of locations (Admin)
```

### WebSocket Endpoints
```
WS     /ws/rodie/?token=<jwt>                      - Rodie consumer (listen for offers)
WS     /ws/rider/?token=<jwt>                      - Rider consumer (listen for updates)
WS     /ws/admin/?token=<jwt>                      - Admin consumer (monitoring)
WS     /ws/availability/                            - Availability tracking (not in routing.py but defined)
```

---

## AUTHENTICATION & AUTHORIZATION

### Token Generation & Validation
- **serializer:** CustomTokenObtainPairSerializer adds `login_id` to JWT payload
- **Verification:** CustomJWTAuthentication checks token's login_id against user.current_login_id
  - **Single-device enforcement:** If another device logs in, old session becomes invalid
  - **Implementation location:** [users/authentication.py](users/authentication.py#L1-L25)

### Role-Based Access Control
```python
ROLE_CHOICES = {
    'RIDER':    'Rider',      # Request service
    'RODIE':    'Rodie',      # Provide service (roadside assistance)
    'MECHANIC': 'Mechanic',   # Can also provide services
    'ADMIN':    'Admin',      # Platform administration
}
```

### Permission Models
- **IsAuthenticated:** Most endpoints require authentication
- **AllowAny:** Registration, login, platform config GET
- **Custom Role Checks:** Views explicitly verify `request.user.role`

### Wallet-Based Access Control
- Users with wallet balance below `-max_negative_balance` cannot:
  - Create new requests (rider)
  - Accept requests (rodie)
  - Both checked in `clean()` method and view logic

### Issues
1. **No explicit permission classes in many views** - rely on manual role checks
2. **Admin status not enforced** - only checked in token serializer
3. **No DRF-compatible permissions** for fine-grained control
4. **Token expiry:** Set to 50 years (impractical, should be 24-48 hours with refresh)

---

## RIDER APP ARCHITECTURE

### Directory Structure
```
rider-app/lib/
├── screens/
│   ├── login_screen.dart         - Username/password login
│   ├── register_screen.dart      - Registration form (7 fields + NIN)
│   ├── home_screen.dart          - Map + service list
│   ├── service_detail_screen.dart - Service details & booking
│   ├── requesting_screen.dart    - Waiting for rodie acceptance
│   ├── ride_screen.dart          - Active ride with chat & tracking
│   ├── rating_screen.dart        - Rate rodie (no API call visible)
│   ├── wallet_screen.dart        - Balance & transaction history
│   ├── profile_screen.dart       - User info & document uploads
│   ├── history_screen.dart       - Past requests
│   ├── referrals_screen.dart     - Referral program
│   ├── help_screen.dart          - FAQs/support
│   └── splash_screen.dart        - App initialization
└── services/
    ├── api_service.dart          - REST API client
    └── websocket_service.dart    - Real-time communication
```

### Key Screens & Functionality

#### **LoginScreen** ([rider-app/lib/screens/login_screen.dart](rider-app/lib/screens/login_screen.dart#L1-L50))
- **Inputs:** Username, Password
- **Action:** Calls `ApiService.login(username, password, 'RIDER')`
- **Flow:** Success → HomeScreen
- **Issues:**
  - No phone/email recovery
  - Error messages generic ("Check console logs")

#### **RegisterScreen** ([rider-app/lib/screens/register_screen.dart](rider-app/lib/screens/register_screen.dart#L1-L100))
- **Inputs:** firstName, lastName, username, email, phone, NIN (14 chars), password
- **Action:** Calls `ApiService.signup(...)` then auto-logs in
- **Validation:** Basic form validation (no regex patterns visible)
- **Issue:** No email verification
- **Call:** `POST /api/register/` but backend expects `role` field!
  - **Bug:** Rider app doesn't send role in registration body

#### **HomeScreen** ([rider-app/lib/screens/home_screen.dart](rider-app/lib/screens/home_screen.dart#L1-L150))
- **Components:**
  - FlutterMap with current location marker
  - Service list grid
  - AppBar with notifications icon (non-functional)
- **Behavior:**
  1. Requests location permission → Gets GPS via geolocator
  2. Connects to WebSocket for real-time updates
  3. Fetches services list via `ApiService.getServices()`
  4. Sends location every 8 seconds to WebSocket
- **Issues:**
  - `_fetchServices()` call visible but `getServices()` implementation shows map parsing issues
  - Fallback to /services/ endpoint that might not return proper format

#### **ServiceDetailScreen** ([rider-app/lib/screens/service_detail_screen.dart](rider-app/lib/screens/service_detail_screen.dart#L1-L100))
- **Displays:**
  - Service name (hero animation)
  - Description
  - Current location (with coordinates)
  - Optional notes textbox
- **Action:** `_bookService()` → `createRequest(serviceTypeId, lat, lng, notes)`
- **Success:** Navigate to RequestingScreen with request ID
- **Issue:** No error handling for location unavailability beyond showing snackbar

#### **RequestingScreen** ([rider-app/lib/screens/requesting_screen.dart](rider-app/lib/screens/requesting_screen.dart#L1-L100))
- **Display:** Animated "Requesting..." with pulsing WiFi icon
- **Real-time Updates:** Listens for REQUEST_UPDATE and REQUEST_PROXIMITY events
- **Transitions:**
  - ACCEPTED → RideScreen
  - EXPIRED → PopUp + Navigator.pop()
- **Shows:** Distance and ETA to nearest rodie (if REQUEST_PROXIMITY received)
- **Issue:** No manual cancellation button during request wait

#### **RideScreen** ([rider-app/lib/screens/ride_screen.dart](rider-app/lib/screens/ride_screen.dart#L1-L150))
- **Components:**
  - FlutterMap with rider and rodie markers
  - Chat input field
  - Phone call button (uses url_launcher)
  - Start/Complete assist buttons (roadie only)
- **Real-time:** Receives RODIE_LOCATION, RIDER_LOCATION, CHAT_MESSAGE, REQUEST_UPDATE
- **Behavior:**
  1. Parses initial locations from request object
  2. Sends location every 5 seconds
  3. Maps center between both parties
- **Issue:** Completion request triggers rating navigation but no rating API call shown
- **Issue:** Cannot pop/leave screen (PopScope prevents it)

#### **RatingScreen** (referenced but not fully analyzed)
- **Expected:** Submit rider feedback/rating to rodie
- **Issue:** No API endpoint for submitting ratings visible

#### **WalletScreen** ([rider-app/lib/screens/wallet_screen.dart](rider-app/lib/screens/wallet_screen.dart#L1-L50))
- **Display:** Balance card, transaction history
- **Fetch:** `ApiService.getWallet()` → `/api/wallet/`
- **Actions:** Deposit & Withdraw buttons (UI only, no implementation)
- **Issue:** Transaction list shows raw data, no formatting
- **Issue:** Deposit/Withdraw not fully integrated

#### **ProfileScreen** ([rider-app/lib/screens/profile_screen.dart](rider-app/lib/screens/profile_screen.dart#L1-L60))
- **Display:** Avatar, username, email, phone, wallet balance
- **Upload:** Calls `ApiService.uploadUserImage(file, type)` for profile, NIN, etc.
- **Issue:** Endpoint `/api/images/user-images/` not found in backend urls.py

### API Service Implementation
([rider-app/lib/services/api_service.dart](rider-app/lib/services/api_service.dart#L1-L378))

**Features:**
- Retry logic (max 3 retries with 2-sec delay)
- JWT token storage in SharedPreferences
- Automatic logout on 401 responses
- Token payload parsing for offline data

**Key Methods:**
```dart
login(username, password, role)           → /api/login/{role}/
signup(...7 fields...)                    → /api/register/
getServices()                             → /api/services/
getWallet()                               → /api/wallet/
createRequest(serviceId, lat, lng, notes) → /api/requests/create/
uploadUserImage(file, type)               → /api/images/user-images/
```

**Issues:**
1. `/api/requests/create/` → Should be `/api/requests/create/` (CORRECT)
2. `/api/images/user-images/` → Not in backend (BROKEN)
3. `/api/referrals/` → Backend path is `/api/referrals/` (CORRECT)
4. `/api/services/` → Returns array or paginated (needs parsing)
5. No error responses differentiation - all failures treated the same

### WebSocket Service
([rider-app/lib/services/websocket_service.dart](rider-app/lib/services/websocket_service.dart#L1-L110))

**URL Pattern:** `wss://backend.vehix.ug/ws/{role}/?token=<jwt>`
- Maps "RIDER" → "rider", "RODIE" → "rodie"

**Features:**
- Auto-reconnect with exponential backoff (5 attempts max, 5-25 sec delays)
- Ping every 25 seconds to keep connection alive
- Custom message types:
  - LOCATION: `{type, lat, lng}`
  - CHAT: `{type, request_id, text}`
  - Custom: Any JSON data

**Issue:** Hardcoded `backend.vehix.ug` URL in WebSocketService prevents local testing

### State Management Approach
- **Pattern:** StatefulWidgets with setState()
- **No external state management** (Provider, Riverpod, BLoC)
- **Issues:**
  1. No shared state between screens
  2. No caching of user data
  3. Expensive rebuilds on every location update
  4. No offline support

---

## ROADIE/DRIVER APP ARCHITECTURE

### Directory Structure
```
roadie_app/lib/
├── screens/
│   ├── login_screen.dart         - Same as rider app
│   ├── register_screen.dart      - Same as rider app (registers as RODIE)
│   ├── home_screen.dart          - Map + offline/online toggle + offer dialog
│   ├── ride_screen.dart          - Accept & complete service
│   ├── rating_screen.dart        - Rate rider
│   ├── wallet_screen.dart        - Balance & history
│   ├── profile_screen.dart       - Profile
│   ├── history_screen.dart       - Completed services
│   ├── referrals_screen.dart     - Referrals
│   ├── help_screen.dart          - Help
│   └── splash_screen.dart        - Initialization
└── services/
    ├── api_service.dart          - REST API client (similar to rider)
    └── websocket_service.dart    - Real-time (same implementation)
```

### Key Screens & Functionality

#### **HomeScreen** ([roadie_app/lib/screens/home_screen.dart](roadie_app/lib/screens/home_screen.dart#L1-L200))
- **Components:**
  - FlutterMap with current location
  - Online/Offline status toggle (visual only!)
  - Service request offer dialog
  - Audio notifications (Sound.mpeg asset)
- **Behavior:**
  1. Gets location via GPS
  2. Connects to WebSocket
  3. Sends location every 10 seconds
  4. Listens for OFFER_REQUEST type
  5. Plays notification sound on offer
  6. Shows popup with request details
- **Offer Dialog:**
  - Service type, distance, fee
  - 10-second countdown timer
  - Accept/Decline buttons
  - Auto-dismiss on timeout
- **Issues:**
  1. **Status toggle is non-functional** - Switch widget sets value directly but calls empty `onChanged: (v) {}`
  2. No API call to update `/api/roadie/status/`
  3. Audio asset path hardcoded (should check if file exists)
  4. Offer dialog doesn't validate rodie has that service

#### **RideScreen** (roadie perspective)
- Similar to rider RideScreen but rodie perspective
- Buttons: Start Service, Complete Service
- Calls: `POST /requests/{id}/start/`, `POST /requests/{id}/complete/`
- Chat functionality similar to rider

### API Service Differences
([roadie_app/lib/services/api_service.dart](roadie_app/lib/services/api_service.dart#L1-L393))

**Key differences from rider app:**
```dart
login(username, password)                 → /api/login/roadie/ (rodie-only)
acceptRequest(requestId)                  → /api/requests/{id}/accept/
declineRequest(requestId)                 → /api/requests/{id}/decline/
```

**Missing from roadie app:**
- No `uploadUserImage()` (KYC not visible)
- No service selection UI
- No referral API calls (code exists but no UI)

### State Management
- **Same issue as rider app:** StatefulWidget with setState()
- **UI state not persisted:** All state resets on app recycle
- **No offline rehydration**

---

## INTEGRATION POINTS

### Endpoint Contract Analysis

#### **1. Login Flow**
| Layer | Endpoint | Method | Request | Response | Status |
|-------|----------|--------|---------|----------|--------|
| Rider App | `/api/login/rider/` | POST | `{username, password}` | `{access, refresh, ...}` | ✅ EXISTS |
| Roadie App | `/api/login/roadie/` | POST | `{username, password}` | `{access, refresh, ...}` | ✅ EXISTS |
| Backend URLs | users/urls.py | - | - | - | ⚠️ **MISSING ROUTES** |

**Issue:** URLs defined in users/urls.py **DO NOT include** RiderLoginView or RoadieLoginView paths!
- Line 50-51 in urls.py:
  ```python
  path('login/rider/', RiderLoginView.as_view(), name='rider_login'),
  path('login/roadie/', RoadieLoginView.as_view(), name='roadie_login'),
  ```
- **These exist in tokens.py but not registered in urls.py!**

#### **2. Service Request Creation**
| Component | Call | Endpoint | Request | Response |
|-----------|------|----------|---------|----------|
| Rider App | `createRequest(serviceId, lat, lng)` | POST `/api/requests/create/` | `{service_type, rider_lat, rider_lng, notes}` | `{id, status, ...}` |
| Backend | CreateServiceRequestView | matches `/requests/create/` | ✅ | Returns ServiceRequest |

**Contract Mismatch SEVERITY: LOW** - Endpoints match but request field `notes` is not in serializer

#### **3. Service Listing**
| Component | Call | Endpoint | Response Format |
|-----------|------|----------|-----------------|
| Rider App | `getServices()` | GET `/api/services/` | Array OR `{results: [...]}` |
| Backend | ServiceTypeListView | `/services/` | Paginated list |

**Issue:** App expects flat array, backend returns paginated. ApiService has fallback parsing but fragile.

#### **4. Nearby Search**
| Component | Call | Endpoint | Query Params |
|-----------|------|----------|--------------|
| Rider App (called but not shown) | `searchNearbyRoadies(lat, lng, serviceId)` | GET `/api/requests/nearby/` | `lat, lng, service_id` |
| Backend | NearbyRodieListView | `/requests/nearby/` | Same params |

**Status:** ✅ Correct, both expect same format

#### **5. Request Status Updates**
| Op | Endpoint | Who | Backend Handler |
|----|----------|-----|-----------------|
| Accept | POST `/api/requests/{id}/accept/` | Rodie | AcceptRequestView |
| Decline | POST `/api/requests/{id}/decline/` | Rodie | DeclineRequestView |
| Cancel | POST `/api/requests/{id}/cancel/` | Rider/Rodie | CancelRequestView |
| En-Route | POST `/api/requests/{id}/enroute/` | Rodie | EnrouteRequestView |
| Start | POST `/api/requests/{id}/start/` | Rodie | StartRequestView |
| Complete | POST `/api/requests/{id}/complete/` | Rodie | CompleteRequestView |

**Status:** ✅ All endpoints exist and properly routed

#### **6. Chat Messages**
| Component | Call | Endpoint | Request |
|-----------|------|----------|---------|
| Both Apps | `ws.sendChat(requestId, text)` | WebSocket msg | `{type: CHAT, request_id, text}` |
| Backend | ChatMessageCreateAPIView | POST `/api/requests/{id}/chat/` | `{service_request, text}` |

**Issues:**
1. Chat in WebSocket is real-time only
2. REST API endpoint also exists but not used by apps
3. **No history endpoint:** Apps can't retrieve past messages
4. Broadcast handled by consumers but no persistence visible

#### **7. Wallet Operations**
| Op | Endpoint | Request | Response |
|----|----------|---------|----------|
| Get Balance | GET `/api/wallet/` | auth'd | `{balance, ...}` |
| Deposit | POST `/api/wallet/deposit/` | `{amount, phone_number?}` | `{payment_id, redirect_url, ...}` |
| Withdraw | POST `/api/wallet/withdraw/` | `{amount, phone_number}` | `{reference}` |

**Issues:**
1. Deposit requires Pesapal integration (incomplete)
2. Withdraw doesn't check if provider returns success
3. Apps don't handle payment callbacks
4. No transaction history retrieval on demand

#### **8. Image Upload (KYC)**
| Component | Endpoint | Method | Request |
|-----------|----------|--------|---------|
| Rider App | `/api/images/user-images/` | POST multipart | `image, image_type` |
| Backend | URLs.py | - | **NOT FOUND** |

**Critical Issue:** Endpoint called by frontend but not implemented in backend!

#### **9. Notifications**
| Op | Endpoint | Backend | Status |
|----|----------|---------|--------|
| List | GET `/api/notifications/` | ✅ NotificationListCreateView | OK |
| Create | POST `/api/notifications/` | ✅ | OK |
| Update | PUT `/api/notifications/{id}/` | ✅ NotificationRUDView | OK |
| Real-time Push | WebSocket `notification` | ✅ Broadcast in consumers | OK |

**Status:** ✅ Mostly complete

#### **10. Referrals**
| Component | Call | Endpoint |
|-----------|------|----------|
| Rider App | `getReferrals()` | GET `/api/users/referrals/` |
| Backend | MyReferralsView | `/referrals/` |

**Mismatch:** App calls `/users/referrals/` but backend is `/referrals/`
- Backend URLs.py line 34: `path('referrals/', MyReferralsView.as_view(), ...)`
- **App will fail!**

#### **11. Rodie Status Update**
| Component | Call | Endpoint | Payload |
|-----------|------|----------|---------|
| Backend | RoadieStatusUpdateView | POST `/api/roadie/status/` | `{is_online: bool}` |
| Rider App | (not used) | - | N/A |
| Roadie App | (UI exists, API call missing!) | - | **NOT CALLED** |

**Critical Issue:** Roadie app has toggle UI for online/offline but **never calls the API!**
- HomeScreen.dart line 250: `Switch(value: true, onChanged: (v) {})` - empty handler!

---

## CRITICAL ISSUES & BUGS

### 1. **Missing URL Routes** 🔴 BLOCKING
**File:** `users/urls.py` lines 50-51 defined but missing from actual urlpatterns

```python
# Classes exist in tokens.py:
class RiderLoginView(TokenObtainPairView)
class RoadieLoginView(TokenObtainPairView)

# But NOT in urls.py urlpatterns!
# This breaks:
# - Rider app: POST /api/login/rider/
# - Roadie app: POST /api/login/roadie/
```

**Impact:** Neither app can log in currently (unless generic /api/login/ is used and role checked differently)

**Fix:**
```python
urlpatterns = [
    ...existing...
    path('login/rider/', RiderLoginView.as_view(), name='rider_login'),
    path('login/roadie/', RoadieLoginView.as_view(), name='roadie_login'),
]
```

### 2. **Missing Image Upload Endpoint** 🔴 BLOCKING
**Files:**
- Called by: `rider-app/lib/screens/profile_screen.dart:50`
- Endpoint: `POST /api/images/user-images/`
- Backend: **Not in urls.py!**

**Impact:** Users cannot upload KYC documents (profile, NIN, license, vehicle photos)

**Missing Code:**
```python
# In urls.py:
path('user-images/', UserImageCreateView.as_view(), name='user-image-upload'),
# or in images/urls.py:
path('user-images/', UserImageCreateView.as_view()),
```

### 3. **Non-Functional Roadie Status Toggle** 🔴 BLOCKING
**File:** `roadie_app/lib/screens/home_screen.dart:250`

```dart
Switch(
  value: true,
  onChanged: (v) {}, // <- EMPTY! No API call
)
```

**Impact:** Roadies cannot set themselves online/offline. Always shows "Online" regardless of actual status.

**Backend exists:** `POST /api/roadie/status/` with `{is_online: bool}`

**Fix needed in roadie app:**
```dart
Switch(
  value: _isOnline,
  onChanged: (v) async {
    setState(() => _isOnline = v);
    await ApiService.post('/roadie/status/', {'is_online': v}, requiresAuth: true);
  }
)
```

### 4. **Single-Device Login Bug** 🟡 MEDIUM
**File:** `users/authentication.py:15-21`

```python
if not token_login_id or str(user.current_login_id) != str(token_login_id):
    raise exceptions.AuthenticationFailed('This session is no longer valid...')
```

**Issue:** When user first creates account, `current_login_id` is never set!
- User.current_login_id is nullable, defaults to NULL
- First login token has login_id, gets stored
- But subsequent logins fail because it's set dynamically

**Impact:** Users might get locked out unexpectedly

**Fix:** Set login_id on registration and update on each login in token generation

### 5. **Service Fee Charging Race Condition** 🟡 MEDIUM
**File:** `requests/models.py:97-127` (charge_fee_for_request)

The signal handler catches COMPLETED status but:
```python
charge_service_fee_initial(sender, instance, created, **kwargs):
    return  # <- Does nothing!
```

Then `charge_service_fee` tries to charge but:
```python
if instance.status == 'COMPLETED':
    if tx_exists:
        # Only update flag, no actual charging
    else:
        charge_fee_for_request(instance)  # Called here
```

**Issues:**
1. Duplicate signal handlers that might both fire
2. Fee not charged immediately on completion
3. No idempotency guarantee
4. Trial period check happens in service_fee handler but not in validate method

**Impact:** Fees might not be collected or charged twice

### 6. **Chat History Not Retrievable** 🟡 MEDIUM
**Files:**
- Created: `requests/models_chat.py`
- API: Only `POST /api/requests/<id>/chat/` exists
- No `GET /api/requests/<id>/chat/` or similar

**Impact:**
- Apps restart → lose all chat messages
- No chat history available
- Users can't see what was discussed

**Fix:** Add ChatMessageListView to retrieve paginated history

### 7. **Rating System Not Implemented** 🟡 MEDIUM
**Files:**
- UI exists: `rider-app/lib/screens/rating_screen.dart`
- No rating model in backend
- No API endpoint to submit ratings

**Impact:** Request marked COMPLETED but no feedback on rodie

**Missing:**
```python
# Model needed:
class Rating(models.Model):
    request = FK(ServiceRequest)
    rater = FK(User)  # Could be rider or rodie
    rating = IntegerField(1-5)
    comment = TextField()

# Endpoint:
POST /api/requests/<id>/rate/
```

### 8. **No Referral UI in Apps** 🟡 MEDIUM
**Files:**
- Backend: Referral model exists, endpoints working
- Frontend: referrals_screen.dart exists but likely just shows list
- No way to share referral code or claim referral

**Impact:** Referral program can't be used

### 9. **Registration Doesn't Send Role** 🟡 MEDIUM
**File:** `rider-app/lib/services/api_service.dart:141-155`

```dart
await post("/register/", {
    "username": username,
    "email": email,
    // ... other fields ...
    // NO "role" field sent!
});
```

But backend RegisterSerializer expects role. Works because signup then auto-login passes role to login endpoint, but registration data doesn't match schema.

### 10. **Map Libraries Hard-Coded** 🟡 MEDIUM
**Files:**
- `roadie_app/lib/screens/home_screen.dart:65` & riders equivalent
- Tile server: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- WebSocket: `wss://backend.vehix.ug/...`

**Impact:** Can't test locally without changing code

### 11. **No Error Recovery for Location Tracking** 🟡 MEDIUM
**File:** `rider-app/lib/screens/home_screen.dart:66-85`

Location requests wrapped in try-catch but:
```dart
catch (e) {
    debugPrint("Rider initial location error: $e");
    // No user feedback!
    // No fallback location
}
```

**Impact:** If GPS fails, user sees blank map with no indication of problem

### 12. **Pesapal Integration Incomplete** 🟡 MEDIUM
**Files:** `users/views.py:96-130` (DepositView)

```python
try:
    client = PesapalClient()
    # Call external API
    response = client.submit_order(payment, callback_url)
except Exception as e:
    payment.status = 'FAILED'
    payment.save()
    return Response({'error': str(e)})  # Exposes error details!
```

**Issues:**
1. No IPN (web hook) callback verification
2. No timeout handling
3. Error message exposes internal details
4. No rate limiting
5. Callback at `/api/users/wallet/callback/` - not in urls.py!

### 13. **Wallet Negative Balance Logic Inconsistent** 🟡 MEDIUM
**Files:**
- `users/models.py:217` (PlatformConfig) sets `max_negative_balance`
- Checked in: ServiceRequest.clean(), AcceptRequestView, CreateServiceRequestView
- But: Wallet.deposit and .withdraw don't check it

**Impact:** Platform rules not consistently applied

### 14. **No Transaction IDs Returned** 🟡 MEDIUM
**File:** `requests/views.py` - accept, decline, cancel, etc.

```python
return Response({'detail': 'Request accepted', 'request_id': req.id})
```

But WebSocket message broadcasted has full request object. Some messages are async so caller might not get state.

### 15. **Offer Timeout Race Condition** 🔴 BLOCKING
**File:** `requests/services.py:73-150` (_sequential_offers thread)

```python
for r in rodies:
    if time.time() - start >= expiry_seconds:
        req = ServiceRequest.objects.get(id=request_id)
        if req.status == 'REQUESTED':  # <- Check is not atomic!
            req.status = 'EXPIRED'
            req.save()
        break
```

**Issue:** Between check and update, another rodie might accept. Double-update possible.

**Impact:** Request state inconsistency

---

## MISSING FEATURES

### Core Missing Features (Not Implemented)
1. **Ratings & Reviews** - UI only, no backend
2. **Dispute Resolution** - No model, no process
3. **Chat History** - No persistence or retrieval
4. **Request Cancellation by Rider** - UI in RequestingScreen but no button
5. **Manual Location Update** - Both apps rely on GPS only
6. **Offline Mode** - No offline data sync
7. **Background Location Tracking** - No service/location manager on iOS/Android
8. **Payment Receipts** - No PDF generation or email
9. **In-App Messaging** - Only WebSocket, no persistent threads
10. **Document Verification Status** - Garage model supports but no public API
11. **Service Categories/Subcategories** - Flat list only
12. **Service Availability Hours** - ServiceType has no scheduling
13. **Rodie Availability Logs** - Model exists but not used
14. **Mechanic Evaluation** - Model for mechanics role but no business logic
15. **Promo Codes** - No code model or validation
16. **Wallet Limits** - No withdrawal limits or daily caps
17. **Two-Factor Authentication** - No 2FA
18. **Phone Verification** - No SMS verification on registration
19. **Emergency SOS** - No emergency contact triggers
20. **Service History for Businesses** - Garages not tied to requests

### Partially Implemented Features
1. **Role-Based Access** - Works but no permission classes
2. **Real-Time Tracking** - WebSocket works but unreliable without keepalive
3. **Service Selection** - Works but no filtering (distance, rating, price)
4. **Wallet Management** - Deposit/withdraw exist but Pesapal incomplete
5. **Image Management** - Model exists but API endpoint missing
6. **Notifications** - Database + WebSocket but no notification types

### Stubbed/Incomplete Features
1. **Profile Photo Upload** - Form field exists, no backend
2. **Referral Codes** - Generated but no way to share/claim
3. **User Search** - No search functionality
4. **Ratings** - Rating screen exists in both apps but no data flow
5. **History Filtering** - History pages exist but no date/status filters

---

## DATA/API MISMATCHES

### 1. Referral Endpoint Path Mismatch
| Component | Path | Status |
|-----------|------|--------|
| Rider App | `/api/users/referrals/` | ❌ WRONG |
| Backend | `/api/referrals/` | ✅ CORRECT |

**Fix:** Rider App should call `/api/referrals/`

### 2. Service List Response Format
| Scenario | Response Format |
|----------|-----------------|
| Direct GET | Array of ServiceType objects |
| Paginated | `{count, next, previous, results: []}` |
| TypeError response | `{results: []}` |

**App handles:** Array OR .results field, but fragile

### 3. Chat Message Sender Format
| Field | Rider Request | Rodie Request | Backend |
|-------|---|---|---|
| sender_id | Not used | Not used | Should be `sender.id` |
| sender_name | Expected | Expected | Must be derived |

**Issue:** Apps expect sender name but serializer only returns ID

### 4. Rodie Location Data Inconsistency
| Source | Format | TTL |
|--------|--------|-----|
| RodieLocation DB | Persistent record | Forever |
| User.lat, User.lng | Fallback fields | Forever |
| Redis cache | Ephemeral | 5 minutes |
| WebSocket broadcast | Real-time | Immediate |

**Issue:** Four different location sources can be out of sync

### 5. Service Request Status Timestamp Mismatch
| Status | Timestamp Field | Updated When |
|--------|---|---|
| REQUESTED | created_at | Auto-set |
| ACCEPTED | accepted_at | Manual set in view |
| EN_ROUTE | en_route_at | Manual set in view |
| STARTED | started_at | Manual set in view |
| COMPLETED | completed_at | Manual set in view |

**Issue:** If manually updated outside view, timestamps not updated

### 6. Wallet Balance vs. Wallet Transactions Mismatch
| Component | Updates Wallet.balance | Creates WalletTransaction |
|-----------|---|---|
| Deposit success | ❓ See below | ✅ YES |
| Withdrawal | ✅ YES | ✅ YES |
| Service fee | ✅ YES | ✅ YES |
| Deposit failure | ❌ NO | ✅ YES (with negative) |

**Issue:** Deposit doesn't immediately update wallet, only on payment callback

### 7. Request Chat Message IDs
| Component | Message ID | Issue |
|-----------|---|---|
| Apps | Not tracked | Can't retry if failed |
| Backend | Auto-incremented | No idempotency key |
| WebSocket | Broadcast in message | Not returned to sender |

**Issue:** Apps can't confirm message was saved

### 8. Nearby Rodie Response vs. Accept Response
```
GET /requests/nearby/ returns:
[
  {rodie_id, username, lat, lng, distance_km, eta_seconds, distance_meters}
]

POST /requests/<id>/accept/ returns:
{detail, request_id}
```

**Issue:** Accept response doesn't include rodie location, but RideScreen expects it in request object

### 9. Rodie Service Assignment Data Mismatch
| Place | Service Representation |
|-------|---|
| RodieService model | `rodie_id` + `service_id` as FK |
| API response | `{service_id, service_name}` |
| RodieMyServicesView | Flattens to array of IDs or names |

**Issue:** Consumer must parse differently depending on endpoint

### 10. User Profile Data Incomplete
```
GET /api/me/ should return:
- All user fields
- Wallet balance
- Rating/stats
- Availability status

But apps expect:
- Basic user info (for chat)
- Wallet balance (separate call)
- Ratings (not fetched)
```

**Issue:** Multiple API calls needed instead of single profile fetch

---

## ROLE-BASED DIFFERENCES

| Feature | Rider | Rodie | Mechanic | Admin |
|---------|-------|-------|----------|-------|
| Create Request | ✅ | ❌ | ❌ | ❌ |
| Accept Request | ❌ | ✅ | ✅ | ❌ |
| Complete Request | ❌ | ✅ | ✅ | ❌ |
| Manage Services | ❌ | ✅ | ✅ | ❌ |
| Upload Documents | ✅ | ✅ | ✅ | ❌ |
| Rating System | ✅ | ✅ | ✅ | ❌ |
| Onboard Garage | ❌ | ❌ | ? | ❌ |
| View All Requests | ❌ | ❌ | ❌ | ✅ |
| Assign Requests | ❌ | ❌ | ❌ | ✅ |
| Configure Platform | ❌ | ❌ | ❌ | ✅ |

**Gaps:**
- Mechanic role defined but no clear business logic
- No mechanic-specific onboarding (they don't onboard garages)
- Rating system not implemented anywhere

---

## RECOMMENDATIONS

### Priority 1: BLOCKING ISSUES (Fix ASAP)
1. **Add missing URL routes** for RiderLoginView, RoadieLoginView
   - File: `users/urls.py`
   - Add lines 50-51 to urlpatterns list

2. **Implement image upload endpoint**
   - Create: `images/views.py` with UserImageCreateView
   - Route: `/api/images/user-images/` (POST multipart)
   - Add to `images/urls.py`

3. **Fix Roadie status toggle**
   - Roadie app: Implement actual API call in Switch.onChanged
   - Verify backend receives updates and broadcasts to admin/riders

4. **Fix offer timeout race condition**
   - Use atomic transaction for ExpireRequest
   - Add request lock/timeout mechanism
   - Implement proper state machine

### Priority 2: DATA CONSISTENCY (Fix in Next Sprint)
1. **Standardize location storage strategy**
   - Single source of truth (Redis preferred)
   - Sync User.lat/lng periodically from cache
   - Document TTL and fallback strategy

2. **Implement chat history retrieval**
   - Add GET `/api/requests/<id>/chat/` endpoint
   - Paginate with page/limit params
   - Return ordered by created_at

3. **Fix wallet balance calculation**
   - Every transaction must update both balance AND transaction log atomically
   - Add periodic reconciliation job

4. **Implement rating system**
   - Create Rating model
   - Add endpoints: POST/GET /api/requests/<id>/rate/
   - Include both apps' UI implementations

5. **Fix role-based permissions**
   - Use DRF permission classes instead of manual checks
   - Example: IsRider, IsRodie, IsAdminUser
   - Apply to all views

### Priority 3: FEATURE COMPLETENESS (Next Release)
1. **Implement missing endpoints:**
   - Chat history retrieval
   - Request cancellation confirmation
   - Service filtering by distance/rating
   - User search
   - Dispute management

2. **Add background location tracking** (native iOS/Android)
   - Use platform channels to start background service
   - Report location every 10 seconds to backend
   - Works even when app is minimized

3. **Complete Pesapal integration:**
   - Verify webhooks signature
   - Add timeout/retry logic
   - Send confirmation SMS/email
   - Handle multiple payment methods

4. **Offline mode:**
   - Cache last 20 requests
   - Queue operations while offline
   - Sync when reconnected

5. **Notification system:**
   - Implement FCM/APNs push notifications
   - Replace WebSocket with hybrid approach
   - Add notification preferences

### Priority 4: POLISH & PERFORMANCE
1. **State management refactor:**
   - Migrate to Provider / Riverpod
   - Centralize user/auth state
   - Add offline data rehydration

2. **Error handling standardization:**
   - Consistent error response format
   - Proper HTTP status codes
   - User-friendly error messages in apps

3. **API rate limiting:**
   - Add rate limit middleware in Django
   - Example: 100 requests/min per user
   - Including WebSocket messages

4. **Database indexing:**
   - Index frequently queried fields
   - Add indexes for foreign keys
   - Monitor slow queries

5. **WebSocket connection reliability:**
   - Heartbeat mechanism
   - Exponential backoff reconnection (already done)
   - Connection pooling

### Code Organization Improvements
1. **Separate concerns:**
   - Move business logic to services.py files
   - Use serializers for all data validation
   - Views should only handle HTTP

2. **Add comprehensive logging:**
   - Use Python logging with proper levels
   - Log all API calls, errors, state changes
   - Structured logging for debugging

3. **Implement proper testing:**
   - Unit tests for models
   - Integration tests for views
   - API tests for endpoints
   - UI tests for critical flows (Flutter)

4. **Documentation:**
   - API documentation (Swagger already configured)
   - Architecture decisions (ADR)
   - Setup instructions for development

---

## SUMMARY TABLE: Feature Completeness

| Feature | Backend | Rider App | Roadie App | Status |
|---------|---------|-----------|-----------|--------|
| User Management | ✅ | ✅ | ✅ | Complete |
| Authentication | ⚠️ | ⚠️ | ⚠️ | Missing routes |
| Service Requests | ✅ | ✅ | ✅ | Complete |
| Chat | ⚠️ | ✅ | ✅ | No history |
| Wallets | ⚠️ | ⚠️ | ⚠️ | Pesapal incomplete |
| Ratings | ❌ | ⚠️ | ⚠️ | UI only |
| Real-Time Tracking | ✅ | ✅ | ✅ | Complete |
| Notifications | ⚠️ | ⚠️ | ⚠️ | WebSocket only |
| Image Upload/KYC | ❌ | ⚠️ | ⚠️ | Missing endpoint |
| Referrals | ✅ | ⚠️ | ⚠️ | No UI flow |
| Rodie Onboarding | ❌ | ❌ | ❌ | Not built |
| Garage Onboarding | ⚠️ | ❌ | ❌ | Model only |
| Admin Features | ✅ | ❌ | ❌ | No admin app |

**Legend:** ✅ = Fully implemented, ⚠️ = Partially, ❌ = Missing

---

## CONTACTS FOR NEXT STEPS
- Backend issues: See Django apps in config/
- Rider app issues: See rider-app/lib/ structure
- Roadie app issues: See roadie_app/lib/ structure
- Database: See users/models.py for schema

