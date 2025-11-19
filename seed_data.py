"""
Seed script to populate the database with sample movies.
Run this after creating the database to add initial data.
"""

from app import create_app
from extensions import db
from models import Movie, Genre, MovieGenreMap
from werkzeug.security import generate_password_hash

def seed_database():
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        MovieGenreMap.query.delete()
        Genre.query.delete()
        Movie.query.delete()
        
        # Create genres
        genres_data = [
            "Action", "Drama", "Comedy", "Thriller", "Sci-Fi", 
            "Romance", "Horror", "Fantasy", "Animation", "Documentary"
        ]
        
        genres = {}
        for genre_name in genres_data:
            genre = Genre(name=genre_name)
            db.session.add(genre)
            genres[genre_name] = genre
        
        db.session.commit()
        
        # Create sample movies
        movies_data = [
            {
                "title": "The Shawshank Redemption",
                "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
                "release_year": 1994,
                "duration_minutes": 142,
                "poster_path": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop",
                "avg_rating": 4.8,
                "genres": ["Drama"]
            },
            {
                "title": "Inception",
                "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea.",
                "release_year": 2010,
                "duration_minutes": 148,
                "poster_path": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=400&h=600&fit=crop",
                "avg_rating": 4.7,
                "genres": ["Sci-Fi", "Thriller"]
            },
            {
                "title": "The Dark Knight",
                "description": "When the menace known as the Joker wreaks havoc on Gotham, Batman must accept one of the greatest psychological tests.",
                "release_year": 2008,
                "duration_minutes": 152,
                "poster_path": "https://images.unsplash.com/photo-1509347528160-9a9e33742cdb?w=400&h=600&fit=crop",
                "avg_rating": 4.8,
                "genres": ["Action", "Thriller"]
            },
            {
                "title": "Pulp Fiction",
                "description": "The lives of two mob hitmen, a boxer, and a pair of diner bandits intertwine in four tales of violence and redemption.",
                "release_year": 1994,
                "duration_minutes": 154,
                "poster_path": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?w=400&h=600&fit=crop",
                "avg_rating": 4.6,
                "genres": ["Drama", "Thriller"]
            },
            {
                "title": "Forrest Gump",
                "description": "The presidencies of Kennedy and Johnson unfold through the perspective of an Alabama man with an IQ of 75.",
                "release_year": 1994,
                "duration_minutes": 142,
                "poster_path": "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?w=400&h=600&fit=crop",
                "avg_rating": 4.5,
                "genres": ["Drama", "Romance"]
            },
            {
                "title": "The Matrix",
                "description": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
                "release_year": 1999,
                "duration_minutes": 136,
                "poster_path": "https://images.unsplash.com/photo-1574267432644-f610ed74f134?w=400&h=600&fit=crop",
                "avg_rating": 4.6,
                "genres": ["Sci-Fi", "Action"]
            },
            {
                "title": "Interstellar",
                "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
                "release_year": 2014,
                "duration_minutes": 169,
                "poster_path": "https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=400&h=600&fit=crop",
                "avg_rating": 4.7,
                "genres": ["Sci-Fi", "Drama"]
            },
            {
                "title": "The Godfather",
                "description": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
                "release_year": 1972,
                "duration_minutes": 175,
                "poster_path": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=400&h=600&fit=crop",
                "avg_rating": 4.9,
                "genres": ["Drama"]
            },
            {
                "title": "Fight Club",
                "description": "An insomniac office worker and a devil-may-care soap maker form an underground fight club.",
                "release_year": 1999,
                "duration_minutes": 139,
                "poster_path": "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=400&h=600&fit=crop",
                "avg_rating": 4.5,
                "genres": ["Drama", "Thriller"]
            },
            {
                "title": "Parasite",
                "description": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
                "release_year": 2019,
                "duration_minutes": 132,
                "poster_path": "https://images.unsplash.com/photo-1594908900066-3f47337549d8?w=400&h=600&fit=crop",
                "avg_rating": 4.6,
                "genres": ["Drama", "Thriller"]
            },
            {
                "title": "The Grand Budapest Hotel",
                "description": "A writer encounters the owner of an aging high-class hotel, who tells him of his early years serving as a lobby boy.",
                "release_year": 2014,
                "duration_minutes": 99,
                "poster_path": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=400&h=600&fit=crop",
                "avg_rating": 4.4,
                "genres": ["Comedy", "Drama"]
            },
            {
                "title": "Spirited Away",
                "description": "During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods and witches.",
                "release_year": 2001,
                "duration_minutes": 125,
                "poster_path": "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=400&h=600&fit=crop",
                "avg_rating": 4.7,
                "genres": ["Animation", "Fantasy"]
            }
        ]
        
        for movie_data in movies_data:
            movie_genres = movie_data.pop("genres")
            movie = Movie(**movie_data)
            db.session.add(movie)
            db.session.flush()
            
            # Add genre mappings
            for genre_name in movie_genres:
                mapping = MovieGenreMap(movie_id=movie.id, genre_id=genres[genre_name].id)
                db.session.add(mapping)
        
        db.session.commit()
        print(f"✅ Successfully seeded {len(movies_data)} movies!")


if __name__ == "__main__":
    seed_database()