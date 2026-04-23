from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress


def get_rate_limit_key():
    """Use the first forwarded IP when behind a trusted proxy, otherwise remote addr."""
    from flask import request

    if request.access_route:
        return request.access_route[0]
    return request.remote_addr or "127.0.0.1"

db = SQLAlchemy()
login_manager = LoginManager()
compress = Compress()

# Initialize security extensions (will be configured in app.py)
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["200 per hour"],
    strategy="fixed-window"
)
