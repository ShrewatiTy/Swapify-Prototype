from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
NOTICES_FILE = os.path.join(os.path.dirname(__file__), 'notices.json')

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)


def resolve_index_file():
    candidates = ['index.html.html', 'index.html', 'Swapify1.html', 'Swapify.HTML', 'SHRESHTH.HTML']
    for name in candidates:
        if os.path.exists(os.path.join(BASE_DIR, name)):
            return name
    return 'index.html.html'

def read_notices():
    try:
        with open(NOTICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def write_notices(list_):
    with open(NOTICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(list_, f, indent=2)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Swapify backend'})

@app.route('/api/notices', methods=['GET'])
def get_notices():
    return jsonify(read_notices())

@app.route('/api/notices', methods=['POST'])
def post_notice():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Invalid notice format'}), 400
    notices = read_notices()
    if isinstance(data, list):
        for n in data:
            n['createdAt'] = n.get('createdAt') or __import__('datetime').datetime.utcnow().isoformat()
            notices.append(n)
    else:
        data['createdAt'] = data.get('createdAt') or __import__('datetime').datetime.utcnow().isoformat()
        notices.append(data)
    write_notices(notices)
    return jsonify({'ok': True, 'notice': data})

@app.route('/api/notices', methods=['DELETE'])
def delete_notices():
    write_notices([])
    return jsonify({'ok': True})

# Serve site files from parent HTML folder
@app.route('/<path:path>', methods=['GET'])
def static_proxy(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(BASE_DIR, resolve_index_file())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 80))
    site_url = 'http://swapify.com' if port == 80 else f'http://swapify.com:{port}'
    print(f"Swapify Flask API serving {BASE_DIR} on {site_url}")
    app.run(host='0.0.0.0', port=port)
