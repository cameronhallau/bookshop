#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path
import sys
import requests
import re
import shutil
# Features specific to Script A's functionality
from libgen_api_enhanced import LibgenSearch

# --- FILE CONFIGURATION ---
SCRIPT_DIR = Path(sys.argv[0]).resolve().parent
SOURCE_DIR = SCRIPT_DIR / "library"
LOG_FILE = SCRIPT_DIR / "book_fetcher.log"
HISTORY_FILE = SCRIPT_DIR / "processed_queries.txt"
REQUESTS_FILE = SCRIPT_DIR / "requests.txt"
MIN_QUERY_LENGTH = 3

# --- CALIBRE CONFIGURATION ---
CALIBRE_DB_PATH = "/home/bookuser/calibre_db"
CALIBRE_SERVER_PATH = '/usr/bin/calibre-server' # Server executable path
# Hardcoded server parameters for restart (from calibre_authuser_toggle.py)
PORT = '8080'
LOG_FILE_PATH = '/home/bookuser/calibre-server.log'
EBOOK_CONVERT_PATH = "ebook-convert" # Assuming it is in PATH

# --- INITIALIZATION ---
try:
    LG_CLIENT = LibgenSearch(mirror="bz")
except Exception as e:
    print(f"Error initializing LibgenSearch: {e}. Defaulting to standard mirror.")
    LG_CLIENT = LibgenSearch()


# --- HELPER FUNCTIONS (Prefixed with _) ---

