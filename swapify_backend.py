from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

# --- APP SETUP & CORS ---
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enables CORS so GitHub Pages can make requests to this backend

DB_PATH = Path('swapify_db.json')
ADMIN_PASSWORD = '12367'
EXPENSIVE_ITEMS = [
    'car', 'house', 'yacht', 'jet', 'plane', 'boat', 'diamonds', 'diamond',
    'gold', 'jewellery', 'jewelry', 'submarine', 'bunker', 'island', 'castle',
    'masterpiece', 'art'
]

DEFAULT_DB = {
    'items': [],
    'accounts': []
}


# --- DATABASE HELPERS ---
def load_db() -> Dict[str, Any]:
    if not DB_PATH.exists():
        save_db(DEFAULT_DB.copy())
    with DB_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def save_db(data: Dict[str, Any]) -> None:
    with DB_PATH.open('w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)


def normalize_username(username: str) -> str:
    return str(username or '').strip().lower()


def is_expensive_text(text: str) -> bool:
    content = str(text or '').lower()
    return any(item in content for item in EXPENSIVE_ITEMS)


def is_admin_password(password: str) -> bool:
    return str(password or '').strip() == ADMIN_PASSWORD


def find_account(accounts: list[dict], username: str) -> dict | None:
    normalized = normalize_username(username)
    return next((acc for acc in accounts if normalize_username(acc.get('username')) == normalized), None)


# --- HEALTH & STATIC ROUTES ---
@app.route('/')
@app.route('/index.html')
def serve_index() -> Any:
    if Path('index.html').exists():
        return send_from_directory('.', 'index.html')
    return "Swapify backend is running smoothly!"


@app.route('/<path:path>')
def serve_file(path: str) -> Any:
    if Path(path).exists():
        return send_from_directory('.', path)
    if Path('index.html').exists():
        return send_from_directory('.', 'index.html')
    return "Swapify backend is running smoothly!"


# --- ITEM ENDPOINTS ---
@app.route('/api/items', methods=['GET'])
def api_get_items() -> Any:
    db = load_db()
    return jsonify(db['items'])


@app.route('/api/items', methods=['POST'])
def api_new_item() -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    required = ['name', 'category', 'condition', 'exchange', 'description']
    if any(not payload.get(field) for field in required):
        return abort(400, 'Missing required item fields.')

    if not payload.get('premiumOwner') and is_expensive_text(' '.join([payload.get('name', ''), payload.get('exchange', ''), payload.get('description', '')])):
        return abort(403, 'Expensive listings require Premium membership.')

    item = {
        'id': payload.get('id') or str(uuid4()),
        'name': payload['name'],
        'category': payload['category'],
        'condition': payload['condition'],
        'exchange': payload['exchange'],
        'description': payload['description'],
        'image': payload.get('image', ''),
        'documentName': payload.get('documentName', ''),
        'premiumOwner': bool(payload.get('premiumOwner', False)),
        'ratingSum': 0,
        'ratingCount': 0,
        'reviews': [],
        'interestedChats': [],
        'postedBy': payload.get('postedBy', 'Guest'),
        'postedByAdmin': bool(payload.get('postedByAdmin', False))
    }

    db['items'].insert(0, item)
    save_db(db)
    return jsonify(item), 201


@app.route('/api/items/<listing_id>/interest', methods=['POST'])
def api_add_interest(listing_id: str) -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    message = str(payload.get('message') or '').strip()
    from_user = str(payload.get('from') or payload.get('fromUser') or 'Guest').strip() or 'Guest'

    if not listing_id or not message:
        return abort(400, 'Missing interest message fields.')

    item = next((item for item in db['items'] if item.get('id') == listing_id), None)
    if not item:
        return abort(404, 'Listing not found.')

    item.setdefault('interestedChats', []).append({
        'from': from_user,
        'message': message,
        'createdAt': datetime.utcnow().isoformat() + 'Z'
    })
    save_db(db)
    return jsonify(item)


# --- ACCOUNT & AUTH ENDPOINTS ---
@app.route('/api/accounts', methods=['GET'])
def api_get_accounts() -> Any:
    db = load_db()
    return jsonify(db['accounts'])


@app.route('/api/accounts', methods=['POST'])
def api_create_account() -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username') or '').strip()
    email = str(payload.get('email') or '').strip()
    phone = str(payload.get('phone') or '').strip()
    password = str(payload.get('password') or '')

    if not username or not email or not phone or not password:
        return abort(400, 'Missing required registration fields.')

    if find_account(db['accounts'], username):
        return abort(409, 'Username already exists.')

    account = {
        'username': username,
        'email': email,
        'phone': phone,
        'password': password,
        'premium': bool(payload.get('premium') or is_admin_password(password)),
        'admin': bool(payload.get('admin') or is_admin_password(password))
    }
    db['accounts'].append(account)
    save_db(db)
    return jsonify(account), 201


@app.route('/api/login', methods=['POST'])
def api_login() -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')

    if not username or not password:
        return abort(400, 'Missing login credentials.')

    account = find_account(db['accounts'], username)
    if not account or account.get('password') != password:
        return abort(401, 'Invalid username or password.')

    account['admin'] = account.get('admin', False) or is_admin_password(password)
    account['premium'] = account.get('premium', False) or account['admin']
    save_db(db)
    return jsonify(account)


@app.route('/api/accounts/<username>', methods=['PUT'])
def api_update_account(username: str) -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    existing = find_account(db['accounts'], username)
    if not existing:
        return abort(404, 'Account not found.')

    if payload.get('username'):
        normalized_new = normalize_username(payload['username'])
        duplicated = find_account(db['accounts'], payload['username'])
        if duplicated and normalize_username(duplicated['username']) != normalize_username(existing['username']):
            return abort(409, 'Username already taken.')
        existing['username'] = payload['username'].strip()
        for item in db['items']:
            if normalize_username(item.get('postedBy')) == normalize_username(username):
                item['postedBy'] = existing['username']

    if payload.get('premium') is not None:
        existing['premium'] = bool(payload['premium']) or existing.get('admin', False)
    if payload.get('admin') is not None:
        existing['admin'] = bool(payload['admin'])
        if existing['admin']:
            existing['premium'] = True

    save_db(db)
    return jsonify(existing)


@app.route('/api/accounts/<username>', methods=['DELETE'])
def api_delete_account(username: str) -> Any:
    db = load_db()
    normalized = normalize_username(username)
    before = len(db['accounts'])
    db['accounts'] = [acc for acc in db['accounts'] if normalize_username(acc.get('username')) != normalized]
    if len(db['accounts']) == before:
        return abort(404, 'Account not found.')
    save_db(db)
    return jsonify({'deleted': True})


@app.route('/api/premium', methods=['POST'])
def api_premium_toggle() -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username') or '').strip()
    premium = bool(payload.get('premium', False))
    account = find_account(db['accounts'], username)
    if not account:
        return abort(404, 'Account not found.')
    account['premium'] = premium or account.get('admin', False)
    save_db(db)
    return jsonify(account)


@app.route('/api/review', methods=['POST'])
def api_add_review() -> Any:
    db = load_db()
    payload = request.get_json(silent=True) or {}
    listing_id = str(payload.get('listingId') or '').strip()
    rating = int(payload.get('rating') or 0)
    review_text = str(payload.get('reviewText') or '').strip()
    if not listing_id or not rating or not review_text:
        return abort(400, 'Missing review fields.')

    item = next((item for item in db['items'] if item.get('id') == listing_id), None)
    if not item:
        return abort(404, 'Listing not found.')

    item['ratingSum'] = item.get('ratingSum', 0) + rating
    item['ratingCount'] = item.get('ratingCount', 0) + 1
    item.setdefault('reviews', []).insert(0, {
        'rating': rating,
        'text': review_text
    })
    save_db(db)
    return jsonify(item)


# --- SERVER RUNNER ---
if __name__ == '__main__':
    # Dynamically grabs Render's PORT environment variable, or defaults to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)