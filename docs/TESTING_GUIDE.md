````markdown
# Google OAuth Testing Guide

## Pre-Testing Setup

### 1. Get Google OAuth Credentials

```bash
# Go to: https://console.cloud.google.com/
1. Create new project or use existing
2. Go to: APIs & Services → Credentials
3. Click: "+ Create Credentials" → "OAuth 2.0 Client ID"
4. Choose: Web application
5. Authorized JavaScript origins:
   - http://localhost:5000 (local dev)
   - https://yourdomain.com (production)
6. Authorized redirect URIs:
   - http://localhost:5000/auth/callback/google (local)
   - https://yourdomain.com/auth/callback/google (production)
7. Copy: Client ID and Client Secret
```

### 2. Configure Environment

```bash
# Create .env file in project root
echo "GOOGLE_CLIENT_ID=your-client-id" > .env
echo "GOOGLE_CLIENT_SECRET=your-client-secret" >> .env
echo "SECRET_KEY=your-secret-key" >> .env
echo "TMDB_API_KEY=your-tmdb-key" >> .env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

```bash
# If new database:
python app.py  # Will auto-create tables

# If existing database:
python scripts/migrate_add_oauth.py
```

## Testing Scenarios

### Test 1: Traditional Email/Password Login ✅

**Steps:**

1. Navigate to `http://localhost:5000/auth/login`
2. Enter registered email
3. Enter correct password
4. Click "Sign In"

**Expected:**

- Redirect to home page
- User logged in
- Session active

**Error Case:**

- Invalid password → Flash error message
- Non-existent email → Flash error message

---

### Test 2: Traditional Email/Password Sign-Up ✅

**Steps:**

1. Navigate to `http://localhost:5000/auth/register`
2. Enter new full name
3. Enter new email
4. Enter password (6+ chars)
5. Click "Create Account"

**Expected:**

- Account created
- Auto-login after registration
- Redirect to home page
- User can see profile

**Error Case:**

- Email exists → Flash error, stay on register
- Password too short → Browser validation prevents

---

### Test 3: Google OAuth Login ✅

**Steps:**

1. Navigate to `http://localhost:5000/auth/login`
2. Click "Continue with Google"
3. Sign in with Google account (use test account)
4. Grant permissions
5. Automatic redirect

**Expected:**

- Redirects to Google login page
- After auth, redirects to `/auth/callback/google`
- Then redirects to home page
- User is logged in
- "Welcome, [Name]!" message

**Database Check:**

- New user created in database
- `google_id` populated
- `oauth_provider` = "google"
- `password_hash` = NULL
- `avatar` set to Google picture
- `name` = Google name

---

### Test 4: Google OAuth Sign-Up ✅

**Steps:**

1. Navigate to `http://localhost:5000/auth/register`
2. Click "Sign up with Google"
3. Use new Google account (not yet registered)
4. Grant permissions

**Expected:**

- New account created
- Auto-logged in
- Redirect to home
- Profile shows correct info
- Profile picture is set

---

### Test 5: Account Linking ✅

**Scenario:** User already registered with email/password, then tries Google OAuth

**Steps:**

1. User registers via email/password: `test@example.com`
2. Later, clicks Google sign-up
3. Uses same email with Google account

**Expected:**

- Google ID linked to existing account
- `oauth_provider` updated to "google"
- User can now log in either way
- Original password still valid
- No duplicate account created

---

### Test 6: Multiple Sign-In Methods ✅

**Scenario:** User has both password and Google linked

**Steps:**

1. User has account with both methods
2. Try login with password
3. Then logout
4. Try login with Google

**Expected:**

- Both work
- Session properly managed
- No conflicts
- Correct user logged in each time

---

### Test 7: Error Handling ✅

**Test 7a: Missing Authorization Code**

```
URL: http://localhost:5000/auth/callback/google
(Without ?code parameter)
```

**Expected:** Flash error, redirect to login

**Test 7b: Invalid Code**

```
URL: http://localhost:5000/auth/callback/google?code=invalid123
```

**Expected:** Flash error about token exchange, redirect to login

**Test 7c: Network Error**

```
(Simulate by disconnecting internet during Google login)
```

**Expected:** Error message, graceful fallback to login page

---

### Test 8: Responsive Design ✅

**Mobile (375px width)**

- [ ] Login page layout correct
- [ ] Sign-up page layout correct
- [ ] Buttons full width
- [ ] Text readable
- [ ] No horizontal scroll
- [ ] Touch targets adequate

