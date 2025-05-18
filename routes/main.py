from flask import Blueprint, render_template, session, request
from util.database import execute_query
from util.constants import MODE_NAMES

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    recent_maps = {}
    for mode in range(4):
        query = """
            SELECT c.SetID, bs.Artist, bs.Title, c.CreatorID, c.Timestamp, c.Metadata
            FROM cache_home_recent_maps c
            JOIN beatmapsets bs ON c.SetID = bs.SetID
            WHERE c.Mode = %s
            ORDER BY c.Timestamp DESC
            LIMIT 8
        """
        mode_maps = execute_query(query, (mode,), fetch_all=True) or []
        recent_maps[mode] = mode_maps
    
    query = """
        SELECT b.BeatmapID, b.SetID, bs.Artist, bs.Title, b.DifficultyName, bs.CreatorID,
               tm.RatingCount, tm.WeightedAvg, b.Mode
        FROM top_maps tm
        JOIN beatmaps b ON tm.BeatmapID = b.BeatmapID
        JOIN beatmapsets bs ON b.SetID = bs.SetID
        ORDER BY tm.WeightedAvg DESC, tm.RatingCount DESC
        LIMIT 10
    """
    top_maps = execute_query(query, fetch_all=True) or []
    
    for map_data in top_maps:
        map_data['Metadata'] = f"{map_data['Artist']} - {map_data['Title']} [{map_data['DifficultyName']}]"

    best_maps = {}
    query = """
        SELECT c.BeatmapID, b.SetID, bs.Artist, bs.Title, b.DifficultyName, bs.CreatorID, 
               tm.RatingCount, tm.WeightedAvg, c.Mode
        FROM cache_home_best_map c
        JOIN beatmaps b ON c.BeatmapID = b.BeatmapID
        JOIN beatmapsets bs ON b.SetID = bs.SetID
        JOIN top_maps tm ON c.BeatmapID = tm.BeatmapID
        WHERE c.Mode = %s
    """
    
    for mode in range(4):
        result = execute_query(query, (mode,), fetch_one=True)
        if result:
            result['Metadata'] = f"{result['Artist']} - {result['Title']} [{result['DifficultyName']}]"
            best_maps[mode] = result
    
    return render_template('index.html',
                          recent_maps=recent_maps,
                          top_maps=top_maps,
                          best_maps=best_maps,
                          mode_names=MODE_NAMES,
                          user=session.get('user', None))

@main_bp.route('/about')
def about():
    stats = {}
    queries = {
        'beatmapsets': "SELECT COUNT(DISTINCT SetID) as count FROM beatmapsets",
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
        SELECT bs.SetID, bs.Artist, bs.Title, bs.CreatorID, bs.DateRanked,
               (SELECT COUNT(DISTINCT r.UserID) FROM ratings r
                JOIN beatmaps bm ON r.BeatmapID = bm.BeatmapID
                WHERE bm.SetID = bs.SetID) as RatingCount,
               (SELECT AVG(r.Score) FROM ratings r
                JOIN beatmaps bm ON r.BeatmapID = bm.BeatmapID
                WHERE bm.SetID = bs.SetID) as AvgRating
        FROM beatmapsets bs
        JOIN beatmaps b ON bs.SetID = b.SetID
        WHERE MATCH(b.DifficultyName) AGAINST (%s IN BOOLEAN MODE)
           OR MATCH(bs.Artist, bs.Title) AGAINST (%s IN BOOLEAN MODE)
        GROUP BY bs.SetID, bs.Artist, bs.Title, bs.CreatorID, bs.DateRanked
        ORDER BY bs.DateRanked DESC
        LIMIT 30
    """
    results = execute_query(query, (f'{query_string}*', f'{query_string}*'), fetch_all=True) or []
    
    return render_template('search.html',
                          results=results,
                          query=query_string,
                          user=session.get('user', None))