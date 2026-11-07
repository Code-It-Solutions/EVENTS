# KAYO Mobile API Documentation

## Base URL
```
https://monsiuer.pythonanywhere.com/api/v1
```

## Authentication
All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## Endpoints

### 🔓 Public Endpoints (No Authentication Required)

#### Status & Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Check API status and JWT availability |
| GET | `/health` | API health check |
| GET | `/docs` | Get full API documentation (JSON) |

#### Church Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/church/archdeaconries` | Get list of all archdeaconries |
| GET | `/church/parishes` | Get parishes (optional: `?archdeaconry=name`) |
| GET | `/church/local-churches` | Get local churches (optional: `?parish=name`) |
| GET | `/church/hierarchy` | Get complete church hierarchy tree |

#### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | List all events |
| GET | `/events/<id>` | Get event details |
| GET | `/events/active` | Get currently active event |

---

### 🔐 Authentication Endpoints

#### Login
```http
POST /auth/login
Content-Type: application/json

{
    "email_or_phone": "user@example.com",
    "password": "your_password"
}
```

**Response:**
```json
{
    "success": true,
    "token": "eyJ...",
    "user": {
        "id": 1,
        "name": "John Doe",
        "email": "user@example.com",
        "role": "chair"
    }
}
```

#### Register
```http
POST /auth/register
Content-Type: application/json

{
    "name": "John Doe",
    "email": "user@example.com",
    "phone": "0712345678",
    "password": "secure_password",
    "role": "chair",
    "local_church": "St. Paul's",
    "parish": "Nairobi Central",
    "archdeaconry": "Nairobi"
}
```

#### Google OAuth Login
```http
POST /auth/google
Content-Type: application/json

{
    "id_token": "google_id_token_from_android_app"
}
```

#### Forgot Password
```http
POST /auth/forgot-password
Content-Type: application/json

{
    "email": "user@example.com"
}
```

#### Reset Password
```http
POST /auth/reset-password
Content-Type: application/json

{
    "token": "reset_token_from_email",
    "new_password": "new_secure_password"
}
```

#### Change Password (Authenticated)
```http
POST /auth/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
    "current_password": "old_password",
    "new_password": "new_password"
}
```

---

### 👤 Profile Endpoints (Authentication Required)

#### Get Profile
```http
GET /auth/profile
Authorization: Bearer <token>
```

#### Update Profile
```http
PUT /auth/profile
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Updated Name",
    "phone": "0712345678",
    "local_church": "New Church",
    "parish": "New Parish",
    "archdeaconry": "New Archdeaconry"
}
```

---

### 👥 Delegate Endpoints (Authentication Required)

#### List Delegates
```http
GET /delegates
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number (default: 1) |
| per_page | int | Items per page (default: 50) |
| is_paid | bool | Filter by payment status |
| archdeaconry | string | Filter by archdeaconry |
| parish | string | Filter by parish |
| search | string | Search by name/ticket |

#### Register Delegate
```http
POST /delegates
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Delegate Name",
    "phone_number": "0712345678",
    "local_church": "St. Paul's",
    "parish": "Nairobi Central",
    "archdeaconry": "Nairobi",
    "gender": "Male",
    "category": "Delegate",
    "pricing_tier_id": 1,
    "event_id": 1
}
```

#### Get Delegate
```http
GET /delegates/<id>
Authorization: Bearer <token>
```

#### Update Delegate
```http
PUT /delegates/<id>
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Updated Name",
    "phone_number": "0712345679"
}
```

#### Delete Delegate
```http
DELETE /delegates/<id>
Authorization: Bearer <token>
```

#### Bulk Upload (Excel)
```http
POST /delegates/bulk-upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <excel_file.xlsx>
```

#### Download Bulk Template
```http
GET /delegates/bulk-template
Authorization: Bearer <token>
```

---

### ✅ Check-in Endpoints (Authentication Required)

#### QR Code Check-in
```http
POST /checkin/scan
Authorization: Bearer <token>
Content-Type: application/json

{
    "qr_data": "KAYO|TKT-001|John Doe|0712345678",
    "session_id": 1
}
```

#### Manual Check-in
```http
POST /checkin/manual
Authorization: Bearer <token>
Content-Type: application/json

{
    "search": "TKT-001",
    "delegate_id": 1,
    "session_id": 1
}
```

---

### 📊 Dashboard Endpoints (Authentication Required)

#### Get Statistics
```http
GET /dashboard/stats
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| event_id | int | Filter by event |

**Response:**
```json
{
    "stats": {
        "total_delegates": 100,
        "paid_delegates": 75,
        "unpaid_delegates": 25,
        "checked_in": 50,
        "total_amount_due": 25000
    }
}
```

