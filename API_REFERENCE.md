# VEHIX Platform - Complete API Reference

**Last Updated:** March 4, 2026 (v1.2 - Roadie Service Selection Added)

---

## Table of Contents
1. [Authentication & Login](#authentication--login)
2. [User Account Management](#user-account-management)
3. [Profile Editing & Photo Upload](#profile-editing--photo-upload-new)
4. [Roadie Service Selection](#roadie-service-selection-new)
5. [Wallet & Payments](#wallet--payments)
6. [Roadie Payments](#roadie-payments)
7. [Notifications](#notifications)
8. [Status Updates](#status-updates)

---

## Authentication & Login

### Single Device Login Feature
**Status:** ✅ **IMPLEMENTED** (March 4, 2026)

When a user logs in from a new device, they are **automatically logged out from all previous devices**. Each login generates a new `login_id` (UUID) that invalidates previous sessions.

#### How It Works:
1. User logs in on Device 1 → New `login_id` generated → Stored in database
2. User logs in on Device 2 → New `login_id` generated → Previous `login_id` replaced
3. Device 1 makes any request → Token's `login_id` doesn't match current user `login_id` → **Request rejected**
4. Device 1 receives error: `"This session is no longer valid. Another device has logged in."`
5. WebSocket connections also validate `login_id` → Automatically disconnected

### Login Endpoint
**POST** `/api/users/login/`

**Request:**
```json
{
  "username": "user123",
  "password": "password123"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "user123",
    "email": "user@example.com",
    "phone": "254700123456",
    "role": "RIDER",
    "external_id": "R001",
    "services_selected": false,
    "is_approved": true
  }
}
```

**Response (Roadie with services selected):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 5,
    "username": "johndoe",
    "email": "john@example.com",
    "phone": "254700123456",
    "role": "RODIE",
    "external_id": "BS001",
    "services_selected": true,
    "is_approved": true
  }
}
```

**Token Contains:**
- `user_id`: User's ID
- `login_id`: Session UUID (validated on each request)
- `exp`: Expiration time

**Important:** 
- `services_selected` flag: If `false` for a roadie, they should be redirected to the service selection page on first login
- Only present for RIDER and RODIE roles

---

### Rider Login Endpoint
**POST** `/api/users/login/rider/`

Same as login endpoint but validates user has `role='RIDER'`

**Error Response (if not a rider):**
```json
{
  "detail": "This account is not a Rider account."
}
```

---

### Roadie Login Endpoint
**POST** `/api/users/login/roadie/`

Same as login endpoint but validates user has `role='RODIE'`

**Error Response (if not a roadie):**
```json
{
  "detail": "This account is not a Roadie account."
}
```

---

### Token Refresh Endpoint
**POST** `/api/users/refresh/`

**Request:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

---

### Admin Login Endpoint
**POST** `/api/users/auth/admin/login/`

**Request:**
```json
{
  "username": "admin@example.com",
  "password": "admin_password"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "admin@example.com",
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "role": "ADMIN",
    "is_approved": false
  }
}
```

**Errors:**
```json
{
  "detail": "Invalid credentials or not an admin"
}
```

---

## User Account Management

### Get Current User Profile
**GET** `/api/users/me/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": 5,
  "external_id": "BS001",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "254700123456",
  "username": "johndoe",
  "role": "RODIE",
  "referral_code": "VX001",
  "nin": "12345678901234",
  "is_approved": true,
  "created_at": "2026-03-01T10:30:00Z",
  "updated_at": "2026-03-04T15:45:30Z",
  "wallet": {
    "id": 5,
    "user_id": 5,
    "user_external_id": "BS001",
    "user_username": "johndoe",
    "balance": "5000.00",
    "transactions": [
      {
        "id": 1,
        "amount": "1000.00",
        "reason": "Deposit DEP-ABC123",
        "created_at": "2026-03-03T12:00:00Z"
      }
    ]
  },
  "services": [
    {
      "service_id": 1,
      "service_name": "Basic Ride",
      "fixed_price": "500.00",
      "image": "https://example.com/images/basic-ride.jpg"
    }
  ],
  "profile_photo": "https://example.com/images/profile.jpg"
}
```

---

### Register New User
**POST** `/api/users/register/`

**Request:**
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "254700123456",
  "role": "RODIE",
  "nin": "12345678901234",
  "referred_by_code": "VX001"
}
```

**Response:**
```json
{
  "id": 5,
  "username": "newuser",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "254700123456",
  "role": "RODIE",
  "nin": "12345678901234"
}
```

**Errors:**
```json
{
  "email": ["This field must be unique."],
  "phone": ["This field must be unique."],
  "username": ["This field must be unique."]
}
```

---

## Profile Editing & Photo Upload (NEW)

**Status:** ✅ **IMPLEMENTED** (March 4, 2026)

Both riders and roadies can edit their profile and upload profile photos.

### Update User Profile
**PATCH** `/api/users/profile/`

Update user profile information (name, email, phone, username).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "newemail@example.com",
  "phone": "254700999888",
  "username": "newusername"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "user": {
    "id": 5,
    "external_id": "BS001",
    "first_name": "John",
    "last_name": "Smith",
    "email": "newemail@example.com",
    "phone": "254700999888",
    "username": "newusername",
    "role": "RODIE",
    "referral_code": "VX001",
    "nin": "12345678901234",
    "is_approved": true,
    "created_at": "2026-03-01T10:30:00Z",
    "updated_at": "2026-03-04T16:30:00Z",
    "wallet": {...},
    "services": [...],
    "profile_photo": "..."
  }
}
```

**Errors:**
```json
{
  "success": false,
  "errors": {
    "email": ["This email is already in use."],
    "phone": ["This phone number is already in use."],
    "username": ["This username is already taken."]
  }
}
```

---

### Upload or Update Profile Photo
**POST** `/api/users/profile/photo/`

Upload a new profile photo. Each upload replaces the previous profile photo.

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Request:**
```
POST /api/users/profile/photo/
Content-Type: multipart/form-data

profile_photo: <binary image file>
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Profile photo uploaded successfully",
  "profile_photo": {
    "id": 42,
    "url": "https://example.com/media/user_images/roadies/BS001/originals/profile_photo.jpg",
    "thumbnail_url": "https://example.com/media/user_images/roadies/BS001/thumbnails/profile_photo_thumb.jpg",
    "created_at": "2026-03-04T16:45:00Z"
  }
}
```

**Error Responses:**
```json
{
  "success": false,
  "errors": {
    "profile_photo": ["Profile photo size must be less than 5MB."]
  }
}
```

---

### Get Profile Photo
**GET** `/api/users/profile/photo/`

Retrieve the current profile photo URL.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "profile_photo_url": "https://example.com/media/user_images/roadies/BS001/originals/profile_photo.jpg",
  "thumbnail_url": "https://example.com/media/user_images/roadies/BS001/thumbnails/profile_photo_thumb.jpg",
  "created_at": "2026-03-04T16:45:00Z",
  "id": 42
}
```

**Response (No Photo):**
```json
{
  "profile_photo_url": null,
  "message": "No profile photo uploaded yet"
}
```

---

## Roadie Service Selection (NEW)

**Status:** ✅ **IMPLEMENTED** (March 4, 2026)

Roadies must select their services on first login. After selection, they can manage services from the drawer menu.

### Initial Service Selection (First Login)
**POST** `/api/users/auth/rodie/services/initial/`

Select services for the very first time after registration/login. This endpoint can only be used once per roadie.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "service_ids": [1, 2, 3]
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Services selected successfully",
  "services": [
    {
      "service_id": 1,
      "service_name": "Basic Ride",
      "fixed_price": "500.00",
      "code": "BASIC",
      "category": "BASIC"
    },
    {
      "service_id": 2,
      "service_name": "Premium Ride",
      "fixed_price": "800.00",
      "code": "PREMIUM",
      "category": "BASIC"
    }
  ],
  "services_selected": true
}
```

**Error Response (Already selected):**
```json
{
  "message": "Services already selected. Use Manage My Services to update."
}
```

**Error Response (No services provided):**
```json
{
  "error": "Please select at least one service"
}
```

**Error Response (Invalid service IDs):**
```json
{
  "error": "No valid services found"
}
```

**User Experience Flow:**
1. Roadie logs in → Check `services_selected` flag in login response
2. If `false` → Show service selection page with all available services
3. User selects services and submits
4. Call this endpoint with selected service IDs
5. Upon success, set `services_selected = true` in local storage/state
6. Close modal and show main app

---

### Manage My Services (Drawer Menu)
**GET** `/api/users/auth/rodie/services/`

Get current services and their status.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "services": [
    {
      "id": 5,
      "service_id": 1,
      "service_name": "Basic Ride"
    },
    {
      "id": 6,
      "service_id": 2,
      "service_name": "Premium Ride"
    }
  ],
  "services_selected": true
}
```

---

### Update Services (Drawer Menu)
**POST** `/api/users/auth/rodie/services/`

Update services selection. Can be called multiple times to manage services.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "service_ids": [1, 3, 4]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Services updated successfully",
  "services": [
    {
      "service_id": 1,
      "service_name": "Basic Ride"
    },
    {
      "service_id": 3,
      "service_name": "Economy Ride"
    },
    {
      "service_id": 4,
      "service_name": "XL Ride"
    }
  ],
  "services_selected": true
}
```

---

## Wallet & Payments

### Get Wallet Balance
**GET** `/api/users/wallet/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": 5,
  "user_id": 5,
  "user_external_id": "BS001",
  "user_username": "johndoe",
  "balance": "5000.00",
  "transactions": [
    {
      "id": 1,
      "amount": "1000.00",
      "reason": "Deposit DEP-ABC123",
      "created_at": "2026-03-03T12:00:00Z"
    },
    {
      "id": 2,
      "amount": "-500.00",
      "reason": "Service fee charged",
      "created_at": "2026-03-02T14:30:00Z"
    }
  ]
}
```

---

### Make a Deposit (General Endpoint)
**POST** `/api/users/wallet/deposit/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "amount": "1000.00",
  "phone_number": "254700123456"
}
```

**Response:**
```json
{
  "payment_id": 123,
  "redirect_url": "https://pay.pesapal.com/...",
  "reference": "DEP-ABC123DEF456",
  "stk_pushed": true
}
```

---

### Request a Withdrawal
**POST** `/api/users/wallet/withdraw/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "amount": "500.00",
  "phone_number": "254700123456"
}
```

**Response:**
```json
{
  "message": "Withdrawal request submitted",
  "reference": "WTH-XYZ789ABC123"
}
```

**Errors:**
```json
{
  "error": "Insufficient funds"
}
```

---

## Roadie Payments (NEW)

### Get Payment History & Wallet Summary
**GET** `/api/users/roadie/payments/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Role Required:** `RODIE`

