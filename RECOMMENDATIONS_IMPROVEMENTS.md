# Recommendations System - Major Improvements

## Overview
The recommendations system has been completely revamped to be much smarter and more effective. It now uses multiple strategies including collaborative filtering, user preference analysis, and AI-powered suggestions.

## Key Improvements

### 1. **Collaborative Filtering** 🤝
- Finds users with similar watchlists 
- Recommends items they watched but you haven't
- Scores recommendations by how many similar users watched them
- This is the strongest signal for personalization

```python
_get_similar_users_recommendations()  # New function
```

### 2. **User Genre Preferences** ⭐
- Analyzes your 4-5 star ratings to find your favorite genres
- Weights recommendations based on what you actually rated highly
- Much more accurate than just looking at watchlist

```python
_get_user_genre_preferences()  # New function
```

### 3. **Multi-Factor Scoring System** 📊
Recommendations are now scored based on:
- **Vote Average** (TMDB rating) - weighted 2x
- **Popularity** (capped at 2 points)
- **Genre Match** - bonus if it matches your preferences
- **Collaboration Score** - if similar users watched it
- **Quality Threshold** - minimum vote_average ≥ 5.5 and 50+ votes

```python
_score_recommendations()  # New function
```

### 4. **Smarter Recommendation Pipeline** 🔄
The new order of operations:
1. Try collaborative filtering (find similar users' recommendations)
2. Get your genre preferences from ratings
3. Call AI with better context about what you like
4. Score all results using multi-factor system
5. Apply media mix (respect movie/TV/anime preferences)
6. Use smart fallback if AI fails

### 5. **Better AI Prompts** 🤖
- Includes your top genres per media type (movies/TV/anime)
- Specifies media preference ratio
- More specific instructions about quality
- Better handling of anime vs Western cartoons

### 6. **Enhanced Fallback Strategy** 🆘
When AI is unavailable:
- Fetches 30+ items from trending/top-rated pools (not just 24)
- Genre-specific searches for your favorite genres
- Prioritizes based on your media preference distribution
- Quality filtering before returning results

### 7. **Better Media Type Handling** 📺
- Correctly identifies anime vs regular TV
- Respects if you watch mostly anime (prioritizes anime)
- Respects if you watch mostly movies (prioritizes movies)
- Better mixed results instead of one type dominating

## Technical Changes

### Modified Functions

#### `_get_watchlist_recommendation_seed()` ← Enhanced
- Added `genre_ratings` field for better analysis
- Better tracking of media types per genre
- Improved anime detection

#### `get_personalized_recommendations()` ← Rebuilt
- Added collaborative filtering
- Added user genre preferences extraction
- Improved AI prompting
- Added multi-factor scoring
- Better error handling

#### `get_personalized_recommendations_paginated()` ← Rebuilt  
- Similar improvements as main function
- Better "load more" experience with varied results
- Smarter pagination strategy

#### `get_fallback_recommendations()` ← Enhanced
- Larger content pools (30 items instead of 24)
- Genre-targeted search
- Smart media type distribution
- Quality threshold filtering
- Better edge case handling

### New Helper Functions

1. **`_get_user_genre_preferences(user_id, limit=50)`**
   - Queries user's highly-rated reviews (4-5 stars)
   - Extracts genres from those highly-rated items
   - Returns weighted genre preferences
   - Falls back gracefully if no reviews exist

2. **`_get_similar_users_recommendations(current_user_id, watchlist_ids, limit)`**
   - Finds users with watchlist overlap
   - Gets items they watched but you haven't
   - Ranks by how many similar users watched them
   - Handles anime/movie/TV classification

3. **`_score_recommendations(candidates, seed, user_genre_prefs)`**
   - Applies multi-factor scoring algorithm
   - Considers vote average, popularity, genres, collaboration
   - Returns sorted results by score
   - Filters out low-engagement items

## Behavior Changes

### Before
- Recommendations were mostly based on TMDB's "similar" and "recommended" endpoints
- User watchlist type preferences were only loosely respected
- Ratings/reviews were completely ignored
- Same recommendations on every page load (deterministic)
- Low-quality items could appear
- Anime users might get Western cartoons

### After
- **Collaborative approach** - learns from similar users
- **Preference-aware** - uses your actual ratings to determine taste
- **Quality-focused** - enforces minimum rating/engagement thresholds
- **Diverse** - different results on "load more" (smarter pagination)
- **Media-aware** - respects movie/TV/anime preferences correctly
- **Fallback-smart** - intelligent degradation when AI unavailable

## User Experience Impact

### Better Recommendations Because:
1. System learns from what you **rated** not just what you watched
2. If 10 users like the same movies as you, their other picks become suggestions
3. Hidden gems appear alongside popular titles
4. Your genre preferences are respected
5. Anime stays anime, movies stay movies
6. Each "load more" has varied suggestions instead of repeats

### When to Expect Best Results:
- After rating several movies/shows
- When you have 10+ items in watchlist
- If other users share similar taste
- When ANTHROPIC_API_KEY is configured (AI enhancement)

### Graceful Degradation:
- If AI fails → uses collaborative + genre-based
- If no collaborators → uses genre + popularity
- If no genres → uses trending/popular
- Never returns empty unless database is empty

## Configuration Options (Optional)

No new config needed! Works with existing setup. But benefits from:
- `ANTHROPIC_API_KEY` - Better recommendations with AI
- User ratings/reviews - More personalized suggestions
- Watchlist diversity - Better collaborative filtering

## Testing the New System

1. Add 10+ movies/shows to your watchlist
2. Rate some of them (4-5 stars preferred)
3. Visit /recommendations
4. You should see recommendations that:
   - Match your rated content
   - Include hidden gems not just blockbusters
   - Respect if you like anime/movies/TV
   - Change intelligently on "Load More"

## Performance Notes

- Collaborative filtering adds 1-2 DB queries
- Genre preference extraction adds ~1-2 TMDB calls
- Overall response time shouldn't increase noticeably
- Caching within single request for efficiency
- Graceful degradation if services are slow

---

**Result:** A recommendation system that actually learns your taste instead of just following TMDB's generic suggestions! 🎬✨
