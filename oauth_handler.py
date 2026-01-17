import requests
from flask import current_app
from urllib.parse import urlencode, parse_qs
from urllib.request import urlopen
import json


class GoogleOAuth:
    """Google OAuth 2.0 handler"""
    
    @staticmethod
    def get_google_provider_config():
        """Fetch Google OAuth configuration"""
        return requests.get(
            current_app.config["GOOGLE_DISCOVERY_URL"]
        ).json()
    
    @staticmethod
    def get_authorization_url():
        """Generate Google authorization URL"""
        google_provider_cfg = GoogleOAuth.get_google_provider_config()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        
        request_uri = (
            f"{authorization_endpoint}?"
            f"client_id={current_app.config['GOOGLE_CLIENT_ID']}&"
            f"response_type=code&"
            f"scope=openid email profile&"
            f"redirect_uri={GoogleOAuth.get_redirect_uri()}&"
            f"access_type=offline"
        )
        return request_uri
    
    @staticmethod
    def get_redirect_uri():
        """Get the redirect URI for OAuth callback"""
        from flask import url_for
        return url_for("auth.google_callback", _external=True)
    
    @staticmethod
    def exchange_code_for_token(code):
        """Exchange authorization code for access token"""
        google_provider_cfg = GoogleOAuth.get_google_provider_config()
        token_endpoint = google_provider_cfg["token_endpoint"]
        
        token_request = {
            "code": code,
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": GoogleOAuth.get_redirect_uri(),
            "grant_type": "authorization_code",
        }
        
        response = requests.post(token_endpoint, data=token_request)
        tokens = response.json()
        return tokens
    
    @staticmethod
    def get_user_info(token):
        """Get user info from Google using the access token"""
        google_provider_cfg = GoogleOAuth.get_google_provider_config()
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(userinfo_endpoint, headers=headers)
        return response.json()
