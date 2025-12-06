
### Enabling HTTPS

Kobo devices often require HTTPS connections. Since we are running on a local network, we can use a self-signed certificate.

1.  **Generate a Certificate on your Raspberry Pi**:
    Run this command in the `kosync` directory on your Pi to generate `cert.pem` and `key.pem`.
    ```bash
    openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/CN=kobo-server"
    ```
    *Note: If `openssl` is not installed, install it with `sudo apt install openssl`.*

2.  **Update Kobo Configuration**:
    Update your Kobo's `api_endpoint` in `/.kobo/Kobo/Kobo eReader.conf` to use `https`:
    ```ini
    api_endpoint=https://192.168.X.XXX:8000/kobo/test
    ```

3.  **Run the Server**:
    Simply run the server as before. It will automatically detect the `.pem` files and switch to HTTPS mode.
    ```bash
    python server.py
    ```

**Important Note on Certificate Warnings**:
The Kobo might reject the self-signed certificate because it doesn't trust the issuer. If sync fails immediately with SSL errors:
1. You may need to ignore SSL errors (which is hard on Kobo without patching).
2. Or reverting to HTTP might be the only "easy" path without patching the device's root CA bundle.
