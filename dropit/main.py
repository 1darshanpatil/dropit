#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2024 Darshan P.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



import os
import socket
import logging
import argparse
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from flask_basicauth import BasicAuth
import time
import qrcode


# Setting up the argument parser for comman-line options.
parser = argparse.ArgumentParser(description='File server with optional basic authentication.')
parser.add_argument('--password', help='Set the password for basic authentication.', default=None)
parser.add_argument('--geturl', action='store_true', help='Print the URL')
parser.add_argument('--getqr', action='store_true', help='Display a QR code')
parser.add_argument('--maxsize', type=int, default=2, help='Maximum file upload size in GB (default: 2GB)')
args = parser.parse_args()


# Initialize the Flask application.
app = Flask(__name__)
# Configuration settings for the Flask application.
home_path = os.path.expanduser('~/sharex/')  # Default directory for uploads/downloads.
app.config['UPLOAD_FOLDER'] = home_path
GB_SIZE = args.maxsize * 1024 * 1024 * 1024  # Converts maxsize from GB to Bytes
app.config['MAX_CONTENT_LENGTH'] = GB_SIZE  
app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = args.password
app.config['BASIC_AUTH_FORCE'] = bool(args.password)  # Force basic auth if password is set.
basic_auth = BasicAuth(app)

"""
Flask application to serve files with optional basic authentication.

This module sets up a Flask web server that can handle file uploads to a specified directory.
It supports basic authentication if a password is provided, limits file upload sizes, and can
output the server's URL or a QR code for it to the console.

The server's behavior and capabilities can be configured via command-line arguments.
"""

def optional_auth(f):
    """
    Decorator to enforce basic authentication conditionally based on the presence of a password.

    If the `BASIC_AUTH_PASSWORD` configuration is set, this decorator will enforce HTTP Basic Auth
    for the decorated route using the credentials specified in the app configuration.
    If no password is set, it will allow unrestricted access to the route.

    Parameters:
    - f (function): The Flask view function to decorate.

    Returns:
    - function: The decorated view function with optional authentication.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if app.config['BASIC_AUTH_PASSWORD']:
            return basic_auth.required(f)(*args, **kwargs)
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET', 'POST'])
@optional_auth
def index():
    """
    Serve the main page and handle file uploads and listing.

    This route allows users to upload files to the server and displays a list of all uploaded files.
    If a POST request is received with files, the files are saved to the configured upload folder.
    For both GET and POST requests, the route retrieves all files from the upload folder and prepares
    their information to be displayed via the 'index.html' template.

    Returns:
    - Rendered template: The main page template populated with information about the uploaded files.
    """
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
    """
    Converts a file size from bytes to a more human-readable format (KB, MB, GB).

    Parameters:
    - size_bytes (int): The size of the file in bytes.

    Returns:
    - tuple: A tuple containing the size converted to the most appropriate unit (float) and the unit as a string.
    """
    if size_bytes < 1024:
        return size_bytes, 'B'  # Bytes
    elif size_bytes < 1024 ** 2:
        return round(size_bytes / 1024, 2), 'KB'  # Kilobytes
    elif size_bytes < 1024 ** 3:
        return round(size_bytes / 1024 ** 2, 2), 'MB'  # Megabytes
    else:
        return round(size_bytes / 1024 ** 3, 2), 'GB'  # Gigabytes

@app.route('/files/<filename>')
@optional_auth
def download_file(filename):
    """
    Serve a file download to the client.

    This route allows users to download a specific file from the server's upload directory,
    with optional basic authentication if configured.

    Parameters:
    - filename (str): The name of the file to be downloaded.

    Returns:
    - Response: A response object that lets the user download the specified file.
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete/<filename>')
@optional_auth
def delete_file(filename):
    """
    Deletes a specific file from the server.

    This route allows users to delete a specific file from the upload directory.
    After attempting to delete the file, the user is redirected back to the index page.

    Parameters:
    - filename (str): The name of the file to be deleted.

    Returns:
    - Redirect: A redirection response back to the main page.
    """
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('index'))

def get_ip():
    """
    Retrieves the local IP address of the server.

    This utility function fetches the local IP address by creating a temporary socket
    connection to an external point (Google's DNS server at 8.8.8.8).

    Returns:
    - str: The local IP address.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    finally:
        s.close()
    return IP


def create_qr_in_terminal(text):
    """
    Generates and prints a QR code in the terminal.

    This function creates a QR code for the provided text and prints it using ASCII characters. 
    The QR code is configured for low error correction with a specific size and border.

    Parameters:
    - text (str): The text to be encoded into a QR code.
    """
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
    """
    Cycles through colors and prints the server's IP address and port in the terminal.

    This function is designed to catch the user's attention by displaying the IP address and port in various colors.
    It can optionally clear the terminal before printing each color variant.

    Parameters:
    - ip (str): The IP address of the server.
    - port (int): The port number on which the server is running.
    - lag (float): Time in seconds to wait between color changes.
    - cl (bool): If True, clear the terminal between color changes.
    """
    os.system('cls' if os.name == 'nt' else 'clear')
    colors = ["\033[1;32m", "\033[1;34m", "\033[1;31m", "\033[1;33m", "\033[1;35m", "\033[1;36m"]
    for color in colors:
        if cl:
            os.system('cls' if os.name == 'nt' else 'clear')  
        print(f"{color}The URL to enter on your other device connected to the same wifi network is: http://{ip}:{port}\033[0m")
        time.sleep(lag)  
    print("Starting the server. Please navigate to the URL shown above on your devices.")



def print_colored(text, color):
    """
    Returns a string wrapped in terminal color codes.

    Parameters:
    - text (str): The text to color.
    - color (str): The name of the color to apply. Valid options are 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'.

    Returns:
    - str: The colored text string.
    """
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
    ip   = get_ip()
    port = 5001
    # use https in the printed URL now that we're running TLS
    server_url = f"https://{ip}:{port}"

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    if args.getqr:
        create_qr_in_terminal(server_url)
    if args.geturl:
        # prints in color but won’t clear your QR code
        print_colored_ip(ip, port, 0.5, cl=False)

    print(print_colored(f"Server is ready! Access it at: {server_url}", "green"))
    print(print_colored(f"Files can be found in: {app.config['UPLOAD_FOLDER']}", "blue"))

    app.run(
        host='0.0.0.0',
        port=port,
        ssl_context='adhoc'   # ← adds a self-signed cert on the fly
    )
    
if __name__ == '__main__':
    run_app()

