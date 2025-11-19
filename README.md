# 🎬 LUMO

A modern, professional movie rating and discovery platform built with Flask. LUMO features a beautiful glassmorphic UI with a dark theme, user authentication, movie reviews, and watchlist management.

## ✨ Features

- **User Authentication**: Secure registration and login system
- **Movie Discovery**: Browse and search through a curated collection of movies
- **Review System**: Rate and review movies on a 5-star scale
- **Personal Watchlist**: Save movies to watch later
- **User Profiles**: View your watched movies and ratings
- **Trending Section**: Discover popular movies based on view counts
- **Top Rated**: See the highest-rated movies
- **Modern UI**: Glassmorphic design with smooth animations

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone or download the project**

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize the database**

   ```bash
   python app.py
   ```

   This will create the `instance/cine_sphere.db` SQLite database.

6. **Seed the database with sample movies** (optional but recommended)

   ```bash
   python seed_data.py
   ```

7. **Run the application**

   ```bash
   python app.py
   ```

8. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

## 📁 Project Structure

```
cinesphere/
├── app.py                 # Application factory and initialization
├── config.py              # Configuration settings
├── extensions.py          # Flask extensions (SQLAlchemy, LoginManager)
├── models.py              # Database models
├── routes_auth.py         # Authentication routes
├── routes_main.py         # Home page routes
├── routes_movies.py       # Movie-related routes
├── routes_users.py        # User profile routes
├── seed_data.py           # Database seeding script
├── requirements.txt       # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css     # Styling
│   └── js/
│       └── main.js       # JavaScript (empty, ready for future use)
└── templates/
    ├── base.html         # Base template
    ├── index.html        # Home page
    ├── auth/
    │   ├── login.html    # Login page
    │   └── register.html # Registration page
    ├── movies/
    │   ├── list.html     # Movie listing page
    │   └── detail.html   # Movie detail page
    └── users/
        └── profile.html  # User profile page
```

## 🎨 Key Features Explained

### Authentication System

- Secure password hashing using Werkzeug
- Flask-Login for session management
- Protected routes requiring authentication

### Movie Management

- Browse all movies with search functionality
- View detailed movie information including ratings and reviews
- Add movies to your personal watchlist
- Submit and update reviews

### User Experience

- Responsive design that works on all devices
- Glassmorphic UI with backdrop blur effects
- Smooth hover animations and transitions
- Star rating system for reviews

### Database Models

- **User**: User accounts with authentication
- **Movie**: Movie information and metadata
- **Review**: User reviews and ratings
- **Watchlist**: User's saved movies
- **ViewLog**: Track movie views for trending calculation
- **Genre**: Movie genres (ready for future use)

## 🔒 Security Notes

**Important**: Before deploying to production:

1. Change the `SECRET_KEY` in `config.py`:

   ```python
   SECRET_KEY = "your-secure-random-secret-key"
   ```

   Generate a secure key using:

   ```python
   import secrets
   secrets.token_hex(32)
   ```

2. Set `debug=False` in production
3. Use a production-ready database (PostgreSQL recommended)
4. Add environment variable support for sensitive data

## 🛠️ Customization

### Adding More Movies

1. Edit `seed_data.py` to add your movies to the `movies_data` list
2. Run the seed script again:
   ```bash
   python seed_data.py
   ```

### Changing the Theme

- Edit `static/css/style.css`
- Modify CSS variables in the `:root` selector:
  ```css
  :root {
    --bg: #050816;
    --accent: #7b5cff;
    --text: #f5f5f7;
    --muted: #a1a1aa;
  }
  ```

## 📝 Future Enhancements

Potential features to add:

- Movie recommendations based on user preferences
- Social features (follow users, share reviews)
- Advanced search with genre filters
- Movie trailers embedded in detail page
- User avatars upload
- Admin panel for movie management
- API integration with TMDB or similar services
- Export watchlist functionality

## 🐛 Troubleshooting

**Database errors**: Delete `instance/cine_sphere.db` and restart the app to recreate

**Import errors**: Make sure virtual environment is activated and dependencies are installed

**Port already in use**: Change the port in `app.py`:

```python
app.run(debug=True, port=5001)
```

## 📄 License

This project is open source and available for educational purposes.

## 🤝 Contributing

Feel free to fork this project and submit pull requests with improvements!

---

Made with ❤️ for movie lovers
