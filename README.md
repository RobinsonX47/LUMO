# 🎬 LUMO

<p align="center">
  <strong>A Flask movie and TV platform with watchlists, reviews, social profiles, recommendations, and desktop support.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Flask-3-black?style=for-the-badge&logo=flask" alt="Flask 3" />
  <img src="https://img.shields.io/badge/SQLAlchemy-ORM-orange?style=for-the-badge" alt="SQLAlchemy" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
</p>

## ✨ What LUMO Does

LUMO is a content discovery and tracking app built around real usage flows, not just a static catalog.

- 🎥 Browse movies, TV series, anime, genres, trending titles, and top-rated picks
- 📝 Read and write reviews on title detail pages
- 📌 Save movies and series to a watchlist with media-type aware handling
- ⏯️ Track continue-watching progress per user
- 👥 Build public profiles, follow other users, and discover people through search and directory pages
- 🤖 Generate recommendations from watchlist seeds with fallback logic
- 🔒 Use CSRF protection, rate limiting, security headers, and production checks
- 🖥️ Run as a local desktop app with Windows packaging support
- ❤️ Expose /health and /ready endpoints for deployment monitoring

## 🔍 Feature Map

| Area | What you get |
| --- | --- |
| 🎞️ Discovery | Home hero carousel, trending movies, top-rated pages, genre browsing, anime, and TV sections |
| 🧾 Title Pages | Movie and TV detail pages, trailers/player integration, reviews, related actions |
| 📚 Library | Watchlist page, continue-watching page, watch progress persistence |
| 👤 Accounts | Email/password auth, Google OAuth, profile editing, avatars |
| 🌐 Social | Public profiles, follow/unfollow, followers/following lists, user search, notifications, directory |
| 🤖 Recommendations | Personalized recommendation pages with fallback to TMDB-derived suggestions |
| 🛡️ Operations | Health checks, readiness checks, logging, rate limits, security headers |
| 🖥️ Desktop | Local launcher, native window support, PyInstaller build scripts, installer scripts |

## 🚀 Quick Start

### 🪟 Windows PowerShell

```powershell
git clone https://github.com/RobinsonX47/LUMO.git
cd LUMO

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# Edit .env and set at least SECRET_KEY and TMDB_API_KEY

python app.py
```

Open http://localhost:5000

### 🐧 macOS / Linux

```bash
git clone https://github.com/RobinsonX47/LUMO.git
cd LUMO

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set at least SECRET_KEY and TMDB_API_KEY

python app.py
```

## ⚙️ Configuration

### Required

- 🔑 `SECRET_KEY`
- 🎬 `TMDB_API_KEY`

### Optional

- 🗃️ `DATABASE_URL` for PostgreSQL in production
- 🧠 `REDIS_URL` for rate-limit storage in production
- 🔐 `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for Google OAuth
- 🤖 `ANTHROPIC_API_KEY` for recommendation ranking support
- 🎛️ `EMBED_PROVIDER_*` for licensed embed provider integration

The app also normalizes some production database URLs automatically, including incomplete Render-style hostnames.

## 🧪 Useful Commands

```bash
# Run the test suite
pytest

# Create an admin user for local content management
python scripts/make_admin.py --create --email admin@example.com --name "Admin" --password "change-me"

# Migrations for older databases
python scripts/migrate_add_oauth.py
python scripts/migrate_add_username.py
python scripts/migrate_add_watch_progress.py
python scripts/migrate_add_media_type.py
python scripts/migrate_add_tmdb_id.py
python scripts/migrate_add_performance_indexes.py
```

## 🖥️ Desktop App

LUMO also ships with a desktop launcher for Windows.

```powershell
pip install -r desktop/requirements.txt
powershell -ExecutionPolicy Bypass -File desktop/build_desktop.ps1
```

- `desktop/launcher.py` runs the local desktop experience
- `desktop/build_desktop.ps1` packages the app with PyInstaller
- `desktop/build_installer.ps1` builds a simple Windows installer wrapper
- Full desktop notes live in [docs/DESKTOP_APP.md](docs/DESKTOP_APP.md)

## 🔐 Production Notes

LUMO includes production-oriented defaults, but you still need to configure your own deployment correctly.

- 🔒 Set a strong `SECRET_KEY`
- 🗃️ Use PostgreSQL in production
- 🧠 Use Redis for rate limiting in production
- 🌍 Put Google OAuth redirect URIs in the Google Cloud console
- 🧰 Keep `FLASK_ENV=production` for production deployments
- ✅ Verify `/health` and `/ready` after deploying

For full deployment steps, see [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md).

## 📚 Documentation

- [docs/START_HERE.md](docs/START_HERE.md) - best entry point for the docs
- [docs/QUICK_SETUP.md](docs/QUICK_SETUP.md) - fast local and Render setup
- [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md) - production checklist and hosting notes
- [docs/GOOGLE_OAUTH_SETUP.md](docs/GOOGLE_OAUTH_SETUP.md) - Google login setup
- [docs/SOCIAL_FEATURES.md](docs/SOCIAL_FEATURES.md) - social features overview
- [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - auth and OAuth validation flows
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - app structure and runtime flow
- [docs/DESKTOP_APP.md](docs/DESKTOP_APP.md) - desktop packaging and launcher details

## 🧱 Project Layout

```text
app.py                # Flask app factory, security setup, health endpoints
config.py             # Environment-aware configuration
models.py             # SQLAlchemy models
routes_*.py           # Blueprints for auth, movies, users, legal, admin
services/             # API integrations and helper services
static/               # CSS, JS, images, uploads
templates/            # Jinja2 templates
scripts/              # Migrations and admin helpers
desktop/              # Desktop launcher and packaging scripts
docs/                # Setup, deployment, testing, and architecture docs
tests/               # Automated tests
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, development setup, and pull request expectations.

## 📄 License

MIT. See [LICENSE](LICENSE).
