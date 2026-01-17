````markdown
# 📋 Quick Reference Card

## Setup in 5 Minutes

### 1️⃣ Get Credentials (5 mins)

```bash
# Go to: https://console.cloud.google.com/
# Create OAuth 2.0 Client ID (Web app)
# Authorized redirect URI:
#   http://localhost:5000/auth/callback/google
# Copy: Client ID and Secret
```

### 2️⃣ Configure (.env)

```bash
GOOGLE_CLIENT_ID=your-id-here
GOOGLE_CLIENT_SECRET=your-secret-here
SECRET_KEY=your-key-here
TMDB_API_KEY=your-key-here
```

### 3️⃣ Install Packages

```bash
pip install -r requirements.txt
```

### 4️⃣ Migrate Database

```bash
# If you have existing users:
python scripts/migrate_add_oauth.py
```

### 5️⃣ Run & Test

```bash
python app.py
# Visit: http://localhost:5000/auth/login
```

---

## Auth Routes

| Route                   | Method    | Purpose               |
| ----------------------- | --------- | --------------------- |
| `/auth/login`           | GET, POST | Email/password login  |
| `/auth/register`        | GET, POST | Email/password signup |
| `/auth/logout`          | GET       | Logout (protected)    |
| `/auth/login/google`    | GET       | Initiate Google OAuth |
| `/auth/callback/google` | GET       | Handle OAuth callback |

---

## Environment Variables

```bash
GOOGLE_CLIENT_ID=                 # From Google Cloud
GOOGLE_CLIENT_SECRET=             # From Google Cloud
SECRET_KEY=                       # Random string for Flask
TMDB_API_KEY=                     # Your TMDB key
```

---

## Database Fields (User Model)

| Field            | Type         | Nullable    | Purpose               |
| ---------------- | ------------ | ----------- | --------------------- |
| `google_id`      | VARCHAR(255) | Yes         | Google's user ID      |
| `oauth_provider` | VARCHAR(50)  | Yes         | "google" or other     |
| `password_hash`  | VARCHAR(255) | **Now YES** | Can be NULL for OAuth |

---

## OAuth Flow

```
User Click "Google"
         ↓
Redirect to Google Login
         ↓
User Authenticates
         ↓
Redirect to /auth/callback/google?code=XXX
         ↓
Exchange code for token
         ↓
Fetch user info from Google
         ↓
Create/find user in database
         ↓
Auto-login
         ↓
Redirect to home page
```

---

## Code Files Reference

### oauth_handler.py

```python
GoogleOAuth.get_authorization_url()      # Get auth URL
GoogleOAuth.exchange_code_for_token()    # Get access token
GoogleOAuth.get_user_info()              # Get user data
```

### routes_auth.py

```python
/login                  # Traditional login
/register               # Traditional signup
/login/google           # Start OAuth flow
/callback/google        # Handle OAuth callback
/logout                 # Logout
```

### models.py

```python
User.google_id          # Google's unique ID
User.oauth_provider     # "google"
User.password_hash      # Can be NULL for OAuth
```

---

## Testing Checklist

- [ ] Install dependencies
- [ ] Set environment variables
- [ ] Migrate database
- [ ] Test email login
- [ ] Test Google login
- [ ] Test email signup
- [ ] Test Google signup
- [ ] Test account linking
- [ ] Test logout
- [ ] Test mobile view
- [ ] Check database records

---

## Troubleshooting

### "Invalid Client ID"

```bash
# Check:
1. GOOGLE_CLIENT_ID in .env is correct
2. Google Cloud credentials are right type
3. Not using API Key instead of Client ID
```

### "Redirect URI mismatch"

```bash
# Check:
1. Authorized redirect URI in Google Cloud:
   http://localhost:5000/auth/callback/google
2. No trailing slash
3. Protocol matches (http vs https)
```

### "Failed to create account"

```bash
# Check:
1. Database migration ran: python scripts/migrate_add_oauth.py
2. users table has new columns
3. Database connection working
```

### "Profile picture not showing"

