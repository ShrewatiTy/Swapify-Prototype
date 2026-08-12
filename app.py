import os
import secrets
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Google API imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# Database config (change to your DB URI or leave as sqlite for prototype)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///swapify.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# verification config
CODE_TTL_MINUTES = int(os.environ.get("CODE_TTL_MINUTES", 10))
MAX_VERIFICATION_ATTEMPTS = int(os.environ.get("MAX_VERIFICATION_ATTEMPTS", 5))

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    verification_code_hash = db.Column(db.String(200), nullable=True)
    code_sent_at = db.Column(db.DateTime, nullable=True)

# Create DB tables if not exist (for prototype)
with app.app_context():
    db.create_all()

# --- Utilities ---
def generate_6_digit_code():
    return f"{secrets.randbelow(900000) + 100000}"  # ensures 6 digits (100000-999999)

# Gmail API helpers
def _get_gmail_service():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError("Missing Gmail API credentials in environment")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    # Refresh to populate creds.token
    creds.refresh(Request())
    service = build('gmail', 'v1', credentials=creds)
    return service

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")


def send_verification_email(to_email, code):
    """
    Send the verification code using Gmail API. Requires GOOGLE_* env vars and SENDER_EMAIL.
    """
    if not SENDER_EMAIL:
        raise RuntimeError("SENDER_EMAIL env missing")

    subject = "Swapify verification code"
    body = (
        f"Hello,\n\nYour Swapify verification code is: {code}\n"
        f"This code will expire in {CODE_TTL_MINUTES} minutes.\n\nIf you did not sign up, ignore this email.\n"
    )
    mime_msg = MIMEText(body)
    mime_msg['to'] = to_email
    mime_msg['from'] = SENDER_EMAIL
    mime_msg['subject'] = subject

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

    service = _get_gmail_service()
    message = {"raw": raw}
    sent = service.users().messages().send(userId="me", body=message).execute()
    return sent


def ai_check_code_format_and_rate(code, attempts):
    """
    Lightweight 'AI' heuristics:
    - must be 6 digits
    - not allow too many attempts (rate limiting)
    - flag trivial weak codes
    """
    if attempts is None:
        attempts = 0
    # Reject invalid format quickly
    if not code.isdigit() or len(code) != 6:
        return False, "Code must be exactly 6 digits."
    if attempts >= MAX_VERIFICATION_ATTEMPTS:
        return False, "Too many attempts. Please contact support."
    weak_codes = {"123456", "111111", "000000", "654321", "222222"}
    if code in weak_codes:
        return True, "Suspicious code pattern detected but proceeding with verification."
    return True, "OK"


def is_gmail_address(email):
    email = (email or "").lower().strip()
    return email.endswith("@gmail.com") or email.endswith("@googlemail.com")

# --- Routes ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    # If you have an existing signup page, integrate the sending into your existing flow.
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")  # hash this if storing; example below
        if not email:
            return "Email is required", 400
        existing = User.query.filter_by(email=email).first()
        if existing:
            return "Email already registered", 400

        # create user but keep email_verified False
        user = User(
            email=email,
            password_hash=generate_password_hash(password) if password else None,
            email_verified=False
        )

        # generate, hash and store the 6-digit code
        code = generate_6_digit_code()
        user.verification_code_hash = generate_password_hash(code)
        user.code_sent_at = datetime.utcnow()
        db.session.add(user)
        db.session.commit()

        # send code (only once at signup) — use Gmail API to send from SENDER_EMAIL
        try:
            send_verification_email(user.email, code)
        except Exception as e:
            # Roll back or warn — keep user created but inform of send failure
            app.logger.exception("Failed to send verification email")
            return f"User created but failed to send verification email: {e}", 500

        # keep user in session for verification page
        session['user_id'] = user.id
        session['verify_attempts'] = 0

        return redirect(url_for("verify_prompt"))

    # GET => show a simple signup form (or integrate into your existing HTML)
    return render_template("signup.html")


@app.route("/verify", methods=["GET"])
def verify_prompt():
    # Page shown after signup telling user to check Gmail and enter code
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("signup"))
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404
    if user.email_verified:
        return "Your email is already verified."
    return render_template("verify.html", email=user.email)


@app.route("/verify-code", methods=["POST"])
def verify_code():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "msg": "Session expired. Please log in again."}), 401
    user = User.query.get(user_id)
    if not user:
        return jsonify({"ok": False, "msg": "User not found."}), 404
    if user.email_verified:
        return jsonify({"ok": True, "msg": "Already verified."})

    payload = request.json or request.form
    code = (payload.get("code") or "").strip()
    # AI-like check (format + rate limit)
    attempts = session.get("verify_attempts", 0)
    ok, message = ai_check_code_format_and_rate(code, attempts)
    if not ok:
        return jsonify({"ok": False, "msg": message}), 400

    # check TTL
    if not user.code_sent_at or datetime.utcnow() > user.code_sent_at + timedelta(minutes=CODE_TTL_MINUTES):
        return jsonify({"ok": False, "msg": "Code expired. Contact support or re-signup."}), 400

    # check hashed code
    if check_password_hash(user.verification_code_hash or "", code):
        # success -> mark verified and clear the stored code
        user.email_verified = True
        user.verification_code_hash = None
        user.code_sent_at = None
        db.session.commit()
        return jsonify({"ok": True, "msg": "Email verified. Thank you!"})
    else:
        # increment attempts
        session['verify_attempts'] = attempts + 1
        attempts_left = MAX_VERIFICATION_ATTEMPTS - session['verify_attempts']
        return jsonify({"ok": False, "msg": f"Incorrect code. Attempts left: {attempts_left}"}), 400


if __name__ == "__main__":
    app.run(debug=True)
