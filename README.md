# 🎬 LUMO - Complete Setup Guide with TMDB Integration

## 📋 Prerequisites

- Python 3.8 or higher
- TMDB API Key (free)

## 🔑 Step 1: Get Your TMDB API Key

1. Go to [https://www.themoviedb.org/](https://www.themoviedb.org/)
2. Create a free account
3. Go to Settings → API
4. Request an API key (choose "Developer" option)
5. Fill out the form (you can use placeholder information for personal projects)
6. Copy your API Key (v3 auth)

## 🚀 Step 2: Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

## ⚙️ Step 3: Configure Your API Key

### Option 1: Environment Variable (Recommended for production)

**Windows:**
```bash
set TMDB_API_KEY=your_api_key_here
```

**macOS/Linux:**
```bash
export TMDB_API_KEY=your_api_key_here
```

### Option 2: Direct in config.py (For development only)

Open `config.py` and replace:
```python
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "YOUR_TMDB_API_KEY_HERE"
```

With:
```python
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "your_actual_api_key_here"
```

**⚠️ WARNING:** Never commit your API key to version control!

### Option 3: Using .env file (Best practice)

1. Create a `.env` file in your project root:
```
TMDB_API_KEY=your_actual_api_key_here
SECRET_KEY=your_secret_key_here
```

2. Install python-dotenv:
```bash
pip install python-dotenv
```

3. Update `config.py` to load from .env:
```python
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "change-this-secret-key-in-production"
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
    # ... rest of config
```

## 🗄️ Step 4: Initialize Database

```bash
python app.py
```

This will:
- Create the `instance` folder
- Create the `cine_sphere.db` SQLite database
- Set up all tables

The app will start running. Press `Ctrl+C` to stop it.

## 🎯 Step 5: Run the Application

```bash
python app.py
```

Open your browser and go to: **http://localhost:5000**

## ✨ What You Can Do

### Home Page Features:
- **Hero Carousel**: 5 random popular movies with auto-rotation
- **Trending This Week**: Top 10 trending movies
- **Top Rated**: Top 10 rated movies of all time
- **Browse by Genre**: Filter movies by genre

### Movie Features:
- Search movies by title
- View detailed movie information
- Watch trailers
- Add movies to watchlist
- Write and edit reviews (1-5 stars)
- See similar movie recommendations
- View cast information

### User Features:
- Register and login
- Personal profile with statistics
- View all your reviews
- Manage your watchlist
- Edit profile and bio

## 🔧 Troubleshooting

### "TMDB API Error" Messages
- Check that your API key is correctly set
- Verify your internet connection
- Ensure the API key hasn't expired

### No Movies Showing
- API key might be invalid
- Check your internet connection
- Look at terminal/console for error messages

### Database Errors
```bash
# Delete the database and restart
rm instance/cine_sphere.db  # On Windows: del instance\cine_sphere.db
python app.py
```

### Import Errors
```bash
# Make sure all dependencies are installed
pip install -r requirements.txt
```

## 📁 Project Structure

```
LUMO/
├── app.py                    # Application entry point
├── config.py                 # Configuration with TMDB settings
├── extensions.py             # Flask extensions
├── models.py                 # Database models (TMDB integrated)
├── tmdb_service.py          # TMDB API service (NEW)
├── routes_auth.py           # Authentication routes
├── routes_main.py           # Home and genre routes (TMDB)
├── routes_movies.py         # Movie routes (TMDB)
├── routes_users.py          # User profile routes (TMDB)
├── requirements.txt         # Python dependencies
├── static/
│   └── css/
│       └── style.css        # Styling
└── templates/
    ├── base.html           # Base template
    ├── index.html          # Home with carousel (NEW)
    ├── auth/
    │   ├── login.html
    │   └── register.html
    ├── movies/
    │   ├── list.html
    │   ├── detail.html     # Movie detail (TMDB)
    │   └── genre.html      # Genre filtering (NEW)
    └── users/
        ├── profile.html    # User profile (TMDB)
        └── edit_profile.html
```

## 🎨 Key Changes from Old Version

### Database Changes:
- ✅ Removed local `Movie` table
- ✅ Reviews now use `tmdb_movie_id` instead of local movie ID
- ✅ Watchlist now uses `tmdb_movie_id` with cached title/poster
- ✅ All movie data fetched dynamically from TMDB

### New Features:
- ✅ Hero carousel with 5 random movies
- ✅ Trending movies section
- ✅ Top rated movies section
- ✅ Genre browsing with filter pills
- ✅ Cast information on movie details
- ✅ Similar movie recommendations
- ✅ Trailers from YouTube
- ✅ TMDB ratings alongside user ratings

### Benefits:
- 📦 No manual movie data entry needed
- 🔄 Always up-to-date movie information
- 🎬 Access to 1,000,000+ movies
- 🖼️ High-quality posters and backdrops
- 📊 Accurate ratings and popularity data

## 🔐 Security Notes

Before deploying to production:

1. **Change SECRET_KEY** in `config.py`:
```python
import secrets
SECRET_KEY = secrets.token_hex(32)
```

2. **Use environment variables** for sensitive data
3. **Set debug=False** in production
4. **Use a production database** (PostgreSQL recommended)
5. **Add .env to .gitignore**

## 📊 API Rate Limits

TMDB Free Tier:
- 40 requests per 10 seconds
- This is plenty for a personal project
- For production, consider caching responses

## 🆘 Need Help?

- TMDB API Documentation: https://developers.themoviedb.org/3
- Check the console/terminal for error messages
- Ensure your API key is valid and active

## 🎉 You're All Set!

Your professional movie rating platform is ready to use with full TMDB integration!

Enjoy discovering and rating movies! 🍿