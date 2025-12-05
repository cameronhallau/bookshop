# Kobink (Python Version)

Automatically sync local books to your Kobo by pretending to be the Kobo Store. This is a lightweight Python port of the original Rust project, designed for Raspberry Pi Zero.

### Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Kobo**:
    On the Kobo, open `/.kobo/Kobo/Kobo eReader.conf` and change `api_endpoint` to your local machine where Kobink runs (e.g., `http://192.168.0.1:8000`).
    
    *Note: You may also need to redirect `storeapi.kobo.com` to your server's IP via DNS or hosts file if changing the config isn't enough.*

3.  **Run Server**:
    ```bash
    # Set the host URL to your Pi's IP address
    export HOST_URL="http://192.168.0.1:8000"
    export LIBRARY_PATH="/path/to/epubs"
    python server.py
    ```

4.  **Sync**:
    Press "Sync" on the Kobo — all EPUB files in `LIBRARY_PATH` should now automatically be fetched to the device.