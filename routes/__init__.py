from flask import Flask

def register_blueprints(app: Flask) -> None:
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.beatmaps import beatmaps_bp
    from routes.users import users_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(beatmaps_bp)
    app.register_blueprint(users_bp)