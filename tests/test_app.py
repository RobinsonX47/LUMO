"""Basic app tests."""
import pytest
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_app_exists():
    """Test that the app exists."""
    assert app is not None


def test_app_is_testing():
    """Test that the app is in testing mode."""
    app.config['TESTING'] = True
    assert app.config['TESTING'] is True


def test_csp_blocks_external_navigation(client):
    """The app should send a CSP that prevents embedded content from redirecting the top page."""
    response = client.get("/")

    csp_header = response.headers.get("Content-Security-Policy", "")
    assert "navigate-to 'self'" in csp_header
