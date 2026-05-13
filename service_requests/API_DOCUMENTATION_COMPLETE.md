# Vehix System - Complete API & WebSocket Documentation

This documentation covers the entire Vehix platform, including Client APIs (Rider/Roadie), Admin Dashboard APIs, and Real-time WebSocket events.

## Table of Contents
1. [Authentication](#1-authentication)
2. [User & Wallet APIs](#2-user--wallet-apis)
3. [Service Request APIs (Client)](#3-service-request-apis-client)
4. [Roadie Operations](#4-roadie-operations)
5. [Image & KYC APIs](#5-image--kyc-apis)
6. [Admin Dashboard APIs](#6-admin-dashboard-apis)
    - [Service Requests](#admin-service-requests)
    - [Real-time Monitoring](#admin-real-time)
    - [User & Wallet Management](#admin-users)
    - [Service Configuration](#admin-services)
7. [WebSockets (Real-time)](#7-websockets-real-time)

---

## 1. Authentication

**Base URL:** `/api/users/` or `/api/auth/` (depending on router configuration)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| POST | `register/` | Register a new user (Rider or Roadie). | No |
| POST | `login/` | Obtain JWT Access & Refresh tokens. | No |
| POST | `refresh/` | Refresh an expired access token. | No |

**Headers for Authenticated Requests:**
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## 2. User & Wallet APIs

**Base URL:** `/api/users/`

### Profile
- **GET** `me/`
  - Returns current user details, role, and approval status.

### Wallet
- **GET** `wallet/`
  - Returns current balance and transaction history.
- **POST** `wallet/deposit/`
  - Initiate a deposit (e.g., via PesaPal STK Push).
- **POST** `wallet/withdraw/`
  - Request a withdrawal.

### Notifications
- **GET** `notifications/`
  - List in-app notifications.
- **PATCH** `notifications/<id>/`
  - Mark notification as read.

---

## 3. Service Request APIs (Client)

**Base URL:** `/api/requests/`

### Create Request (Rider)
**POST** `create/`
```json
{
  "service_type": 1,
  "rider_lat": 6.5244,
  "rider_lng": 3.3792
}
```
**Response:** Returns the created request with status `REQUESTED`.

### My Requests (Rider)
**GET** `my/`
- **Query Params:** `?status=active` (optional)
- Returns a list of requests.

### Nearby Roadies (Rider)
**GET** `nearby/`
- **Query Params:** `lat`, `lng`, `service_id`
- Returns active roadies with ETA and distance (calculated via OSRM).

### Chat
**POST** `<id>/chat/`
- Sends a chat message to the request participants.
- **Body:** `{"text": "Hello"}`

---

## 4. Roadie Operations

### Status & Services
- **POST** `/api/users/roadie/status/`
  - Body: `{"is_online": true, "lat": 6.52, "lng": 3.37}`
- **GET** `/api/rodie/services/`
  - List services offered by the logged-in Roadie.

### Request Lifecycle (Roadie)
These endpoints update the state of a Service Request.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| POST | `<id>/accept/` | Accept a request. Checks wallet balance. |
| POST | `<id>/decline/` | Decline a request. |
| POST | `<id>/enroute/` | Mark status as `EN_ROUTE`. |
| POST | `<id>/start/` | Mark status as `STARTED`. |
| POST | `<id>/complete/` | Mark status as `COMPLETED`. Triggers fee charge. |

---

## 5. Image & KYC APIs

**Base URL:** `/api/images/`

### User Uploads
- **POST** `user-images/`
  - Upload Profile Picture or ID documents.
  - **Body (Multipart):** `image` (file), `image_type` (e.g., 'PROFILE'), `description`.
- **GET** `user-images/`
  - List uploaded images.

---

## 6. Admin Dashboard APIs

These APIs are for the back-office dashboard. Requires `role='ADMIN'`.

### Admin: Service Requests
**Base URL:** `/api/admin/requests/`

- **GET** `/`
  - List all requests. Supports filtering/searching by username or status.
- **POST** `/`
  - Create a request manually (e.g., for phone bookings).
  - **Body:** `{"rider_username_input": "...", "service_type_id": 1, ...}`
- **PATCH** `<id>/`
  - Update request status or assign a Roadie manually.
- **POST** `<id>/assign/`
  - Manually assign a Roadie to a `REQUESTED` task.
- **GET** `<id>/route/`
  - Get route details (geometry/ETA) between assigned Roadie and Rider.

### Admin: Real-time
**Base URL:** `/api/admin/requests/realtime/`

- **GET** `locations/`
  - Returns a list of active riders/requests with current coordinates.
- **GET** `map/`
  - Returns a GeoJSON `FeatureCollection` of active requests for map rendering.

### Admin: Users
**Base URL:** `/api/admin/users/` (Inferred)

- **GET** `wallets/`
  - View all user wallet balances.
- **POST** `images/admin-upload/`
  - Upload images on behalf of a user (e.g., manual KYC verification).
  - **Serializer:** `AdminImageUploadSerializer`

### Admin: Services
**Base URL:** `/api/admin/services/` (Inferred)

- **GET/POST** `/`
  - Manage `ServiceType` objects (e.g., Towing, Tire Change).
  - **Serializer:** `ServiceTypeSerializer` (Fields: `name`, `code`, `is_active`).

### Platform Config
- **GET/POST** `/api/platform/config/`
  - Manage global settings like `service_fee` and `max_negative_balance`.

---

## 7. WebSockets (Real-time)

The system uses Django Channels. Clients must connect to the appropriate endpoint based on their role.

**Base URL:** `wss://<host>/ws/`

### Connection Endpoints
1. **Rider:** `/ws/rider/?token=<jwt_access_token>`
2. **Roadie:** `/ws/rodie/?token=<jwt_access_token>`
3. **Request Chat:** `/ws/request/<request_id>/?token=<jwt_access_token>`

### Events: Server -> Client

#### To Roadie (`RodieConsumer`)
| Event Type | Payload | Description |
| :--- | :--- | :--- |
| `OFFER_REQUEST` | `{ data: { ...request_details... } }` | A new request is available for acceptance. |
| `NEW_REQUEST` | `{ data: { ... } }` | Broadcast of a new request in the vicinity. |
| `CHAT_MESSAGE` | `{ sender_id, text, ... }` | Chat message from Rider. |

#### To Rider (`RiderConsumer`)
| Event Type | Payload | Description |
| :--- | :--- | :--- |
| `RODIE_LOCATION` | `{ lat, lng }` | Real-time location updates from the assigned Roadie. |
| `RODIE_STATUS` | `{ data: ... }` | Updates on Roadie status. |
| `CHAT_MESSAGE` | `{ sender_id, text, ... }` | Chat message from Roadie. |

### Events: Client -> Server

#### From Roadie
- **Location Update:**
  ```json
  {
    "type": "LOCATION",
    "lat": 6.5244,
    "lng": 3.3792,
    "rider_id": 5  // ID of the rider being serviced
  }
  ```
  *Server forwards this to the specific Rider as `RODIE_LOCATION`.*

- **Chat:**
  ```json
  {
    "type": "CHAT",
    "request_id": 101,
    "text": "I'm here!"
  }
  ```

#### From Rider
- **Chat:**
  ```json
  {
    "type": "CHAT",
    "request_id": 101,
    "text": "Where are you?"
  }
  ```