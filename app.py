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
from flask_cors import CORS

load_dotenv()



app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key-123')

CORS(app, supports_credentials=True, origins=["https://cardiosee.onrender.com", "http://localhost:5000"])


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
    import traceback
    from flask import request
    
    # Get request info
    token = request.headers.get('Authorization', '')
    origin = request.headers.get('Origin', '')
    host = request.headers.get('Host', '')
    
    print(f"\n=== AUTH ATTEMPT ===")
    print(f"Origin: {origin}")
    print(f"Host: {host}")
    print(f"Token provided: {'YES' if token else 'NO'}")
    
    if token and token.startswith('Bearer '):
        token = token[7:]
        print(f"Token length: {len(token)} chars")
        print(f"Token starts with: {token[:50]}...")
    
    if not token or not token.startswith('Bearer '):
        print("ERROR: No Bearer token in header")
        return jsonify({"error": "No Bearer token provided"}), 401
    
    token = token[7:]
    
    try:
        # Try without revocation check first
        decoded_token = auth.verify_id_token(token, check_revoked=False, clock_skew_seconds=300)
        print(f"✅ Token VERIFIED")
        print(f"   User UID: {decoded_token.get('uid')}")
        print(f"   User email: {decoded_token.get('email')}")
        print(f"   Audience (project): {decoded_token.get('aud')}")
        print(f"   Issuer: {decoded_token.get('iss')}")
        print(f"   Expires: {decoded_token.get('exp')}")
        
        # Now check if revoked
        try:
            auth.check_revoked(decoded_token)
            print("✅ Token NOT revoked")
            
            # Store in session
            session['user'] = decoded_token
            
            return jsonify({
                "success": True,
                "user": {
                    "uid": decoded_token.get('uid'),
                    "email": decoded_token.get('email')
                }
            })
            
        except auth.RevokedIdTokenError as e:
            print(f"❌ Token REVOKED: {e}")
            return jsonify({"error": "Token revoked. Please log in again."}), 401
            
    except auth.InvalidIdTokenError as e:
        print(f"❌ INVALID TOKEN ERROR: {e}")
        print(f"   Error type: {type(e).__name__}")
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401
    except auth.ExpiredIdTokenError as e:
        print(f"❌ EXPIRED TOKEN: {e}")
        return jsonify({"error": "Token expired. Please refresh."}), 401
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        print("Traceback:")
        traceback.print_exc()
        return jsonify({"error": f"Authentication failed: {type(e).__name__}: {str(e)}"}), 401














@app.route('/test-firebase')
def test_firebase():
    import os, json, firebase_admin
    from firebase_admin import credentials
    
    result = {
        "firebase_initialized": len(firebase_admin._apps) > 0,
        "current_directory": os.getcwd(),
        "files": os.listdir('.'),
        "firebase_auth_exists": os.path.exists('firebase-auth.json'),
        "service_account_info": None
    }
    
    if result['firebase_auth_exists']:
        try:
            with open('firebase-auth.json', 'r') as f:
                data = json.load(f)
                result['service_account_info'] = {
                    "project_id": data.get('project_id'),
                    "client_email": data.get('client_email'),
                    "private_key_exists": bool(data.get('private_key'))
                }
        except Exception as e:
            result['file_error'] = str(e)
    
    return jsonify(result)

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
    response = make_response(redirect(url_for('login')))
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


@app.route("/settings")
@auth_required
def settings():
    return render_template("settings.html")




@app.route("/library")
@auth_required
def library():
    return render_template("library.html")



if __name__ == '__main__':
    #app.run(debug=True)
    app.run()