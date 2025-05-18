from flask import Blueprint, request, redirect, url_for, session, flash
from datetime import datetime

from config import OSU_CLIENT_ID, OSU_CLIENT_SECRET, OSU_REDIRECT_URI
from util.auth import get_oauth_token, get_user_info, save_user_to_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    auth_url = f"https://osu.ppy.sh/oauth/authorize?client_id={OSU_CLIENT_ID}&redirect_uri={OSU_REDIRECT_URI}&response_type=code&scope=identify"
    return redirect(auth_url)

@auth_bp.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        flash('Authentication failed', 'error')
        return redirect(url_for('main.index'))
    
    token_data = get_oauth_token(OSU_CLIENT_ID, OSU_CLIENT_SECRET, code, OSU_REDIRECT_URI)
    if not token_data:
        flash('Failed to obtain token', 'error')
        return redirect(url_for('main.index'))
    
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    
    user_data = get_user_info(access_token)
    if not user_data:
        flash('Failed to get user info', 'error')
        return redirect(url_for('main.index'))
    
    session.permanent = True
    session['user_id'] = user_data['id']
    session['username'] = user_data['username']
    session['avatar_url'] = user_data['avatar_url']
    session['user'] = {
        'id': user_data['id'],
        'username': user_data['username'],
        'avatar_url': user_data['avatar_url']
    }

    save_user_to_db(user_data)
    flash('Login successful', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('main.index'))