# LUMO - Social Features Documentation

## New Social Features Overview

This update introduces a comprehensive social network for LUMO, allowing users to connect, follow each other, discover profiles, and receive notifications.

### Features Added

#### 1. **Unique Usernames**

- Each user now has a unique, unchangeable username (3-30 characters)
- Usernames are alphanumeric with hyphens and underscores allowed
- Real-time availability checking during registration and profile editing
- Auto-generated usernames for OAuth users

**Setup:**

- Added `username` field to User model
- Username validation with pattern matching
- Uniqueness constraint at database level

#### 2. **User Follow System**

- Follow and unfollow other users
- View follower/following counts
- Follow relationship tracking with timestamps
- Cannot follow yourself

**Database:**

- `user_followers` association table for many-to-many relationships
- Tracks follow timestamps for future analytics

#### 3. **Public User Profiles**

- Browse other users' profiles at `/users/u/<username>`
- View public reviews, watchlist, and stats
- One-click follow/unfollow from profile
- Professional card-based layout

**Routes:**

- `GET /users/u/<username>` - View public profile
- Shows limited watchlist and reviews
- Respects privacy settings

#### 4. **User Search & Discovery**

- Global user search functionality at `/users/search`
- Search by name or username
- Real-time search with pagination
- Autocomplete API for fast lookups

**Routes:**

- `GET /users/search?q=<query>` - Search results
- `GET /users/api/search-users?q=<query>&limit=5` - Autocomplete API
- Fuzzy search with ILIKE for flexibility

#### 5. **User Directory**

- Browse all users at `/users/directory`
- Sort by: Most Popular (followers), Newest, Alphabetical
- Profile cards with stats
- Pagination support

**Routes:**

- `GET /users/directory?sort=<followers|newest|alphabetical>`
- Shows follower count and review count for each user

#### 6. **Followers & Following Lists**

- Dedicated pages to view followers and following
- Search within followers/following
- Pagination with 12 users per page
- Quick follow/unfollow buttons

**Routes:**

- `GET /users/<username>/followers` - View followers
- `GET /users/<username>/following` - View following
- Support for search parameter

#### 7. **Notifications System**

- Real-time notifications for new followers
- Notifications dashboard at `/users/notifications`
- Filter by: All, Unread, Follows
- Mark as read functionality
- Unread badge in navigation

**Database:**

- `Notification` model for tracking activities
- Types: 'follow' (easily extensible for reviews, etc.)
- Read/unread status tracking

#### 8. **Enhanced User Profiles**

- Updated own profile at `/users/profile/edit`
- Edit username with real-time validation
- View follower/following counts
- Improved profile visualization
- Professional UI with stats cards

#### 9. **API Endpoints**

- `/users/api/check-username` - Check username availability
- `/users/api/search-users` - Autocomplete search
- `/users/api/user/<username>/stats` - Get user stats
- `/users/<user_id>/follow` - Follow user (POST)
- `/users/<user_id>/unfollow` - Unfollow user (POST)
- `/users/notifications/mark-as-read` - Mark all as read (POST)

### File Changes

#### Models (`models.py`)

```python
# Added fields to User model
username = db.Column(db.String(50), unique=True, nullable=True, index=True)
updated_at = db.Column(db.DateTime, ...)

# New association table
user_followers = db.Table('user_followers', ...)

# New Notification model
class Notification(db.Model):
    user_id, actor_id, notification_type, is_read, created_at
```

#### Routes (`routes_auth.py`)

- Added username validation functions
- Updated registration to include username
- Auto-generate usernames for OAuth users

#### Routes (`routes_users.py`)

- Complete rewrite with 400+ lines of new code
- 16 new routes for social features
- API endpoints for autocomplete and validation

#### Templates

- `users/profile.html` - Enhanced with social stats
- `users/public_profile.html` - New public profile view
- `users/edit_profile.html` - Username editing
- `users/search_results.html` - Search results grid
- `users/directory.html` - User directory
- `users/followers_list.html` - Followers list
- `users/following_list.html` - Following list
- `users/notifications.html` - Notifications dashboard
- `auth/register.html` - Updated with username field
- `base.html` - Navigation updates

#### Scripts

- `scripts/migrate_add_username.py` - Migration script for existing users

### Database Migration

**Step 1: Run migration script**

```bash
python scripts/migrate_add_username.py
```

This script will:

- Find all users without usernames
- Generate unique usernames from their names
- Update database

**Step 2: Apply database changes**
The app will automatically create new tables on first request via `db.create_all()`.