**Response:**
```json
{
  "summary": {
    "current_balance": "5000.00",
    "total_earned": "15000.00",
    "total_withdrawn": "10000.00",
    "pending_deposits": "1000.00",
    "transaction_count": 25
  },
  "transactions": [
    {
      "id": "payment_123",
      "type": "DEPOSIT",
      "amount": "1000.00",
      "reason": "Wallet Deposit - 1000.00 KES",
      "status": "COMPLETED",
      "reference": "DEP-ABC123DEF456",
      "created_at": "2026-03-04T10:30:00Z"
    },
    {
      "id": "payment_124",
      "type": "DEPOSIT",
      "amount": "500.00",
      "reason": "Wallet Deposit - 500.00 KES",
      "status": "PENDING",
      "reference": "DEP-XYZ789ABC123",
      "created_at": "2026-03-04T09:15:00Z"
    },
    {
      "id": "transaction_456",
      "type": "TRANSACTION",
      "amount": "500.00",
      "reason": "Service fee deducted",
      "status": "COMPLETED",
      "reference": "TXN-456",
      "created_at": "2026-03-03T14:00:00Z"
    },
    {
      "id": "payment_122",
      "type": "WITHDRAWAL",
      "amount": "2000.00",
      "reason": "Withdrawal to 254700123456",
      "status": "COMPLETED",
      "reference": "WTH-DEF456GHI789",
      "created_at": "2026-03-02T11:20:00Z"
    }
  ],
  "wallet_id": 5,
  "user_id": 5,
  "user_external_id": "BS001"
}
```

