# LUMO

A Flask-based movie and TV tracking platform with social features, watch progress, and desktop packaging support.

## Highlights

- Content discovery: trending, top-rated, genres, anime, and TV sections
- Detailed title pages with reviews, watchlist actions, and trailer/player support
- Personalized recommendations from watchlist seeds with fallback logic
- User social layer: public profiles, follow/unfollow, search, directory, and notifications
- Continue watching with per-user progress tracking
- Security defaults: CSRF, rate limiting, security headers, and production checks
- Health endpoints for deployment: /health and /ready
- Optional Windows desktop launcher and installer scripts

## Tech Stack

- Python 3.10+
- Flask 3, SQLAlchemy, Flask-Login, Flask-WTF
- SQLite (default) or PostgreSQL via DATABASE_URL
- Redis-backed rate limiting in production (memory fallback in local dev)

## Quick Start (Windows PowerShell)

```powershell
git clone https://github.com/RobinsonX47/lumo.git
cd lumo

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# Edit .env and set at least TMDB_API_KEY and SECRET_KEY

python app.py
```

Open http://localhost:5000

## Quick Start (macOS/Linux)

```bash
git clone https://github.com/RobinsonX47/lumo.git
cd lumo

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set at least TMDB_API_KEY and SECRET_KEY

python app.py
```

## Configuration

Required:

- SECRET_KEY
- TMDB_API_KEY

Optional:

- DATABASE_URL (PostgreSQL in production)
- REDIS_URL (recommended in production for rate-limit storage)
- GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (Google OAuth)
- ANTHROPIC_API_KEY (LLM-assisted recommendation ranking)
- EMBED_PROVIDER_* (licensed embed provider integration)

The app automatically normalizes DATABASE_URL values and has recovery logic for incomplete Render-style hostnames.

## Common Commands

```bash
# Run tests
pytest

# Create admin user
python scripts/make_admin.py --create --email admin@example.com --name "Admin" --password "change-me"

# Optional migrations for older databases
python scripts/migrate_add_oauth.py
python scripts/migrate_add_username.py
python scripts/migrate_add_watch_progress.py
python scripts/migrate_add_media_type.py
python scripts/migrate_add_tmdb_id.py
python scripts/migrate_add_performance_indexes.py
```

## Desktop Build (Optional)

```powershell
pip install -r desktop/requirements.txt
powershell -ExecutionPolicy Bypass -File desktop/build_desktop.ps1
```

Full details: docs/DESKTOP_APP.md

## Documentation

- docs/START_HERE.md
- docs/QUICK_SETUP.md
- docs/PRODUCTION_DEPLOYMENT_GUIDE.md
- docs/GOOGLE_OAUTH_SETUP.md
- docs/SOCIAL_FEATURES.md
- docs/TESTING_GUIDE.md
- docs/ARCHITECTURE.md

## Project Layout

```text
app.py                # App factory, security setup, blueprint registration
config.py             # Environment-driven configuration
models.py             # SQLAlchemy models
routes_*.py           # Feature blueprints
tmdb_service.py       # TMDB API and caching helpers
desktop/              # Desktop launcher and installer scripts
docs/                 # Deployment and architecture documentation
tests/                # Test suite
```

## Contributing

See CONTRIBUTING.md for development workflow and PR guidance.

## License

MIT. See LICENSE.
