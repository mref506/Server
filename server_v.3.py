import http.server
import socketserver
import os
import sys
import cgi # Needed for parsing multipart/form-data (uploads)
from urllib.parse import quote, unquote
from io import BytesIO

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SHARED_FOLDER = "./shared"
NOTE_FILE = "note.txt" # Keep note file outside shared folder if possible

# Create shared folder if it doesn't exist
if not os.path.exists(SHARED_FOLDER):
    os.makedirs(SHARED_FOLDER)

# List of files/patterns to hide in the listing
HIDDEN_PATTERNS = [
    ".~lock.*", # Hide lock files (regex pattern might be needed for complex cases)
    "note.txt", # Hide the note file itself if it were in SHARED_FOLDER
    # Add any other files or patterns you want to hide
]
# Compiled regex might be better for patterns, but simple startswith/exact match is used here

class CustomHandler(http.server.SimpleHTTPRequestHandler):

    # Override translate_path to ensure files are served ONLY from SHARED_FOLDER
    def translate_path(self, path):
        # Prevent directory traversal attacks
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = os.path.normpath(unquote(path))
        words = path.split('/')
        words = filter(None, words)
        filepath = SHARED_FOLDER # Start in the shared folder
        for word in words:
            if os.path.dirname(word) or word in (os.curdir, os.pardir):
                # Ignore components that are directories or refer to parent/current dir
                continue
            filepath = os.path.join(filepath, word)
        # Check if the resulting path is still within the intended SHARED_FOLDER
        # (This basic check might need enhancement depending on security needs)
        if not os.path.abspath(filepath).startswith(os.path.abspath(SHARED_FOLDER)):
             # If path tries to escape SHARED_FOLDER, deny access by returning a non-existent path
             # or handle as an error. Here, we let SimpleHTTPRequestHandler handle the 404 later.
             # A more direct approach would be to send 403 Forbidden here.
             # For simplicity, we'll rely on the base class's 404 if the final path is invalid/outside.
             pass # Allow base class to handle path resolution, which should fail safely if outside root

        # Return the path relative to the CWD for the base handler to use
        # The base handler will prepend the current working directory if needed.
        # We need to return a path that *results* in the correct file *within* shared
        # when the base class combines it with os.getcwd().
        # A simpler way: return the absolute path directly (might bypass some base class logic)
        # Let's stick to returning a relative path assuming the server runs where SHARED_FOLDER is './shared'
        # This part is tricky with SimpleHTTPRequestHandler. A dedicated framework handles this better.
        # For now, let's return the calculated absolute path and see if the base handler uses it.
        # *Correction*: SimpleHTTPRequestHandler expects path relative to CWD.
        # So, the logic should be: calculate the full path, check it's within SHARED_FOLDER,
        # then return the *original* path string (relative to root) for the base class to process.
        # The base class `send_head` will then call `translate_path` again.

        # Let's refine: The goal of translate_path is to map URL path to FS path.
        # Base implementation does os.getcwd() + path. We want os.getcwd() + SHARED_FOLDER + requested_file
        base = os.getcwd()
        requested_path = super().translate_path(path) # Get path relative to CWD

        # Construct the intended path within the shared folder
        # Note: `path` starts with '/', so os.path.join needs care
        relative_url_path = path.lstrip('/')
        full_intended_path = os.path.abspath(os.path.join(base, SHARED_FOLDER, relative_url_path))

        # Security check: Ensure the final path is inside the shared folder
        if not full_intended_path.startswith(os.path.abspath(os.path.join(base, SHARED_FOLDER))):
            # Attempt to access outside shared folder - deny
            # Returning an invalid path often leads to 404 by the base handler.
            return os.path.join(base, "nonexistent_path_due_to_security") # Force 404

        return full_intended_path # Return the securely calculated full path


    # Override list_directory to provide the custom HTML interface
    def list_directory(self, path):
        # Note: The 'path' argument received here is the actual filesystem path
        # Ensure we're listing the SHARED_FOLDER, not other directories
        if os.path.abspath(path) != os.path.abspath(SHARED_FOLDER):
             self.send_error(403, "Access Forbidden")
             return None

        try:
            list_items = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None

        list_items.sort(key=lambda a: a.lower())
        response = BytesIO()
        note_text = ""
        note_filepath = os.path.join(os.path.dirname(__file__) or '.', NOTE_FILE) # Store note outside shared
        if os.path.exists(note_filepath):
            try:
                with open(note_filepath, "r", encoding="utf-8") as f:
                    note_text = f.read()
            except Exception as e:
                print(f"Error reading note file: {e}")
                note_text = "Error loading notes."


        # --- HTML Content ---
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📂 Enock Server- File Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            background-color: #f8f9fa; /* Light mode default */
            color: #212529;
            transition: background-color 0.3s, color 0.3s;
            padding-top: 56px; /* Adjust for fixed navbar */
        }}
        .navbar {{
             background-color: #e9ecef; /* Lighter gray for light mode */
        }}
         .navbar-brand {{
             font-weight: bold;
             color: #dc3545 !important; /* Reddish color for brand */
         }}
         .brand-dot {{ color: #6c757d; }} /* Gray dot */

        .main-content {{
            padding: 20px;
        }}
        .note-container {{
            background-color: #ffffff; /* White background for light mode */
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
            border: 1px solid #dee2e6;
        }}
        .note-textarea {{
            min-height: 250px; /* Taller text area */
            border: 1px solid #ced4da;
            background-color: #fff; /* Ensure textarea bg matches container */
            color: #212529; /* Ensure text color matches body */
            resize: vertical;
        }}
        .action-buttons .btn {{
            margin-right: 5px;
            margin-bottom: 5px; /* Add spacing below buttons */
        }}
        .status-indicator {{
            display: flex;
            align-items: center;
            margin-top: 10px;
            color: #6c757d; /* Gray for status text */
        }}
        .status-indicator .bi-check-lg {{
            color: #198754; /* Green checkmark */
            margin-right: 5px;
        }}
        .file-list-container {{ margin-top: 30px; }}

        /* --- Dark Mode --- */
        body.dark-mode {{
            background-color: #1a1a1a; /* Darker background */
            color: #e0e0e0; /* Lighter text */
        }}
        .dark-mode .navbar {{
             background-color: #212529; /* Dark navbar */
             border-bottom: 1px solid #343a40;
        }}
        .dark-mode .navbar-brand {{
             color: #ff4d4d !important; /* Brighter red for brand */
        }}
        .dark-mode .brand-dot {{ color: #adb5bd; }} /* Lighter gray dot */
        .dark-mode .nav-link {{ color: #adb5bd !important; }}
        .dark-mode .nav-link:hover {{ color: #f8f9fa !important; }}

        .dark-mode .note-container {{
            background-color: #2c2c2c; /* Dark gray for container */
            border: 1px solid #444;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
        }}
         .dark-mode h4, .dark-mode h2 {{ color: #e0e0e0; }}
        .dark-mode .note-textarea {{
            background-color: #3a3a3a; /* Darker textarea */
            color: #e0e0e0;
            border: 1px solid #555;
        }}
        .dark-mode .note-textarea::placeholder {{ color: #888; }}
        .dark-mode .btn-outline-secondary {{
            color: #adb5bd; border-color: #6c757d;
        }}
         .dark-mode .btn-outline-secondary:hover {{
            background-color: #6c757d; color: #1a1a1a;
        }}
         .dark-mode .btn-secondary {{ /* Make main toggle button fit dark mode */
             background-color: #6c757d; border-color: #6c757d; color: #fff;
         }}
         .dark-mode .btn-primary {{ background-color: #0d6efd; border-color: #0d6efd; }} /* Adjust if needed */
         .dark-mode .btn-success {{ background-color: #198754; border-color: #198754; }} /* Adjust if needed */
         .dark-mode .list-group-item {{
             background-color: #2c2c2c;
             border-color: #444;
             color: #e0e0e0;
         }}
         .dark-mode .list-group-item a {{ color: #6ea8fe; }} /* Lighter blue links */
         .dark-mode .form-control {{
              background-color: #3a3a3a;
              color: #e0e0e0;
              border-color: #555;
         }}
          .dark-mode .form-control::placeholder {{ color: #888; }}
          .dark-mode .form-control:focus {{ background-color: #3a3a3a; color: #e0e0e0; border-color: #80bdff; box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25); }}
          .dark-mode .form-control[type="file"]::file-selector-button {{
              background-color: #6c757d;
              color: #fff;
              border-color: #6c757d;
          }}
          .dark-mode hr {{ border-top-color: #444; }}
          .dark-mode .status-indicator {{ color: #adb5bd; }}
    </style>
    <script>
        function toggleTheme() {{
            document.body.classList.toggle('dark-mode');
            // Optional: Save preference in localStorage
            if (document.body.classList.contains('dark-mode')) {{
                localStorage.setItem('theme', 'dark');
            }} else {{
                localStorage.setItem('theme', 'light');
            }}
        }}

        function applyInitialTheme() {{
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {{
                document.body.classList.add('dark-mode');
            }} else {{
                // Optional: explicitly remove if needed, though default is light
                document.body.classList.remove('dark-mode');
            }}
        }}

        function copyNoteText() {{
            const textArea = document.getElementById('noteTextArea');
            textArea.select();
            textArea.setSelectionRange(0, 99999); // For mobile devices
            try {{
                navigator.clipboard.writeText(textArea.value).then(() => {{
                    // Optional: Show a temporary success message
                    const copyButton = document.getElementById('copyButton');
                    const originalText = copyButton.innerHTML;
                    copyButton.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
                    setTimeout(() => {{ copyButton.innerHTML = originalText; }}, 2000);
                }}, (err) => {{
                    console.error('Async: Could not copy text: ', err);
                    // Fallback for older browsers (less reliable)
                    try {{
                       document.execCommand('copy');
                       // Optional success feedback here too
                    }} catch (err) {{
                       console.error('Fallback: Could not copy text: ', err);
                       alert('Failed to copy text.');
                    }}
                }});
            }} catch (e) {{
                 console.error('Clipboard API not available: ', e);
                 alert('Failed to copy text. Clipboard API might not be supported or available in this context (e.g., http).');
            }}
            // Deselect text afterwards
            window.getSelection().removeAllRanges();
        }}

         // Apply theme on load
         document.addEventListener('DOMContentLoaded', applyInitialTheme);
    </script>
</head>
<body>

<nav class="navbar navbar-expand-lg fixed-top">
  <div class="container-fluid">
    <a class="navbar-brand" href="#">Simple<span class="brand-dot">.</span>Savr</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav ms-auto">
        <li class="nav-item">
          <a class="nav-link active" aria-current="page" href="#">Home</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#">Features</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#">Debug</a>
        </li>
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
            Support
          </a>
          <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="#">Action</a></li>
            <li><a class="dropdown-item" href="#">Another action</a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item" href="#">Something else here</a></li>
          </ul>
        </li>
      </ul>
    </div>
  </div>
</nav>

<div class="container main-content">
    <div class="note-container">
        <h4><i class="bi bi-pencil-square"></i> Instructor Notes / Scratchpad</h4>
         <p class="text-muted small">Start Typing!</p>

        <div class="action-buttons mb-3">
            <button id="copyButton" class="btn btn-sm btn-outline-secondary" onclick="copyNoteText()"><i class="bi bi-clipboard"></i> Copy</button>
            <button class="btn btn-sm btn-outline-secondary" disabled><i class="bi bi-link-45deg"></i> Links</button> <!-- Placeholder -->
             <!-- The actual upload uses the form below, this button is illustrative -->
            <label for="fileUploadInput" class="btn btn-sm btn-outline-secondary"><i class="bi bi-upload"></i> Upload</label> <!-- Visually triggers file input -->
            <button class="btn btn-sm btn-outline-secondary" disabled><i class="bi bi-download"></i> Download</button> <!-- Placeholder -->
            <button class="btn btn-sm btn-outline-secondary" onclick="toggleTheme()"><i class="bi bi-circle-half"></i> Dark Mode</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="location.reload();"><i class="bi bi-arrow-clockwise"></i></button> <!-- Refresh -->
            <button class="btn btn-sm btn-outline-secondary" disabled><i class="bi bi-gear"></i></button> <!-- Settings Placeholder -->
        </div>

        <form method="POST" action="/save_note">
            <textarea id="noteTextArea" class="form-control note-textarea" name="note" rows="10" placeholder="Enter your notes here...">{note_text}</textarea>
            <button type="submit" class="btn btn-primary mt-2">Save Note</button>
        </form>
        <div class="status-indicator">
             <i class="bi bi-check-lg"></i> <span>Saved (static example)</span>
             <span class="ms-auto">Last change: unknown</span> <!-- Placeholder -->
        </div>
    </div>

    <hr>

    <div class="upload-container mt-4">
        <h4><i class="bi bi-cloud-arrow-up-fill"></i> Upload Homework / Files</h4>
        <form method="POST" action="/upload" enctype="multipart/form-data">
            <div class="input-group">
              <!-- Hidden actual input, triggered by the label button above or this control -->
              <input type="file" name="file" class="form-control" id="fileUploadInput" required>
              <button type="submit" class="btn btn-success">Upload</button>
            </div>
             <small class="form-text text-muted">Files will be saved to the shared folder.</small>
        </form>
    </div>

    <hr>

    <div class="file-list-container mt-4">
        <h4><i class="bi bi-folder-fill"></i> Available Files in Shared Folder</h4>
        <ul class="list-group file-list">
"""

        # --- File Listing Logic ---
        if not list_items:
             html_content += '<li class="list-group-item">No files found in shared folder.</li>'
        else:
            for name in list_items:
                # Check against hidden patterns more carefully
                hide_this = False
                if name.startswith(".~lock"): # Specific check for lock files
                    hide_this = True
                elif name == NOTE_FILE or name == "nots.txt": # Example exact matches
                    hide_this = True
                # Add other specific checks or regex matches here if needed

                if hide_this:
                    continue

                # Ensure it's a file, not a directory within shared (unless desired)
                full_path = os.path.join(path, name)
                if os.path.isdir(full_path):
                    # Optionally list directories or skip them
                    continue # Skipping directories for this example

                # Generate link for downloading
                link_name = quote(name) # URL-encode the filename
                display_name = name # Keep original name for display

                html_content += f'<li class="list-group-item d-flex justify-content-between align-items-center">'
                # Link uses relative path which should resolve correctly via GET requests
                html_content += f'<a href="/{link_name}">{display_name}</a>'
                html_content += f'<a href="/{link_name}" class="btn btn-outline-primary btn-sm" download="{display_name}"><i class="bi bi-download"></i> Download</a>'
                html_content += '</li>'

        # --- End of HTML ---
        html_content += """
                </ul>
            </div>
        </div> <!-- End main container -->

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """
        # --- Send Response ---
        encoded_html = html_content.encode("utf-8")
        response.write(encoded_html)
        length = response.tell()
        response.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(response.read())
        return None # Important: return None to prevent base class behavior

    # Override do_GET to ensure '/' serves our custom directory listing
    def do_GET(self):
        if self.path == '/':
            # Serve the custom listing for the root path, pointing to SHARED_FOLDER
            self.list_directory(SHARED_FOLDER)
        else:
            # For other paths (file downloads), let the base class handle it
            # The base class will call translate_path, which we've restricted
             try:
                 super().do_GET()
             except ConnectionResetError:
                  print("Connection reset by peer during GET.")
             except BrokenPipeError:
                  print("Broken pipe during GET.")


    # Override do_POST to handle form submissions
    def do_POST(self):
        try:
            if self.path == "/upload":
                # Use cgi module to parse multipart/form-data
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                             'CONTENT_TYPE': self.headers['Content-Type'],
                             })

                if 'file' in form:
                    file_item = form['file']
                    if file_item.filename:
                        # Prevent directory traversal in filename
                        filename = os.path.basename(file_item.filename)
                        if not filename: # Handle cases like filename="../.." -> ""
                             raise ValueError("Invalid filename")

                        filepath = os.path.join(SHARED_FOLDER, filename)

                        # Check if path is still within shared folder (redundancy is good)
                        if not os.path.abspath(filepath).startswith(os.path.abspath(SHARED_FOLDER)):
                            raise ValueError("Attempted path traversal in upload")


                        # Write the file content in binary mode
                        with open(filepath, 'wb') as f:
                            # Read the file content chunk by chunk if needed for large files
                            # file_item.file is the file-like object
                            # f.write(file_item.value) # .value reads the whole thing (might use lots of RAM)
                            import shutil
                            shutil.copyfileobj(file_item.file, f) # More efficient for large files
                        print(f"Uploaded file saved to: {filepath}")
                    else:
                        print("No file selected or empty filename received.")
                else:
                    print("Form data received, but 'file' field is missing.")

                # Redirect back to the main page after upload
                self.send_response(303) # 303 See Other is appropriate after POST
                self.send_header("Location", "/")
                self.end_headers()

            elif self.path == "/save_note":
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode("utf-8")

                # A more robust way to parse form data
                from urllib.parse import parse_qs
                parsed_data = parse_qs(post_data)
                note_content = parsed_data.get('note', [''])[0] # Get first value or empty string

                # Determine note file path (outside shared folder)
                note_filepath = os.path.join(os.path.dirname(__file__) or '.', NOTE_FILE)
                try:
                    with open(note_filepath, "w", encoding="utf-8") as f:
                        # No need to unquote manually if parse_qs is used correctly
                        f.write(note_content)
                    print(f"Note saved to: {note_filepath}")
                except Exception as e:
                    print(f"Error saving note: {e}")

                # Redirect back to the main page
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()

            else:
                # Handle other POST requests if necessary, or send error
                self.send_error(404, "Endpoint not found")
        except ConnectionResetError:
             print("Connection reset by peer during POST.")
        except BrokenPipeError:
             print("Broken pipe during POST.")
        except Exception as e:
             print(f"Error handling POST request to {self.path}: {e}")
             # Send an error response to the client
             self.send_error(500, f"Server error processing request: {e}")


# --- Main execution ---
if __name__ == "__main__":
    # Ensure server uses the custom handler
    Handler = CustomHandler
    # Allow address reuse (useful for quick restarts)
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving files from '{SHARED_FOLDER}' folder on http://localhost:{PORT}")
        print(f"Notes will be saved to '{os.path.abspath(NOTE_FILE)}'")
        print("Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopping.")
            httpd.shutdown()