---

### Initiate a Deposit Payment (Roadie Endpoint)
**POST** `/api/users/roadie/payments/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Role Required:** `RODIE`

**Request:**
```json
{
  "amount": "1000.00",
  "phone_number": "254700123456"
}
```

**Response (Success):**
```json
{
  "success": true,
  "payment_id": 125,
  "redirect_url": "https://pay.pesapal.com/pesapalv3/gettransactionstatus?id=...",
  "reference": "DEP-ABC123DEF456",
  "amount": "1000.00",
  "stk_pushed": true,
  "message": "Payment initiated. Complete the payment to add funds to your wallet."
}
```

**Response (Failure):**
```json
{
  "success": false,
  "error": "Failed to authenticate with Pesapal",
  "message": "Failed to initiate payment. Please try again."
}
```

**Error - Not a Roadie:**
```json
{
  "error": "Only roadies can make deposits"
}
```

---

## Notifications

### List My Notifications
**GET** `/api/users/notifications/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Payment Received",
    "body": "You've received 500 KES from a completed ride",
    "data": {
      "ride_id": 123,
      "amount": "500.00"
    },
    "read": false,
    "broadcast": false,
    "target_role": null,
    "created_at": "2026-03-04T15:30:00Z"
  },
  {
    "id": 2,
    "title": "System Announcement",
    "body": "Maintenance scheduled for tonight",
    "data": null,
    "read": true,
    "broadcast": true,
    "target_role": null,
    "created_at": "2026-03-04T12:00:00Z"
  }
]
```

---

### Get Notification Details
**GET** `/api/users/notifications/{id}/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": 1,
  "title": "Payment Received",
  "body": "You've received 500 KES from a completed ride",
  "data": {
    "ride_id": 123,
    "amount": "500.00"
  },
  "read": false,
  "broadcast": false,
  "target_role": null,
  "created_at": "2026-03-04T15:30:00Z"
}
```

---

### Mark Notification as Read
**PATCH** `/api/users/notifications/{id}/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request:**
```json
{
  "read": true
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Payment Received",
  "body": "You've received 500 KES from a completed ride",
  "data": {
    "ride_id": 123,
    "amount": "500.00"
  },
  "read": true,
  "broadcast": false,
  "target_role": null,
  "created_at": "2026-03-04T15:30:00Z"
}
```

