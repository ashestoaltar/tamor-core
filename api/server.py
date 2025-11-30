from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes.stremio_christmas import stremio_bp
from routes.memory_api import memory_bp
from routes.chat_api import chat_bp
from routes.auth_api import auth_bp
from routes.conversations_api import conversations_bp
from routes.projects_api import projects_bp


load_dotenv()

app = Flask(__name__)

# Needed for session cookies
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

# CORS must support credentials for login sessions
CORS(app, supports_credentials=True)

# Register blueprints
app.register_blueprint(stremio_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(conversations_bp)
app.register_blueprint(projects_bp)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055)