#### Recent Delegates
```http
GET /dashboard/recent-delegates
Authorization: Bearer <token>
```

---

### 💳 Payment Endpoints (Authentication Required)

#### Initiate M-Pesa Payment
```http
POST /payments/initiate
Authorization: Bearer <token>
Content-Type: application/json

{
    "delegate_ids": [1, 2, 3],
    "phone_number": "254712345678"
}
```

#### Check Payment Status
```http
GET /payments/status/<payment_id>
Authorization: Bearer <token>
```

#### Confirm Payment (Finance Role Only)
```http
POST /payments/confirm
Authorization: Bearer <token>
Content-Type: application/json

{
    "delegate_ids": [1, 2, 3],
    "receipt_number": "RCP-001",
    "payment_method": "mpesa",
    "amount": 3000
}
```

#### Get Pending Payment Delegates (Finance Role Only)
```http
GET /payments/pending-delegates
Authorization: Bearer <token>
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number |
| per_page | int | Items per page |
| archdeaconry | string | Filter by archdeaconry |
| parish | string | Filter by parish |

---

### 🔔 Notification Endpoints (Authentication Required)

#### Register Device for Push Notifications
```http
POST /notifications/register-device
Authorization: Bearer <token>
Content-Type: application/json

{
    "fcm_token": "firebase_cloud_messaging_token",
    "device_type": "android"
}
```

---

## User Roles & Permissions

| Role | Delegate Registration | Payment Confirmation | Bulk Upload |
|------|----------------------|---------------------|-------------|
| chair | ✅ | ❌ | ❌ |
| minister | ✅ | ❌ | ❌ |
| clerk | ✅ | ❌ | ✅ |
| registrar | ✅ | ✅ | ✅ |
| treasurer | ❌ | ✅ | ❌ |
| finance | ❌ | ✅ | ❌ |
| admin | ✅ | ✅ | ✅ |
| super_admin | ✅ | ✅ | ✅ |

---

## Error Responses

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input data |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource does not exist |
| 500 | Internal Server Error |
| 503 | Service Unavailable - JWT not installed |

### Error Response Format
```json
{
    "success": false,
    "error": "Error message description"
}
```

---

## Android Integration Tips

### 1. Store JWT Token Securely
Use Android's EncryptedSharedPreferences to store the JWT token:
```kotlin
val sharedPreferences = EncryptedSharedPreferences.create(
    "secure_prefs",
    masterKeyAlias,
    context,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
)
```

### 2. Add Token to All Requests
```kotlin
val client = OkHttpClient.Builder()
    .addInterceptor { chain ->
        val request = chain.request().newBuilder()
            .addHeader("Authorization", "Bearer $token")
            .build()
        chain.proceed(request)
    }
    .build()
```

### 3. Handle Token Expiration
Tokens expire after 7 days. When you receive a 401 error, redirect to login.

### 4. QR Code Format
When scanning QR codes, the format is:
```
KAYO|TICKET_NUMBER|NAME|PHONE
```

Example: `KAYO|TKT-2024-001|John Doe|0712345678`

---

## Sample Android Retrofit Interface

```kotlin
interface KayoApiService {
    
    // Auth
    @POST("auth/login")
    suspend fun login(@Body credentials: LoginRequest): Response<AuthResponse>
    
    @POST("auth/register")
    suspend fun register(@Body user: RegisterRequest): Response<AuthResponse>
    
    @POST("auth/forgot-password")
    suspend fun forgotPassword(@Body email: ForgotPasswordRequest): Response<ApiResponse>
    
    @POST("auth/reset-password")
    suspend fun resetPassword(@Body request: ResetPasswordRequest): Response<ApiResponse>
    
    @POST("auth/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): Response<ApiResponse>
    
    @GET("auth/profile")
    suspend fun getProfile(): Response<UserProfile>
    
    // Delegates
    @GET("delegates")
    suspend fun getDelegates(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 50,
        @Query("is_paid") isPaid: Boolean? = null
    ): Response<DelegatesResponse>
    
    @POST("delegates")
    suspend fun registerDelegate(@Body delegate: DelegateRequest): Response<DelegateResponse>
    
    // Check-in
    @POST("checkin/scan")
    suspend fun scanCheckin(@Body qrData: CheckinRequest): Response<CheckinResponse>
    
    // Dashboard
    @GET("dashboard/stats")
    suspend fun getStats(@Query("event_id") eventId: Int? = null): Response<StatsResponse>
    
    // Church Data
    @GET("church/hierarchy")
    suspend fun getChurchHierarchy(): Response<ChurchHierarchy>
}
```

---

## Live API Test
Visit the docs endpoint to get a JSON version of this documentation:
```
GET https://monsiuer.pythonanywhere.com/api/v1/docs
```
