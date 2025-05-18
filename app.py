from flask import Flask
from ossapi import Ossapi

from config import (
    SECRET_KEY, 
    PERMANENT_SESSION_LIFETIME, 
    DB_CONFIG, 
    OSU_CLIENT_ID, 
    OSU_CLIENT_SECRET, 
    DEBUG
)

from util.database import init_db_pool
from routes import register_blueprints

app = Flask(__name__)
API = Ossapi(OSU_CLIENT_ID, OSU_CLIENT_SECRET)

app.secret_key = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
    
init_db_pool(DB_CONFIG)
register_blueprints(app)

if __name__ == '__main__':
    app.run(debug=DEBUG)