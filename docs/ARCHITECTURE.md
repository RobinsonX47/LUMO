# LUMO Architecture

## Runtime Overview

LUMO is a Flask monolith organized with blueprints and service modules.

1. app.py initializes configuration, security middleware, database, and blueprints.
2. config.py builds environment-aware settings (SQLite local, PostgreSQL in production).
3. routes_*.py modules expose feature routes by domain.
4. tmdb_service.py encapsulates TMDB API access and caching.
5. models.py defines users, reviews, watchlist, social relations, notifications, and watch progress.

## Blueprint Map

- main (routes_main.py): home, discovery sections, genre browsing
- auth (routes_auth.py): login/register, logout, Google OAuth callbacks
- movies (routes_movies.py): details, reviews, watchlist, player config, recommendations, progress updates
- users (routes_users.py): profile, public profile, edit profile, search, directory, follow graph, notifications, continue watching
- legal (routes_legal.py): privacy, terms, cookies
- admin (routes_admin.py): optional admin pages (registered when available)

## Security and Reliability Layer

- CSRF protection enabled through Flask-WTF
- Rate limiting through Flask-Limiter (Redis in production, memory locally)
- Security headers and CSP through Flask-Talisman
- ProxyFix enabled for reverse-proxy deployments
- Health endpoints:
  - GET /health (database connectivity)
  - GET /ready (readiness signal)

## Data and Storage

- Local development default: SQLite at instance/cine_sphere.db
- Production default: PostgreSQL when DATABASE_URL is present
- DATABASE_URL normalization and hostname recovery are handled in config.py
- Runtime cache files live under instance/cache
- Uploaded avatars are stored in static/uploads/avatars

## Recommendation Pipeline

1. Pull watchlist seed titles/genres for current user.
2. Attempt LLM-assisted recommendation title generation when ANTHROPIC_API_KEY is set.
3. Resolve candidate titles through TMDB.
4. Fall back to genre-driven TMDB recommendations when needed.

## Desktop Mode

- desktop/launcher.py and desktop/launcher_qt.py run the Flask app locally and open a desktop shell.
- Desktop runtime uses LUMO_RUNTIME_ROOT and LUMO_DESKTOP_DATA_DIR to separate packaged data from source tree.
- Desktop mode disables routes/features that depend on external browser behavior where applicable.
