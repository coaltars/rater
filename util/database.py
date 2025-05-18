import mysql.connector
from mysql.connector import pooling
from typing import Optional, Dict, List, Any, Union
from datetime import datetime

db_pool = None
def init_db_pool(config: Dict[str, Any]) -> None:
    global db_pool
    try:
        db_pool = mysql.connector.pooling.MySQLConnectionPool(**config)
        print("Database pool initialized successfully")
    except Exception as e:
        print(f"Failed to create database pool: {e}")
        db_pool = None

def get_db_connection():
    try:
        if not db_pool:
            raise Exception("Database pool not initialized")
        conn = db_pool.get_connection()
        return conn
    except Exception as e:
        print(f"Failed to get connection from pool: {e}")
        return None

def execute_query(query: str, params: Union[tuple, dict] = None, fetch_all: bool = False,
                  fetch_one: bool = False, commit: bool = False) -> Union[List, Dict, None]:
    conn = get_db_connection()
    if not conn:
        return None
    
    result = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if fetch_all:
            result = cursor.fetchall()
        elif fetch_one:
            result = cursor.fetchone()
        
        if commit:
            conn.commit()
            
        cursor.close()
    except Exception as e:
        print(f"Query execution error: {e}")
        if commit:
            conn.rollback()
    finally:
        conn.close()
        
    return result

def get_beatmap(beatmap_id: int) -> Optional[Dict]:
    query = """
        SELECT * FROM beatmaps 
        WHERE BeatmapID = %s
    """
    return execute_query(query, (beatmap_id,), fetch_one=True)

def get_beatmaps_by_set_id(set_id: int) -> List[Dict]:
    query = """
        SELECT * FROM beatmaps 
        WHERE SetID = %s
        ORDER BY SR ASC
    """
    return execute_query(query, (set_id,), fetch_all=True) or []

def search_beatmaps(search_term: str, limit: int = 20) -> List[Dict]:
    query = """
        SELECT * FROM beatmaps 
        WHERE MATCH(Artist, Title, DifficultyName) AGAINST(%s IN NATURAL LANGUAGE MODE)
        LIMIT %s
    """
    return execute_query(query, (search_term, limit), fetch_all=True) or []

def get_top_rated_beatmaps(limit: int = 50) -> List[Dict]:
    query = """
        SELECT * FROM beatmaps 
        WHERE WeightedAvg IS NOT NULL
        ORDER BY WeightedAvg DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch_all=True) or []

def get_user(user_id: int) -> Optional[Dict]:
    query = """
        SELECT * FROM users 
        WHERE UserID = %s
    """
    return execute_query(query, (user_id,), fetch_one=True)

def get_user_by_name(username: str) -> Optional[Dict]:
    query = """
        SELECT * FROM users 
        WHERE Username = %s
    """
    return execute_query(query, (username,), fetch_one=True)

def is_user_blacklisted(user_id: int) -> bool:
    query = """
        SELECT * FROM blacklist 
        WHERE UserID = %s
    """
    result = execute_query(query, (user_id,), fetch_one=True)
    return result is not None

def update_user_tokens(user_id: int, access_token: str, refresh_token: str) -> bool:
    query = """
        UPDATE users 
        SET AccessToken = %s, RefreshToken = %s 
        WHERE UserID = %s
    """
    execute_query(query, (access_token, refresh_token, user_id), commit=True)
    return True

def get_user_ratings(user_id: int) -> List[Dict]:
    # Note: Ensure column names match exactly with the database schema
    query = """
        SELECT r.*, b.Artist, b.Title, b.DifficultyName 
        FROM ratings r
        JOIN beatmaps b ON r.BeatmapID = b.BeatmapID
        WHERE r.UserID = %s
        ORDER BY r.date DESC
    """
    return execute_query(query, (user_id,), fetch_all=True) or []

def get_beatmap_ratings(beatmap_id: int) -> List[Dict]:
    query = """
        SELECT r.*, u.Username 
        FROM ratings r
        JOIN users u ON r.UserID = u.UserID
        WHERE r.BeatmapID = %s
        ORDER BY r.date DESC
    """
    return execute_query(query, (beatmap_id,), fetch_all=True) or []

def get_recently_rated_beatmaps(limit: int = 50) -> List[Dict]:
    query = """
        SELECT b.* FROM beatmaps b
        JOIN ratings r ON b.BeatmapID = r.BeatmapID
        GROUP BY b.BeatmapID
        ORDER BY MAX(r.date) DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch_all=True) or []

