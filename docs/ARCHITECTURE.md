````markdown
# 🎨 Implementation Overview

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   USER INTERFACE                         │
├────────────────────┬────────────────────────────────────┤
│  Login Page        │  Sign-Up Page (NEW!)               │
│  ├─ Email Form     │  ├─ Name/Email/Password Form       │
│  ├─ Google Button  │  ├─ Google Button (NEW!)           │
│  └─ Sign-up Link   │  └─ Login Link                     │
└────────────────────┴────────────────────────────────────┘
         ↓                         ↓
┌─────────────────────────────────────────────────────────┐
│                  AUTHENTICATION LAYER                    │
├─────────────────────────────────────────────────────────┤
│  routes_auth.py (5 endpoints)                           │
│  ├─ /login (POST) - Email authentication                │
│  ├─ /register (POST) - Email registration               │
│  ├─ /login/google (GET) - OAuth initiation              │
│  ├─ /callback/google (GET) - OAuth callback             │
│  └─ /logout (POST) - Session cleanup                    │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│                  OAUTH HANDLER LAYER                     │
├─────────────────────────────────────────────────────────┤
│  oauth_handler.py                                        │
│  ├─ get_authorization_url() → Google Auth Page          │
│  ├─ exchange_code_for_token() → Access Token            │
│  ├─ get_user_info() → User Profile Data                 │
│  └─ get_redirect_uri() → Callback URL                   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│              GOOGLE OAUTH 2.0 SERVICE                    │
├─────────────────────────────────────────────────────────┤
│  https://accounts.google.com/                            │
│  ├─ Authorization endpoint                              │
│  ├─ Token endpoint                                      │
│  └─ User info endpoint                                  │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│                   DATABASE LAYER                         │
├─────────────────────────────────────────────────────────┤
│  SQLite (models.py - User model)                         │
│  ├─ id (PK)                                             │
│  ├─ name                                                │
│  ├─ email (UNIQUE)                                      │
│  ├─ password_hash (NULLABLE - NEW!)                     │
│  ├─ avatar                                              │
│  ├─ google_id (UNIQUE) - NEW!                           │
│  ├─ oauth_provider - NEW!                               │
│  └─ created_at                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### Traditional Login Flow

```
User Form Input (email + password)
         ↓
routes_auth.py::login()
         ↓
Query User.email
         ↓
Verify password_hash
         ↓
login_user() ← Flask-Login
         ↓
Create Session
         ↓
Redirect to home
```

### Google OAuth Flow

```
User Clicks "Google"
         ↓
routes_auth.py::google_login()
         ↓
Redirect to Google Auth URL
         ↓
User Authenticates @ Google
         ↓
Google Redirects: /callback/google?code=XXX
         ↓
routes_auth.py::google_callback()
         ↓
oauth_handler.exchange_code_for_token()
         ↓
oauth_handler.get_user_info()
         ↓
Query User.google_id
         ├─ Found? → Use existing user
         └─ Not found? → Create new user
         ↓
login_user() ← Flask-Login
         ↓
Create Session
         ↓
Redirect to home
```

---

## Database Schema Visualization

```
USERS TABLE
┌────────────┬──────────────┬────────────────┐
│ Column     │ Type         │ Notes          │
├────────────┼──────────────┼────────────────┤
│ id (PK)    │ INTEGER      │ Auto-increment │
│ name       │ VARCHAR(100) │ Required       │
│ email      │ VARCHAR(120) │ UNIQUE         │
│ password_  │ VARCHAR(255) │ NULLABLE *NEW* │
│   hash     │              │                │
│ bio        │ TEXT         │ Optional       │
│ avatar     │ VARCHAR(255) │ Optional       │
│ role       │ VARCHAR(10)  │ default:user   │
│ created_at │ DATETIME     │ Timestamp      │
│ google_id  │ VARCHAR(255) │ UNIQUE *NEW*   │
│ oauth_     │ VARCHAR(50)  │ "google" *NEW* │
│   provider │              │                │
└────────────┴──────────────┴────────────────┘

* NULLABLE password_hash allows OAuth-only users
* UNIQUE google_id prevents duplicate OAuth IDs
* oauth_provider allows future OAuth providers
```

---

## Request/Response Lifecycle

```
Google OAuth Login Flow (Detailed)

1. Client: GET /auth/login/google
   ▼
2. Server: Generates authorization URL
   ▼
3. Client: Redirects to Google auth endpoint
   ▼
4. Google: Prompts user to authenticate
   ▼
5. Google: Asks for permissions (email, profile)
   ▼
6. User: Approves permissions
   ▼
7. Google: Redirects to callback URL with code
   └─ GET /auth/callback/google?code=ABC123&state=XYZ
   ▼
8. Server: Validates code & state
   ▼
9. Server: POSTs code + client_secret to Google
   ▼
10. Google: Returns access_token
    ▼
11. Server: GETs user info from Google using token
    ▼
12. Server: Creates/updates user in database
    ▼
13. Server: Creates session
    ▼
14. Server: Redirects to home page
    ▼
15. Client: User now logged in!
```

---

## Configuration Flow

```
.env file
│
├─ GOOGLE_CLIENT_ID ──────┐
├─ GOOGLE_CLIENT_SECRET ──┤
├─ SECRET_KEY ────────────┼──→ config.py
├─ TMDB_API_KEY ──────────┤
│                          ├──→ app.py
│                          │
└─────────────────────────┘
                          │
                          ▼
                    Flask Config
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     oauth_handler   routes_auth      models
      (reads)         (reads)         (reads)
```

---

## Summary

✅ **Architecture**: Modular, with separation of concerns
✅ **Security**: OAuth 2.0 backend token exchange
✅ **Database**: Extended User model with OAuth fields
✅ **UI**: Modern, responsive login and sign-up
✅ **Documentation**: Comprehensive guides included
✅ **Ready**: For immediate testing and deployment

---

**Everything is connected and working together!** 🎯
````
