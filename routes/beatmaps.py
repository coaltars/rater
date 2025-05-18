from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime

from util.database import execute_query
from util.auth import login_required
from util.constants import MODE_NAMES

beatmaps_bp = Blueprint('beatmaps', __name__)

@beatmaps_bp.route('/beatmapset/<int:set_id>')
def beatmapset(set_id):
    query = """
        SELECT * FROM beatmapsets 
        WHERE SetID = %s
    """
    beatmapset = execute_query(query, (set_id,), fetch_one=True)
    
    if not beatmapset:
        return render_template('error.html', message="Beatmapset not found")
        
    query = """
        SELECT * FROM beatmaps 
        WHERE SetID = %s 
        ORDER BY Mode, SR
    """
    beatmaps = execute_query(query, (set_id,), fetch_all=True) or []
    
    if not beatmaps:
        return render_template('error.html', message="No beatmaps found in this set")
    
    query = "SELECT UserID, Username FROM mappernames WHERE UserID = %s"
    creator = execute_query(query, (beatmapset['CreatorID'],), fetch_one=True)

    if not creator:
        query = "SELECT UserID, Username FROM users WHERE UserID = %s"
        creator = execute_query(query, (beatmapset['CreatorID'],), fetch_one=True)
    
    user_ratings = {}
    if 'user_id' in session:
        query = """
            SELECT BeatmapID, Score as Rating FROM ratings
            WHERE UserID = %s AND BeatmapID IN (
                SELECT BeatmapID FROM beatmaps
                WHERE SetID = %s
            )
        """
        ratings = execute_query(query, (session['user_id'], set_id), fetch_all=True) or []
        for row in ratings:
            user_ratings[row['BeatmapID']] = row['Rating']

    query = """
        SELECT b.BeatmapID, AVG(r.Score) as AvgRating, COUNT(r.Score) as RatingCount
        FROM beatmaps b
        LEFT JOIN ratings r ON b.BeatmapID = r.BeatmapID
        WHERE b.SetID = %s
        GROUP BY b.BeatmapID
    """
    avg_ratings_results = execute_query(query, (set_id,), fetch_all=True) or []
    
    avg_ratings = {}
    for row in avg_ratings_results:
        avg_ratings[row['BeatmapID']] = {
            'avg': round(row['AvgRating'] or 0, 2),
            'count': row['RatingCount']
        }
    
    query = """
        SELECT c.CommentID, c.UserID, c.Comment, c.date, u.Username
        FROM comments c
        LEFT JOIN users u ON c.UserID = u.UserID
        WHERE c.SetID = %s
        ORDER BY c.date DESC
    """
    comments = execute_query(query, (set_id,), fetch_all=True) or []
    
    return render_template('beatmapset.html', 
                          beatmapset=beatmapset,
                          beatmaps=beatmaps,
                          creator=creator,
                          user_ratings=user_ratings,
                          avg_ratings=avg_ratings,
                          comments=comments,
                          mode_names=MODE_NAMES,
                          user=session.get('user', None))

@beatmaps_bp.route('/rate', methods=['POST'])
@login_required
def rate():
    beatmap_id = request.form.get('beatmap_id', type=int)
    rating = request.form.get('rating', type=float)
    
    if not beatmap_id or rating not in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
        return jsonify({'success': False, 'error': 'Invalid parameters'})

    query = "SELECT RatingID FROM ratings WHERE UserID = %s AND BeatmapID = %s"
    existing = execute_query(query, (session['user_id'], beatmap_id), fetch_one=True)
    
    if existing:
        query = """
            UPDATE ratings 
            SET Score = %s, date = %s
            WHERE UserID = %s AND BeatmapID = %s
        """
        result = execute_query(query, (rating, datetime.now(), session['user_id'], beatmap_id), commit=True)
    else:
        query = """
            INSERT INTO ratings (UserID, BeatmapID, Score, date)
            VALUES (%s, %s, %s, %s)
        """
        result = execute_query(query, (session['user_id'], beatmap_id, rating, datetime.now()), commit=True)
    
    if result is None:
        return jsonify({'success': False, 'error': 'Database error'})

    query = """
        SELECT AVG(Score) as avg, COUNT(*) as count
        FROM ratings
        WHERE BeatmapID = %s
    """
    result = execute_query(query, (beatmap_id,), fetch_one=True)
    
    if not result:
        return jsonify({'success': False, 'error': 'Failed to get updated rating'})
    
    new_avg = round(result['avg'], 2) if result['avg'] else 0
    rating_count = result['count']
    
    query = "UPDATE beatmaps SET WeightedAvg = %s, RatingCount = %s WHERE BeatmapID = %s"
    execute_query(query, (new_avg, rating_count, beatmap_id), commit=True)
    
    return jsonify({
        'success': True, 
        'new_avg': new_avg,
        'count': rating_count
    })

@beatmaps_bp.route('/comment', methods=['POST'])
@login_required
def add_comment():
    set_id = request.form.get('set_id', type=int)
    comment_text = request.form.get('comment')
    
    if not set_id or not comment_text or len(comment_text.strip()) == 0:
        return jsonify({'success': False, 'error': 'Invalid parameters'})
    
    query = """
        INSERT INTO comments (UserID, SetID, Comment, date)
        VALUES (%s, %s, %s, %s)
    """
    result = execute_query(query, (session['user_id'], set_id, comment_text, datetime.now()), commit=True)
    
    if result is None:
        return jsonify({'success': False, 'error': 'Database error'})
    
    return jsonify({
        'success': True,
        'comment': {
            'username': session['username'],
            'comment': comment_text,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    })