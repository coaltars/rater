from flask import Blueprint, render_template, session, request, jsonify
from util.database import execute_query
from util.constants import MODE_NAMES
from util.auth import login_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/user/<int:user_id>')
def user_profile(user_id):
    query = "SELECT * FROM users WHERE UserID = %s"
    user_info = execute_query(query, (user_id,), fetch_one=True)
    
    if not user_info:
        return render_template('error.html', message="User not found")

    query = """
        SELECT r.BeatmapID, r.Score as Rating, r.date as Timestamp,
               b.SetID, b.DifficultyName, b.Mode,
               bs.Artist, bs.Title, bs.CreatorID
        FROM ratings r
        JOIN beatmaps b ON r.BeatmapID = b.BeatmapID
        JOIN beatmapsets bs ON b.SetID = bs.SetID
        WHERE r.UserID = %s
        ORDER BY r.date DESC
        LIMIT 50
    """
    ratings = execute_query(query, (user_id,), fetch_all=True) or []

    query = """
        SELECT COUNT(*) as total, AVG(Score) as average
        FROM ratings
        WHERE UserID = %s
    """
    stats = execute_query(query, (user_id,), fetch_one=True) or {'total': 0, 'average': 0}

    custom_ratings = {
        '0.0': user_info.get('Custom00Rating', ''),
        '0.5': user_info.get('Custom05Rating', ''),
        '1.0': user_info.get('Custom10Rating', ''),
        '1.5': user_info.get('Custom15Rating', ''),
        '2.0': user_info.get('Custom20Rating', ''),
        '2.5': user_info.get('Custom25Rating', ''),
        '3.0': user_info.get('Custom30Rating', ''),
        '3.5': user_info.get('Custom35Rating', ''),
        '4.0': user_info.get('Custom40Rating', ''),
        '4.5': user_info.get('Custom45Rating', ''),
        '5.0': user_info.get('Custom50Rating', '')
    }
    
    user_avatar = "https://a.ppy.sh/" + str(user_data.UserID)
    return render_template('user.html', 
                          user_info=user_info,
                          avatar=user_avatar,
                          ratings=ratings,
                          stats=stats,
                          custom_ratings=custom_ratings,
                          mode_names=MODE_NAMES,
                          user=session.get('user', None))

@users_bp.route('/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    if request.method == 'POST':
        updates = {}
        fields = {
            'custom00': 'Custom00Rating',
            'custom05': 'Custom05Rating',
            'custom10': 'Custom10Rating',
            'custom15': 'Custom15Rating',
            'custom20': 'Custom20Rating',
            'custom25': 'Custom25Rating',
            'custom30': 'Custom30Rating',
            'custom35': 'Custom35Rating',
            'custom40': 'Custom40Rating',
            'custom45': 'Custom45Rating',
            'custom50': 'Custom50Rating'
        }
        
        for field_name, db_field in fields.items():
            if field_name in request.form:
                value = request.form[field_name].strip()
                if len(value) <= 60:
                    updates[db_field] = value
        
        if 'trueRandom' in request.form:
            updates['DoTrueRandom'] = 1 if request.form['trueRandom'] == '1' else 0
            
        if 'userWeight' in request.form:
            try:
                weight = float(request.form['userWeight'])
                if 0 <= weight <= 1:
                    updates['Weight'] = weight
            except ValueError:
                pass
        
        if updates:
            query = "UPDATE users SET "
            query += ", ".join([f"{field} = %s" for field in updates.keys()])
            query += " WHERE UserID = %s"
            
            params = list(updates.values())
            params.append(session['user_id'])
            
            execute_query(query, tuple(params), commit=True)
            
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'No valid updates'})
    
    query = "SELECT * FROM users WHERE UserID = %s"
    user_info = execute_query(query, (session['user_id'],), fetch_one=True)
    
    if not user_info:
        return render_template('error.html', message="User not found")
    
    return render_template('user_settings.html',
                          user_info=user_info,
                          user=session.get('user', None))

@users_bp.route('/user/apikey', methods=['POST'])
@login_required
def generate_api_key():
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    api_key = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    name = request.form.get('name', 'API Key')
    
    query = """
        INSERT INTO apikeys (Name, ApiKey, UserID)
        VALUES (%s, %s, %s)
    """
    result = execute_query(query, (name, api_key, session['user_id']), commit=True)
    
    if result is None:
        return jsonify({'success': False, 'error': 'Failed to create API key'})
    
    return jsonify({
        'success': True,
        'key': api_key
    })