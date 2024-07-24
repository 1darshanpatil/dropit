#!/usr/bin/env python3
import os
import socket
import logging
import argparse
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from flask_basicauth import BasicAuth
import time
import qrcode

parser = argparse.ArgumentParser(description='File server with optional basic authentication.')
parser.add_argument('--password', help='Set the password for basic authentication.', default=None)
parser.add_argument('--geturl', action='store_true', help='Print the URL')
parser.add_argument('--getqr', action='store_true', help='Display a QR code')
parser.add_argument('--maxsize', type=int, default=2, help='Maximum file upload size in GB (default: 2GB)')
args = parser.parse_args()


app = Flask(__name__)
home_path = os.path.expanduser('~/sharex/')
app.config['UPLOAD_FOLDER'] = home_path
GB_SIZE = args.maxsize * 1024 * 1024 * 1024  
app.config['MAX_CONTENT_LENGTH'] = GB_SIZE  
app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = args.password
app.config['BASIC_AUTH_FORCE'] = bool(args.password)
basic_auth = BasicAuth(app)


def optional_auth(f):
    """Decorator to enforce basic authentication conditionally."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if app.config['BASIC_AUTH_PASSWORD']:
            return basic_auth.required(f)(*args, **kwargs)
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET', 'POST'])
@optional_auth
def index():
    """Route for the main page that handles file uploads and displays files."""
    if request.method == 'POST':
        files = request.files.getlist('files')
        for file in files:
            if file:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
                
    files_info = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        size_bytes = os.path.getsize(filepath)
        size, unit = format_size(size_bytes)
        filetype = filename.split('.')[-1] if '.' in filename else 'Unknown'
        files_info.append({'name': filename, 'size': f"{size} {unit}", 'type': filetype})
        
    return render_template('index.html', files=files_info)

def format_size(size_bytes):
    """Converts a size in bytes to a more human-readable form."""
    if size_bytes < 1024:
        return size_bytes, 'B'  
    elif size_bytes < 1024 ** 2:
        return round(size_bytes / 1024, 2), 'KB'  
    elif size_bytes < 1024 ** 3:
        return round(size_bytes / 1024 ** 2, 2), 'MB'  
    else:
        return round(size_bytes / 1024 ** 3, 2), 'GB'  

@app.route('/files/<filename>')
@optional_auth
def download_file(filename):
    """Route to download a file."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete/<filename>')
@optional_auth
def delete_file(filename):
    """Route to delete a specific file."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('index'))

def get_ip():
    """Utility function to get the local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    finally:
        s.close()
    return IP


def create_qr_in_terminal(text):
    qr = qrcode.QRCode(
            version = 1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
    qr.add_data(text)
    qr.make(fit=True)
    qr.print_ascii(invert= True)


def print_colored_ip(ip, port, lag, cl=True):
    """Prints the IP address in the terminal with changing colors."""
    os.system('cls' if os.name == 'nt' else 'clear')
    colors = ["\033[1;32m", "\033[1;34m", "\033[1;31m", "\033[1;33m", "\033[1;35m", "\033[1;36m"]
    for color in colors:
        if cl:
            os.system('cls' if os.name == 'nt' else 'clear')  
        print(f"{color}The URL to enter on your other device connected to the same wifi network is: http://{ip}:{port}\033[0m")
        time.sleep(lag)  
    print("Starting the server. Please navigate to the URL shown above on your devices.")



def print_colored(text, color):
    colors = {
        "red": "\033[1;31m",
        "green": "\033[1;32m",
        "yellow": "\033[1;33m",
        "blue": "\033[1;34m",
        "magenta": "\033[1;35m",
        "cyan": "\033[1;36m",
        "white": "\033[1;37m",
        "reset": "\033[0m"
    }
    return f"{colors[color]}{text}{colors['reset']}"


def run_app():
    """Starts the Flask application."""
    ip = get_ip()
    port = 5001
    server_url = f"http://{ip}:{port}"
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    if args.getqr:
        create_qr_in_terminal(server_url)
    if args.geturl:
        print_colored_ip(ip, port, 0.5, cl=False)
        # cl = False ; To avoid clearing the QR code if printed.
    print(print_colored("Server is ready! Access it at: " + server_url, "green"))
    print(print_colored("Files can be found in: " + app.config['UPLOAD_FOLDER'], "blue"))
    app.run(host='0.0.0.0', port=port, debug=False)

    
if __name__ == '__main__':
    run_app()