def log(msg):
    """Logs message to console and file."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{ts}] {msg}\n"
    print(msg)
    try:
        if LOG_FILE.exists():
            LOG_FILE.write_text(LOG_FILE.read_text() + full_msg)
        else:
            LOG_FILE.write_text(full_msg)
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}")

def run(cmd, check=True):
    """Executes a subprocess command with logging."""
    log(f"CMD: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        if isinstance(cmd, str):
            cmd = cmd.split()

        result = subprocess.run(cmd, check=check, capture_output=True, text=True)

        if result.stderr and not check:
            log(f"Subprocess Output: {result.stderr.strip()}")
        elif result.stderr and check:
            log(f"CRITICAL ERROR (Subprocess): {result.stderr.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        log(f"CRITICAL ERROR: Command failed with exit code {e.returncode}")
        log(f"Stderr: {e.stderr.strip()}")
        raise
    except FileNotFoundError:
        log(f"CRITICAL ERROR: Command not found: {cmd[0]}")
        raise

def _kill_running_server():
    """Stops any existing calibre-server instance using the pgrep/kill method."""
    log("Attempting to stop any existing calibre-server using process ID...")
    try:
        # Find PID of running server using the executable path and library path
        pid_output = subprocess.run(
            ['pgrep', '-f', f'{CALIBRE_SERVER_PATH}.*{CALIBRE_DB_PATH}'],
            capture_output=True, text=True, check=True
        )
        pids = pid_output.stdout.strip().split('\n')

        killed_count = 0
        for pid in pids:
            if pid:
                subprocess.run(['kill', pid], check=False)
                log(f"Killed process ID: {pid}")
                killed_count += 1

        # Wait a moment to ensure termination
        if killed_count > 0:
            time.sleep(2)

        return killed_count > 0

    except subprocess.CalledProcessError:
        log("No running calibre-server instance found.")
        return False
    except Exception as e:
        log(f"Error during kill process: {e}")
        return False

def _start_server_daemon():
    """Starts the calibre server in daemon mode."""
    log("\nStarting calibre-server daemon...")

    command = [
        CALIBRE_SERVER_PATH,
        CALIBRE_DB_PATH,
        '--port', PORT,
        '--daemonize',
        '--log', LOG_FILE_PATH,
        # IMPORTANT: AUTHENTICATION FLAGS ARE OMITTED HERE.
    ]

    try:
        # Use Popen to execute the command and detach immediately
        subprocess.Popen(command, close_fds=True, cwd=Path.cwd())
        log(f"Server restart command executed successfully on port {PORT}.")
    except Exception as e:
        log(f"FATAL ERROR starting server: {e}")
        log("Check if the CALIBRE_SERVER_PATH is correct.")

# --- NEW RELIABILITY FUNCTION ---

def restart_calibre_server():
    """Kills any running server processes and then starts a new daemon."""
    log("--- Starting Server Restart ---")
    _kill_running_server()
    _start_server_daemon()
    log("Server restart initiated.")

def check_gui_running():
    """Checks if the main Calibre GUI is running."""
    try:
        subprocess.run(["pgrep", "-x", "calibre"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

# --- Kobo FIX LOGIC ---

def _process_epub_for_kobo(epub_path: Path):
    """
    Checks an EPUB for hardcoded line-height/font rules and converts it 
    to a filtered KEPUB format if issues are found.
    """
    log(f"Checking {epub_path.name} for hardcoded styles...")
    
    # 1. Check for offending CSS properties
    try:
        check_cmd = [
            "unzip", "-c", str(epub_path), "*.css"
        ]
        
        # Use subprocess.run to execute the unzip command and pipe its output to grep
        check_proc = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Now, grep the output from the unzip process
        grep_proc = subprocess.run(
            ['grep', '-iE', "line-height|font-family|font-size"],
            input=check_proc.stdout,
            capture_output=True,
            text=True,
            check=False
        )
        
        if grep_proc.stdout:
            log("Found hardcoded styles. Initiating conversion to KEPUB.")
            
            # 2. Define New Output Path (Use .kepub.epub to denote fixed KEPUB)
            new_filename = epub_path.stem + ".kepub.epub"
            new_path = epub_path.with_name(new_filename)
            
            # 3. Execute Conversion
            conversion_cmd = [
                EBOOK_CONVERT_PATH,
                str(epub_path),
                str(new_path),
                "--filter-css", "font-family,font-size,line-height",
                "--output-profile", "kobo"
            ]
            run(conversion_cmd, check=True)
            log(f"Conversion successful. New file: {new_path.name}")
            
            # 4. Replace Original with New File
            epub_path.unlink() # Delete original EPUB
            new_path.rename(epub_path) # Rename KEPUB back to original name (it is now a clean KEPUB)
            log(f"Cleaned KEPUB saved as: {epub_path.name}")
            
            # Note: Calibre will now import the KEPUB file.
            return True
        else:
            log("No hardcoded styles found. No conversion needed.")
            return False
            
    except subprocess.CalledProcessError as e:
        # This handles errors if unzip fails (e.g., file corrupt)
        log(f"WARNING: Check/Unzip failed for {epub_path.name}: {e.stderr.strip()}. Skipping fix.")
        return False
    except Exception as e:
        log(f"WARNING: Unexpected error during Kobo check/fix: {e}. Skipping fix.")
        return False


# --- REMAINING UNMODIFIED HELPER FUNCTIONS ---

def load_history():
    try:
        if HISTORY_FILE.exists():
            return set(HISTORY_FILE.read_text().splitlines())
        return set()
    except Exception as e:
        log(f"CRITICAL: Could not load history file: {e}")
        return set()

def save_history(history):
    if not history:
        return
    try:
        HISTORY_FILE.write_text("\n".join(sorted(history)))
        log(f"SUCCESS: Saved {len(history)} total unique queries to local history.")
    except Exception as e:
        log(f"CRITICAL: Could not write to history file ({HISTORY_FILE}): {e}")

def load_requests():
    try:
        if REQUESTS_FILE.exists():
            content = REQUESTS_FILE.read_text()
            return {line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')}
        log(f"CRITICAL: Requests file not found at {REQUESTS_FILE}.")
        return set()
    except Exception as e:
        log(f"CRITICAL: Error reading requests file: {e}")
        return set()

def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '-', name)
    name = re.sub(r'[- ]+', ' ', name).strip()
    return name

def is_isbn(query):
    cleaned_query = query.replace('-', '').replace(' ', '').upper()
    isbn10_pattern = r'^\d{9}[0-9X]$'
    isbn13_pattern = r'^\d{13}$'

    if re.match(isbn10_pattern, cleaned_query):
        return True
    if re.match(isbn13_pattern, cleaned_query):
        return True
    return False

def download_file(url, filename):
    local_path = SOURCE_DIR / filename
    log(f"Downloading {filename}...")

    try:
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        log("Download complete.")
        return True
    except Exception as e:
        log(f"Failed to complete download for {filename}: {e}")
        return False


# --- CORE LOGIC ---

def process_query(query):
    log(f"\n--- Processing Query: {query} ---")

    is_isbn_query = is_isbn(query)

    if is_isbn_query:
        log("Detected as ISBN. Searching using exact match.")
        search_func = LG_CLIENT.search_default_filtered
        exact_match_flag = True
    else:
        log("Detected as Title/Query. Searching using inexact match.")
        search_func = LG_CLIENT.search_title_filtered
        exact_match_flag = False

    if len(query) < MIN_QUERY_LENGTH:
        log("Query too short for search.")
        return None

    # 1. Execute Search
    book_filters = {"extension": "epub", "language": "English"}
    results = []

    try:
        results = search_func(
            query=query,
            filters=book_filters,
            exact_match=exact_match_flag
        )
    except AttributeError:
        log("Falling back to generic search_title...")
        results = LG_CLIENT.search_title(query)
    except Exception as e:
        log(f"CRITICAL: Search failed due to network/API error: {e}")
        return None

    # 2. Filter Results
    epub_result = None
    if results:
        for book in results:
            is_epub = book.extension and book.extension.lower() == 'epub'
            is_english = book.language and book.language.lower() == 'english'

            if is_epub and is_english:
                epub_result = book
                break

    if not epub_result:
        log(f"RESULT: Book not found for query '{query}' or no English EPUB file available.")
        return None

    # 3. Select the matching Book object
    book = epub_result
    title = book.title
    author = book.author

    # 4. Construct filename
    safe_title = sanitize_filename(title)
    safe_author = sanitize_filename(author)
    filename = f"{safe_author} - {safe_title}.epub"

    if (SOURCE_DIR / filename).exists():
        log(f"RESULT: Book '{filename}' already downloaded.")
        return filename

    log(f"Found book: {title} by {author}. Resolving direct download link...")

    # 5. Resolve direct download link
    try:
        book.resolve_direct_download_link()
        final_download_url = book.resolved_download_link
    except Exception as e:
        log(f"CRITICAL: Failed to resolve download link for {title}: {e}")
        return None

    if not final_download_url:
        log(f"CRITICAL: Could not generate a direct download link for {title}.")
        return None

    # 6. Execute Download
    if download_file(final_download_url, filename):
        return filename
    else:
        return None


def import_into_calibre():
    """Stops the local server, processes files for Kobo fix, adds books, then cleans up."""
    # Ensure all stray calibre processes are terminated before proceeding
    subprocess.run(['pkill', '-f', 'calibre|calibre-server'], check=False)
    files_to_sync = list(SOURCE_DIR.glob("*.epub")) # Only process EPUBs
    if not files_to_sync:
        log("No new files to import.")
        return

    log(f"Importing {len(files_to_sync)} files into Calibre...")

    # 1. SAFETY CHECK: Ensure GUI is closed
    if check_gui_running():
        log("CRITICAL ERROR: Calibre GUI is running. You must close the Calibre application before running this script.")
        return

    # 2. Stop the Server
    _kill_running_server()
    log("Server is confirmed stopped for safe import.")

    # 3. Remove Lock File (Just in case)
    lock_file = Path(CALIBRE_DB_PATH) / "metadata.db.lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
            log("Removed stale metadata.db.lock file.")
        except Exception as e:
            log(f"Warning: Could not remove lock file: {e}")

    try:
        # --- NEW STEP: Kobo Fix Processing ---
        log("Starting Kobo style filtering and KEPUB conversion...")
        for epub_file in files_to_sync:
            _process_epub_for_kobo(epub_file)
        log("Kobo style filtering complete.")
        # -----------------------------------
        
        # 4. Execute Import
        cmd = [
            "calibredb", "add",
            str(SOURCE_DIR),
            "--with-library", CALIBRE_DB_PATH,
            "--recurse"
        ]

        log("Running calibredb import...")
        run(cmd, check=True)
        log("Import successful.")

        # 5. Cleanup Source Files (ONLY IF IMPORT SUCCEEDED)
        log("Cleaning up source directory...")
        for item in SOURCE_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                log(f"Warning: Could not delete {item}: {e}")

        log("Cleanup successful.")

    except subprocess.CalledProcessError as e:
        log(f"CRITICAL: Calibre import failed: {e}")
        raise # Re-raise to ensure `finally` block runs, but subsequent main steps are skipped
    except FileNotFoundError:
        log("CRITICAL: 'calibredb' command not found. Is Calibre installed?")
        raise
    except Exception as e:
        log(f"CRITICAL: An unexpected error occurred during import: {e}")
        raise


def main():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Fetching master list from: {REQUESTS_FILE}")
    history = load_history()
    log(f"Loaded {len(history)} previously processed queries from history.")

    master_queries = load_requests()
    new_queries = master_queries - history

    if not new_queries:
        log("No new queries found in local list since the last run.")
        return

    log(f"Found {len(new_queries)} new unique queries to process.")

    successful_downloads = []

    # Process New Queries
    for query in new_queries:
        filename = process_query(query)
        if filename:
            successful_downloads.append(query)

    log(f"Successfully processed {len(successful_downloads)} new queries.")

    # Update History
    history=None
    save_history(history)

    # Sync to Calibre and Restart Server
    log("--- Starting Calibre Sync ---")

    # Use try...finally to guarantee server restart
    try:
        import_into_calibre()
    except Exception:
        # We log the error in import_into_calibre, just pass here to hit finally
        pass
    finally:
        # 7. Restart Server (GUARANTEED RESTART)
        restart_calibre_server()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"\nCRITICAL ERROR during script execution: {e}")
