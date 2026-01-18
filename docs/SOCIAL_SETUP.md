# LUMO Social Features - Quick Setup Guide

## Installation & Deployment Steps

### Prerequisites

- Existing LUMO installation
- Python 3.8+
- Flask application running

### Step 1: Update Models

The `models.py` file has been updated with:

- New `username` field for User model
- New `user_followers` association table
- New `Notification` model

✅ **Already done** - Models are updated

### Step 2: Update Authentication Routes

`routes_auth.py` now includes:

- Username validation functions
- Username field in registration form
- Auto-generation of usernames for OAuth users

✅ **Already done** - Auth routes are updated

### Step 3: Install New User Routes

`routes_users.py` has been completely replaced with comprehensive social features:

- 16 new routes
- Follow/unfollow functionality
- User search and directory
- Notifications system
- API endpoints

✅ **Already done** - User routes are updated

### Step 4: Update Templates

#### New Templates Created:

- `templates/users/public_profile.html` - View other users' profiles
- `templates/users/search_results.html` - Search results page
- `templates/users/directory.html` - User directory/discovery
- `templates/users/followers_list.html` - Followers list
- `templates/users/following_list.html` - Following list
- `templates/users/notifications.html` - Notifications dashboard

#### Updated Templates:

- `templates/users/profile.html` - Enhanced with social stats
- `templates/users/edit_profile.html` - Added username field
- `templates/auth/register.html` - Added username field
- `templates/base.html` - Added navigation links

✅ **Already done** - All templates are updated

### Step 5: Database Migration

#### For Existing Users:

```bash
cd f:\LUMO
python scripts/migrate_add_username.py
```

**What this does:**

- Generates unique usernames for all users without usernames
- Updates the database
- Maintains data integrity
- Safe to run multiple times

**Output:**

```
============================================================
LUMO - Username Migration Script
============================================================

📝 Found 50 users without usernames
Generating usernames...

  ✓ John Doe (john@example.com) → @johndoe
  ✓ Jane Smith (jane@example.com) → @janesmith
  ... (more users)

✅ Migration complete! 50 users updated.
============================================================
```

#### For New Installation:

The database tables are automatically created on first app request via `db.create_all()`.

### Step 6: Verify Installation

1. **Start the application:**

```bash
python app.py
```

2. **Check new routes:**

- Navigate to `http://localhost:5000/users/directory` - Should see User Directory
- Navigate to `http://localhost:5000/users/search` - Should see search page
- Login and view profile - Should see follower counts

3. **Test features:**

- Search for a user
- Click on a user profile
- Try the follow button
- Check notifications

### Step 7: Deploy to Production

```bash
# 1. Create database backup
cp instance/cine_sphere.db instance/cine_sphere.db.backup

# 2. Run migration
python scripts/migrate_add_username.py

# 3. Commit changes
git add .
git commit -m "feat: add comprehensive social features"

# 4. Deploy
git push origin main
```

On Render/deployment platform:

- The migration script will run automatically if needed
- Database is initialized on first request

## Configuration

### No new environment variables needed!

All features use existing configuration:

- Database URL from `config.py`
- TMDB API already configured
- No additional dependencies

## Performance Tuning

### Database Indexes

Automatically created for:

- `users.username` (UNIQUE)
- `notifications.user_id`
- Foreign keys

### Recommended Settings for Production

In `config.py`, you can add (optional):

```python
# Connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
}

# Query limits
USERS_PER_PAGE = 12  # Already implemented
NOTIFICATIONS_PER_PAGE = 20  # Already implemented
```

## Troubleshooting

### Issue: "username column does not exist"

**Solution:** Run migration script

```bash
python scripts/migrate_add_username.py
```

### Issue: Follow button returns 404

**Solution:** Verify routes_users.py is properly loaded

```python
# Check app.py registration
app.register_blueprint(users_bp, url_prefix="/users")
```

### Issue: Users created before update have no username

**Solution:** Run migration script to auto-generate

### Issue: OAuth users not getting usernames

**Solution:** Update was applied - new OAuth users will get auto-generated usernames

### Issue: Database foreign key errors

**Solution:** Ensure migrations are run before app starts

## API Endpoints Reference

### Follow/Unfollow

```
POST /users/{user_id}/follow
POST /users/{user_id}/unfollow
```

### User Search

```
GET /users/search?q=<query>&page=1
GET /users/api/search-users?q=<query>&limit=5
GET /users/api/check-username?username=<username>
GET /users/api/user/<username>/stats
```

### User Discovery

```
GET /users/directory?sort=followers|newest|alphabetical&page=1
GET /users/<username>/followers?search=<query>&page=1
GET /users/<username>/following?search=<query>&page=1
```

### Notifications

```
GET /users/notifications?filter=all|unread|follows&page=1
POST /users/notifications/mark-as-read
POST /users/notifications/{notification_id}/read
```

### Profiles

```
GET /users/profile - Own profile
GET /users/profile/edit - Edit profile
GET /users/u/<username> - Public profile
```

## Rollback Instructions

If you need to rollback (not recommended):

```bash
# 1. Restore database backup
cp instance/cine_sphere.db.backup instance/cine_sphere.db

# 2. Revert code changes
git revert <commit-hash>

# 3. Restart application
python app.py
```

## Monitoring

### Check User Adoption

```python
from models import User
# Count users with usernames
active_users = User.query.filter(User.username != None).count()
```

### Monitor Follow Activity

```python
from models import Notification
# Count recent follows
from datetime import datetime, timedelta
recent = Notification.query.filter(
    Notification.notification_type == 'follow',
    Notification.created_at >= datetime.utcnow() - timedelta(hours=24)
).count()
```

## Testing Checklist

- [ ] Register a new user - username field present and validated
- [ ] Login with existing user - username auto-generated if needed
- [ ] View own profile - shows username and follower counts
- [ ] Edit profile - can change username
- [ ] Search for users - results display correctly
- [ ] Browse directory - shows all users
- [ ] View public profile - shows other user's info
- [ ] Follow user - button works and shows notification
- [ ] Check followers/following - lists display correctly
- [ ] View notifications - shows follow notifications
- [ ] Test on mobile - all features responsive

## Next Steps

1. ✅ **Deploy social features**
2. **Monitor usage metrics**
3. **Gather user feedback**
4. **Plan future enhancements:**
   - Activity feed from follows
   - Advanced notifications
   - User messages/chat
   - Trending users
   - User recommendations

## Support

For issues or questions:

1. Check SOCIAL_FEATURES.md documentation
2. Review error logs in console
3. Check browser developer console for frontend errors

## Version Info

- **Social Features Version:** 2.0.0
- **Release Date:** January 2026
- **Status:** Production Ready
- **Backwards Compatible:** Yes (graceful degradation for non-social features)

---

Happy deploying! 🚀
