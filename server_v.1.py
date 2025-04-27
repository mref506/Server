import http.server
import socketserver
import os
import sys
from urllib.parse import parse_qs
from urllib.parse import quote, unquote
from io import BytesIO

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SHARED_FOLDER = "./shared"
NOTE_FILE = "note.txt"

if not os.path.exists(SHARED_FOLDER):
    os.makedirs(SHARED_FOLDER)

# List of files to hide
HIDDEN_FILES = [
    ".~lock.*",  # Hide all files starting with .~lock
    "nots.txt",
    "note.txt"
]

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def list_directory(self, path):
        try:
            list_items = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None

        list_items.sort(key=lambda a: a.lower())
        response = BytesIO()
        note_text = ""
        if os.path.exists(NOTE_FILE):
            with open(NOTE_FILE, "r", encoding="utf-8") as f:
                note_text = f.read()

        html_content = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>File Server</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ font-family: Arial, sans-serif; background: #f8f9fa; padding: 20px; }}
                .container {{ max-width: 800px; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); }}
                .file-list {{ margin-top: 10px; }}
                a {{ text-decoration: none; font-weight: bold; }}
                .dark-mode {{ background: #121212; color: white; }}
                .dark-mode .container {{ background: #1e1e1e; }}
            </style>
            <script>
                function toggleTheme() {{
                    document.body.classList.toggle('dark-mode');
                }}
            </script>
        </head>
        <body>
        <div class="container">
            <h2 class="text-center text-primary">📂 Enock Server</h2>
            <button class="btn btn-secondary" onclick="toggleTheme()">Toggle Black/White Theme</button>
            <h4>Instructor Notes:</h4>
            <form method="POST" action="/save_note">
                <textarea class="form-control" name="note" rows="4">{note_text}</textarea>
                <button type="submit" class="btn btn-primary mt-2">Save Note</button>
            </form>
            <hr>
            <h4>Upload Homework:</h4>
            <form method="POST" action="/upload" enctype="multipart/form-data">
                <input type="file" name="file" class="form-control">
                <button type="submit" class="btn btn-success mt-2">Upload</button>
            </form>
            <hr>
            <h4>Available Files:</h4>
            <ul class="list-group file-list">
        """

        for name in list_items:
            if name in HIDDEN_FILES or name.startswith(".~lock"):
                continue
            if name.endswith(".py"):
                continue
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                continue
            link_name = quote(name)
            html_content += f'<li class="list-group-item d-flex justify-content-between align-items-center">'
            html_content += f'<a href="/{link_name}" download>{name}</a>'
            html_content += f'<a href="/{link_name}" class="btn btn-outline-primary btn-sm" download>Download</a>'
            html_content += '</li>'

        html_content += "</ul></div></body></html>"
        response.write(html_content.encode("utf-8"))
        length = response.tell()
        response.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return self.wfile.write(response.read())


def do_POST(self):
    if self.path == "/upload":
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        form_data = parse_qs(post_data.decode('utf-8'))
        file_item = form_data.get('file', [None])[0]
        
        if file_item:
            filename = os.path.basename(file_item)
            filepath = os.path.join(SHARED_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(file_item.encode())  # Convert to bytes
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()
    elif self.path == "/save_note":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode("utf-8")
            note_content = post_data.split("note=")[1].replace("+", " ").replace("%0D%0A", "\n")
            with open(NOTE_FILE, "w", encoding="utf-8") as f:
                f.write(unquote(note_content))
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
        


# Start the server
with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()