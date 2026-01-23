import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# ---------------------------------------------------------
# Load .env explicitly BEFORE anything else uses env vars
# ---------------------------------------------------------
load_dotenv(dotenv_path="/home/tamor/tamor-core/api/.env")

# Read environment variables once
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

# ---------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["OPENAI_API_KEY"] = OPENAI_API_KEY       
app.config["OPENAI_MODEL"] = OPENAI_MODEL           

# Upload folder setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_ROOT

# CORS support
CORS(app, supports_credentials=True)

# ---------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------
from routes.stremio_christmas import stremio_bp
from routes.memory_api import memory_bp
from routes.chat_api import chat_bp
from routes.auth_api import auth_bp
from routes.conversations_api import conversations_bp
from routes.projects_api import projects_bp
from routes.search_api import search_bp
from routes.files_api import files_bp
from routes.tasks_api import tasks_bp
from routes.status_api import status_bp
from routes.messages_api import messages_bp
from routes.plugins_api import plugins_bp



app.register_blueprint(stremio_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(conversations_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(search_bp)
app.register_blueprint(files_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(status_bp, url_prefix="/api")
app.register_blueprint(messages_bp)
app.register_blueprint(plugins_bp)




# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055)

