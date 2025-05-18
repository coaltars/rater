#!/usr/bin/env python3
from ossapi import Ossapi
import mysql.connector
import datetime
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any, Union

load_dotenv()
RULESETS = {
    "osu": 0,
    "taiko": 1,
    "fruits": 2,
    "mania": 3,
}

DB_CONFIG = {
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'rater')
}

OSU_CLIENT_ID = os.getenv('OSU_CLIENT_ID', '')
OSU_CLIENT_SECRET = os.getenv('OSU_CLIENT_SECRET', '')

def update_beatmaps() -> None:
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return
    
    api = Ossapi(OSU_CLIENT_ID, OSU_CLIENT_SECRET)

    cursor.execute("SELECT MAX(DateRanked) FROM beatmapsets;")
    result = cursor.fetchone()
    latest_date = result[0] if result and result[0] else datetime.datetime(2007, 1, 1)
    
    current_time = datetime.datetime.now()
    cursor.execute("SELECT COUNT(*) FROM setretrieveinfo")
    has_rows = cursor.fetchone()[0] > 0
    
    if has_rows:
        cursor.execute("UPDATE setretrieveinfo SET LastRetrieval = %s, LastDate = %s", 
                      (current_time, current_time.date()))
    else:
        cursor.execute("INSERT INTO setretrieveinfo (LastRetrieval, LastDate) VALUES (%s, %s)", 
                      (current_time, current_time.date()))
    cnx.commit()

    sql_beatmapsets = """
        REPLACE INTO beatmapsets (
            SetID, CreatorID, Status, Timestamp,
            Genre, Lang, Artist, Title, DateRanked,
            HasStoryboard, HasVideo
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    sql_beatmaps = """
        REPLACE INTO beatmaps (
            BeatmapID, SetID, DifficultyName, Mode, 
            Status, SR, Timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    while True:
        beatmapsets = api.search_beatmapsets(
            query=f"ranked>\"{latest_date.strftime('%Y-%m-%d %H:%M:%S')}\"",
            sort="ranked_asc",
            explicit_content="show"
        ).beatmapsets
        
        if not beatmapsets:
            print("No new beatmapsets found")
            break
        
        print(f"Found {len(beatmapsets)} new beatmapsets")
        
        for beatmapset in beatmapsets:
            display_date = beatmapset.ranked_date
            if str(beatmapset.ranked) == "RankStatus.LOVED":
                display_date = beatmapset.submitted_date

            try:
                cursor.execute(
                    "INSERT IGNORE INTO mappernames (UserID, Username, Country) VALUES (%s, %s, %s)",
                    (beatmapset.user_id, beatmapset.creator, beatmapset.creator_country_code if hasattr(beatmapset, 'creator_country_code') else None)
                )
                cnx.commit()
                
                beatmapset_values = (
                    beatmapset.id,
                    beatmapset.user_id,
                    beatmapset.status.value if hasattr(beatmapset, 'status') else 1,
                    datetime.datetime.now(),
                    beatmapset.genre_id if hasattr(beatmapset, 'genre_id') else None,
                    beatmapset.language_id if hasattr(beatmapset, 'language_id') else None,
                    beatmapset.artist,
                    beatmapset.title,
                    display_date,
                    1 if getattr(beatmapset, 'has_storyboard', False) else 0,
                    1 if getattr(beatmapset, 'has_video', False) else 0
                )
                
                try:
                    cursor.execute(sql_beatmapsets, beatmapset_values)
                    cnx.commit()
                except Exception as e:
                    print(f"Error inserting beatmapset {beatmapset.id}: {e}")
                
                for beatmap in beatmapset.beatmaps:
                    cursor.execute("SELECT * FROM blacklist WHERE UserID = %s;", (beatmap.user_id,))
                    result = cursor.fetchone()
                    
                    blacklisted = 1 if result else 0
                    blacklist_reason = "Mapper has requested blacklist." if result else None

                    beatmap_values = (
                        beatmap.id,
                        beatmapset.id,
                        beatmap.version,
                        beatmap.mode_int,
                        beatmap.status.value,
                        beatmap.difficulty_rating,
                        datetime.datetime.now()
                    )
                    
                    try:
                        cursor.execute(sql_beatmaps, beatmap_values)
                        cnx.commit()
            
                        if blacklisted:
                            cursor.execute(
                                "UPDATE beatmaps SET Blacklisted = %s, BlacklistReason = %s WHERE BeatmapID = %s",
                                (blacklisted, blacklist_reason, beatmap.id)
                            )
                            cnx.commit()

                        cursor.execute("""
                            INSERT IGNORE INTO beatmap_creators (BeatmapID, CreatorID)
                            VALUES (%s, %s)
                        """, (beatmap.id, beatmap.user_id))
                        cnx.commit()

                        cursor.execute("""
                            REPLACE INTO recent_maps (SetID, Mode, Timestamp, LastUpdated)
                            VALUES (%s, %s, %s, NOW())
                        """, (beatmapset.id, beatmap.mode_int, datetime.datetime.now()))
                        cnx.commit()
                    except Exception as e:
                        print(f"Error inserting beatmap {beatmap.id}: {e}")
                
                latest_date = display_date   
            except Exception as e:
                print(f"Error processing beatmapset {beatmapset.id}: {e}")

    cursor.close()
    cnx.close()

def update_ratings() -> None:
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return
    
    confidence = 20
    m = 3.0

    cursor.execute("SELECT DISTINCT BeatmapID FROM ratings")
    beatmap_ids = cursor.fetchall()

    for index, beatmap_id_row in enumerate(beatmap_ids):
        beatmap_id = beatmap_id_row[0]
        
        cursor.execute("SELECT Mode FROM beatmaps WHERE BeatmapID = %s", (beatmap_id,))
        mode_result = cursor.fetchone()
        if not mode_result:
            continue
        mode = mode_result[0]

        cursor.execute("""
            SELECT 
                SUM(r.Score * u.Weight) / SUM(u.Weight) AS weighted_avg, 
                SUM(u.Weight) AS weight_sum, 
                COUNT(*) AS rating_count 
            FROM ratings r 
            INNER JOIN users u ON r.UserID = u.UserID 
            WHERE r.BeatmapID = %s
        """, (beatmap_id,))
        
        result = cursor.fetchone()
        avg = result[0]
        weighted_count = result[1]
        count = result[2]

        if weighted_count is None or weighted_count < 1.5:
            bayesian = None
        else:
            bayesian = ((weighted_count * avg) + (m * confidence)) / (weighted_count + confidence)
            if weighted_count < 20 and mode == 0:
                interp_factor = pow((max(1, min(weighted_count, 20)) - 1) / 19.0, 3)
                bayesian = 2.9 + interp_factor * (bayesian - 2.9)

        cursor.execute("""
            UPDATE beatmaps 
            SET WeightedAvg = %s, RatingCount = %s 
            WHERE BeatmapID = %s
        """, (avg, count, beatmap_id))
        cnx.commit()

        if count >= 5 and bayesian is not None:
            cursor.execute("SELECT SetID FROM beatmaps WHERE BeatmapID = %s", (beatmap_id,))
            set_id_result = cursor.fetchone()
            if set_id_result:
                set_id = set_id_result[0]
                
                cursor.execute("""
                    REPLACE INTO top_maps (BeatmapID, SetID, Mode, WeightedAvg, RatingCount, LastUpdated)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (beatmap_id, set_id, mode, bayesian, count))
                cnx.commit()

                cursor.execute("SELECT YEAR(DateRanked) FROM beatmapsets WHERE SetID = %s", (set_id,))
                year_result = cursor.fetchone()
                if year_result and year_result[0]:
                    year = year_result[0]
                    cursor.execute("""
                        REPLACE INTO top_maps_yearly (BeatmapID, SetID, Mode, Year, WeightedAvg, RatingCount, LastUpdated)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (beatmap_id, set_id, mode, year, bayesian, count))
                    cnx.commit()

    cursor.execute("""
        UPDATE beatmaps
        SET Rating = CASE
            WHEN SR < 1.5 THEN 'Easy'
            WHEN SR < 2.25 THEN 'Normal'
            WHEN SR < 3.75 THEN 'Hard'
            WHEN SR < 5.25 THEN 'Insane'
            WHEN SR < 6.75 THEN 'Expert'
            ELSE 'Expert+'
        END
        WHERE Rating IS NULL OR Rating = ''
    """)
    cnx.commit()
    
    cursor.execute("""
        SET @rank := 0;
        UPDATE beatmaps b
        JOIN (
            SELECT BeatmapID, (@rank := @rank + 1) as new_rank
            FROM beatmaps
            WHERE RatingCount >= 5
            ORDER BY WeightedAvg DESC, RatingCount DESC
        ) r ON b.BeatmapID = r.BeatmapID
        SET b.ChartRank = r.new_rank
    """)
    cnx.commit()
    
    current_year = datetime.datetime.now().year
    cursor.execute("""
        SET @year_rank := 0;
        UPDATE beatmaps b
        JOIN beatmapsets bs ON b.SetID = bs.SetID
        JOIN (
            SELECT b.BeatmapID, (@year_rank := @year_rank + 1) as new_rank
            FROM beatmaps b
            JOIN beatmapsets bs ON b.SetID = bs.SetID
            WHERE b.RatingCount >= 5 AND YEAR(bs.DateRanked) = %s
            ORDER BY b.WeightedAvg DESC, b.RatingCount DESC
        ) r ON b.BeatmapID = r.BeatmapID
        SET b.ChartYearRank = r.new_rank
        WHERE YEAR(bs.DateRanked) = %s
    """, (current_year, current_year))
    cnx.commit()
    
    update_home_caches(cursor, cnx)
    cursor.close()
    cnx.close()

def update_home_caches(cursor, cnx):
    cursor.execute("TRUNCATE TABLE cache_home_best_map")
    
    for mode in range(4):  # 0=osu, 1=taiko, 2=fruits, 3=mania
        cursor.execute("""
            INSERT INTO cache_home_best_map (BeatmapID, Mode)
            SELECT BeatmapID, Mode
            FROM top_maps 
            WHERE Mode = %s
            ORDER BY WeightedAvg DESC, RatingCount DESC
            LIMIT 1
        """, (mode,))
    cnx.commit()
    
    cursor.execute("TRUNCATE TABLE cache_home_recent_maps")
    
    for mode in range(4):
        cursor.execute("""
            INSERT INTO cache_home_recent_maps (SetID, Timestamp, Metadata, CreatorID, Mode)
            SELECT bs.SetID, rm.Timestamp, CONCAT(bs.Artist, ' - ', bs.Title) as Metadata, 
                   bs.CreatorID, rm.Mode
            FROM recent_maps rm
            JOIN beatmapsets bs ON rm.SetID = bs.SetID
            WHERE rm.Mode = %s
            ORDER BY rm.Timestamp DESC
            LIMIT 5
        """, (mode,))
    cnx.commit()

if __name__ == "__main__":
    update_beatmaps()
    update_ratings()