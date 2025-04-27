import http.server
import socketserver
import os
import sys
import cgi
import json
import mimetypes
from urllib.parse import unquote, quote
from datetime import datetime
import time # For modification times
import shutil # For copyfileobj

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SHARED_FOLDER = "./shared"
NOTE_FILE = "note.txt" # Store outside shared folder
LAST_CHANGE_FILE = "last_change.txt" # To persist last change time
TEMPLATE_FILE = "template.html"

# Create shared folder if it doesn't exist
if not os.path.exists(SHARED_FOLDER):
    os.makedirs(SHARED_FOLDER)

# List of files/patterns to hide in the listing
HIDDEN_PATTERNS = [
    ".~lock.*", # Example pattern
    NOTE_FILE,
    LAST_CHANGE_FILE,
    TEMPLATE_FILE,
    os.path.basename(__file__), # Hide the script itself
    # Add any other files or patterns you want to hide
]

# --- Helper Functions ---

def get_last_change_time():
    """Reads the last change timestamp from its file."""
    try:
        if os.path.exists(LAST_CHANGE_FILE):
            with open(LAST_CHANGE_FILE, "r") as f:
                return f.read().strip()
    except Exception as e:
        print(f"Error reading last change file: {e}")
    return None # Return None if not found or error

def update_last_change_time():
    """Writes the current timestamp to the last change file."""
    now_iso = datetime.now().isoformat()
    try:
        with open(LAST_CHANGE_FILE, "w") as f:
            f.write(now_iso)
        return now_iso
    except Exception as e:
        print(f"Error writing last change file: {e}")
        return None # Indicate failure

def is_hidden(filename):
    """Checks if a filename matches any hidden patterns."""
    if filename in HIDDEN_PATTERNS:
        return True
    if filename.startswith(".~lock"): # Handle specific patterns
        return True
    # Add more complex pattern matching (regex) if needed
    return False

def secure_path(base_folder, filename):
    """Constructs and validates a path within the base folder."""
    if not filename or filename == '.' or filename == '..':
        raise ValueError("Invalid filename component.")

    # Normalize to prevent tricks like 'file/../../etc/passwd'
    # Unquote first to handle URL-encoded characters like %2F (/)
    filename = os.path.normpath(unquote(filename))

    # Disallow absolute paths or components trying to go up
    if os.path.isabs(filename) or filename.startswith(".."):
         raise ValueError("Path traversal attempt detected.")

    full_path = os.path.abspath(os.path.join(base_folder, filename))

    # Final check: Ensure the final absolute path is *within* the base folder
    if not full_path.startswith(os.path.abspath(base_folder) + os.sep) and \
       full_path != os.path.abspath(base_folder): # Allow base folder itself if needed, but usually not for files
        raise ValueError("Path is outside the designated shared folder.")

    return full_path


# --- Request Handler ---

