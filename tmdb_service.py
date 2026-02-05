"""
TMDB API Service - Enhanced with Working Caching and Rate Limiting
Handles all interactions with The Movie Database API with intelligent caching
"""

import requests
from flask import current_app
import random
import json
import os
import time
import math
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

class TMDBCache:
    """Handles caching of TMDB API responses"""
    
    def __init__(self, cache_dir='instance/cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = timedelta(hours=6)  # Cache for 6 hours
        print(f"✅ Cache directory: {self.cache_dir.absolute()}")
    
    def get_cache_path(self, key):
        """Get the file path for a cache key using hash for safe filenames"""
        # Use hash to create safe, consistent filenames
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def get(self, key):
        """Get cached data if it exists and is not expired"""
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
            
            print(f"✅ Cache HIT: {key[:50]}...")
            return cache_data['data']
        except Exception as e:
            print(f"⚠️ Cache read error: {e}")
            # Delete corrupted cache file
            try:
                cache_path.unlink()
            except:
                pass
            return None
    
    def set(self, key, data):
        """Cache data with timestamp"""
        cache_path = self.get_cache_path(key)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'key': key,  # Store original key for debugging
                'data': data
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"✅ Cache SET: {key[:50]}...")
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")
    
    def clear(self):
        """Clear all cache files"""
        try:
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            print("✅ Cache cleared")
        except Exception as e:
            print(f"⚠️ Cache clear error: {e}")

class TMDBService:
    cache = None
    last_request_time = 0
    min_request_interval = 0.26  # ~4 requests per second (well under 40/10s limit)

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
    def _make_request(endpoint, params=None, use_cache=True, retries=2):
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
        
        # Try with retries
        for attempt in range(retries + 1):
            # Rate limit before making request
            TMDBService._rate_limit()
            
            try:
                if attempt > 0:
                    print(f"🔄 Retry {attempt}/{retries}: {endpoint}")
                else:
                    print(f"🌐 API Request: {endpoint}")
                    
                response = requests.get(f"{base_url}/{endpoint}", params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                # Cache the response
                if use_cache:
                    TMDBService.cache.set(cache_key, data)
                
                return data
                
            except requests.exceptions.Timeout:
                if attempt < retries:
                    print(f"⏱️ TMDB API Timeout, retrying... ({attempt + 1}/{retries})")
                    time.sleep(0.5)  # Brief pause before retry
                    continue
                print(f"⏱️ TMDB API Timeout after {retries} retries: {endpoint}")
                return None
                
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    print(f"⚠️ TMDB API Error, retrying... ({attempt + 1}/{retries})")
                    time.sleep(0.5)
                    continue
                print(f"❌ TMDB API Error after {retries} retries: {e}")
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
        data = TMDBService._make_request(f'movie/{movie_id}', {
            'append_to_response': 'credits,videos,similar,images',
            'include_image_language': 'en,null'
        })
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
        data = TMDBService._make_request(f'tv/{tv_id}', {
            'append_to_response': 'credits,videos,similar,images',
            'include_image_language': 'en,null'
        })
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
        data = TMDBService._make_request('search/movie', params)
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
        data = TMDBService._make_request('search/multi', params)
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
        print("\n" + "="*60)
        print("🔥 Warming up TMDB cache...")
        print("="*60)
        
        try:
            # Initialize cache
            TMDBService.init_cache()
            
            # Movies
            print("📽️  Caching movies...")
            TMDBService.get_trending_movies('week')
            TMDBService.get_top_rated_movies()
            TMDBService.get_popular_movies()
            
            # TV Series
            print("📺 Caching TV series...")
            TMDBService.get_trending_tv('week')
            TMDBService.get_top_rated_tv()
            TMDBService.get_popular_tv()
            
            # Anime
            print("🎌 Caching anime...")
            TMDBService.get_trending_anime()
            TMDBService.get_top_rated_anime()
            
            # Genres
            print("🎭 Caching genres...")
            genres = TMDBService.get_genres()
            for i, genre in enumerate(genres[:5]):  # Cache first 5 genres
                print(f"   Genre {i+1}/5: {genre['name']}")
                TMDBService.get_movies_by_genre(genre['id'])
            
            print("\n" + "="*60)
            print("✅ Cache warming complete!")
            print("="*60 + "\n")
        except Exception as e:
            print(f"\n❌ Cache warming error: {e}")
            import traceback
            traceback.print_exc()