from flask import Flask, request, jsonify, send_file, Response
import os
import json
from library import Library

app = Flask(__name__)

# Configuration
LIBRARY_PATH = os.environ.get("LIBRARY_PATH", "/media/kobink_test")
HOST_URL = os.environ.get("HOST_URL", "http://192.168.1.100:8000") # Change this to your Pi's IP

# Initialize Library
library = Library(LIBRARY_PATH)
library.scan()

# Initialization Data (Embedded for simplicity)
INITIALIZATION_DATA = {
    "Resources": {
        "access_token_endpoint": "https://storeapi.kobo.com/v1/auth/device",
        "image_host": "https://kbiages1-a-akamaihd.net",
        "api_endpoint": "https://storeapi.kobo.com/v1",
        "library_sync": f"{HOST_URL}/kobo/test/v1/library/sync",
        "device_auth": f"{HOST_URL}/kobo/test/v1/auth/device",
        # Add other necessary endpoints as stubs or real URLs if needed
        # For barebones sync, we mostly need auth and sync
    }
}
# Using the full initialization JSON from the original project is safer to avoid client errors
# I will load it from the existing file if possible, or use a simplified version.
# For now, let's use a minimal set and see if the Kobo accepts it. 
# Actually, let's just use the one we read earlier to be safe.

try:
    with open("initialization.json", "r") as f:
        FULL_INIT_DATA = json.load(f)
        # Override critical endpoints
        FULL_INIT_DATA["Resources"]["device_auth"] = f"{HOST_URL}/kobo/test/v1/auth/device"
        FULL_INIT_DATA["Resources"]["library_sync"] = f"{HOST_URL}/kobo/test/v1/library/sync"
        # We might need to override others if the Kobo tries to contact them and fails
except FileNotFoundError:
    print("Warning: initialization.json not found. Using minimal fallback.")
    FULL_INIT_DATA = INITIALIZATION_DATA


@app.route('/kobo/<key>/v1/initialization', methods=['GET'])
@app.route('/kobo/<key>/v1/v1/initialization', methods=['GET'])
def initialization(key):
    # Dynamically grab the host from the request
    # request.host_url usually returns "http://1.2.3.4:8000/" (with trailing slash)
    host = request.host_url.rstrip('/')
    
    # Ensure initialization.json is loaded
    try:
        with open("initialization.json", "r") as f:
            full_init_data = json.load(f)
            # Override critical endpoints with dynamic host
            full_init_data["Resources"]["device_auth"] = f"{host}/kobo/{key}/v1/auth/device"
            full_init_data["Resources"]["library_sync"] = f"{host}/kobo/{key}/v1/library/sync"
            return jsonify(full_init_data)
    except Exception as e:
        print(f"Error loading initialization.json: {e}")
        return jsonify({"Error": "Failed to load initialization data"}), 500

@app.route('/kobo/<key>/v1/auth/device', methods=['POST'])
@app.route('/kobo/<key>/v1/v1/auth/device', methods=['POST'])
def auth_device(key):
    # Stub authentication
    response = {
        "AccessToken": "SAMPLE_ACCESS_TOKEN",
        "RefreshToken": "SAMPLE_REFRESH_TOKEN",
        "TokenType": "Bearer",
        "TrackingId": "SAMPLE_TRACKING_ID",
        "UserKey": "SAMPLE_USER_KEY"
    }
    resp = jsonify(response)
    resp.headers['x-kobo-synctoken'] = 'SAMPLE_SYNCTOKEN'
    return resp

@app.route('/kobo/<key>/v1/library/sync', methods=['GET'])
@app.route('/kobo/<key>/v1/v1/library/sync', methods=['GET'])
def library_sync(key):
    # Rescan library on sync request (optional, but good for "dynamic" updates)
    # library.scan() 
    
    # Dynamically grab the host from the request
    host = request.host_url.rstrip('/')
    
    events = library.get_sync_events(host)
    
    print(f"Sending {len(events)} books to Kobo")
    
    # The Kobo expects a list of sync events
    # We also need to handle pagination if we have many books, but for barebones we'll send all
    
    # Add required sync headers
    resp = jsonify(events)
    # resp.headers['x-kobo-sync'] = 'continue' # Removed to stop endless loop
    resp.headers['x-kobo-synctoken'] = 'sync-token-' + str(len(events))
    return resp

@app.route('/download/<book_id>/<book_format>/<filename>', methods=['GET'])
def download_book(book_id, book_format, filename):
    # We can validate book_id or format if we want, but for now rely on filename
    if book_format != "EPUB":
        # Rust reference only handles EPUB explicit check (implied by file extension mostly)
        pass 

    book_path = library.get_book_path(filename)
    if book_path and os.path.exists(book_path):
        return send_file(book_path, as_attachment=True)
    else:
        return "File not found", 404

# Catch-all for other Kobo requests to prevent errors
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(path):
    print(f"Unhandled request: {path}")
    return jsonify({})

if __name__ == '__main__':
    # Run on 0.0.0.0 to be accessible from the network
    app.run(host='0.0.0.0', port=8000)
