````markdown
# Google OAuth Setup Guide

This guide will help you set up Google OAuth for your LUMO application.

## Step 1: Create a Google OAuth Application

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **+ Create Credentials** → **OAuth 2.0 Client ID**
5. If prompted, configure the OAuth consent screen first:
   - Choose **External** for User Type
   - Fill in the required fields (App name, User support email, etc.)
   - Add scopes: `openid`, `email`, `profile`
6. For OAuth 2.0 Client ID:
   - Application type: **Web application**
   - Name: "LUMO"
   - Add Authorized JavaScript origins:
     - `http://localhost:5000` (for local development)
     - `https://yourdomain.com` (for production)
   - Add Authorized redirect URIs:
     - `http://localhost:5000/auth/callback/google` (for local)
     - `https://yourdomain.com/auth/callback/google` (for production)
7. Copy the **Client ID** and **Client Secret**

## Step 2: Configure Environment Variables

1. Create or update your `.env` file in the project root:

```bash
SECRET_KEY=your-secret-key-here
TMDB_API_KEY=your-tmdb-api-key-here
GOOGLE_CLIENT_ID=your-client-id-from-google
GOOGLE_CLIENT_SECRET=your-client-secret-from-google
```

Make sure your `.env` file is added to `.gitignore` and never committed to version control.

## Step 3: Install Dependencies

Run the following command to install the required packages:

```bash
pip install -r requirements.txt
```

This will install:

- `google-auth-oauthlib==1.0.0`
- `google-auth==2.25.2`

## Step 4: Update Database Schema

If you have an existing database with users, run the migration script:

```bash
python scripts/migrate_add_oauth.py
```

This adds the new columns needed for OAuth:

- `google_id` (unique identifier from Google)
- `oauth_provider` (authentication provider)
- Makes `password_hash` nullable (for OAuth-only users)

For new databases, the columns will be created automatically when you initialize the app.

## Step 5: Test the Setup

1. Start your Flask app:

```bash
python app.py
```

2. Navigate to the login page: `http://localhost:5000/auth/login`

3. You should see a "Continue with Google" button

4. Click it and follow the Google authentication flow

## Features

✅ **Login with Google Account** - Users can sign in using their Google account
✅ **Automatic Account Creation** - New users are automatically registered
✅ **Account Linking** - Existing users can link their Google account
✅ **Profile Picture** - User's Google profile picture is automatically set as avatar
✅ **Password-less Login** - OAuth users don't need to set a password

## How It Works

1. User clicks "Continue with Google" button
2. App redirects to Google's authorization endpoint
3. User logs in with their Google account and grants permissions
4. Google redirects back to `/auth/callback/google` with an authorization code
5. App exchanges code for access token
6. App retrieves user info (name, email, profile picture)
7. App checks if user exists:
   - If yes: User is logged in
   - If no: New user is created and logged in
8. User is redirected to home page

## Troubleshooting

### "Failed to get authorization code from Google"

- Check that your redirect URIs in Google Console match exactly
- Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set correctly

### CORS or redirect errors

- Verify authorized JavaScript origins in Google Cloud Console
- For local development, use `http://localhost:5000` (not `https`)

### "Invalid Client ID"

- Double-check your `GOOGLE_CLIENT_ID` in `.env`
- Make sure it matches what's in Google Cloud Console

## Additional Notes

- The app uses OpenID Connect (OIDC) for secure authentication
- Access tokens are obtained but not stored (stateless)
- User profile data is fetched fresh each time during callback
- OAuth users have `oauth_provider='google'` in the database
````