class CustomHandler(http.server.SimpleHTTPRequestHandler):

    # Override SimpleHTTPRequestHandler methods slightly for API structure

    def send_json_response(self, status_code, data):
        """Sends a JSON response."""
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, status_code, message):
        """Sends a JSON error response."""
        self.send_json_response(status_code, {"success": False, "message": message})

    def do_GET(self):
        """Handles GET requests for the main page, files, and API endpoints."""
        try:
            # API: Get Note
            if self.path == '/api/note':
                note_content = ""
                if os.path.exists(NOTE_FILE):
                    try:
                        with open(NOTE_FILE, "r", encoding="utf-8") as f:
                            note_content = f.read()
                    except Exception as e:
                        print(f"Error reading note file: {e}")
                        # Don't send error to client, just return empty note maybe?
                last_change = get_last_change_time()
                self.send_json_response(200, {"note": note_content, "lastChange": last_change})

            # API: Get File List
            elif self.path == '/api/files':
                files_list = []
                try:
                    for name in os.listdir(SHARED_FOLDER):
                        if is_hidden(name):
                            continue
                        full_path = os.path.join(SHARED_FOLDER, name)
                        if os.path.isfile(full_path): # Only list files
                            files_list.append({
                                "name": name,
                                # URL encode filename for safe use in href
                                "url": f"/shared/{quote(name)}"
                            })
                    files_list.sort(key=lambda x: x['name'].lower()) # Sort by name
                    self.send_json_response(200, files_list)
                except OSError as e:
                    print(f"Error listing directory {SHARED_FOLDER}: {e}")
                    self.send_error_response(500, "Could not list files.")

            # Serve the main HTML template
            elif self.path == '/':
                 if os.path.exists(TEMPLATE_FILE):
                     self.send_response(200)
                     self.send_header("Content-type", "text/html; charset=UTF-8")
                     # Prevent caching of the template itself during development
                     self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                     self.send_header("Pragma", "no-cache")
                     self.send_header("Expires", "0")
                     self.end_headers()
                     with open(TEMPLATE_FILE, 'rb') as f:
                         self.wfile.write(f.read())
                 else:
                     self.send_error(404, f"{TEMPLATE_FILE} not found")

            # Serve files from SHARED_FOLDER (e.g., /shared/myhomework.pdf)
            elif self.path.startswith('/shared/'):
                filename = self.path[len('/shared/'):]
                try:
                    file_path = secure_path(SHARED_FOLDER, filename) # Validate path
                    if os.path.isfile(file_path):
                         # Use SimpleHTTPRequestHandler's file serving logic
                         # We need to temporarily adjust 'path' for the base handler
                         original_path = self.path
                         # Map URL path to filesystem path relative to CWD for base handler
                         self.path = os.path.relpath(file_path, os.getcwd())
                         super().do_GET() # Let base class handle Range, HEAD, etc.
                         self.path = original_path # Restore path
                    else:
                         self.send_error(404, "File not found")
                except ValueError as e: # Path traversal or invalid
                    print(f"Security Error serving file: {e}")
                    self.send_error(403, "Forbidden")
                except FileNotFoundError:
                     self.send_error(404, "File not found")
                except Exception as e:
                     print(f"Error serving file {filename}: {e}")
                     self.send_error(500, "Server error serving file")

            # Fallback for other paths (or let base class handle if needed)
            else:
                 # self.send_error(404, "Resource not found")
                 # Or maybe let base class handle for things like favicon.ico?
                 super().do_GET() # Be careful with security implications

        except ConnectionResetError:
             print("Connection reset by peer during GET.")
        except BrokenPipeError:
             print("Broken pipe during GET.")
        except Exception as e:
            print(f"Unexpected error during GET {self.path}: {e}")
            # Avoid sending detailed errors to client unless debugging
            self.send_error(500, "Internal Server Error")


    def do_POST(self):
        """Handles POST requests for saving notes and uploading files."""
        try:
            # API: Save Note
            if self.path == '/api/note':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                     return self.send_error_response(400, "No data received.")

                post_data_raw = self.rfile.read(content_length)
                try:
                    post_data = json.loads(post_data_raw.decode('utf-8'))
                    note_content = post_data.get('note', '') # Default to empty string

                    with open(NOTE_FILE, "w", encoding="utf-8") as f:
                        f.write(note_content)

                    last_change = update_last_change_time()
                    print(f"Note saved to: {NOTE_FILE}")
                    self.send_json_response(200, {"success": True, "message": "Note saved!", "lastChange": last_change})

                except json.JSONDecodeError:
                    self.send_error_response(400, "Invalid JSON data.")
                except Exception as e:
                    print(f"Error saving note: {e}")
                    self.send_error_response(500, f"Could not save note: {e}")

            # API: Upload Files
            elif self.path == '/api/upload':
                 ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
                 if ctype == 'multipart/form-data':
                     # Adjust boundary for FieldStorage if needed
                     pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
                     pdict['CONTENT-LENGTH'] = int(self.headers.get('content-length'))

                     form = cgi.FieldStorage(
                         fp=self.rfile,
                         headers=self.headers,
                         environ={'REQUEST_METHOD': 'POST',
                                  'CONTENT_TYPE': self.headers['content-type'],
                                  })

                     uploaded_files = []
                     errors = []
                     # Handle multiple files sent with name 'files[]'
                     if 'files[]' in form:
                         file_items = form['files[]']
                         # Ensure file_items is always a list
                         if not isinstance(file_items, list):
                             file_items = [file_items]

                         for file_item in file_items:
                             if file_item.filename:
                                 try:
                                     # Use secure_path to construct and validate
                                     # Need basename again inside secure_path? Let secure_path handle it.
                                     filename_only = os.path.basename(file_item.filename) # Sanitize again
                                     filepath = secure_path(SHARED_FOLDER, filename_only)

                                     with open(filepath, 'wb') as f:
                                         shutil.copyfileobj(file_item.file, f)
                                     uploaded_files.append(filename_only)
                                     print(f"Uploaded file saved to: {filepath}")
                                 except ValueError as e: # Security error from secure_path
                                     print(f"Upload security error for {file_item.filename}: {e}")
                                     errors.append(f"Blocked '{file_item.filename}': Invalid path.")
                                 except Exception as e:
                                     print(f"Error saving uploaded file {file_item.filename}: {e}")
                                     errors.append(f"Failed to save '{file_item.filename}'.")
                             else:
                                 # This might happen if field is present but no file selected
                                 print("Received 'files[]' field with no filename.")
                         # After loop
                         if uploaded_files:
                             last_change = update_last_change_time()
                             message = f"Successfully uploaded {len(uploaded_files)} file(s)."
                             if errors: message += f" Encountered {len(errors)} error(s)."
                             self.send_json_response(200, {
                                 "success": True, # Partial success is still success overall
                                 "message": message,
                                 "uploaded": uploaded_files,
                                 "errors": errors,
                                 "lastChange": last_change
                             })
                         elif errors:
                              self.send_error_response(400, f"Upload failed. Errors: {'; '.join(errors)}")
                         else:
                             self.send_error_response(400, "No valid files were uploaded.")

                     else:
                         self.send_error_response(400, "No 'files[]' field found in upload data.")
                 else:
                     self.send_error_response(400, "Invalid content type. Expected 'multipart/form-data'.")


            # Unknown POST path
            else:
                self.send_error(404, "Endpoint not found")

        except ConnectionResetError:
             print("Connection reset by peer during POST.")
        except BrokenPipeError:
             print("Broken pipe during POST.")
        except Exception as e:
            print(f"Unexpected error during POST {self.path}: {e}")
            self.send_error_response(500, f"Server error processing request: {e}")


# --- Main execution ---
if __name__ == "__main__":
    # Ensure necessary files/folders exist
    if not os.path.exists(SHARED_FOLDER): os.makedirs(SHARED_FOLDER)
    if not os.path.exists(NOTE_FILE): open(NOTE_FILE, 'a').close() # Create if not exists
    if not os.path.exists(LAST_CHANGE_FILE): update_last_change_time() # Create if not exists

    # Allow address reuse (useful for quick restarts)
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"Serving from http://localhost:{PORT}")
        print(f"HTML Template: '{TEMPLATE_FILE}'")
        print(f"Shared Folder: '{os.path.abspath(SHARED_FOLDER)}'")
        print(f"Note File: '{os.path.abspath(NOTE_FILE)}'")
        print(f"Last Change File: '{os.path.abspath(LAST_CHANGE_FILE)}'")
        print("Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopping.")
            httpd.shutdown()