---

### Delete Notification
**DELETE** `/api/users/notifications/{id}/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:** HTTP 204 No Content

---

## Status Updates

### Update Roadie Online Status
**POST** `/api/users/roadie/status/`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Role Required:** `RODIE`

**Request:**
```json
{
  "is_online": true
}
```

**Response:**
```json
{
  "is_online": true
}
```

**Error - Not a Roadie:**
```json
{
  "error": "Only roadies can update status"
}
```

---

## Pesapal IPN Callback

### Pesapal Payment Notification Callback
**GET** `/api/users/payments/pesapal/ipn/`

**Query Parameters:**
```
?OrderTrackingId=ORDER123456
&OrderMerchantReference=DEP-ABC123DEF456
&OrderNotificationType=PAYMENT
```

**Response:**
```json
{
  "orderNotificationType": "PAYMENT",
  "orderTrackingId": "ORDER123456",
  "orderMerchantReference": "DEP-ABC123DEF456",
  "status": 200
}
```

**How It Works:**
1. Pesapal sends payment status update to this endpoint
2. System verifies payment status with Pesapal
3. If status is "COMPLETED":
   - Payment record updated to "COMPLETED"
   - Amount added to wallet if it's a DEPOSIT
   - WalletTransaction created for audit trail
4. If status is "FAILED":
   - Payment record updated to "FAILED"

---

## Common HTTP Status Codes

| Status Code | Meaning |
|---|---|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 204 | No Content - Request successful, no response body |
| 400 | Bad Request - Invalid field values |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - User lacks permission |
| 404 | Not Found - Resource doesn't exist |
| 500 | Server Error - Backend issue |

---

## Authentication Headers

All authenticated endpoints require:

```
Authorization: Bearer {access_token}
```

Where `{access_token}` is obtained from login response.

---

## Error Response Format

All error responses follow this format:

```json
{
  "error": "Error message",
  "detail": "Additional details (optional)"
}
```

Or with field validation errors:

```json
{
  "field_name": ["Error message for field"]
}
```

---

## Notes

- **Timestamps** are in ISO 8601 format (UTC timezone)
- **Decimal fields** (amounts) are strings with 2 decimal places
- **Phone numbers** should include country code (e.g., 254700123456 for Kenya)
- **External IDs** format: R001-R999 (Riders), BS001-BS999 (Roadies), IT001-IT999 (Mechanics)
- **Single Device Login** ensures only one device can be logged in per account at a time
- **Payment amounts** are in KES (Kenyan Shillings)
- **Profile Photos**: Maximum 5MB. Supported formats: JPG, PNG, GIF, WebP. Old photos are automatically deleted on new upload.
- **Profile Editing**: Both riders and roadies can update their personal information. Email, phone, and username must be unique across the platform.
- **Image Storage**: Profile photos are organized by user type and external ID for easy management

---

**Document Version:** 1.2
**Last Updated:** March 4, 2026
**Status:** ✅ Production Ready

**Recent Updates (v1.2):**
- ✅ Added Roadie Service Selection endpoints
- ✅ First-time service selection with `services_selected` flag
- ✅ POST `/api/users/auth/rodie/services/initial/` for first-time selection
- ✅ GET/POST `/api/users/auth/rodie/services/` for managing services
- ✅ Login response now includes `services_selected` flag
- ✅ Roadies cannot access initial service selection if already selected
- ✅ Drawer menu can update services multiple times

**Previous Updates (v1.1):**
- ✅ Added Profile Editing endpoint (PATCH `/api/users/profile/`)
- ✅ Added Profile Photo Upload endpoint (POST `/api/users/profile/photo/`)
- ✅ Added Profile Photo Retrieval endpoint (GET `/api/users/profile/photo/`)
- ✅ Both riders and roadies can update their profiles
- ✅ Image upload with 5MB size limit
- ✅ Automatic old profile photo deletion on new upload

