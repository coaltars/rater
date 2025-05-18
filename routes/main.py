from flask import Blueprint, render_template, session, request
from util.database import execute_query
from util.constants import MODE_NAMES

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    recent_maps = {}
    for mode in range(4):
        query = """
            SELECT b.SetID, b.Artist, b.Title, b.SetCreatorID as CreatorID, 
                   b.Timestamp
            FROM beatmaps b
            WHERE b.Mode = %s AND b.Status > 0
            GROUP BY b.SetID
            ORDER BY b.Timestamp DESC
            LIMIT 8
        """
        mode_maps = execute_query(query, (mode,), fetch_all=True) or []

        for map_data in mode_maps:
            map_data['Metadata'] = f"{map_data['Artist']} - {map_data['Title']}"
            
        recent_maps[mode] = mode_maps

    query = """
        SELECT b.SetID, b.Artist, b.Title, b.SetCreatorID as CreatorID, 
               AVG(r.Score) as AvgRating, COUNT(r.Score) as RatingCount
        FROM ratings r
        JOIN beatmaps b ON r.BeatmapID = b.BeatmapID
        GROUP BY b.SetID
        HAVING RatingCount >= 5
        ORDER BY AvgRating DESC
        LIMIT 10
    """
    top_maps = execute_query(query, fetch_all=True) or []
    
    return render_template('index.html', 
                          recent_maps=recent_maps, 
                          top_maps=top_maps, 
                          mode_names=MODE_NAMES,
                          user=session.get('user', None))

@main_bp.route('/about')
def about():
    stats = {}
    queries = {
        'beatmapsets': "SELECT COUNT(DISTINCT SetID) as count FROM beatmaps",
        'beatmaps': "SELECT COUNT(*) as count FROM beatmaps",
        'users': "SELECT COUNT(*) as count FROM users",
        'ratings': "SELECT COUNT(*) as count FROM ratings"
    }
    
    for key, query in queries.items():
        result = execute_query(query, fetch_one=True)
        stats[key] = result['count'] if result else 0
    
    return render_template('about.html', 
                          stats=stats,
                          user=session.get('user', None))

@main_bp.route('/search')
def search():
    query_string = request.args.get('q', '')
    
    if not query_string or len(query_string) < 3:
        return render_template('search.html', 
                              results=None, 
                              query=query_string,
                              user=session.get('user', None))

    query = """
        SELECT b.SetID, b.Artist, b.Title, b.SetCreatorID as CreatorID, 
               (SELECT COUNT(DISTINCT r.UserID) FROM ratings r WHERE r.BeatmapID IN 
                (SELECT BeatmapID FROM beatmaps WHERE SetID = b.SetID)) as RatingCount,
               (SELECT AVG(r.Score) FROM ratings r WHERE r.BeatmapID IN 
                (SELECT BeatmapID FROM beatmaps WHERE SetID = b.SetID)) as AvgRating,
               MAX(b.DateRanked) as DateRanked
        FROM beatmaps b
        WHERE MATCH(b.Artist, b.Title, b.DifficultyName) AGAINST (%s IN BOOLEAN MODE)
        GROUP BY b.SetID, b.Artist, b.Title, b.SetCreatorID
        ORDER BY DateRanked DESC
        LIMIT 30
    """
    results = execute_query(query, (f'{query_string}*',), fetch_all=True) or []
    
    return render_template('search.html', 
                          results=results, 
                          query=query_string,
                          user=session.get('user', None))