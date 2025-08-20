import os

# Environment configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyB2RVyN1kHR9iI_FJldNJNEhDLTERjU59k")
FLASK_ENV = os.getenv("FLASK_ENV", "development")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "reimburse-flow-secret-key-2025")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "16777216"))

# Firebase Web Config (for frontend) - Using optimal-analogy-394213 project
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "AIzaSyDv1Z_ww71gEHfuZ2Z636bhAtKz-Eg7OcY")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", "optimal-analogy-394213.firebaseapp.com")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "optimal-analogy-394213")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "optimal-analogy-394213.firebasestorage.app")
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID", "234251111713")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID", "1:234251111713:web:8ee95f76e1a2c78d140260")

# Firebase Admin SDK Config
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")