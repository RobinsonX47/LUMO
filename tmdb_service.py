"""
TMDB API Service - Enhanced with Working Caching and Rate Limiting
Handles all interactions with The Movie Database API with intelligent caching
"""

import requests
from flask import current_app, has_request_context, has_app_context, g
import random
import json
import os
import time
import math
import logging
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

try:
    import redis
except Exception:  # pragma: no cover - graceful fallback when redis client unavailable
    redis = None


logger = logging.getLogger(__name__)

class TMDBCache:
    """Handles caching of TMDB API responses"""
    
    def __init__(self, cache_dir='instance/cache'):
        self.redis_client = None
        self.redis_prefix = 'tmdb:cache:'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = timedelta(hours=6)  # Cache for 6 hours
        self.cache_duration_seconds = int(self.cache_duration.total_seconds())

        redis_url = current_app.config.get('REDIS_URL') if has_app_context() else None
        if redis_url and redis is not None:
            try:
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("TMDB cache backend: redis")
            except Exception as exc:
                logger.warning("Redis cache unavailable, falling back to filesystem: %s", exc)
                self.redis_client = None

        logger.info("TMDB cache directory: %s", self.cache_dir.absolute())
    
    def get_cache_path(self, key):
        """Get the file path for a cache key using hash for safe filenames"""
        # Use hash to create safe, consistent filenames
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get_redis_key(self, key):
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return f"{self.redis_prefix}{key_hash}"
    
    def get(self, key):
        """Get cached data if it exists and is not expired"""
        if self.redis_client:
            redis_key = self.get_redis_key(key)
            try:
                raw = self.redis_client.get(redis_key)
                if not raw:
                    return None
                cache_data = json.loads(raw)
                logger.debug("TMDB redis cache hit: %s", key[:50])
                return cache_data.get('data')
            except Exception as exc:
                logger.warning("TMDB redis cache read error: %s", exc)
                return None

        cache_path = self.get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > self.cache_duration:
                # Cache expired, delete it
                try:
                    cache_path.unlink()
                except:
                    pass
                return None
            
            logger.debug("TMDB cache hit: %s", key[:50])
            return cache_data['data']
        except Exception as e:
            logger.warning("TMDB cache read error: %s", e)
            # Delete corrupted cache file
            try:
                cache_path.unlink()
            except:
                pass
            return None
    
    def set(self, key, data):
        """Cache data with timestamp"""
        if self.redis_client:
            redis_key = self.get_redis_key(key)
            try:
                cache_data = {
                    'timestamp': datetime.now().isoformat(),
                    'key': key,
                    'data': data,
                }
                self.redis_client.setex(redis_key, self.cache_duration_seconds, json.dumps(cache_data, ensure_ascii=False))
                logger.debug("TMDB redis cache set: %s", key[:50])
                return
            except Exception as exc:
                logger.warning("TMDB redis cache write error: %s", exc)

        cache_path = self.get_cache_path(key)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'key': key,  # Store original key for debugging
                'data': data
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug("TMDB cache set: %s", key[:50])
        except Exception as e:
            logger.warning("TMDB cache write error: %s", e)
    
    def clear(self):
        """Clear all cache files"""
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter(f"{self.redis_prefix}*"):
                    self.redis_client.delete(key)
                logger.info("TMDB redis cache cleared")
            except Exception as exc:
                logger.warning("TMDB redis cache clear error: %s", exc)

        try:
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            logger.info("TMDB cache cleared")
        except Exception as e:
            logger.warning("TMDB cache clear error: %s", e)

