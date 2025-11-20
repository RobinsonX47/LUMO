"""
TMDB API Service - Enhanced with Anime and TV Series support
Handles all interactions with The Movie Database API
"""

import requests
from flask import current_app
import random

class TMDBService:
    
    @staticmethod
    def _make_request(endpoint, params=None):
        """Make a request to TMDB API"""
        base_url = current_app.config['TMDB_BASE_URL']
        api_key = current_app.config['TMDB_API_KEY']
        
        if not params:
            params = {}
        params['api_key'] = api_key
        
        try:
            response = requests.get(f"{base_url}/{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"TMDB API Error: {e}")
            return None
    
    @staticmethod
    def get_image_url(path, size='w500', is_backdrop=False):
        """Get full image URL from TMDB path"""
        if not path:
            return None
        base_url = current_app.config['TMDB_IMAGE_BASE_URL']
        if is_backdrop:
            size = current_app.config['TMDB_BACKDROP_SIZE']
        else:
            size = current_app.config['TMDB_POSTER_SIZE']
        return f"{base_url}/{size}{path}"
    
    # ===== MOVIES =====
    
    @staticmethod
    def get_trending_movies(time_window='week', page=1):
        """Get trending movies"""
        data = TMDBService._make_request(f'trending/movie/{time_window}', {'page': page})
        if data and 'results' in data:
            movies = data['results'][:10]
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
                movie['media_type'] = 'movie'
            return movies
        return []
    
    @staticmethod
    def get_top_rated_movies(page=1):
        """Get top rated movies of all time"""
        data = TMDBService._make_request('movie/top_rated', {'page': page})
        if data and 'results' in data:
            movies = data['results'][:10]
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
                movie['media_type'] = 'movie'
            return movies
        return []
    
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
        data = TMDBService._make_request(f'trending/tv/{time_window}', {'page': page})
        if data and 'results' in data:
            series = data['results'][:10]
            for show in series:
                show['title'] = show.get('name')  # TV shows use 'name' instead of 'title'
                show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
                show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
                show['release_date'] = show.get('first_air_date')
                show['media_type'] = 'tv'
            return series
        return []
    
    @staticmethod
    def get_top_rated_tv(page=1):
        """Get top rated TV series"""
        data = TMDBService._make_request('tv/top_rated', {'page': page})
        if data and 'results' in data:
            series = data['results'][:10]
            for show in series:
                show['title'] = show.get('name')
                show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
                show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
                show['release_date'] = show.get('first_air_date')
                show['media_type'] = 'tv'
            return series
        return []
    
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
        """Get trending anime (TV shows with Animation genre from Japan)"""
        params = {
            'with_genres': '16',  # Animation genre
            'with_origin_country': 'JP',
            'sort_by': 'popularity.desc',
            'page': page
        }
        data = TMDBService._make_request('discover/tv', params)
        if data and 'results' in data:
            anime = data['results'][:10]
            for show in anime:
                show['title'] = show.get('name')
                show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
                show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
                show['release_date'] = show.get('first_air_date')
                show['media_type'] = 'anime'
            return anime
        return []
    
    @staticmethod
    def get_top_rated_anime(page=1):
        """Get top rated anime"""
        params = {
            'with_genres': '16',
            'with_origin_country': 'JP',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100,
            'page': page
        }
        data = TMDBService._make_request('discover/tv', params)
        if data and 'results' in data:
            anime = data['results'][:10]
            for show in anime:
                show['title'] = show.get('name')
                show['poster_url'] = TMDBService.get_image_url(show.get('poster_path'))
                show['backdrop_url'] = TMDBService.get_image_url(show.get('backdrop_path'), is_backdrop=True)
                show['release_date'] = show.get('first_air_date')
                show['media_type'] = 'anime'
            return anime
        return []
    
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
            'append_to_response': 'credits,videos,similar'
        })
        if data and 'id' in data:
            data['poster_url'] = TMDBService.get_image_url(data.get('poster_path'))
            data['backdrop_url'] = TMDBService.get_image_url(data.get('backdrop_path'), is_backdrop=True)
            data['media_type'] = 'movie'
            
            # Get trailer
            if 'videos' in data and 'results' in data['videos']:
                trailers = [v for v in data['videos']['results'] if v['type'] == 'Trailer' and v['site'] == 'YouTube']
                if trailers:
                    data['trailer_key'] = trailers[0]['key']
                    data['trailer_url'] = f"https://www.youtube.com/watch?v={trailers[0]['key']}"
            
            return data
        return None
    
    @staticmethod
    def get_tv_details(tv_id):
        """Get detailed information about a TV show"""
        data = TMDBService._make_request(f'tv/{tv_id}', {
            'append_to_response': 'credits,videos,similar'
        })
        if data and 'id' in data:
            data['title'] = data.get('name')
            data['poster_url'] = TMDBService.get_image_url(data.get('poster_path'))
            data['backdrop_url'] = TMDBService.get_image_url(data.get('backdrop_path'), is_backdrop=True)
            data['release_date'] = data.get('first_air_date')
            data['runtime'] = data.get('episode_run_time', [45])[0] if data.get('episode_run_time') else 45
            data['media_type'] = 'tv'
            
            # Get trailer
            if 'videos' in data and 'results' in data['videos']:
                trailers = [v for v in data['videos']['results'] if v['type'] == 'Trailer' and v['site'] == 'YouTube']
                if trailers:
                    data['trailer_key'] = trailers[0]['key']
                    data['trailer_url'] = f"https://www.youtube.com/watch?v={trailers[0]['key']}"
            
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