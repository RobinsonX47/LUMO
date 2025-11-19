"""
TMDB API Service
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
            response = requests.get(f"{base_url}/{endpoint}", params=params)
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
    
    @staticmethod
    def get_trending_movies(time_window='week', page=1):
        """Get trending movies"""
        data = TMDBService._make_request(f'trending/movie/{time_window}', {'page': page})
        if data and 'results' in data:
            movies = data['results'][:10]  # Top 10
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
            return movies
        return []
    
    @staticmethod
    def get_top_rated_movies(page=1):
        """Get top rated movies of all time"""
        data = TMDBService._make_request('movie/top_rated', {'page': page})
        if data and 'results' in data:
            movies = data['results'][:10]  # Top 10
            for movie in movies:
                movie['poster_url'] = TMDBService.get_image_url(movie.get('poster_path'))
                movie['backdrop_url'] = TMDBService.get_image_url(movie.get('backdrop_path'), is_backdrop=True)
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
        
        return selected
    
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
            return movies
        return []
    
    @staticmethod
    def get_movie_details(movie_id):
        """Get detailed information about a movie"""
        data = TMDBService._make_request(f'movie/{movie_id}', {
            'append_to_response': 'credits,videos,similar'
        })
        if data:
            data['poster_url'] = TMDBService.get_image_url(data.get('poster_path'))
            data['backdrop_url'] = TMDBService.get_image_url(data.get('backdrop_path'), is_backdrop=True)
            
            # Get trailer
            if 'videos' in data and 'results' in data['videos']:
                trailers = [v for v in data['videos']['results'] if v['type'] == 'Trailer' and v['site'] == 'YouTube']
                if trailers:
                    data['trailer_url'] = f"https://www.youtube.com/watch?v={trailers[0]['key']}"
            
            return data
        return None
    
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
            return movies
        return []