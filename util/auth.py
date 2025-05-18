from flask import session, redirect, url_for, request
from functools import wraps
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from util.database import execute_query

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_oauth_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
    token_url = "https://osu.ppy.sh/oauth/token"
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        return None
    
    return response.json()

def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    user_url = "https://osu.ppy.sh/api/v2/me"
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(user_url, headers=headers)
    
    if response.status_code != 200:
        return None
    
    return response.json()

def save_user_to_db(user_data: Dict[str, Any]) -> bool:
    query = """
        REPLACE INTO users (UserID, Username, LastAccessedSite) 
        VALUES (%s, %s, %s)
    """
    params = (
        user_data['id'], 
        user_data['username'],
        datetime.now()
    )
    
    return execute_query(query, params, commit=True) is not None