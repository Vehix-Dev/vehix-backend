# Vehix System API Documentation

This document provides a comprehensive reference for all APIs in the Vehix system, derived from the codebase analysis.

## Table of Contents
1. [Core & Essential APIs](#1-core--essential-apis)
2. [Rider Specific APIs](#2-rider-specific-apis)
3. [Roadie Specific APIs](#3-roadie-specific-apis)
4. [Image & KYC APIs](#4-image--kyc-apis)
5. [Admin & Monitoring APIs](#5-admin--monitoring-apis)
6. [Real-time Communication (WebSockets)](#6-real-time-communication-websockets)
7. [Implementation Notes](#7-implementation-notes)

---

## Authentication & Headers

All endpoints except `login/` and `register/` require a valid JWT token.

**Headers:**
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## 1. Core & Essential APIs

### Authentication Flow

#### Register User
**Endpoint:** `POST /api/register/`  
**Description:** Create a new Rider or Roadie account.  
**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+254700000000",
  "username": "johndoe",
  "password": "securepassword123",
  "role": "RIDER", // Options: "RIDER", "RODIE"
  "nin": "12345678901234", // Required for RIDER and RODIE (14 chars)
  "referred_by_code": "VEHIX123" // Optional
}
```
**Response (201 Created):**
```json
{
  "id": 15,
  "username": "johndoe",
  "email": "john@example.com",
  "role": "RIDER",
  "external_id": "VHX-7890"
}
```

#### Login
**Endpoint:** `POST /api/login/`  
**Description:** Exchange credentials for JWT tokens.  
**Request Body:**
```json
{
  "username": "johndoe",
  "password": "securepassword123"
}
```
**Response (200 OK):**
```json
{
  "access": "eyJ0eXAi...",
  "refresh": "eyJ0eXAi..."
}
```
**Error (401 Unauthorized):**
```json
{
  "detail": "No active account found with the given credentials"
}
```

#### Refresh Token
**Endpoint:** `POST /api/refresh/`  
**Description:** Get a new access token using a refresh token.  
**Request Body:**
```json
{
  "refresh": "eyJ0eXAi..."
}
```
**Response (200 OK):**
```json
{
  "access": "eyJ0eXAi..."
}
```

#### Me (Profile)
**Endpoint:** `GET /api/me/`  
**Description:** Retrieve profile, wallet balance, and offered services (for Roadies).  
**Response (200 OK):**
```json
{
  "id": 15,
  "external_id": "VHX-7890",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+254700000000",
  "username": "johndoe",
  "role": "RIDER",
  "referral_code": "VHX-ABC1",
  "nin": "12345678901234",
  "is_approved": true,
  "wallet": {
    "balance": "500.00",
    "transactions": [
      {
        "id": 1,
        "amount": "100.00",
        "reason": "referral credit",
        "created_at": "2023-11-01T10:00:00Z"
      }
    ]
  },
  "services": [] // List of service objects if role is RODIE
}
```

### Wallet & Financials

#### My Wallet
**Endpoint:** `GET /api/wallet/`  
**Description:** Get current balance and detailed transaction history.  
**Response (200 OK):**
```json
{
  "id": 10,
  "user_id": 15,
  "user_external_id": "VHX-7890",
  "user_username": "johndoe",
  "balance": "1250.50",
  "transactions": [
    {
      "id": 45,
      "amount": "-50.00",
      "reason": "service fee for request #101",
      "created_at": "2023-11-01T12:00:00Z"
    }
  ]
}
```

#### Deposit Funds (PesaPal)
**Endpoint:** `POST /api/wallet/deposit/`  
**Description:** Initiate a deposit. Triggers a PesaPal STK push if `phone_number` is provided.  
**Request Body:**
```json
{
  "amount": 1000.00,
  "phone_number": "+254700000000" // Optional: Triggers STK Push
}
```
**Response (200 OK):**
```json
{
  "payment_id": 5,
  "redirect_url": "https://pay.pesapal.com/...",
  "reference": "DEP-ABCD1234EFGH",
  "stk_pushed": true
}
```

#### Withdraw Funds
**Endpoint:** `POST /api/wallet/withdraw/`  
**Description:** Request a withdrawal. Balance is deducted immediately and a pending payment record is created.  
**Request Body:**
```json
{
  "amount": 500.00,
  "phone_number": "+254700000001" // Optional, defaults to user phone
}
```
**Response (200 OK):**
```json
{
  "message": "Withdrawal request submitted",
  "reference": "WTH-XYZ789"
}
```
**Error (400 Bad Request):**
```json
{
  "error": "Insufficient funds"
}
```

### Notifications

#### List Notifications
**Endpoint:** `GET /api/notifications/`  
**Description:** Retrieve all notifications for the authenticated user.  
**Response (200 OK):**
```json
[
  {
    "id": 101,
    "user": 15,
    "title": "Request Accepted",
    "body": "A roadie has accepted your request!",
    "data": {"request_id": 101},
    "read": false,
    "broadcast": false,
    "target_role": null,
    "created_at": "2023-11-01T12:05:00Z"
  }
]
```

#### Mark Read / Update
**Endpoint:** `PATCH /api/notifications/<id>/`  
**Request Body (Partial):**
```json
{
  "read": true
}
```
**Response (200 OK):**
```json
{
  "id": 101,
  "read": true,
  "title": "Request Accepted",
  "..." : "..."
}
```

#### Decline Request
**Endpoint:** `POST /api/requests/<id>/decline/`  
**Role:** Roadie  
**Description:** Declines a request offer.
**Response:** `{"detail": "Declined"}`

#### Cancel Request
**Endpoint:** `POST /api/requests/<id>/cancel/`  
**Role:** Rider or Roadie  
**Description:** Cancels the request. Roadies cannot cancel if within 10 meters of the rider.
**Response:** `{"detail": "Cancelled"}`

#### Mark En-Route
**Endpoint:** `POST /api/requests/<id>/enroute/`  
**Role:** Roadie  
**Description:** Updates status to `EN_ROUTE`.
**Response:** `{"detail": "Marked en-route"}`

#### Start Service
**Endpoint:** `POST /api/requests/<id>/start/`  
**Role:** Roadie  
**Description:** Updates status to `STARTED`.
**Response:** `{"detail": "Service started"}`

#### Complete Service
**Endpoint:** `POST /api/requests/<id>/complete/`  
**Role:** Roadie  
**Description:** Updates status to `COMPLETED`. Triggers platform fee charge on the Roadie's wallet.
**Response:** `{"detail": "Service completed"}`

---

## 2. Rider Specific APIs

These APIs are used by the Rider mobile application to manage service requests and find help.

### Service Request Lifecycle

#### Create Service Request
**Endpoint:** `POST /api/requests/create/`  
**Description:** Requests a service at the rider's current location.  
**Request Body:**
```json
{
  "service_type": 1,          // ID of the ServiceType
  "rider_lat": -1.286389,
  "rider_lng": 36.817223
}
```
**Response (201 Created):**
```json
{
  "id": 101,
  "status": "REQUESTED",
  "rider_id": 15,
  "service_type_name": "Towing",
  "rider_lat": "-1.286389",
  "rider_lng": "36.817223",
  "created_at": "2023-11-01T14:00:00Z"
}
```

#### List My Requests
**Endpoint:** `GET /api/requests/my/`  
**Description:** Get history of requests created by the Rider.  
**Query Params:** `?status=active` (Optional: filter for REQUESTED, ACCEPTED, EN_ROUTE, STARTED)  
**Response (200 OK):**
```json
[
  {
    "id": 101,
    "service_type": 1,
    "service_type_name": "Towing",
    "rider_id": 15,
    "rodie_id": 20,
    "status": "ACCEPTED",
    "rider_lat": "-1.286389",
    "rider_lng": "36.817223",
    "accepted_at": "2023-11-01T14:05:22Z",
    "en_route_at": null,
    "started_at": null,
    "completed_at": null,
    "is_paid": false,
    "fee_charged": false,
    "created_at": "2023-11-01T14:00:00Z",
    "updated_at": "2023-11-01T14:05:22Z"
  }
]
```

#### Cancel Request
**Endpoint:** `POST /api/requests/<id>/cancel/`  
**Description:** Cancel a request.  
**Response (200 OK):** `{"detail": "Cancelled"}`  
**Error (403 Forbidden):** `{"detail": "Cannot cancel: within proximity of rider"}` (For Roadies)

#### Search Nearby Roadies
**Endpoint:** `GET /api/requests/nearby/`  
**Description:** Finds active Roadie positions for a specific service.  
**Query Params:** `lat`, `lng`, `service_id`  
**Response (200 OK):**
```json
[
  {
    "rodie_id": 20,
    "username": "roadiesam",
    "lat": -1.287000,
    "lng": 36.818000,
    "distance_km": 0.12,
    "eta_seconds": 45,
    "distance_meters": 120
  }
]
```

---

## 3. Roadie Specific APIs

### Online Status & Services

#### Toggle Online Status
**Endpoint:** `POST /api/roadie/status/`  
**Request Body:** `{"is_online": true}`  
**Response (200 OK):** `{"is_online": true}`

#### Manage Offered Services
**Endpoint:** `POST /api/rodie/services/`  
**Description:** Set which services this roadie currently offers.  
**Request Body:**
```json
{
  "service_ids": [1, 2, 5]
}
```
**Response (200 OK):** `[{"service_id": 1, "service_name": "Towing", ...}]`

### Request Handling

| Action | Endpoint | Method | Success Response Example |
| :--- | :--- | :--- | :--- |
| **Accept** | `/api/requests/<id>/accept/` | POST | `{"detail": "Request accepted", "request_id": 101}` |
| **Decline**| `/api/requests/<id>/decline/`| POST | `{"detail": "Declined"}` |
| **En-route**| `/api/requests/<id>/enroute/`| POST | `{"detail": "Marked en-route"}` |
| **Start**  | `/api/requests/<id>/start/`  | POST | `{"detail": "Service started"}` |
| **Complete**| `/api/requests/<id>/complete/`| POST | `{"detail": "Service completed"}` |

### Chat System

#### Send Message
**Endpoint:** `POST /api/requests/<id>/chat/`  
**Description:** Send a message to the other participant.  
**Request Body:**
```json
{
  "service_request": 101, // Required by serializer
  "text": "I've arrived at your location."
}
```
**Response (201 Created):**
```json
{
  "id": 50,
  "service_request": 101,
  "sender_id": 20,
  "text": "I've arrived at your location.",
  "created_at": "2023-11-01T14:15:00Z"
}
```

---

## 4. Image & KYC APIs

### User Image Management

#### Upload Image
**Endpoint:** `POST /api/images/user-images/`  
**Payload (Multipart/Form-Data):**
- `image`: File
- `image_type`: String (Choices: "PROFILE", "NIN_FRONT", "NIN_BACK", "LICENSE_FRONT", "LICENSE_BACK")
- `description`: String (Optional)
**Response (201 Created):**
```json
{
  "id": 14,
  "user": 15,
  "external_id": "VHX-7890",
  "image_type": "PROFILE",
  "original_url": "http://example.com/media/user_images/original_14.jpg",
  "thumbnail_url": "http://example.com/media/user_images/thumb_14.jpg",
  "status": "PENDING",
  "description": "My profile pic"
}
```

#### List My Images
**Endpoint:** `GET /api/images/user-images/`
**Response (200 OK):**
```json
[
  {
    "id": 14,
    "image_type": "PROFILE",
    "status": "APPROVED",
    "original_url": "...",
    "thumbnail_url": "..."
  }
]
```

---

## 5. Admin & Monitoring APIs

### User Management

#### Management Consoles (Riders/Roadies)
- **Riders:** `GET /api/auth/admin/riders/`
- **Roadies:** `GET /api/auth/admin/roadies/`
**Detailed Item Response:**
```json
{
  "id": 15,
  "username": "johndoe",
  "summary": {
    "stats": {
      "total_requests": 25,
      "completed_requests": 20,
      "active_requests": 1,
      "cancelled_requests": 4,
      "completion_rate": 80.0
    },
    "recent_requests": [
      {"id": 101, "service_type": "Towing", "status": "COMPLETED", "created_at": "..."}
    ]
  }
}
```

#### Restore Deleted User
**Endpoint:** `POST /api/auth/admin/users/<id>/restore/`
**Response (200 OK):** `{"status": "User restored successfully"}`

### Service Request Control

#### Manual Assignment
**Endpoint:** `POST /api/auth/admin/requests/<id>/assign/`  
**Request Body:** `{"rodie_id": 12}`
**Response (200 OK):** `{"detail": "Roadie assigned successfully", "request_id": 101}`

#### Route Details (OSRM)
**Endpoint:** `GET /api/auth/admin/requests/<id>/route/`  
**Response (200 OK):**
```json
{
  "request_id": 101,
  "status": "ACCEPTED",
  "rider": {"id": 15, "lat": -1.28, "lng": 36.81},
  "rodie": {"id": 20, "lat": -1.29, "lng": 36.82},
  "route": {
    "distance_meters": 1500,
    "eta_seconds": 320
  }
}
```

### Real-time Monitoring

#### GeoJSON Map View
**Endpoint:** `GET /api/auth/admin/locations/realtime/map/`  
**Response (200 OK):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "user_id": 20,
        "username": "roadiesam",
        "role": "RODIE",
        "status": "ONLINE"
      },
      "geometry": { "type": "Point", "coordinates": [36.82, -1.29] }
    }
  ]
}
```

### Platform Configuration

#### Global Config
**Endpoint:** `POST /api/auth/admin/platform/config/`  
**Request Body:** `{"service_fee": 50.00, "max_negative_balance": 1000.00}`
**Response (200 OK):**
```json
{
  "id": 1,
  "service_fee": "50.00",
  "max_negative_balance": "1000.00",
  "trial_days": 14
}
```

---

## 6. Real-time Communication (WebSockets)

### Rider Hub (`ws/rider/`)
**Location Update (Client -> Server):**
```json
{ "type": "LOCATION", "lat": -1.286, "lng": 36.817 }
```
**Roadie Tracking (Server -> Client):**
```json
{ "type": "RODIE_LOCATION", "lat": -1.287, "lng": 36.818 }
```

### Roadie Hub (`ws/rodie/`)
**Offer Notification (Server -> Client):**
```json
{
  "type": "OFFER_REQUEST",
  "data": {
    "id": 101,
    "service_type": "Towing",
    "rider_lat": -1.28,
    "rider_lng": 36.81
  }
}
```

### Availability Hub (`ws/availability/`)
**Get Nearby (Client -> Server):** `{"type": "GET_NEARBY", "lat": -1.28, "lng": 36.81}`
**Response:**
```json
{
  "type": "NEARBY_LIST",
  "data": [
    {"rodie_id": 20, "username": "roadiesam", "lat": -1.29, "lng": 36.82}
  ]
}
```

---

## 7. Implementation Notes

- **OSRM Integration:** The backend uses `requests/osrm.py` to calculate distances and ETAs.
- **Wallet Security:** Service acceptance and manual assignment are blocked if the user's wallet is below the `max_negative_balance` defined in platform config.
- **Fee Logic:** Roadies are charged the `service_fee` upon request completion, unless they are within their `trial_days` (counted from account creation).
## 8. Full Admin API Reference

All endpoints in this section require `ADMIN` role. Base path for most is `/api/auth/admin/`.

### 8.1 Administrative Auth

#### Admin Login
**Endpoint:** `POST /api/auth/admin/login/`  
**Description:** Dedicated login for administrators.  
**Response:** Same as standard login.

#### Admin Registration
**Endpoint:** `POST /api/auth/admin/register/`  
**Description:** Create a new administrator account.

---

### 8.2 Comprehensive User Management

#### User List & CRUD
- **Riders:** `GET/POST /api/auth/admin/riders/`
- **Roadies:** `GET/POST /api/auth/admin/roadies/`
- **Admins:** `GET/POST /api/auth/admin/users/`

**Retrieve/Update/Delete:**
- `GET/PUT/PATCH/DELETE /api/auth/admin/riders/<id>/`
- `GET/PUT/PATCH/DELETE /api/auth/admin/roadies/<id>/`
- `GET/PUT/PATCH/DELETE /api/auth/admin/users/<id>/`

**Detailed Item Response (GET):**
```json
{
  "id": 15,
  "external_id": "VHX-7890",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+254700000000",
  "username": "johndoe",
  "role": "RIDER",
  "is_approved": true,
  "created_at": "2023-11-01T10:00:00Z",
  "summary": {
    "stats": {
      "total_requests": 25,
      "completed_requests": 20,
      "active_requests": 1,
      "cancelled_requests": 4,
      "completion_rate": 80.0,
      "status_breakdown": {"COMPLETED": 20, "CANCELLED": 4, "REQUESTED": 1}
    },
    "service_breakdown": [
      {"service_type__name": "Towing", "count": 15}
    ],
    "recent_requests": [
      {
        "id": 101,
        "service_type__name": "Towing",
        "status": "COMPLETED",
        "created_at": "2023-11-01T12:00:00Z",
        "rodie__username": "roadiesam"
      }
    ]
  },
  "wallet": {
    "id": 5,
    "balance": "1250.00"
  }
}
```

#### Account Maintenance
- **Deleted Users List:** `GET /api/auth/admin/users/deleted/`
- **Restore User:** `POST /api/auth/admin/users/<id>/restore/`
- **Password Reset:** `POST /api/auth/admin/users/<id>/password/`  
  **Payload:** `{"password": "new_secure_pass"}`
  **Response:** `{"status": "Password updated successfully"}`

---

### 8.3 Service & Capacity Management

#### Service Types (Catalog)
**Endpoint:** `GET/POST /api/auth/admin/services/`  
**Retrieve/Update/Delete:** `GET/PUT/PATCH/DELETE /api/auth/admin/services/<id>/`  
**Response Example (GET List):**
```json
[
  {
    "id": 1,
    "name": "Towing",
    "code": "TOW",
    "fixed_price": "2500.00",
    "is_active": true,
    "rodie_count": 15
  }
]
```

#### Roadie-Service Assignments
**Endpoint:** `GET/POST /api/auth/admin/rodie-services/`  
**Description:** Assign or remove services from specific Roadies.  
**Payload Example (POST):**
```json
{
  "rodie_id": 20,          // User ID
  "service_id": 1,        // Service Type ID
  "rodie_username_input": "roadiesam" // Optional: alternative to rodie_id
}
```
**Response:**
```json
{
  "id": 45,
  "rodie": 20,
  "rodie_username": "roadiesam",
  "service": 1,
  "service_display": "Towing"
}
```

---

### 8.4 Service Request Hub

#### Global Request Management
- **List/Create:** `GET/POST /api/auth/admin/requests/`
- **Detail/Edit/Delete:** `GET/PUT/PATCH/DELETE /api/auth/admin/requests/<id>/`

**Detailed Request Response (GET):**
```json
{
  "id": 101,
  "rider_username": "johndoe",
  "rodie_username": "roadiesam",
  "service_type_name": "Towing",
  "status": "ACCEPTED",
  "rider_lat": "-1.286389",
  "rider_lng": "36.817223",
  "fee_charged": false,
  "created_at": "2023-11-01T14:00:00Z",
  "service_type_details": {
    "id": 1,
    "name": "Towing",
    "code": "TOW",
    "fixed_price": "2500.00"
  }
}
```

#### Mission Control
- **Real-time Monitoring:** `GET /api/auth/admin/requests/realtime/`
- **GeoJSON Map:** `GET /api/auth/admin/requests/realtime/map/`

#### Operations
- **Get OSRM Route:** `GET /api/auth/admin/requests/<id>/route/`
- **Manual Roadie Assignment:** `POST /api/auth/admin/requests/<id>/assign/`  
  **Payload:** `{"rodie_id": 20}`
  **Response:** `{"detail": "Roadie assigned successfully", "request_id": 101}`

---

### 8.5 Financial Dashboard

#### Wallet Control
- **List/Create Wallets:** `GET/POST /api/auth/admin/wallets/`
- **Retrieve/Update/Delete:** `GET/PUT/PATCH/DELETE /api/auth/admin/wallets/<id>/`

**Wallet Detail Example:**
```json
{
  "id": 5,
  "user_external_id": "VHX-7890",
  "user_username": "johndoe",
  "balance": "1250.00",
  "transactions": [
    {"id": 1, "amount": "500.00", "reason": "Deposit...", "created_at": "..."}
  ]
}
```

#### Referral Management
- **List/Create Referrals:** `GET/POST /api/auth/admin/referrals/`
- **Detail/Edit/Delete:** `GET/PUT/PATCH/DELETE /api/auth/admin/referrals/<id>/`
  **Response:** `{"id": 1, "referrer": 15, "referred_user": 16, "status": "COMPLETED"}`

---

### 8.6 System Engine

#### Platform Configuration
**Endpoint:** `GET/POST /api/auth/admin/platform/config/`  
**Description:** Manage global fees, trial periods, and wallet thresholds.  
**Response:**
```json
{
  "id": 1,
  "service_fee": "50.00",
  "max_negative_balance": "1000.00",
  "trial_days": 14,
  "updated_at": "..."
}
```

#### Global Notifications
- **List/Post Notifications:** `GET/POST /api/auth/admin/notifications/`
- **Detail/Edit/Delete:** `GET/PUT/PATCH/DELETE /api/auth/admin/notifications/<id>/`  
**Payload Example (Broadcast to all Roadies):**
```json
{
  "title": "Platform Maintenance",
  "body": "System will be down for 10 mins.",
  "target_role": "RODIE",
  "broadcast": true
}
```

---

### 8.7 Generic Location Tracking

- **Location List:** `GET /api/auth/admin/locations/realtime/`
- **Location Map (GeoJSON):** `GET /api/auth/admin/locations/realtime/map/`
**Response (Feature Sample):**
```json
{
  "type": "Feature",
  "properties": {
    "user_id": 20,
    "username": "roadiesam",
    "role": "RODIE",
    "is_online": true
  },
  "geometry": { "type": "Point", "coordinates": [36.8, -1.2] }
}
```

---

### 8.8 Media & KYC Command Center

#### Image Management
- **List All System Images:** `GET /api/images/admin-images/`
- **User Specific Images:** `GET /api/images/user-images-by-id/?external_id=VHX-123`
- **Replace/Override Image:** `POST /api/images/admin-images/<id>/replace/` (Requires `image` file)

#### Image Status Workflow
- **Update Status:** `POST /api/images/admin-images/<pk>/update-status/`
  **Payload:** `{"status": "APPROVED"}`
- **Bulk Update:** `POST /api/images/admin-images/bulk-update-status/`
  **Payload:** `{"image_ids": [14, 15, 16], "status": "APPROVED"}`
  **Response:** `{"message": "Updated 3 images", "status": "APPROVED"}`

#### Infrastructure
- **File System Structure:** `GET /api/images/file-structure/`
  **Response:** Returns a recursive tree of the `media/user_images/` directory with file sizes and modified times.
