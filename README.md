# 🎬 LUMO - AI-Powered Movie & Entertainment Tracker

<div align="center">

![LUMO](https://img.shields.io/badge/LUMO-Movie%20Tracker-7b5cff?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-black?style=for-the-badge&logo=flask)
![TMDB](https://img.shields.io/badge/TMDB-API-01d277?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A premium movie and entertainment tracking platform with AI-powered recommendations**

[Features](#features) • [Demo](#demo) • [Installation](#installation) • [Usage](#usage) • [Technologies](#technologies)

</div>

---

## 🌟 Overview

**LUMO** is a modern, feature-rich entertainment tracking platform that helps you organize and discover movies, TV series, and anime. Built with a sleek black & grey minimalist design and powered by The Movie Database (TMDB) API, LUMO provides an intuitive way to:

- **Track** your watched movies, series, and anime
- **Review** and rate content with a 5-star rating system
- **Discover** trending and top-rated entertainment across all categories
- **Get AI-powered recommendations** based on your unique viewing preferences
- **Manage** your personal watchlist for content you want to watch
- **Explore** content by genres, popularity, and ratings

Whether you're a casual viewer or a cinephile, LUMO offers a premium experience for managing your entertainment journey.

---

## ✨ Features

### 🎯 Core Features

#### **Personal Entertainment Library**
- Track all movies, TV series, and anime you've watched
- Maintain a personal watchlist for future viewing
- Write detailed reviews with 5-star ratings
- View your complete viewing history and statistics

#### **AI-Powered Recommendations** ⚡
- Get personalized suggestions based on your watchlist
- Advanced AI analyzes your preferences and viewing patterns
- Discover hidden gems tailored to your taste
- Continuously improving recommendations

#### **Rich Content Discovery**
- Browse trending content updated weekly
- Explore top-rated movies and series of all time
- Filter by genres (Action, Drama, Comedy, Sci-Fi, and more)
- Dedicated sections for Movies, TV Series, and Anime

#### **Detailed Content Pages**
- Full-screen auto-playing trailers for immersive previews
- Comprehensive movie information (cast, runtime, ratings)
- User reviews and community ratings
- Related content recommendations
- High-quality poster and backdrop images

### 🎨 Design & UX

- **Premium Black & Grey Theme** - Modern minimalist aesthetic
- **Apple-Style Glass Morphism** - Smooth, translucent UI elements
- **Responsive Design** - Perfect experience on desktop, tablet, and mobile
- **Smooth Animations** - Polished transitions and hover effects
- **Intuitive Navigation** - Easy-to-use interface with quick access

### 👤 User Features

- Secure user authentication (registration & login)
- Customizable user profiles with avatars
- Personal statistics dashboard
- Review management (edit/delete your reviews)
- Privacy-focused user data handling

---

## 🖼️ Demo

### Home Page with Hero Carousel
Beautiful full-width carousel showcasing popular movies with auto-rotation

### Movie Detail Page
Immersive full-screen trailer experience with detailed information

### AI Recommendations
Personalized suggestions powered by advanced AI

### User Profile
Track your reviews, watchlist, and viewing statistics

---

## 🚀 Installation

### Prerequisites

- **Python 3.8+** installed on your system
- **TMDB API Key** (free - get yours at [themoviedb.org](https://www.themoviedb.org/))
- **Git** (optional, for cloning)

### Step 1: Clone or Download

```bash
git clone https://github.com/RobinsonX47/lumo.git
cd lumo
```

Or download and extract the ZIP file.

### Step 2: Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Get TMDB API Key

1. Visit [TMDB](https://www.themoviedb.org/)
2. Create a free account
3. Go to **Settings → API**
4. Request an API key (choose "Developer" option)
5. Copy your **API Key (v3 auth)**

### Step 5: Configure API Key

**Option A: Environment Variable (Recommended)**

```bash
# Windows (PowerShell):
$env:TMDB_API_KEY="your_api_key_here"

# Mac/Linux:
export TMDB_API_KEY="your_api_key_here"
```

**Option B: Direct Configuration**

Edit `config.py`:
```python
TMDB_API_KEY = "your_actual_api_key_here"
```

### Step 6: Initialize Database

```bash
python scripts/migrate_to_tmdb.py
```

This creates the database with all required tables.

### Step 7: Run the Application

```bash
python app.py
```

Visit **http://localhost:5000** in your browser.

---

## 📖 Usage

### Getting Started

1. **Register an Account**
   - Click "Sign up" in the navigation
   - Enter your details
   - You're ready to start!

2. **Explore Content**
   - Browse Movies, Anime, or TV Series from the navigation
   - Use the search bar to find specific content
   - Filter by genres from the Genres page

3. **Add to Watchlist**
   - Click on any movie/show to view details
   - Click "Add to Watchlist" button
   - Access your watchlist from your profile

4. **Write Reviews**
   - On any movie detail page, scroll to the review section
   - Rate the content (1-5 stars)
   - Write your thoughts
   - Submit your review

5. **Get AI Recommendations**
   - Add at least 3-5 items to your watchlist
   - Click "AI Picks" in the navigation
   - Discover personalized recommendations!

### Admin Features (Optional)

To create an admin user for adding local content:

```bash
python scripts/make_admin.py --create --email admin@example.com --name "Admin" --password "your_password"
```

---

## 🛠️ Technologies

### Backend
- **Flask 3.0** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **Flask-Login** - User session management
- **SQLite** - Lightweight database (easily upgradable to PostgreSQL)

### Frontend
- **HTML5 & CSS3** - Modern web standards
- **Vanilla JavaScript** - No heavy frameworks needed
- **Glass Morphism** - Contemporary UI design
- **Responsive Design** - Mobile-first approach

### APIs & Services
- **TMDB API** - Comprehensive movie database
- **Claude AI API** - Advanced recommendation engine
- **YouTube API** - Embedded trailer playback

### Key Libraries
- **Requests** - HTTP library for API calls
- **Werkzeug** - WSGI utilities and security

---

## 📁 Project Structure

```
LUMO/
├── app.py                 # Main application entry point
├── config.py              # Configuration settings
├── models.py              # Database models
├── tmdb_service.py        # TMDB API integration with caching
├── routes_auth.py         # Authentication routes
├── routes_main.py         # Home and section routes
├── routes_movies.py       # Movie/TV detail and review routes
├── routes_users.py        # User profile routes
├── requirements.txt       # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css     # Premium styling
│   ├── js/
│   │   ├── carousel.js   # Hero carousel functionality
│   │   └── main.js       # General JavaScript
│   └── images/
│       └── logo.svg      # LUMO logo
├── templates/
│   ├── base.html         # Base template with navigation
│   ├── index.html        # Home page
│   ├── auth/             # Login/register pages
│   ├── movies/           # Movie detail and list pages
│   ├── sections/         # Movies/Anime/Series sections
│   └── users/            # User profile pages
└── scripts/
    ├── migrate_to_tmdb.py    # Database migration
    └── make_admin.py         # Admin user creation
```

---

## ⚙️ Configuration

### Cache Settings

LUMO uses intelligent caching to minimize API calls:
- Cache duration: **6 hours**
- Cache warmup on startup for faster initial loads
- Automatic cache invalidation

### API Rate Limiting

- TMDB Free Tier: 40 requests per 10 seconds
- Built-in rate limiting: ~4 requests/second
- More than sufficient for personal use

### Database

Default: SQLite (`instance/cine_sphere.db`)

For production, upgrade to PostgreSQL:
```python
# config.py
SQLALCHEMY_DATABASE_URI = "postgresql://user:pass@localhost/lumo"
```

---

## 🔐 Security Notes

### Before Production Deployment:

1. **Change Secret Key**
   ```python
   SECRET_KEY = "your-strong-random-secret-key-here"
   ```

2. **Use Environment Variables**
   - Store API keys in environment variables
   - Never commit `.env` files

3. **Disable Debug Mode**
   ```python
   app.run(debug=False)
   ```

4. **Use Production Database**
   - Switch from SQLite to PostgreSQL
   - Enable database backups

5. **Add HTTPS**
   - Use SSL certificates
   - Enable secure cookies

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide for Python
- Write clear commit messages
- Test your changes thoroughly
- Update documentation as needed

---

## 🐛 Troubleshooting

### Database Issues
```bash
# Reset database
rm instance/cine_sphere.db
python scripts/migrate_to_tmdb.py
```

### API Key Issues
- Verify your TMDB API key is correct
- Check if you've hit rate limits (wait 10 seconds)
- Ensure your TMDB account is verified

### Cache Issues
```bash
# Clear cache
rm -rf instance/cache/*
```

### Port Already in Use
```bash
# Use a different port
python app.py --port 5001
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **TMDB** - For their comprehensive movie database API
- **Anthropic** - For Claude AI powering recommendations
- **Flask Community** - For the excellent web framework
- **Contributors** - For making LUMO better

---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/lumo/issues)
- **Email**: your.email@example.com
- **Documentation**: [Wiki](https://github.com/yourusername/lumo/wiki)

---

<div align="center">

**Made with ❤️ by [Your Name]**

⭐ Star this repo if you find it helpful!

</div>