class TMDBService:
    cache = None
    last_request_time = 0
    min_request_interval = 0.25  # 4 requests per second (well under 40/10s limit)

    @staticmethod
    def _select_best_trailer(videos):
        """Pick the most appropriate official trailer from TMDB videos."""
        if not videos:
            return None

        def is_bad_variant(name):
            bad_terms = [
                'audio description',
                'audio-described',
                'described',
                'deaf',
                'hard of hearing',
                'closed captions',
                'cc',
                'captioned',
                'subtitled',
                'subtitle',
            ]
            return any(term in name for term in bad_terms)

        def score(video):
            name = (video.get('name') or '').lower()
            score = 0

            if video.get('official'):
                score += 50

            if 'official trailer 2' in name or 'official trailer ii' in name:
                score += 95
            elif 'official trailer' in name:
                score += 100
            elif 'main trailer' in name:
                score += 70
            elif 'trailer 2' in name:
                score += 40

            if 'final trailer' in name:
                score += 20

            if 'teaser' in name:
                score -= 30
            if 'clip' in name or 'featurette' in name or 'tv spot' in name or 'promo' in name:
                score -= 40

            return score

        candidates = [
            v for v in videos
            if v.get('type') == 'Trailer' and v.get('site') == 'YouTube'
        ]

        if not candidates:
            return None

        filtered = [v for v in candidates if not is_bad_variant((v.get('name') or '').lower())]
        if filtered:
            candidates = filtered

        candidates.sort(key=lambda v: (score(v), v.get('published_at') or ''), reverse=True)
        return candidates[0]

    @staticmethod
    def _select_logo(images):
        """Pick the best title logo from TMDB images."""
        if not images or not images.get('logos'):
            return None

        logos = images.get('logos', [])
        if not logos:
            return None

        def lang_rank(logo):
            lang = logo.get('iso_639_1')
            if lang == 'en':
                return 2
            if lang in (None, ''):
                return 1
            return 0

        logos.sort(
            key=lambda l: (
                lang_rank(l),
                l.get('vote_count') or 0,
                l.get('width') or 0,
                l.get('height') or 0,
            ),
            reverse=True,
        )
        return logos[0]
    
    @staticmethod
    def init_cache():
        """Initialize cache (called from app startup)"""
        if TMDBService.cache is None:
            TMDBService.cache = TMDBCache()
    
    @staticmethod
    def _rate_limit():
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - TMDBService.last_request_time
        
        if time_since_last < TMDBService.min_request_interval:
            time.sleep(TMDBService.min_request_interval - time_since_last)
        
        TMDBService.last_request_time = time.time()
    
    @staticmethod
    def _make_request(endpoint, params=None, use_cache=True, retries=3):
        """Make a request to TMDB API with caching and retry logic"""
        # Initialize cache if not done yet
        if TMDBService.cache is None:
            TMDBService.init_cache()
        
        base_url = current_app.config['TMDB_BASE_URL']
        api_key = current_app.config['TMDB_API_KEY']
        
        if not params:
            params = {}
        params['api_key'] = api_key
        
        # Create cache key from endpoint and params (excluding api_key)
        cache_params = {k: v for k, v in params.items() if k != 'api_key'}
        cache_key = f"{endpoint}_{json.dumps(cache_params, sort_keys=True)}"
        
        # Check cache first
        if use_cache:
            cached_data = TMDBService.cache.get(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Try with retries and exponential backoff
        for attempt in range(retries + 1):
            # Rate limit before making request
            TMDBService._rate_limit()

            if has_request_context():
                g.tmdb_api_calls = int(getattr(g, 'tmdb_api_calls', 0)) + 1
            
            try:
                if attempt > 0:
                    logger.info("TMDB retry %s/%s: %s", attempt, retries, endpoint)
                else:
                    logger.debug("TMDB API request: %s", endpoint)
                    
                response = requests.get(f"{base_url}/{endpoint}", params=params, timeout=25,
                                       verify=True)
                response.raise_for_status()
                data = response.json()
                
                # Cache the response
                if use_cache:
                    TMDBService.cache.set(cache_key, data)
                
                return data
                
            except requests.exceptions.Timeout:
                if attempt < retries:
                    # Exponential backoff for timeouts
                    backoff = min(2 ** attempt, 8)  # Cap at 8 seconds
                    logger.warning("TMDB API timeout, retrying in %ss (%s/%s): %s", backoff, attempt + 1, retries, endpoint)
                    time.sleep(backoff)
                    continue
                logger.error("TMDB API timeout after %s retries: %s", retries, endpoint)
                return None
            
            except requests.exceptions.HTTPError as e:
                # Check for specific status codes that should be retried
                status_code = e.response.status_code
                if status_code in [429, 500, 502, 503, 504]:
                    # Retry on rate limit and server errors
                    if attempt < retries:
                        # Longer backoff for rate limits (429) and server errors (5xx)
                        backoff = min(2 ** (attempt + 1), 30)
                        logger.warning("TMDB API HTTP %s, retrying in %ss (%s/%s): %s", 
                                       status_code, backoff, attempt + 1, retries, endpoint)
                        time.sleep(backoff)
                        continue
                
                logger.error("TMDB API HTTP error %s for %s: %s", status_code, endpoint, e)
                return None
                
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    backoff = min(2 ** attempt, 8)
                    logger.warning("TMDB API error, retrying in %ss (%s/%s): %s", backoff, attempt + 1, retries, endpoint)
                    time.sleep(backoff)
                    continue
                logger.error("TMDB API error after %s retries: %s", retries, e)
                return None
            
            except (ValueError, json.JSONDecodeError) as e:
                # JSON parsing error - might be a transient issue
                if attempt < retries:
                    backoff = min(2 ** attempt, 8)
                    logger.warning("TMDB API response parsing error, retrying in %ss (%s/%s): %s", 
                                   backoff, attempt + 1, retries, endpoint)
                    time.sleep(backoff)
                    continue
                logger.error("TMDB API response parsing error after %s retries: %s", retries, e)
                return None
        
        return None

    @staticmethod
    def _get_results_multi_pages(endpoint, base_params=None, min_count=24, max_pages=2):
        """Fetch multiple pages from TMDB and combine results up to min_count.
        Ensures unique items by `id` and respects caching per page.
        """
        combined = []
        seen_ids = set()
        if base_params is None:
            base_params = {}
        for p in range(1, max_pages + 1):
            params = dict(base_params)
            params['page'] = p
            data = TMDBService._make_request(endpoint, params)
            if not data or 'results' not in data:
                break
            for item in data['results']:
                item_id = item.get('id')
                if item_id is not None and item_id in seen_ids:
                    continue
                combined.append(item)
                if item_id is not None:
                    seen_ids.add(item_id)
                if len(combined) >= min_count:
                    return combined[:min_count]
        return combined[:min_count]
    
    @staticmethod
    def get_image_url(path, size=None, is_backdrop=False):
        """Get full image URL from TMDB path with sensible size limits."""
        if not path:
            return None
        base_url = current_app.config['TMDB_IMAGE_BASE_URL']
        if not size:
            size = 'w1280' if is_backdrop else 'w780'
        return f"{base_url}/{size}{path}"
    
    # ===== MOVIES =====
    
    @staticmethod
    def get_trending_movies(time_window='week', page=1, limit=24):
        """Get trending movies"""
        target = max(1, int(limit or 24))
        max_pages = max(1, math.ceil(target / 20))
        results = TMDBService._get_results_multi_pages(
            f'trending/movie/{time_window}', {}, min_count=target, max_pages=max_pages
        )
        for movie in results:
            movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
            movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
            movie['media_type'] = 'movie'
        return results
    
    @staticmethod
    def get_top_rated_movies(page=1, limit=24):
        """Get top rated movies of all time"""
        target = max(1, int(limit or 24))
        max_pages = max(1, math.ceil(target / 20))
        results = TMDBService._get_results_multi_pages(
            'movie/top_rated', {}, min_count=target, max_pages=max_pages
        )
        for movie in results:
            movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
            movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
            movie['media_type'] = 'movie'
        return results
    
    @staticmethod
    def get_popular_movies(page=1):
        """Get popular movies"""
        data = TMDBService._make_request('movie/popular', {'page': page})
        if data and 'results' in data:
            movies = data['results']
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
                movie['media_type'] = 'movie'
            return movies
        return []
    
    @staticmethod
    def get_random_hero_movies(count=5):
        """Get random popular movies for hero carousel"""
        popular = TMDBService.get_popular_movies(page=1)
        if len(popular) > count:
            selected = random.sample(popular, count)
        else:
            selected = popular
        
        for movie in selected:
            movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
            movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
            movie['media_type'] = 'movie'
        
        return selected
    
    # ===== TV SERIES =====
    
    @staticmethod
    def get_trending_tv(time_window='week', page=1):
        """Get trending TV series"""
        results = TMDBService._get_results_multi_pages(f'trending/tv/{time_window}', {}, min_count=24, max_pages=2)
        for show in results:
            show['title'] = show.get('name')
            show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
            show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
            show['release_date'] = show.get('first_air_date')
            show['media_type'] = 'tv'
        return results
    
    @staticmethod
    def get_top_rated_tv(page=1, limit=24):
        """Get top rated TV series"""
        target = max(1, int(limit or 24))
        max_pages = max(1, math.ceil(target / 20))
        results = TMDBService._get_results_multi_pages(
            'tv/top_rated', {}, min_count=target, max_pages=max_pages
        )
        for show in results:
            show['title'] = show.get('name')
            show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
            show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
            show['release_date'] = show.get('first_air_date')
            show['media_type'] = 'tv'
        return results

    @staticmethod
    def get_top_rated_all(limit=100):
        """Get top rated movies and TV shows combined"""
        target = max(1, int(limit or 100))
        movie_limit = max(1, math.ceil(target * 0.6))
        tv_limit = max(1, target - movie_limit)

        movies = TMDBService.get_top_rated_movies(limit=movie_limit)
        shows = TMDBService.get_top_rated_tv(limit=tv_limit)

        combined = movies + shows
        combined.sort(key=lambda item: item.get('vote_average') or 0, reverse=True)
        return combined[:target]
    
    @staticmethod
    def get_popular_tv(page=1):
        """Get popular TV series"""
        data = TMDBService._make_request('tv/popular', {'page': page})
        if data and 'results' in data:
            series = data['results']
            for show in series:
                show['title'] = show.get('name')
                show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
                show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
                show['release_date'] = show.get('first_air_date')
                show['media_type'] = 'tv'
            return series
        return []
    
    # ===== ANIME =====
    
    @staticmethod
    def get_trending_anime(page=1):
        """Get trending anime"""
        base_params = {
            'with_genres': '16',
            'with_origin_country': 'JP',
            'sort_by': 'popularity.desc'
        }
        results = TMDBService._get_results_multi_pages('discover/tv', base_params, min_count=24, max_pages=2)
        for show in results:
            show['title'] = show.get('name')
            show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
            show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
            show['release_date'] = show.get('first_air_date')
            show['media_type'] = 'anime'
        return results
    
    @staticmethod
    def get_top_rated_anime(page=1):
        """Get top rated anime"""
        base_params = {
            'with_genres': '16',
            'with_origin_country': 'JP',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100
        }
        results = TMDBService._get_results_multi_pages('discover/tv', base_params, min_count=24, max_pages=2)
        for show in results:
            show['title'] = show.get('name')
            show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
            show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
            show['release_date'] = show.get('first_air_date')
            show['media_type'] = 'anime'
        return results
    
    # ===== GENRES =====
    
    @staticmethod
    def get_genres():
        """Get list of all movie genres"""
        data = TMDBService._make_request('genre/movie/list')
        if data and 'genres' in data:
            return data['genres']
        return []
    
    @staticmethod
    def get_movies_by_genre(genre_id, page=1):
        """Get movies by genre"""
        params = {
            'with_genres': genre_id,
            'sort_by': 'popularity.desc',
            'page': page
        }
        data = TMDBService._make_request('discover/movie', params)
        if data and 'results' in data:
            movies = data['results']
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
                movie['media_type'] = 'movie'
            return movies
        return []
    
    # ===== DETAILS =====
    
    @staticmethod
    def get_movie_details(movie_id):
        """Get detailed information about a movie"""
        # Use 4 retries for detailed movie fetches (more critical)
        data = TMDBService._make_request(f'movie/{movie_id}', {
            'append_to_response': 'credits,videos,similar,images',
            'include_image_language': 'en,null'
        }, retries=4)
        if data and 'id' in data:
            data['poster_url'] = TMDBService.get_image_url(data.get('poster_path'))
            data['backdrop_url'] = TMDBService.get_image_url(data.get('backdrop_path'), is_backdrop=True)
            data['media_type'] = 'movie'

            logo = TMDBService._select_logo(data.get('images'))
            if logo and logo.get('file_path'):
                data['logo_url'] = TMDBService.get_image_url(logo.get('file_path'), size='w500')
            
            # Get trailer
            if 'videos' in data and 'results' in data['videos']:
                trailer = TMDBService._select_best_trailer(data['videos']['results'])
                if trailer:
                    data['trailer_key'] = trailer['key']
                    data['trailer_url'] = f"https://www.youtube.com/watch?v={trailer['key']}"
            
            return data
        return None
    
    @staticmethod
    def get_tv_details(tv_id):
        """Get detailed information about a TV show"""
        # Use 4 retries for detailed TV fetches (more critical)
        data = TMDBService._make_request(f'tv/{tv_id}', {
            'append_to_response': 'credits,videos,similar,images',
            'include_image_language': 'en,null'
        }, retries=4)
        if data and 'id' in data:
            data['title'] = data.get('name')
            data['poster_url'] = TMDBService.get_image_url(data.get('poster_path'))
            data['backdrop_url'] = TMDBService.get_image_url(data.get('backdrop_path'), is_backdrop=True)
            data['release_date'] = data.get('first_air_date')
            data['runtime'] = data.get('episode_run_time', [45])[0] if data.get('episode_run_time') else 45
            data['media_type'] = 'tv'

            logo = TMDBService._select_logo(data.get('images'))
            if logo and logo.get('file_path'):
                data['logo_url'] = TMDBService.get_image_url(logo.get('file_path'), size='w500')
            
            # Get trailer
            if 'videos' in data and 'results' in data['videos']:
                trailer = TMDBService._select_best_trailer(data['videos']['results'])
                if trailer:
                    data['trailer_key'] = trailer['key']
                    data['trailer_url'] = f"https://www.youtube.com/watch?v={trailer['key']}"
            
            return data
        return None
    
    # ===== SEARCH =====
    
    @staticmethod
    def search_movies(query, page=1):
        """Search for movies"""
        params = {
            'query': query,
            'page': page
        }
        # Use more retries for search to handle transient failures
        data = TMDBService._make_request('search/movie', params, retries=3)
        if data and 'results' in data:
            movies = data['results']
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
                movie['media_type'] = 'movie'
            return movies
        return []
    
    @staticmethod
    def search_all(query, page=1):
        """Search for movies, TV shows, and anime"""
        params = {
            'query': query,
            'page': page
        }
        # Use more retries for search to handle transient failures
        data = TMDBService._make_request('search/multi', params, retries=3)
        if data and 'results' in data:
            results = data['results']
            for item in results:
                if item.get('media_type') in ['movie', 'tv']:
                    if item.get('media_type') == 'tv':
                        item['title'] = item.get('name')
                        item['release_date'] = item.get('first_air_date')
                    item['poster_url'] = TMDBService.get_image_url(item.get('poster_path'))
                    item['backdrop_url'] = TMDBService.get_image_url(item.get('backdrop_path'), is_backdrop=True)
            return [r for r in results if r.get('media_type') in ['movie', 'tv']]
        return []
    
    # ===== CACHE WARMING =====
    
    @staticmethod
    def warm_cache():
        """Pre-populate cache with common requests"""
        logger.info("Starting TMDB cache warmup")
        
        try:
            # Initialize cache
            TMDBService.init_cache()
            
            # Movies
            logger.info("Warming movie caches")
            TMDBService.get_trending_movies('week')
            TMDBService.get_top_rated_movies()
            TMDBService.get_popular_movies()
            
            # TV Series
            logger.info("Warming TV caches")
            TMDBService.get_trending_tv('week')
            TMDBService.get_top_rated_tv()
            TMDBService.get_popular_tv()
            
            # Anime
            logger.info("Warming anime caches")
            TMDBService.get_trending_anime()
            TMDBService.get_top_rated_anime()
            
            # Genres
            logger.info("Warming genre caches")
            genres = TMDBService.get_genres()
            for i, genre in enumerate(genres[:5]):  # Cache first 5 genres
                logger.info("Warming genre %s/5: %s", i + 1, genre['name'])
                TMDBService.get_movies_by_genre(genre['id'])

            logger.info("TMDB cache warmup complete")
        except Exception as e:
            logger.exception("TMDB cache warming error: %s", e)
            import traceback
            traceback.print_exc()