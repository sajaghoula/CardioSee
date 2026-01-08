from flask import Flask, redirect, render_template, request, make_response, session, abort, jsonify, url_for
import secrets
from functools import wraps
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import timedelta
import os
from dotenv import load_dotenv
from data_routes import data_bp
from images_vi import image_bp
from library import lib_bp
from settings import settings_bp
from profile import profile_bp

from flask_cors import CORS
load_dotenv()



app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key-123')

CORS(app, supports_credentials=True, origins=["*" ])

# Configure session cookie settings
app.config['SESSION_COOKIE_SECURE'] = True  # Ensure cookies are sent over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Adjust session expiration as needed
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Can be 'Strict', 'Lax', or 'None'


# Firebase Admin SDK setup
if not firebase_admin._apps:

    if os.environ.get("RENDER") == "true":
        # 🔐 Production (Render) — use env vars
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.environ["FIREBASE_PROJECT_ID"],
            "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
            "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
            "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
            "client_id": os.environ["FIREBASE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ["FIREBASE_CLIENT_X509_CERT_URL"]
        })
    else:
        # 🧪 Local development — use JSON file
        cred = credentials.Certificate("firebase-auth.json")

firebase_admin.initialize_app(cred)
db = firestore.client()


# Register
app.register_blueprint(data_bp)
app.register_blueprint(image_bp)
app.register_blueprint(lib_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(profile_bp)






########################################
""" Authentication and Authorization """

# Decorator for routes that require authentication
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated
        if 'user' not in session:
            return redirect(url_for('login'))
        
        else:
            return f(*args, **kwargs)
        
    return decorated_function


@app.route('/auth', methods=['POST'])
def authorize():
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return "Unauthorized", 401

    token = token[7:]  # Strip off 'Bearer ' to get the actual token

    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True, clock_skew_seconds=60) # Validate token here
        session['user'] = decoded_token # Add user to session
        return redirect(url_for('dashboard'))
    
    except:
        return "Unauthorized", 401


#####################
""" Public Routes """

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('data_visualization'))
    else:
        return render_template('login.html')

@app.route('/signup')
def signup():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return render_template('signup.html')


@app.route('/reset-password')
def reset_password():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return render_template('forgot_password.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove the user from session
    response = make_response(redirect(url_for('home')))
    response.set_cookie('session', '', expires=0)  # Optionally clear the session cookie
    return response


##############################################
""" Private Routes (Require authorization) """

@app.route('/dashboard')
@auth_required
def dashboard():
    return render_template('dashboard.html')


@app.route("/data_visualization")
@auth_required
def data_visualization():
    return render_template("data_visualization.html")

@app.route("/statistics")
@auth_required
def statistics():
    return render_template("statistics.html")



@app.route("/images_visualization")
@auth_required
def images_visualization():
    return render_template("images_visualization.html")



@app.route("/library")
@auth_required
def library():
    return render_template("library.html")

@app.route("/settings")
@auth_required
def settings():
    return render_template("settings.html")

@app.route("/profile")
@auth_required
def profile():
    return render_template("profile.html")

if __name__ == '__main__':
    app.run(debug=True)