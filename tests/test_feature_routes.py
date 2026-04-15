"""Feature route tests."""

import pytest
from app import app
from tmdb_service import TMDBService


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def test_movie_search_filters_tv_results(monkeypatch, client):
    """Search results should respect media type filters."""

    def fake_search_all(query, page=1):
        return [
            {
                "id": 1,
                "title": "Movie Match",
                "media_type": "movie",
                "poster_url": "https://example.com/movie.jpg",
                "release_date": "2024-01-01",
                "vote_average": 7.5,
            },
            {
                "id": 2,
                "name": "Show Match",
                "media_type": "tv",
                "poster_url": "https://example.com/show.jpg",
                "first_air_date": "2024-02-01",
                "vote_average": 8.4,
            },
        ]

    monkeypatch.setattr(TMDBService, "search_all", staticmethod(fake_search_all))
    response = client.get("/movies/?q=match&media_type=tv&sort=rating")

    assert response.status_code == 200
    assert b"Show Match" in response.data
    assert b"Movie Match" not in response.data


def test_continue_watching_requires_login(client):
    """Protected progress pages should redirect anonymous users."""
    response = client.get("/users/continue-watching")
    assert response.status_code in {302, 401}


@pytest.mark.parametrize("path", ["/users/feed", "/users/continue-watching"])
def test_social_pages_require_login(client, path):
    """Authenticated-only social pages should not be public."""
    response = client.get(path)
    assert response.status_code in {302, 401}
