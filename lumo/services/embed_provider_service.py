"""Helper utilities for building safe embedded player URLs."""

from urllib.parse import urlencode
from urllib.parse import urlparse


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_color(value, default_color):
    color = (value or default_color or "").strip().lower().replace("#", "")
    if len(color) == 6 and all(ch in "0123456789abcdef" for ch in color):
        return color
    return (default_color or "e50914").strip().lower().replace("#", "")


def _sanitize_progress(value):
    if value is None or value == "":
        return None
    try:
        progress = int(value)
        return max(progress, 0)
    except (TypeError, ValueError):
        return None


def normalize_provider_base_url(value):
    """Normalize user/config provider URL to a base origin.

    Accepts inputs like:
    - https://www.vidking.net
    - https://www.vidking.net/embed/movie/1078605?color=e50914
    Returns:
    - https://www.vidking.net
    """
    if not value:
        return ""

    raw = str(value).strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"


def _query_params(color, auto_play=False, next_episode=None, episode_selector=None, progress=None):
    params = {
        "color": _sanitize_color(color, "e50914"),
        "autoPlay": str(_parse_bool(auto_play, False)).lower(),
    }
    if next_episode is not None:
        params["nextEpisode"] = str(_parse_bool(next_episode, False)).lower()
    if episode_selector is not None:
        params["episodeSelector"] = str(_parse_bool(episode_selector, True)).lower()

    clean_progress = _sanitize_progress(progress)
    if clean_progress is not None:
        params["progress"] = clean_progress

    return params


def build_movie_embed_url(base_url, tmdb_id, color, auto_play=False, progress=None):
    """Build embed URL for movie content."""
    normalized_base = normalize_provider_base_url(base_url)
    if not normalized_base:
        return None

    params = _query_params(color=color, auto_play=auto_play, progress=progress)
    query = urlencode(params)
    return f"{normalized_base.rstrip('/')}/embed/movie/{int(tmdb_id)}?{query}"


def build_tv_embed_url(base_url, tmdb_id, season, episode, color, auto_play=False, next_episode=True, episode_selector=True, progress=None):
    """Build embed URL for TV content."""
    normalized_base = normalize_provider_base_url(base_url)
    if not normalized_base:
        return None

    safe_season = max(int(season or 1), 1)
    safe_episode = max(int(episode or 1), 1)
    params = _query_params(
        color=color,
        auto_play=auto_play,
        next_episode=next_episode,
        episode_selector=episode_selector,
        progress=progress,
    )
    query = urlencode(params)
    return f"{normalized_base.rstrip('/')}/embed/tv/{int(tmdb_id)}/{safe_season}/{safe_episode}?{query}"