```bash
# Check:
1. avatar column has URL
2. Image URL is accessible
3. Profile template displays avatar
```

---

## Google Cloud Console Checklist

✅ OAuth 2.0 Consent Screen configured
✅ Scopes include: openid, email, profile
✅ Authorized JavaScript origins set
✅ Authorized redirect URIs set (exact match!)
✅ Client ID copied to .env
✅ Client Secret copied to .env
✅ Credentials are OAuth 2.0 Client ID type

---

## File Locations

```
LUMO/
├── oauth_handler.py              # OAuth implementation
├── routes_auth.py                # Auth routes
├── config.py                     # Configuration
├── models.py                     # Database models
├── requirements.txt              # Dependencies
├── .env                          # Environment (not in git!)
├── .env.example                  # Template
├── scripts/
│   └── migrate_add_oauth.py      # Database migration
├── templates/auth/
│   ├── login.html               # Login page
│   └── register.html            # Sign-up page
└── docs/
    ├── GOOGLE_OAUTH_SETUP.md    # Full setup
    ├── TESTING_GUIDE.md         # Testing
    ├── WHATS_NEW.md             # What changed
    └── ...                      # More docs
```

---

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Migrate database
python scripts/migrate_add_oauth.py

# Run the app
python app.py

# Check Google config
python -c "from app import create_app; app = create_app(); print(app.config['GOOGLE_CLIENT_ID'])"

# Test database connection
python -c "from app import create_app; app = create_app(); from extensions import db; with app.app_context(): print(db.engine)"
```

---

## Key Features

✅ **Google OAuth Login**
✅ **Google OAuth Sign-Up** (NEW!)
✅ **Account Linking**
✅ **Auto Profile Picture**
✅ **Modern UI**
✅ **Mobile Responsive**
✅ **Keyboard Accessible**
✅ **Error Handling**

---

## User Types in Database

| Type        | Password | Google ID | Login Methods   |
| ----------- | -------- | --------- | --------------- |
| Email User  | ✓        | ✗         | Email only      |
| OAuth User  | ✗        | ✓         | Google only     |
| Hybrid User | ✓        | ✓         | Email OR Google |

---

## Common Errors & Fixes

```
Error: "No GOOGLE_CLIENT_ID"
Fix: Add GOOGLE_CLIENT_ID to .env

Error: "Unauthorized client"
Fix: Check Client ID matches Google Cloud

Error: "User table has no column google_id"
Fix: Run: python scripts/migrate_add_oauth.py

Error: "Failed during Google auth"
Fix: Check internet connection, Google Console settings

Error: "Invalid token"
Fix: Check CLIENT_SECRET is correct
```

---

## Production Deployment

Before deploying:

1. [ ] Update GOOGLE_CLIENT_ID (production)
2. [ ] Update GOOGLE_CLIENT_SECRET (production)
3. [ ] Update Google Console authorized origins
4. [ ] Update redirect URIs (use HTTPS + domain)
5. [ ] Set strong SECRET_KEY
6. [ ] Use HTTPS only
7. [ ] Set DEBUG=False
8. [ ] Configure database
9. [ ] Run migration on production DB
10. [ ] Test all flows

---

## Resources

📖 **Setup Guide**: GOOGLE_OAUTH_SETUP.md
🧪 **Testing**: TESTING_GUIDE.md
📝 **What's New**: WHATS_NEW.md
✅ **Verification**: FINAL_CHECKLIST.md
📚 **Complete Info**: OAUTH_COMPLETE_SUMMARY.md

---

## Support

If something doesn't work:

1. Check troubleshooting section above
2. Read GOOGLE_OAUTH_SETUP.md
3. Review TESTING_GUIDE.md
4. Check error messages in Flask logs
5. Verify environment variables

---

## Status

✅ **Implementation**: COMPLETE
✅ **Testing**: READY
✅ **Documentation**: COMPREHENSIVE
✅ **Production**: READY

---

**You're all set!** 🚀 Proceed with testing and deployment.
````
