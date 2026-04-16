# LUMO Quick Reference

## Local Setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # Windows: Copy-Item .env.example .env
python app.py
```

Open: http://localhost:5000

## Required Environment Variables

```bash
SECRET_KEY=your-random-secret
TMDB_API_KEY=your-tmdb-key
```

Optional:

```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
ANTHROPIC_API_KEY=...
EMBED_PROVIDER_BASE_URL=https://...
```

## Core Routes

Main:

- GET /
- GET /movies
- GET /movies/trending
- GET /movies/top-rated
- GET /anime
- GET /series
- GET /genres

Auth:

- GET,POST /auth/login
- GET,POST /auth/register
- GET /auth/logout
- GET /auth/login/google
- GET /auth/callback/google

Movies:

- GET /movies/
- GET /movies/<id>
- GET /movies/tv/<id>
- POST /movies/<id>/review
- POST /movies/<id>/watchlist
- GET /movies/watchlist
- GET /movies/recommendations

Users/Social:

- GET /users/profile
- GET /users/profile/edit
- GET /users/u/<username>
- GET /users/directory
- GET /users/search
- POST /users/<user_id>/follow
- GET /users/notifications

Operations:

- GET /health
- GET /ready

## Useful Commands

```bash
# Test suite
pytest

# Create admin account
python scripts/make_admin.py --create --email admin@example.com --name "Admin" --password "change-me"

# Optional migration scripts for older databases
python scripts/migrate_add_oauth.py
python scripts/migrate_add_username.py
python scripts/migrate_add_watch_progress.py
python scripts/migrate_add_media_type.py
python scripts/migrate_add_tmdb_id.py
python scripts/migrate_add_performance_indexes.py
```

## Troubleshooting

- OAuth redirect mismatch: verify Google callback URL exactly matches /auth/callback/google
- DB connection issues: check DATABASE_URL and app logs
- Rate-limit persistence in production: set REDIS_URL
- Missing posters/details: verify TMDB_API_KEY and outbound network access
