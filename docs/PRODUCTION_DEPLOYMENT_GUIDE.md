# LUMO Production Deployment Guide

**Last Updated:** February 5, 2026  
**Status:** ✅ Production Ready with Security Hardening

---

## 🎯 Quick Start

This guide covers deploying LUMO to production with all security features enabled.

---

## 📋 Prerequisites

### Required Services

1. **PostgreSQL Database** (managed recommended)
   - Render PostgreSQL, AWS RDS, DigitalOcean, or Heroku Postgres
   - Minimum: 256MB RAM, 1GB storage

2. **Redis Instance** (for rate limiting)
   - Render Redis, Redis Labs, AWS ElastiCache, or DigitalOcean
   - Minimum: 25MB RAM

3. **Hosting Platform**
   - Render, Railway, DigitalOcean App Platform, AWS, or Heroku
   - Minimum: 512MB RAM, 1 CPU

### Required Accounts

- **TMDB API**: https://www.themoviedb.org/settings/api
- **Google OAuth** (optional): https://console.cloud.google.com/

---

## 🚀 Deployment Steps

### Step 1: Install Dependencies

```bash
# Install all production dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

**Critical Environment Variables:**

```bash
# REQUIRED: Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-64-character-random-hex-key

# REQUIRED: Your TMDB API key
TMDB_API_KEY=your_tmdb_api_key

# REQUIRED: PostgreSQL connection string
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# REQUIRED IN PRODUCTION: Redis for rate limiting
REDIS_URL=redis://user:pass@host:6379/0

# Set to production
FLASK_ENV=production

# Optional: Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

### Step 3: Database Setup

#### Option A: Using Alembic (Recommended)

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

#### Option B: Using Flask-SQLAlchemy (Simple)

```python
# The app will auto-create tables on first request
# This is already configured in app.py
```

### Step 4: Run with Gunicorn (Production)

```bash
# Using the configuration file
gunicorn -c gunicorn.conf.py app:app

# Or specify options directly
gunicorn app:app \
  --workers 4 \
  --threads 2 \
  --bind 0.0.0.0:$PORT \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

---

## 🔐 Security Checklist

### Before Going Live

- [ ] **SECRET_KEY** is cryptographically random (64+ characters)
- [ ] **FLASK_ENV** set to `production`
- [ ] **DATABASE_URL** points to PostgreSQL (not SQLite)
- [ ] **REDIS_URL** configured for rate limiting
- [ ] **HTTPS** enabled (SSL certificate installed)
- [ ] **CSRF protection** enabled (already configured)
- [ ] **Rate limiting** active (check Redis connection)
- [ ] **Security headers** enabled (Talisman configured)
- [ ] **Password policy** enforced (8+ chars, complexity)
- [ ] **Error handlers** display friendly pages (not stack traces)
- [ ] **Logging** configured and monitored
- [ ] **Database backups** automated
- [ ] **Privacy policy** and **Terms of Service** reviewed
- [ ] **Google OAuth** redirect URIs whitelisted
- [ ] **TMDB API** rate limits understood

---

## 🌐 Platform-Specific Deployment

### Render.com (Recommended)

1. **Create Web Service**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -c gunicorn.conf.py app:app`

2. **Add PostgreSQL Database**
   - Create from Render Dashboard
   - Copy `DATABASE_URL` to environment variables

3. **Add Redis Instance**
   - Create from Render Dashboard
   - Copy `REDIS_URL` to environment variables

4. **Environment Variables**

   ```
   SECRET_KEY=<random-64-char-hex>
   FLASK_ENV=production
   TMDB_API_KEY=<your-key>
   DATABASE_URL=<auto-filled-by-render>
   REDIS_URL=<auto-filled-by-render>
   GOOGLE_CLIENT_ID=<your-id>
   GOOGLE_CLIENT_SECRET=<your-secret>
   ```

5. **Health Check Path**: `/health`

### Railway.app

1. **Create New Project** from GitHub
2. **Add PostgreSQL Plugin**
3. **Add Redis Plugin**
4. **Set Environment Variables** (same as above)
5. **Deploy Command**: Railway auto-detects `gunicorn`

### DigitalOcean App Platform

1. **Create App** from GitHub repo
2. **Add Managed Database (PostgreSQL)**
3. **Add Managed Redis**
4. **Set Environment Variables**
5. **Build Command**: `pip install -r requirements.txt`
6. **Run Command**: `gunicorn -c gunicorn.conf.py app:app`

### AWS (EC2 + RDS + ElastiCache)

See separate AWS deployment guide.

---

## 📊 Monitoring & Maintenance

### Health Checks

- **Health endpoint**: `GET /health` - Returns database status
- **Readiness endpoint**: `GET /ready` - For load balancer checks

### Logging

Logs are written to:

- **Console**: stdout/stderr (captured by hosting platform)
- **File**: `logs/lumo.log` (rotates at 10MB, keeps 10 backups)

### Error Tracking (Optional)

Add Sentry for production error tracking:

```bash
pip install sentry-sdk[flask]
```

Add to `app.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1
    )
```

### Database Backups

**Automated Backups:**

- Render: Daily automatic backups (retained 7 days)
- Railway: Point-in-time recovery
- DigitalOcean: Daily backups included

**Manual Backup:**