def get_top_mappers(limit: int = 10) -> List[Dict]:
    query = """
        SELECT b.CreatorID, m.Username, 
            COUNT(DISTINCT b.BeatmapID) as MapCount, 
            AVG(b.WeightedAvg) as AverageRating
        FROM beatmaps b
        JOIN mappernames m ON b.CreatorID = m.UserID
        WHERE b.WeightedAvg IS NOT NULL
        GROUP BY b.CreatorID
        HAVING MapCount >= 3
        ORDER BY AverageRating DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch_all=True) or []

def rate_beatmap(user_id: int, beatmap_id: int, score: float) -> bool:
    check_query = """
        SELECT RatingID FROM ratings 
        WHERE UserID = %s AND BeatmapID = %s
    """
    existing = execute_query(check_query, (user_id, beatmap_id), fetch_one=True)
    
    if existing:
        update_query = """
            UPDATE ratings 
            SET Score = %s, date = %s
            WHERE RatingID = %s
        """
        execute_query(update_query, (score, datetime.now(), existing['RatingID']), commit=True)
    else:
        insert_query = """
            INSERT INTO ratings (BeatmapID, UserID, Score, date) 
            VALUES (%s, %s, %s, %s)
        """
        execute_query(insert_query, (beatmap_id, user_id, score, datetime.now()), commit=True)
    
    update_weighted_avg(beatmap_id)
    return True

def update_weighted_avg(beatmap_id: int) -> None:
    ratings_query = """
        SELECT r.Score, u.Weight 
        FROM ratings r
        JOIN users u ON r.UserID = u.UserID
        WHERE r.BeatmapID = %s AND u.banned = 0
    """
    ratings = execute_query(ratings_query, (beatmap_id,), fetch_all=True) or []
    
    if not ratings:
        return
    
    total_weight = 0
    weighted_sum = 0
    for rating in ratings:
        weight = float(rating['Weight'] or 1.0)
        score = float(rating['Score'])
        weighted_sum += score * weight
        total_weight += weight
    
    weighted_avg = weighted_sum / total_weight if total_weight > 0 else 0
    update_query = """
        UPDATE beatmaps 
        SET WeightedAvg = %s, RatingCount = %s
        WHERE BeatmapID = %s
    """
    execute_query(update_query, (weighted_avg, len(ratings), beatmap_id), commit=True)

def get_comments_for_set(set_id: int) -> List[Dict]:
    query = """
        SELECT c.*, u.Username 
        FROM comments c
        JOIN users u ON c.UserID = u.UserID
        WHERE c.SetID = %s
        ORDER BY c.date DESC
    """
    return execute_query(query, (set_id,), fetch_all=True) or []

def add_comment(user_id: int, set_id: int, comment_text: str) -> bool:
    query = """
        INSERT INTO comments (UserID, SetID, Comment, date) 
        VALUES (%s, %s, %s, %s)
    """
    execute_query(query, (user_id, set_id, comment_text, datetime.now()), commit=True)
    return True

def get_api_key(api_key: str) -> Optional[Dict]:
    query = """
        SELECT * FROM apikeys 
        WHERE ApiKey = %s
    """
    return execute_query(query, (api_key,), fetch_one=True)

def create_api_key(user_id: int, name: str, api_key: str) -> bool:
    query = """
        INSERT INTO apikeys (UserID, Name, ApiKey) 
        VALUES (%s, %s, %s)
    """
    execute_query(query, (user_id, name, api_key), commit=True)
    return True

def get_mapper_by_id(user_id: int) -> Optional[Dict]:
    query = """
        SELECT * FROM mappernames 
        WHERE UserID = %s
    """
    return execute_query(query, (user_id,), fetch_one=True)

def get_mapper_by_name(username: str) -> Optional[Dict]:
    query = """
        SELECT * FROM mappernames 
        WHERE Username = %s
    """
    return execute_query(query, (username,), fetch_one=True)

def get_beatmaps_by_mapper(user_id: int) -> List[Dict]:
    query = """
        SELECT * FROM beatmaps 
        WHERE CreatorID = %s OR SetCreatorID = %s
        ORDER BY DateRanked DESC
    """
    return execute_query(query, (user_id, user_id), fetch_all=True) or []

def get_most_active_raters(limit: int = 10) -> List[Dict]:
    query = """
        SELECT r.UserID, u.Username, COUNT(*) as RatingCount
        FROM ratings r
        JOIN users u ON r.UserID = u.UserID
        WHERE u.banned = 0
        GROUP BY r.UserID
        ORDER BY RatingCount DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch_all=True) or []

def get_most_active_commenters(limit: int = 10) -> List[Dict]:
    query = """
        SELECT c.UserID, u.Username, COUNT(*) as CommentCount
        FROM comments c
        JOIN users u ON c.UserID = u.UserID
        GROUP BY c.UserID
        ORDER BY CommentCount DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch_all=True) or []