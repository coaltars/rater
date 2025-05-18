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

    cursor.execute("SELECT MAX(DateRanked) FROM beatmaps;")
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
    
    sql_beatmaps = """
        REPLACE INTO beatmaps (
            BeatmapID, SetID, CreatorID, SetCreatorID, 
            DifficultyName, Mode, Status, SR, 
            Artist, Title, DateRanked, Timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    print(f"Fetching beatmaps ranked after {latest_date}")
    
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
                    "INSERT IGNORE INTO mappernames (UserID, Username) VALUES (%s, %s)",
                    (beatmapset.user_id, beatmapset.creator)
                )
                cnx.commit()
                
                for beatmap in beatmapset.beatmaps:
                    cursor.execute("SELECT * FROM blacklist WHERE UserID = %s;", (beatmap.user_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        blacklisted = 1
                        blacklist_reason = "Mapper has requested blacklist."
                    else:
                        blacklisted = 0
                        blacklist_reason = None

                    beatmap_values = (
                        beatmap.id,
                        beatmapset.id,
                        beatmap.user_id,
                        beatmapset.user_id,
                        beatmap.version,
                        beatmap.mode_int,
                        beatmap.status.value,
                        beatmap.difficulty_rating,
                        beatmapset.artist,
                        beatmapset.title,
                        display_date,
                        datetime.datetime.now()
                    )
                    
                    try:
                        cursor.execute(sql_beatmaps, beatmap_values)
                        cnx.commit()
                        print(f"Inserted beatmap {beatmap.id}")
                        
                        if blacklisted:
                            cursor.execute(
                                "UPDATE beatmaps SET Blacklisted = %s, BlacklistReason = %s WHERE BeatmapID = %s",
                                (blacklisted, blacklist_reason, beatmap.id)
                            )
                            cnx.commit()
                        
                    except Exception as e:
                        print(f"Error inserting beatmap {beatmap.id}: {e}")

                latest_date = display_date
                        
            except Exception as e:
                print(f"Error processing beatmapset {beatmapset.id}: {e}")

    cursor.close()
    cnx.close()
    print("Beatmap update completed")

def update_ratings() -> None:
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return
    
    print("Updating rating calculations...")

    cursor.execute("""
        UPDATE beatmaps b
        SET RatingCount = (SELECT COUNT(*) FROM ratings r WHERE r.BeatmapID = b.BeatmapID),
            WeightedAvg = (SELECT AVG(r.Score) FROM ratings r WHERE r.BeatmapID = b.BeatmapID)
        WHERE EXISTS (SELECT 1 FROM ratings r WHERE r.BeatmapID = b.BeatmapID)
    """)
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
        SET @rank = 0;
        UPDATE beatmaps
        SET ChartRank = (@rank := @rank + 1)
        WHERE RatingCount >= 5
        ORDER BY WeightedAvg DESC, RatingCount DESC
    """)
    cnx.commit()
    
    current_year = datetime.datetime.now().year
    cursor.execute("""
        SET @rank = 0;
        UPDATE beatmaps
        SET ChartYearRank = (@rank := @rank + 1)
        WHERE RatingCount >= 5 AND YEAR(DateRanked) = %s
        ORDER BY WeightedAvg DESC, RatingCount DESC
    """, (current_year,))
    cnx.commit()
    
    cursor.close()
    cnx.close()
    print("Rating calculations completed")

if __name__ == "__main__":
    update_beatmaps()
    update_ratings()