### Security Features

1. **Username Validation**
   - Pattern matching: `^[a-zA-Z0-9_-]{3,30}$`
   - Client-side and server-side validation
   - Uniqueness constraints

2. **Follow Rate Limiting**
   - Backend validation prevents duplicate follows
   - User cannot follow themselves
   - Error handling for edge cases

3. **XSS Protection**
   - All user data properly escaped in templates
   - HTML encoding for dynamic content
   - Safe profile rendering

4. **Privacy Controls**
   - Only public data shown on user profiles
   - Reviews and watchlist are public by default
   - Future: Add private profile option

### Performance Optimizations

1. **Database Indexing**
   - `username` has UNIQUE index
   - `user_id` has index in Notification
   - Foreign key indexes automatically created

2. **Query Optimization**
   - Lazy loading for relationships
   - Pagination to limit result sets
   - Efficient count queries

3. **Caching Considerations**
   - Notifications could be cached
   - User stats could be cached with TTL
   - Search results benefit from pagination

4. **API Response Compression**
   - JSON responses for autocomplete are minimal
   - Paginated views reduce payload size

### UI/UX Improvements

1. **Navigation Updates**
   - New "Community" link to user directory
   - New "Find Users" search link
   - Notifications bell icon in header
   - Unread notification badge

2. **Profile Cards**
   - Avatar with proper aspect ratio
   - User info with username display
   - Follow/Following buttons
   - Responsive grid layout

3. **Consistent Styling**
   - Uses existing LUMO CSS variables
   - Card-glass components for consistency
   - Smooth transitions and hover effects
   - Mobile-responsive design

### Testing Checklist

- [ ] Register new user with username
- [ ] Check username validation works
- [ ] Visit public profile of another user
- [ ] Test follow/unfollow functionality
- [ ] Search for users
- [ ] Browse user directory with sorting
- [ ] View followers and following lists
- [ ] Check notification system
- [ ] Edit profile and change username
- [ ] Verify OAuth users get auto-generated usernames
- [ ] Run migration script on existing database
- [ ] Check mobile responsiveness

### Future Enhancements

1. **Activity Feed**
   - Show reviews from followed users
   - Show watchlist updates from follows
   - Timeline-style activity view

2. **Advanced Notifications**
   - Friend request system
   - Message/chat system
   - Email notifications

3. **Social Features**
   - User recommendations
   - Trending users
   - User badges/achievements
   - Followers-only content

4. **Analytics**
   - Track follower growth
   - Engagement metrics
   - Popular reviewers

5. **Moderation**
   - Block/report users
   - Spam prevention
   - Community guidelines

### Deployment Notes

1. **Database Migration**
   - Run migration script before deploying
   - Creates migration logs for audit trail
   - Safe to run multiple times

2. **Environment Variables**
   - No new environment variables needed
   - Uses existing database setup

3. **Backup**
   - Backup database before migration
   - Test on staging first

4. **Performance Monitoring**
   - Monitor notification queries
   - Watch for N+1 query problems
   - Profile search query performance

### API Documentation

#### Search Users (Autocomplete)

```
GET /users/api/search-users?q=john&limit=5

Response:
[
  {
    "id": 1,
    "name": "John Doe",
    "username": "johndoe",
    "avatar": "/static/uploads/avatars/..."
  }
]
```

#### Check Username Availability

```
GET /users/api/check-username?username=johndoe

Response:
{
  "available": true,
  "message": "Username available"
}
```

#### Get User Stats

```
GET /users/api/user/johndoe/stats

Response:
{
  "followers": 42,
  "following": 15,
  "reviews": 28,
  "watchlist": 156
}
```

#### Follow User

```
POST /users/1/follow

Response:
{
  "success": true,
  "message": "Now following John Doe"
}
```

#### Unfollow User

```
POST /users/1/unfollow

Response:
{
  "success": true,
  "message": "Unfollowed John Doe"
}
```

### Troubleshooting

**Problem: Username field is NULL for existing users**

- Solution: Run migration script

```bash
python scripts/migrate_add_username.py
```

**Problem: Follow button not working**

- Check browser console for errors
- Verify user is logged in
- Check CORS if API called from different domain

**Problem: Notifications not showing**

- Clear browser cache
- Check if notification was created in database
- Verify current_user is authenticated

**Problem: Search not finding users**

- Check username spelling
- Search is case-insensitive but accent-sensitive
- Try searching by first name instead

---

**Version:** 2.0.0  
**Last Updated:** January 2026  
**Status:** Production Ready