**Tablet (768px width)**

- [ ] Card centered
- [ ] Proper spacing
- [ ] Good readability

**Desktop (1920px width)**

- [ ] Card max-width respected (420px)
- [ ] Centered properly
- [ ] Good visual hierarchy

---

### Test 9: Accessibility ✅

**Keyboard Navigation**

1. Open login page
2. Press Tab multiple times
3. Verify focus visible on:
   - Email input
   - Password input
   - Sign In button
   - Continue with Google button
   - Sign up link

**Expected:** Logical tab order, visible focus rings

**Screen Reader (NVDA/JAWS)**

- [ ] Labels announced properly
- [ ] Button purposes clear
- [ ] Links meaningful
- [ ] Errors announced

---

### Test 10: Visual Verification ✅

**Login Page:**

- [ ] "Welcome Back" heading visible
- [ ] "Sign in to continue to LUMO" subtitle visible
- [ ] Email input with label
- [ ] Password input with label
- [ ] "Sign In" button (purple gradient)
- [ ] "Or" divider visible
- [ ] "Continue with Google" button visible
- [ ] "Don't have an account? Sign up" link visible
- [ ] No broken styling

**Sign-Up Page:**

- [ ] "Join LUMO" heading visible
- [ ] "Create your account..." subtitle visible
- [ ] Full Name input
- [ ] Email input
- [ ] Password input with hint
- [ ] "Create Account" button (purple gradient)
- [ ] "Or" divider visible
- [ ] "Sign up with Google" button visible
- [ ] "Already have an account? Sign in" link visible
- [ ] Consistent styling with login page

---

## Quick Test Checklist

```bash
# Local Testing
[ ] Start app: python app.py
[ ] Visit: http://localhost:5000/auth/login
[ ] Test email login
[ ] Test Google login redirect
[ ] Test Google callback
[ ] Visit: http://localhost:5000/auth/register
[ ] Test email signup
[ ] Test Google signup
[ ] Test mobile view (F12 → toggle device toolbar)
[ ] Test accessibility (Tab key navigation)
[ ] Check database for user records
[ ] Test logout
[ ] Check flash messages
```

## Database Verification

### After Sign-Up with Google:

```sql
SELECT * FROM users WHERE google_id IS NOT NULL;
```

Should show:

- `id` - auto-increment
- `name` - from Google
- `email` - from Google
- `password_hash` - NULL
- `avatar` - Google picture URL
- `google_id` - Google's sub ID
- `oauth_provider` - "google"
- `created_at` - current timestamp

### After Account Linking:

```sql
SELECT id, name, email, password_hash, google_id, oauth_provider FROM users
WHERE email = 'test@example.com';
```

Should show:

- `password_hash` - has value (from email signup)
- `google_id` - has value (from Google linking)
- `oauth_provider` - "google"

---

## Common Issues & Solutions

### Issue: "Invalid Client ID"

**Solution:**

- Verify `GOOGLE_CLIENT_ID` in `.env`
- Check Google Cloud Console settings
- Ensure credentials are OAuth 2.0 Client ID (not API Key)

### Issue: "Redirect URI mismatch"

**Solution:**

- Check authorized redirect URIs in Google Cloud
- Ensure exact match: `http://localhost:5000/auth/callback/google`
- No trailing slash
- Protocol must match (http vs https)

### Issue: Infinite redirect loop

**Solution:**

- Clear browser cookies
- Check that `google_callback` route is defined
- Verify database connection working

### Issue: User not created

**Solution:**

- Check database migration ran
- Verify `users` table has new columns
- Check Flask logs for errors
- Ensure database write permissions

### Issue: Profile picture not showing

**Solution:**

- Check `avatar` column populated
- Verify image URL is accessible
- Check image display logic in profile template

---

## Success Indicators

✅ Users can sign in with email/password
✅ Users can sign up with email/password
✅ Users can sign in with Google
✅ Users can sign up with Google
✅ Profile picture loaded from Google
✅ Account linking works
✅ Session management correct
✅ Logout works properly
✅ Error messages display
✅ Mobile layout correct
✅ Keyboard navigation works
✅ Database reflects changes

---

## Next: Performance Testing

After functional testing works, consider:

- Load testing (multiple concurrent logins)
- Google API rate limits
- Database query performance
- Session management under load

---

**Ready to Test!** Follow the checklist above and verify all scenarios. 🚀
````