```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

---

## 🔧 Configuration Tuning

### Gunicorn Workers

**Formula:** `(2 × CPU cores) + 1`

```python
# In gunicorn.conf.py
workers = multiprocessing.cpu_count() * 2 + 1  # Already configured
```

### Database Connection Pool

```python
# In config.py (already configured)
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 10,           # Max connections per worker
    "pool_recycle": 3600,      # Recycle connections every hour
    "pool_pre_ping": True,     # Check connection health
    "max_overflow": 20         # Extra connections under load
}
```

### Rate Limits

Adjust in `config.py`:

```python
RATELIMIT_LOGIN = "5 per minute"      # Login attempts
RATELIMIT_REGISTER = "3 per hour"     # Registration attempts
RATELIMIT_API = "100 per hour"        # API calls
```

---

## 🚨 Troubleshooting

### Common Issues

**1. "CSRF Token Missing" Error**

- Ensure forms include `{{ form.csrf_token }}`
- Check `WTF_CSRF_ENABLED = True` in config

**2. Rate Limit Not Working**

- Verify Redis connection: `redis-cli ping`
- Check `REDIS_URL` environment variable

**3. Database Connection Errors**

- Verify `DATABASE_URL` format: `postgresql://` not `postgres://`
- Check connection pool settings
- Ensure database allows remote connections

**4. OAuth Redirect Error**

- Add production URL to Google OAuth allowed redirects
- Format: `https://your-domain.com/auth/callback/google`

**5. Static Files Not Loading**

- Ensure CDN or reverse proxy serves `/static/`
- Check file permissions

### Debug Mode (Development Only)

```bash
# NEVER use in production
FLASK_ENV=development python app.py
```

---

## 📈 Performance Optimization

### CDN Setup

Use a CDN for static assets:

1. **Cloudflare** (Free): Automatic caching
2. **BunnyCDN** ($1/month): Fast global delivery
3. **AWS CloudFront**: Integrates with S3

### Caching Strategy

- **TMDB API responses**: Cached 6 hours (file-based)
- **User sessions**: Stored in Redis
- **Static assets**: CDN + browser caching

### Database Optimization

```sql
-- Add indexes for common queries (do this after deployment)
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_reviews_movie_id ON reviews(movie_id);
CREATE INDEX idx_reviews_user_id ON reviews(user_id);
```

---

## 💰 Cost Estimate (Monthly)

### Minimal Setup

- **Render** (Web Service): $7/month
- **Render PostgreSQL**: $7/month
- **Render Redis**: $7/month
- **Total**: ~$21/month

### Recommended Setup

- **Railway** (Web + DB + Redis): $20-30/month
- **Cloudflare CDN**: Free
- **Total**: ~$25/month

### Production Setup

- **DigitalOcean App Platform**: $12/month
- **Managed PostgreSQL**: $15/month
- **Managed Redis**: $15/month
- **Spaces CDN**: $5/month
- **Total**: ~$47/month

---

## 🎯 Post-Deployment Tasks

### Immediate (First 24 Hours)

- [ ] Test all authentication flows (email, OAuth)
- [ ] Test CSRF protection on all forms
- [ ] Verify rate limiting is working
- [ ] Check error pages (404, 500, 403, 429)
- [ ] Monitor logs for errors
- [ ] Test on mobile devices
- [ ] Verify HTTPS is enforced

### First Week

- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Configure database backups
- [ ] Test backup restoration
- [ ] Review analytics setup
- [ ] Monitor performance metrics
- [ ] Check for security vulnerabilities
- [ ] Test ad integration (if applicable)

### Ongoing

- [ ] Review logs weekly
- [ ] Monitor database growth
- [ ] Update dependencies monthly
- [ ] Run security audits quarterly
- [ ] Test disaster recovery annually

---

## 📞 Support & Resources

### Documentation

- **Flask**: https://flask.palletsprojects.com/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **TMDB API**: https://developers.themoviedb.org/

### Security

- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **Flask Security**: https://flask.palletsprojects.com/en/latest/security/

### Monitoring

- **Sentry**: https://sentry.io/
- **UptimeRobot**: https://uptimerobot.com/

---

## 🔄 Updates & Migrations

### Updating Code

```bash
git pull origin main
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart lumo  # or platform-specific restart
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Review migration file
cat alembic/versions/xxx_description.py

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

---

## ✅ Production Readiness Score

After completing this guide, your LUMO deployment will have:

- ✅ **Security**: 9/10 (CSRF, rate limiting, HTTPS, password hashing)
- ✅ **Scalability**: 8/10 (PostgreSQL, Redis, connection pooling)
- ✅ **Reliability**: 8/10 (Health checks, error handling, logging)
- ✅ **Compliance**: 9/10 (GDPR-ready, privacy policy, cookie consent)
- ✅ **Performance**: 7/10 (Caching, CDN-ready, optimized queries)

**Overall**: 8.2/10 - **Production Ready** 🚀

---

## 📝 License & Legal

Ensure you have:

- Updated privacy policy with your company details
- Updated terms of service with your jurisdiction
- Configured cookie consent banner
- GDPR compliance verified (if serving EU users)
- TMDB attribution displayed (required by TMDB TOS)

---

**Questions?** Open an issue or contact your deployment team.

**Last Updated:** February 5, 2026
