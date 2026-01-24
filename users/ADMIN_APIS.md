# Vehix App API Documentation

This document provides a comprehensive list of all APIs (HTTP and WebSockets) required to connect the **Rider** and **Roadie** mobile applications to the Vehix backend.

## Base URL
- **API Base**: `https://0ae745a8c873.ngrok-free.app/api/`
- **WebSocket Base**: `wss://0ae745a8c873.ngrok-free.app/ws/`

---

## 1. Shared / Core APIs

### Authentication
| Endpoint | Method | Description | Roles |
| :--- | :--- | :--- | :--- |
| `register/` | POST | Register a new user. | ALL |
| `login/` | POST | Obtain JWT access/refresh tokens. | ALL |
| `refresh/` | POST | Refresh an expired access token. | ALL |
| `me/` | GET | Retrieve the current user's profile. | ALL |

**JWT Header**: `Authorization: Bearer <access_token>`

### Wallet & Payments
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `wallet/` | GET | View current balance and recent transactions. |
| `wallet/deposit/` | POST | Initiate a deposit (triggers PesaPal STK Push if phone provided). |
| `wallet/withdraw/` | POST | Request a withdrawal from the wallet. |

### Images & KYC
Users (Riders/Roadies) can upload profile pictures or KYC documents.
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `images/user-images/` | POST | Upload a new image (multipart/form-data). |
| `images/user-images/` | GET | List my uploaded images. |
| `images/user-images/thumbnails/` | GET | Get thumbnails of my images. |

**Upload Payload (Multipart):**
- `image`: File
- `image_type`: String (e.g., "PROFILE", "NIN_FRONT", "NIN_BACK")
- `description`: String (Optional)

### Notifications
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `notifications/` | GET | List all in-app notifications. |
| `notifications/<id>/` | PATCH | Mark a notification as read (`{"read": true}`). |

---

## 2. Rider Specific APIs

### Service Management
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `requests/create/` | POST | Request a service at current location. |
| `requests/my/` | GET | List all service requests made by the rider. |
| `requests/my/?status=active` | GET | List only active requests (Accepted, En-route, etc.). |
| `requests/<id>/cancel/` | POST | Cancel a pending or accepted request. |
| `requests/nearby/` | GET | Search for nearby active Roadies via HTTP. |

**Create Request Payload:**
```json
{
  "service_type": 1, // Service ID
  "rider_lat": -1.234567,
  "rider_lng": 36.789012
}
```

---

## 3. Roadie Specific APIs

### Service Settings
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `roadie/status/` | POST | Update online/offline status (`is_online`: true/false). |
| `rodie/services/` | GET | List services currently offered by this Roadie. |
| `rodie/services/` | POST | Bulk update offered services. |

**Update Services Payload:**
```json
{
  "service_ids": [1, 2, 5]
}
```

### Request Lifecycle
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `requests/<id>/accept/` | POST | Accept a new service request. |
| `requests/<id>/decline/` | POST | Decline a service request notification. |
| `requests/<id>/enroute/` | POST | Notify Rider that you are heading to their location. |
| `requests/<id>/start/` | POST | Mark the service as started. |
| `requests/<id>/complete/` | POST | Mark the service as finished. |

---

## 4. Real-time Communication (WebSockets)

### Rider WebSocket (`ws/rider/`)
**Outgoing (Client to Server):**
- **Type `LOCATION`**: Update GPS to stay "Online" and let Roadies find you.
  ```json
  { "type": "LOCATION", "lat": -1.23, "lng": 36.89 }
  ```

**Incoming (Server to Client):**
- **Type `RODIE_LOCATION`**: Real-time position of the assigned Roadie.
- **Type `REQUEST_UPDATE`**: Status changes (Accepted, En-route, etc.).
- **Type `CHAT_MESSAGE`**: New chat from Roadie.

### Roadie WebSocket (`ws/rodie/`)
**Outgoing (Client to Server):**
- **Type `LOCATION`**: Required during active requests for Rider tracking.
  ```json
  { "type": "LOCATION", "lat": -1.23, "lng": 36.89, "rider_id": 456 }
  ```
- **Type `CHAT`**: Send message to Rider.
  ```json
  { "type": "CHAT", "request_id": 789, "text": "I will be there in 5m" }
  ```

**Incoming (Server to Client):**
- **Type `NEW_REQUEST`**: Broadcast to all nearby Roadies when a Rider requests a service.
- **Type `OFFER_REQUEST`**: Direct request to this specific Roadie.

### Availability Hub (`ws/availability/`)
- **Outgoing `GET_NEARBY`**: Get online Roadies around a point.
- **Incoming `NEARBY_LIST`**: List of roadie positions and IDs.

---

## 5. Admin & Monitoring APIs
For use in the platform's central administration dashboard.
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `admin/locations/realtime/` | GET | Get real-time positions of all online Roadies and active Riders. |
| `admin/locations/realtime/map/` | GET | Returns GeoJSON features for map visualization. |
| `admin/requests/realtime/` | GET | Monitor all active service requests. |
| `admin/wallets/` | GET | Manage user balances. |
| `platform/config/` | GET | View/Update platform constants (service fees, max negative balance). |
