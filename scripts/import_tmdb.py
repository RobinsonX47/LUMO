"""
Import movies from TheMovieDB (TMDb) into the LUMO app database.

Usage:
  - Set environment variable `TMDB_API_KEY` to your TMDb API key.
  - Run script to import popular movies or search titles:

Examples:
  # import popular movies
  TMDB_API_KEY=xxx python scripts\import_tmdb.py --mode popular --count 20

  # search and import a specific title
  TMDB_API_KEY=xxx python scripts\import_tmdb.py --mode search --query "Inception"

Notes:
  - Requires `requests`. Optional: `Pillow` to resize posters.
  - Downloads posters to `static/uploads/` and stores public path in Movie.poster_path
  - Uses `backdrop_path` from TMDb as `horizontal_poster_path` (hero/backdrop)
"""
import os
import sys
import argparse
import uuid
import requests
from pathlib import Path

# load .env automatically if present
try:
    from dotenv import load_dotenv
    # load .env from project root
    load_dotenv()
except Exception:
    # python-dotenv not installed; continue (user may set env vars manually)
    pass

# ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from models import Movie

TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"

API_KEY = os.environ.get('TMDB_API_KEY')
if not API_KEY:
    print("ERROR: set TMDB_API_KEY environment variable (or add it to .env)")
    sys.exit(1)

UPLOAD_DIR = ROOT / 'static' / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# optional Pillow
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def tmdb_get(path, params=None):
    params = params or {}
    params['api_key'] = API_KEY
    r = requests.get(TMDB_API + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def download_image(tmdb_path):
    if not tmdb_path:
        return None
    url = TMDB_IMAGE_BASE + tmdb_path
    ext = os.path.splitext(tmdb_path)[1] or '.jpg'
    fname = f"img_{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / fname
    try:
        r = requests.get(url, stream=True, timeout=20)
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(1024 * 8):
                f.write(chunk)
        return f"/static/uploads/{fname}"
    except Exception as e:
        print('Failed to download', url, e)
        return None


def import_movie_from_tmdb_item(item, app):
    # item is a TMDb movie object from /movie/popular or search results
    title = item.get('title') or item.get('name')
    release_date = item.get('release_date') or item.get('first_air_date')
    release_year = None
    if release_date:
        release_year = int(release_date.split('-')[0]) if release_date else None

    # Prefer dedupe by tmdb_id if available, fallback to title+year
    tmdb_id = item.get('id')
    with app.app_context():
        existing = None
        if tmdb_id:
            existing = Movie.query.filter_by(tmdb_id=tmdb_id).first()
        if not existing:
            existing = Movie.query.filter_by(title=title, release_year=release_year).first()
        if existing:
            print('Already exists:', title, release_year)
            return existing

    # Fetch full details to get runtime and overview
    details = tmdb_get(f"/movie/{item['id']}")
    description = details.get('overview')
    runtime = details.get('runtime') or None

    poster_path = item.get('poster_path')
    backdrop_path = item.get('backdrop_path')

    poster_local = download_image(poster_path) if poster_path else None
    horizontal_local = download_image(backdrop_path) if backdrop_path else None

    with app.app_context():
        movie = Movie(
            title=title,
            description=description,
            release_year=release_year,
            duration_minutes=runtime,
            trailer_url=None,
            poster_path=poster_local,
            horizontal_poster_path=horizontal_local,
            tmdb_id=tmdb_id,
        )
        db.session.add(movie)
        db.session.commit()
        print('Imported:', title)
        return movie


def import_popular(count, app):
    per_page = 20
    imported = 0
    page = 1
    while imported < count:
        data = tmdb_get('/movie/popular', {'page': page})
        results = data.get('results', [])
        for item in results:
            import_movie_from_tmdb_item(item, app)
            imported += 1
            if imported >= count:
                break
        if page >= data.get('total_pages', 1):
            break
        page += 1
    print('Done importing popular movies')


def import_trending(count, app, media_type='movie', time_window='week'):
    # media_type: movie / all / tv / person, time_window: day / week
    imported = 0
    page = 1
    while imported < count:
        path = f'/trending/{media_type}/{time_window}'
        data = tmdb_get(path)
        results = data.get('results', [])
        for item in results:
            # trending includes mixed types; skip non-movie if media_type is 'all'
            if media_type == 'movie' or item.get('media_type', 'movie') == 'movie':
                import_movie_from_tmdb_item(item, app)
                imported += 1
            if imported >= count:
                break
        # trending endpoint is not paginated in the same way; break after single fetch
        break
    print('Done importing trending movies')


def search_and_import(query, max_results, app):
    data = tmdb_get('/search/movie', {'query': query, 'page': 1})
    results = data.get('results', [])[:max_results]
    for item in results:
        import_movie_from_tmdb_item(item, app)
    print('Done importing search results')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import movies from TMDb')
    parser.add_argument('--mode', choices=['popular', 'trending', 'search'], default='popular')
    parser.add_argument('--count', type=int, default=10, help='number of movies to import (popular/trending)')
    parser.add_argument('--query', type=str, help='search query for mode=search')
    parser.add_argument('--max-results', type=int, default=5, help='max search results to import')
    parser.add_argument('--time-window', choices=['day', 'week'], default='week', help='time window for trending (day|week)')
    parser.add_argument('--media-type', choices=['movie', 'all', 'tv', 'person'], default='movie', help='media type for trending')
    args = parser.parse_args()

    app = create_app()

    if args.mode == 'popular':
        import_popular(args.count, app)
    elif args.mode == 'trending':
        import_trending(args.count, app, media_type=args.media_type, time_window=args.time_window)
    else:
        if not args.query:
            print('Provide --query for search mode')
            sys.exit(1)
        search_and_import(args.query, args.max_results, app)
