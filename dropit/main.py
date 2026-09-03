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
import errno
import ipaddress
import threading
import socket
import argparse
import datetime
import ssl
import sys
import tempfile
import time
import traceback as traceback_module
import zipfile
from functools import wraps
from urllib.parse import quote, urlsplit

import qrcode
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, abort, jsonify, Response
from flask_basicauth import BasicAuth

from dropit import __version__

DEFAULT_PORT = 5001
DEFAULT_MAX_UPLOAD_GB = 2
BYTES_PER_GB = 1024 ** 3

# One worker per in-flight request. Streaming downloads hold a worker for their whole
# duration, so the pool needs room for several large transfers plus everyone else's browsing.
DEFAULT_WORKER_THREADS = 48

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.dropit')
CERTIFICATE_PATH = os.path.join(CONFIG_DIR, 'cert.pem')
PRIVATE_KEY_PATH = os.path.join(CONFIG_DIR, 'key.pem')
CERTIFICATE_DAYS = 825  # The longest lifetime Apple and Chrome will accept for a leaf cert.

# A listing thumbnail is 30px wide but the browser downloads the whole file to draw it.
# Past this size that costs more than it is worth over Wi-Fi, so show the icon instead;
# the image still opens at full size in the preview.
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024

# Streamed archives are stored, not deflated: the shared files are usually already
# compressed (HEIC, PNG, PDF, MP4), so deflate burns CPU for almost no saving — and
# storing lets us predict the archive size to the byte, which is what gives the browser
# a real progress bar instead of "unknown size".
ZIP_ENTRY_OVERHEAD = 120  # local header + data descriptor + central directory, with ZIP64
ZIP_TRAILER_OVERHEAD = 22  # end-of-central-directory record
STREAM_CHUNK_BYTES = 512 * 1024

# Byte counters for in-flight downloads, keyed by a token the browser generates.
# Shared across worker threads, so every touch goes through the lock.
_download_progress = {}
_download_progress_lock = threading.Lock()
DOWNLOAD_PROGRESS_TTL = 120


def _progress_start(token, total, label):
    if not token:
        return
    with _download_progress_lock:
        _prune_progress()
        _download_progress[token] = {
            'sent': 0, 'total': total, 'label': label,
            'done': False, 'failed': False, 'updated': time.monotonic(),
        }


def _progress_advance(token, sent):
    if not token:
        return
    with _download_progress_lock:
        entry = _download_progress.get(token)
        if entry is not None:
            entry['sent'] = sent
            entry['updated'] = time.monotonic()


def _progress_finish(token, failed=False):
    if not token:
        return
    with _download_progress_lock:
        entry = _download_progress.get(token)
        if entry is not None:
            entry['done'] = True
            entry['failed'] = failed
            entry['updated'] = time.monotonic()


def _prune_progress():
    """Drop finished or abandoned entries. Caller already holds the lock."""
    cutoff = time.monotonic() - DOWNLOAD_PROGRESS_TTL
    for key in [k for k, v in _download_progress.items() if v['updated'] < cutoff]:
        del _download_progress[key]


def collect_download_entries(selected_paths):
    """Expand a selection of files and folders into a flat list of archive entries.

    Folders are walked recursively; symlinks and half-finished uploads are skipped so a
    download can never escape the share root or capture a partial file.
    """
    entries = []
    seen = set()

    def add_file(disk_path, arcname):
        if arcname in seen:
            return
        try:
            stat_result = os.stat(disk_path, follow_symlinks=False)
        except OSError:
            return
        seen.add(arcname)
        entries.append((disk_path, arcname, stat_result.st_size))

    for selected_path in selected_paths:
        disk_path, normalized_path = resolve_shared_path(selected_path)
        if not normalized_path:
            continue

        if os.path.isdir(disk_path) and not os.path.islink(disk_path):
            for directory, subdirectories, filenames in os.walk(disk_path, followlinks=False):
                subdirectories[:] = [
                    name for name in subdirectories
                    if not os.path.islink(os.path.join(directory, name))
                ]
                relative_directory = os.path.relpath(directory, disk_path)
                for filename in filenames:
                    full_path = os.path.join(directory, filename)
                    if os.path.islink(full_path):
                        continue
                    if filename.startswith('.__dropit_upload_') and filename.endswith('.part'):
                        continue
                    relative = filename if relative_directory == '.' else os.path.join(relative_directory, filename)
                    add_file(full_path, f"{normalized_path}/{relative}".replace(os.sep, '/'))
        elif os.path.isfile(disk_path):
            add_file(disk_path, normalized_path)
        else:
            abort(404)

    return entries


def archive_size(entries):
    """Exact byte length of the archive stream_archive() will produce."""
    payload = sum(size for _, _, size in entries)
    names = sum(len(arcname.encode('utf-8')) for _, arcname, _ in entries)
    return payload + 2 * names + ZIP_ENTRY_OVERHEAD * len(entries) + ZIP_TRAILER_OVERHEAD


def content_disposition(filename):
    """Build an attachment header that survives spaces, quotes, and non-ASCII names.

    Plain ASCII goes in the quoted form every client understands; the RFC 5987
    ``filename*`` form carries the real name for anything with an em dash or CJK in it.
    """
    fallback = ''.join(character if 32 <= ord(character) < 127 and character not in '"\\'
                       else '_' for character in filename) or 'download'
    encoded = quote(filename, safe='')
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def suggested_archive_name(selected_paths, entries):
    """Name the ZIP after the folder when there is exactly one, otherwise generically."""
    if len(selected_paths) == 1:
        base = os.path.basename(selected_paths[0].replace('\\', '/').rstrip('/'))
        if base:
            return f'{base}.zip'
    return f'dropit-{len(entries)}-files.zip'


class _ChunkSink:
    """Collects what zipfile writes so the generator can hand it straight to the socket.

    Reporting seekable() as False makes zipfile emit data descriptors, which is what lets
    the archive be produced in one pass without ever knowing a file's CRC in advance.
    """

    def __init__(self):
        self.chunks = []
        self.position = 0

    def write(self, data):
        data = bytes(data)
        self.chunks.append(data)
        self.position += len(data)
        return len(data)

    def drain(self):
        chunks, self.chunks = self.chunks, []
        return chunks

    def flush(self):
        pass

    def seekable(self):
        return False

    def tell(self):
        return self.position


def positive_gigabytes(value):
    """Argparse type that accepts whole gigabytes greater than zero."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f'{value!r} is not a whole number of gigabytes')
    if size < 1:
        raise argparse.ArgumentTypeError('--maxsize must be at least 1 GB')
    return size


def build_parser():
    """Build the command-line parser for the server."""
    parser = argparse.ArgumentParser(
        prog='dropit',
        description='File server with optional basic authentication.',
    )
    parser.add_argument('--version', action='version', version=f'dropit v{__version__}')
    parser.add_argument('--password', help='Set the password for basic authentication.', default=None)
    parser.add_argument('--geturl', action='store_true', help='Print the URL')
    parser.add_argument('--getqr', action='store_true', help='Display a QR code')
    parser.add_argument(
        '--http',
        action='store_true',
        help='Serve plain HTTP instead of HTTPS. No certificate warning, but traffic is unencrypted.',
    )
    parser.add_argument(
        '--maxsize',
        type=positive_gigabytes,
        default=DEFAULT_MAX_UPLOAD_GB,
        help=f'Maximum file upload size in GB (default: {DEFAULT_MAX_UPLOAD_GB}GB)',
    )
    return parser


# Initialize the Flask application.
app = Flask(__name__)
# Configuration settings for the Flask application.
home_path = os.path.expanduser('~/sharex/')  # Default directory for uploads/downloads.
app.config['UPLOAD_FOLDER'] = home_path
app.config['MAX_CONTENT_LENGTH'] = DEFAULT_MAX_UPLOAD_GB * BYTES_PER_GB
app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = None
app.config['BASIC_AUTH_FORCE'] = False
basic_auth = BasicAuth(app)


def configure_app(password=None, maxsize=DEFAULT_MAX_UPLOAD_GB):
    """Apply command-line settings to the Flask application."""
    app.config['MAX_CONTENT_LENGTH'] = maxsize * BYTES_PER_GB
    app.config['BASIC_AUTH_PASSWORD'] = password
    app.config['BASIC_AUTH_FORCE'] = bool(password)  # Force basic auth if password is set.

# The server hands out files from UPLOAD_FOLDER over the local network. Every route below
# resolves user-supplied paths through resolve_shared_path() so nothing outside that folder
# can be read, written, or deleted, and state-changing requests are checked for same-origin.

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


SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})


@app.before_request
def block_cross_site_writes():
    """Reject state-changing requests that a different site tried to make on the user's behalf.

    Browsers attach an ``Origin`` header to every POST, so a mismatch means another page
    submitted the request. Tools such as curl send no ``Origin`` at all and stay unaffected.
    """
    if request.method in SAFE_METHODS:
        return None

    origin = request.headers.get('Origin')
    if not origin:
        return None
    if urlsplit(origin).netloc == request.host:
        return None

    return jsonify({'ok': False, 'error': 'Cross-site requests are not allowed.'}), 403


FILE_TYPE_GROUPS = {
    'document': {'pdf', 'txt', 'rtf', 'md', 'doc', 'docx', 'odt', 'ppt', 'pptx', 'odp'},
    'spreadsheet': {'csv', 'xls', 'xlsx', 'ods'},
    'image': {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'tif', 'tiff', 'heic', 'avif'},
    'audio': {'mp3', 'flac', 'wav', 'm4a', 'aac', 'ogg', 'opus', 'wma'},
    'video': {'mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v', 'mpeg', 'mpg'},
    'archive': {'zip', '7z', 'rar', 'tar', 'gz', 'bz2', 'xz', 'tgz'},
    'code': {'py', 'js', 'ts', 'css', 'scss', 'html', 'htm', 'xml', 'json', 'yaml', 'yml', 'sh', 'php', 'java', 'c', 'cpp', 'h'},
}


def classify_file(filename):
    """Return a stable category and icon name for a file extension."""
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'file'
    category = 'other'
    for group, extensions in FILE_TYPE_GROUPS.items():
        if extension in extensions:
            category = group
            break

    icon = 'pdf' if extension == 'pdf' else category
    return extension, category, icon


def resolve_shared_path(relative_path='', require_directory=False):
    """Resolve a user-facing relative path without allowing it outside the share root."""
    root = os.path.realpath(app.config['UPLOAD_FOLDER'])
    requested = (relative_path or '').replace('\\', '/')
    if '\x00' in requested:
        abort(404)

    requested_parts = [part for part in requested.split('/') if part not in ('', '.')]
    if '..' in requested_parts:
        abort(404)

    normalized = os.path.normpath(requested).lstrip('/\\')
    if normalized == '.':
        normalized = ''

    unresolved_candidate = os.path.abspath(os.path.join(root, normalized))
    try:
        inside_root = os.path.commonpath([root, unresolved_candidate]) == root
    except ValueError:
        inside_root = False

    if not inside_root:
        abort(404)

    current_component = root
    for path_part in [part for part in normalized.split('/') if part]:
        current_component = os.path.join(current_component, path_part)
        if os.path.islink(current_component):
            abort(404)

    candidate = os.path.realpath(unresolved_candidate)
    try:
        inside_root = os.path.commonpath([root, candidate]) == root
    except ValueError:
        inside_root = False

    if not inside_root:
        abort(404)
    if require_directory and not os.path.isdir(candidate):
        abort(404)

    return candidate, normalized.replace(os.sep, '/')


def resolve_upload_target(current_path, client_filename):
    """Map a browser-supplied upload name onto a safe directory and bare filename.

    A dragged folder sends names like ``holiday/2024/IMG_1.jpg``. The leading segments are
    recreated as real folders under the current one; ``..`` and absolute paths are stripped
    first and the result still goes through resolve_shared_path(), so an upload can never
    land outside the share root.
    """
    cleaned = (client_filename or '').replace('\\', '/').replace('\x00', '')
    parts = [part for part in cleaned.split('/') if part not in ('', '.', '..')]
    if not parts:
        return None

    filename = parts[-1]
    relative = '/'.join([part for part in [current_path, *parts[:-1]] if part])
    directory, _ = resolve_shared_path(relative, require_directory=False)

    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        abort(409)

    if not os.path.isdir(directory):
        abort(409)
    return directory, filename


def save_upload_without_overwrite(directory, file_storage, filename):
    """Write an upload privately, then publish it atomically under an unused name."""
    stem, extension = os.path.splitext(filename)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix='.__dropit_upload_',
        suffix='.part',
        dir=directory,
    )

    try:
        destination_file = os.fdopen(descriptor, 'wb')
        descriptor = None
        with destination_file:
            file_storage.save(destination_file)
            destination_file.flush()
            os.fsync(destination_file.fileno())

        use_hard_link = os.name != 'nt'
        copy_number = 0
        while True:
            saved_name = filename if copy_number == 0 else f"{stem} ({copy_number}){extension}"
            destination = os.path.join(directory, saved_name)

            try:
                if use_hard_link:
                    os.link(temporary_path, destination)
                else:
                    # Windows os.rename() refuses to clobber, and filesystems without hard
                    # links get the same guarantee by reserving the name with O_EXCL first.
                    os.close(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
                    os.replace(temporary_path, destination)
                    temporary_path = None
                break
            except FileExistsError:
                copy_number += 1
                continue
            except OSError:
                if not use_hard_link:
                    raise
                # This filesystem cannot hard link (exFAT, some network mounts); reserve instead.
                use_hard_link = False
                continue

        return saved_name
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                os.remove(temporary_path)
            except OSError:
                pass

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
    requested_path = request.values.get('path', '')
    current_directory, current_path = resolve_shared_path(requested_path, require_directory=True)

    if request.method == 'POST':
        files = request.files.getlist('files')
        for file in files:
            if not file or not file.filename:
                continue

            target = resolve_upload_target(current_path, file.filename)
            if target is None:
                continue
            directory, filename = target
            save_upload_without_overwrite(directory, file, filename)

        return redirect(url_for('index', path=current_path) if current_path else url_for('index'))

    items = []
    folder_count = 0
    file_count = 0
    total_size_bytes = 0

    try:
        directory_entries = os.scandir(current_directory)
    except FileNotFoundError:
        abort(404)
    except PermissionError:
        abort(403)

    with directory_entries:
        for entry in directory_entries:
            try:
                if entry.name.startswith('.__dropit_upload_') and entry.name.endswith('.part'):
                    continue
                if entry.is_symlink():
                    continue

                item_path = '/'.join(part for part in (current_path, entry.name) if part)
                if entry.is_dir(follow_symlinks=False):
                    folder_count += 1
                    items.append({
                        'name': entry.name,
                        'path': item_path,
                        'kind': 'folder',
                        'type': 'Folder',
                        'category': 'folder',
                        'icon': 'folder',
                        'size': '—',
                        'size_bytes': 0,
                        'open_url': url_for('index', path=item_path),
                        'download_url': '',
                        'delete_url': url_for('delete_file', filename=item_path),
                        'is_image': False,
                        'thumbnail': False,
                    })
                    continue

                if not entry.is_file(follow_symlinks=False):
                    continue

                size_bytes = entry.stat(follow_symlinks=False).st_size
                size, unit = format_size(size_bytes)
                extension, category, icon = classify_file(entry.name)
                file_count += 1
                total_size_bytes += size_bytes
                items.append({
                    'name': entry.name,
                    'path': item_path,
                    'kind': 'file',
                    'type': extension,
                    'category': category,
                    'icon': icon,
                    'size': f"{size} {unit}",
                    'size_bytes': size_bytes,
                    'open_url': url_for('download_file', filename=item_path),
                    'download_url': url_for('download_file', filename=item_path),
                    'delete_url': url_for('delete_file', filename=item_path),
                    'is_image': category == 'image',
                    'thumbnail': category == 'image' and size_bytes <= THUMBNAIL_MAX_BYTES,
                })
            except (FileNotFoundError, PermissionError):
                continue

    items.sort(key=lambda item: (item['kind'] != 'folder', item['name'].lower()))

    breadcrumbs = [{'name': 'Shared Files', 'url': url_for('index')}]
    path_parts = [part for part in current_path.split('/') if part]
    for index_number, part in enumerate(path_parts):
        breadcrumb_path = '/'.join(path_parts[:index_number + 1])
        breadcrumbs.append({'name': part, 'url': url_for('index', path=breadcrumb_path)})

    parent_path = '/'.join(path_parts[:-1])
    parent_url = None
    if path_parts:
        parent_url = url_for('index', path=parent_path) if parent_path else url_for('index')

    total_size, total_unit = format_size(total_size_bytes)
    max_upload_bytes = app.config['MAX_CONTENT_LENGTH'] or 0
    max_upload_size, max_upload_unit = format_size(max_upload_bytes)
    return render_template(
        'index.html',
        items=items,
        current_path=current_path,
        breadcrumbs=breadcrumbs,
        parent_url=parent_url,
        folder_count=folder_count,
        file_count=file_count,
        total_size=f"{total_size} {total_unit}",
        max_upload_bytes=max_upload_bytes,
        max_upload_label=f"{max_upload_size} {max_upload_unit}",
    )


@app.errorhandler(413)
def upload_too_large(_error):
    """Explain the size limit instead of leaving the browser with a dead connection."""
    size, unit = format_size(app.config['MAX_CONTENT_LENGTH'] or 0)
    return jsonify({
        'ok': False,
        'error': f'That upload is larger than the {size} {unit} limit. '
                 f'Restart dropit with a bigger --maxsize to raise it.',
    }), 413

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

@app.route('/files/<path:filename>')
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
    file_path, normalized_path = resolve_shared_path(filename)
    if not os.path.isfile(file_path):
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], normalized_path)


@app.route('/download-selection', methods=['POST'])
@optional_auth
def download_selection():
    """Stream the selected files and folders, as one file or as a ZIP.

    Nothing is staged on disk first: the archive is produced while it is being sent, so a
    multi-gigabyte folder starts downloading immediately instead of after a long silence.
    """
    selected_paths = request.form.getlist('paths')
    token = (request.form.get('token') or '').strip()[:64]
    entries = collect_download_entries(selected_paths)

    if not entries:
        abort(400)

    if len(entries) == 1 and len(selected_paths) == 1 and os.path.isfile(
            resolve_shared_path(selected_paths[0])[0]):
        disk_path, arcname, size = entries[0]
        download_name = os.path.basename(arcname)
        _progress_start(token, size, download_name)

        def stream_file():
            sent = 0
            try:
                with open(disk_path, 'rb') as source:
                    while True:
                        chunk = source.read(STREAM_CHUNK_BYTES)
                        if not chunk:
                            break
                        sent += len(chunk)
                        _progress_advance(token, sent)
                        yield chunk
            except GeneratorExit:
                _progress_finish(token, failed=True)
                raise
            except OSError:
                _progress_finish(token, failed=True)
                raise
            else:
                _progress_finish(token)

        return Response(
            stream_file(),
            mimetype='application/octet-stream',
            headers={
                'Content-Length': str(size),
                'Content-Disposition': content_disposition(download_name),
            },
        )

    archive_name = suggested_archive_name(selected_paths, entries)
    total = archive_size(entries)
    _progress_start(token, total, archive_name)

    def stream_archive():
        sink = _ChunkSink()
        sent = 0
        try:
            with zipfile.ZipFile(sink, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for disk_path, arcname, size in entries:
                    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_STORED
                    info.file_size = size
                    # force_zip64 keeps every entry's header the same shape, which is what
                    # makes archive_size() exact and removes the 4 GB per-file ceiling.
                    with archive.open(info, 'w', force_zip64=True) as destination:
                        with open(disk_path, 'rb') as source:
                            remaining = size
                            while remaining > 0:
                                chunk = source.read(min(STREAM_CHUNK_BYTES, remaining))
                                if not chunk:
                                    # File shrank mid-read; pad so the length still matches
                                    # the Content-Length we already promised the client.
                                    chunk = b'\0' * remaining
                                destination.write(chunk)
                                remaining -= len(chunk)
                                for piece in sink.drain():
                                    sent += len(piece)
                                    _progress_advance(token, sent)
                                    yield piece
                    for piece in sink.drain():
                        sent += len(piece)
                        _progress_advance(token, sent)
                        yield piece
            for piece in sink.drain():
                sent += len(piece)
                _progress_advance(token, sent)
                yield piece
        except GeneratorExit:
            _progress_finish(token, failed=True)
            raise
        except OSError:
            _progress_finish(token, failed=True)
            raise
        else:
            _progress_finish(token)

    return Response(
        stream_archive(),
        mimetype='application/zip',
        headers={
            'Content-Length': str(total),
            'Content-Disposition': content_disposition(archive_name),
        },
    )


@app.route('/certificate')
@optional_auth
def certificate_download():
    """Hand out the server certificate so a device can trust it permanently.

    Tapping this on Android or iOS starts the system's certificate install flow, which is
    the only way to stop the browser warning for good.
    """
    if not os.path.isfile(CERTIFICATE_PATH):
        abort(404)
    with open(CERTIFICATE_PATH, 'rb') as cert_file:
        body = cert_file.read()
    return Response(
        body,
        mimetype='application/x-x509-ca-cert',
        headers={
            'Content-Length': str(len(body)),
            'Content-Disposition': content_disposition('dropit-certificate.crt'),
        },
    )


@app.route('/download-progress/<token>')
@optional_auth
def download_progress(token):
    """Report how much of an in-flight download has been written."""
    with _download_progress_lock:
        entry = _download_progress.get(token)
        snapshot = dict(entry) if entry else None

    if snapshot is None:
        return jsonify({'known': False})

    snapshot.pop('updated', None)
    snapshot['known'] = True
    return jsonify(snapshot)


@app.route('/delete/<path:filename>', methods=['POST'])
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
    file_path, normalized_path = resolve_shared_path(filename)
    if not normalized_path:
        abort(400)
    if not os.path.exists(file_path):
        abort(404)

    try:
        if os.path.isdir(file_path):
            os.rmdir(file_path)
        else:
            os.remove(file_path)
    except FileNotFoundError:
        abort(404)
    except PermissionError:
        return jsonify({'ok': False, 'error': 'Permission denied while deleting this item.'}), 403
    except OSError as error:
        if error.errno in (errno.ENOTEMPTY, errno.EEXIST):
            return jsonify({'ok': False, 'error': 'The folder must be empty before it can be deleted.'}), 409
        return jsonify({'ok': False, 'error': 'This item could not be deleted.'}), 409

    return jsonify({'ok': True, 'path': normalized_path})

def get_ip():
    """
    Retrieves the local IP address of the server.

    This utility function fetches the local IP address by creating a temporary socket
    connection to an external point (Google's DNS server at 8.8.8.8).

    Falls back to the loopback address when the machine is offline, so the server still
    starts and can be reached from the same computer.

    Returns:
    - str: The local IP address.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('8.8.8.8', 80))
        return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        probe.close()


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


def print_colored_ip(ip, port, lag, cl=True, scheme='https'):
    """
    Cycles through colors and prints the server's IP address and port in the terminal.

    This function is designed to catch the user's attention by displaying the IP address and port in various colors.
    It can optionally clear the terminal before printing each color variant.

    Parameters:
    - ip (str): The IP address of the server.
    - port (int): The port number on which the server is running.
    - lag (float): Time in seconds to wait between color changes.
    - cl (bool): If True, clear the terminal between color changes.
    - scheme (str): 'https' or 'http', matching how the server was started.
    """
    colors = ["\033[1;32m", "\033[1;34m", "\033[1;31m", "\033[1;33m", "\033[1;35m", "\033[1;36m"]
    for color in colors:
        if cl:
            os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{color}The URL to enter on your other device connected to the same wifi network is: {scheme}://{ip}:{port}\033[0m")
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


def certificate_names(ip):
    """Every name and address this machine may be reached by on the local network."""
    hostname = socket.gethostname()
    dns_names = ['localhost']
    for name in (hostname, f'{hostname}.local'):
        if name and name not in dns_names:
            dns_names.append(name)

    addresses = ['127.0.0.1']
    if ip and ip not in addresses:
        addresses.append(ip)
    return dns_names, addresses


def certificate_is_usable(cert_path, ip):
    """True when the stored certificate is still valid and covers the current address."""
    from cryptography import x509

    try:
        with open(cert_path, 'rb') as cert_file:
            certificate = x509.load_pem_x509_certificate(cert_file.read())
    except (OSError, ValueError):
        return False

    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        not_after = certificate.not_valid_after_utc
    except AttributeError:  # cryptography < 42
        not_after = certificate.not_valid_after.replace(tzinfo=datetime.timezone.utc)
    if not_after <= now + datetime.timedelta(days=1):
        return False

    try:
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False

    covered = {str(address) for address in san.get_values_for_type(x509.IPAddress)}
    return ip in covered


def write_certificate(ip):
    """Create a long-lived self-signed certificate for this machine's local addresses."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    dns_names, addresses = certificate_names(ip)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ip or 'localhost'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Dropit'),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=CERTIFICATE_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(name) for name in dns_names]
                + [x509.IPAddress(ipaddress.ip_address(address)) for address in addresses]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    os.makedirs(CONFIG_DIR, exist_ok=True)
    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # Create the key with owner-only permissions before any bytes reach the disk.
    descriptor = os.open(PRIVATE_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'wb') as key_file:
        key_file.write(key_bytes)

    with open(CERTIFICATE_PATH, 'wb') as cert_file:
        cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))


def ensure_certificate(ip):
    """Return a (certificate, key) pair, reusing the stored one whenever it still fits.

    Reusing the certificate is what lets a phone or laptop trust Dropit once instead of
    warning on every single run, which is what an ad-hoc, regenerated certificate does.
    """
    have_both = os.path.isfile(CERTIFICATE_PATH) and os.path.isfile(PRIVATE_KEY_PATH)
    if not (have_both and certificate_is_usable(CERTIFICATE_PATH, ip)):
        write_certificate(ip)
    return CERTIFICATE_PATH, PRIVATE_KEY_PATH


QUIET_SOCKET_ERRNOS = frozenset({
    errno.EBADF, errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN, errno.ECONNABORTED,
})

STATUS_COLORS = {'2': 'green', '3': 'cyan', '4': 'yellow', '5': 'red'}


def shorten_path(path, width=44):
    """Trim a long path from the middle so the extension stays readable."""
    if len(path) <= width:
        return path
    keep = width - 1
    head = keep // 2
    return f"{path[:head]}…{path[-(keep - head):]}"


class ConsoleLog:
    """Human-readable server output.

    Runs of identical lines are collapsed: streaming one video produces dozens of 206
    range requests, and left alone they bury everything actually worth reading.
    """

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.use_color = bool(getattr(self.stream, 'isatty', lambda: False)())
        self._lock = threading.Lock()
        self._last_line = None
        self._repeats = 0
        self._hinted = set()

    def _write(self, text):
        self.stream.write(text + '\n')
        self.stream.flush()

    def _paint(self, text, color):
        return print_colored(text, color) if (self.use_color and color) else text

    def _flush_repeats(self):
        if self._repeats > 1:
            self._write(self._paint(f"          ⤷ repeated {self._repeats} times", 'blue'))
        self._last_line = None
        self._repeats = 0

    def request(self, address, method, path, status_line):
        code = status_line.split(' ', 1)[0]
        key = (address, method, path, code)
        with self._lock:
            if key == self._last_line:
                self._repeats += 1
                return
            self._flush_repeats()
            self._last_line = key
            self._repeats = 1
            line = (f"{time.strftime('%H:%M:%S')}  {address:<15} {method:<4} "
                    f"{shorten_path(path):<44} {code}")
            self._write(self._paint(line, STATUS_COLORS.get(code[:1])))

    def note(self, message, color='yellow'):
        with self._lock:
            self._flush_repeats()
            self._write(self._paint(f"{time.strftime('%H:%M:%S')}  {message}", color))

    def note_once(self, key, message, color='yellow'):
        """Say something actionable the first time only, then stay quiet about it."""
        with self._lock:
            if key in self._hinted:
                return
            self._hinted.add(key)
        self.note(message, color)

    def problem(self, summary, detail=None):
        """An error worth a developer's attention: one line, with the traceback indented."""
        self.note(summary, 'red')
        if detail:
            with self._lock:
                for line in detail.rstrip().splitlines():
                    self._write(f"    {line}")


console = ConsoleLog()


# cheroot reports some conditions as a plain message with no exception attached, so the
# same wording has to be recognisable from the text alone.
CONNECTION_HINTS = (
    (('HTTP_REQUEST',),
     'A device asked for http:// on the secure port. Use the https:// address shown above, '
     'or restart with --http.'),
    (('CERTIFICATE_UNKNOWN', 'UNKNOWN_CA', 'BAD_CERTIFICATE', 'certificate unknown'),
     'A device refused the certificate. Open /certificate on it and install the certificate, '
     'or restart with --http.'),
)


def describe_connection_text(text):
    """Match cheroot's own wording for conditions it reports without an exception."""
    for markers, message in CONNECTION_HINTS:
        if any(marker in text for marker in markers):
            return message
    return None


def describe_connection_error(exception):
    """Render an expected network hiccup as one sentence, or None if it is a real error.

    Phones pause videos, close tabs mid-download, and abandon speculative connections.
    None of that is a fault in the server, so none of it deserves a traceback.
    """
    if isinstance(exception, ssl.SSLError):
        return describe_connection_text(str(exception)) or 'A device closed the secure connection early.'

    if isinstance(exception, TimeoutError):
        return 'Transfer stopped: the device stopped reading (paused, or moved on).'

    if isinstance(exception, (ConnectionResetError, BrokenPipeError)):
        return 'Transfer cancelled by the device.'

    if isinstance(exception, OSError) and exception.errno in QUIET_SOCKET_ERRNOS:
        return 'Connection closed by the device.'

    return None


def install_quiet_unraisable_hook():
    """Stop the garbage collector from printing tracebacks about already-closed sockets.

    When a transfer is abandoned, cheroot's buffered writer is finalised after its socket
    has gone. CPython then prints a full "Exception ignored in __del__" traceback that the
    user can neither act on nor prevent. Anything that is not that is passed through.
    """
    previous_hook = sys.unraisablehook

    def hook(unraisable):
        exception = unraisable.exc_value
        if isinstance(exception, OSError) and exception.errno in QUIET_SOCKET_ERRNOS:
            return
        if isinstance(exception, ValueError) and 'closed file' in str(exception):
            return
        previous_hook(unraisable)

    sys.unraisablehook = hook


class AccessLog:
    """WSGI middleware that reports each request as one aligned line."""

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        def logging_start_response(status, headers, exc_info=None):
            console.request(
                environ.get('REMOTE_ADDR', '-'),
                environ.get('REQUEST_METHOD', '-'),
                environ.get('PATH_INFO', '-'),
                status,
            )
            return start_response(status, headers, exc_info)

        return self.application(environ, logging_start_response)


def build_quiet_server(base_class):
    """Subclass cheroot's server so its error reporting goes through ConsoleLog."""

    class QuietServer(base_class):
        def error_log(self, msg='', level=20, traceback=False):
            exception = sys.exc_info()[1] if traceback else None

            description = describe_connection_text(msg) if msg else None
            if description is None and exception is not None:
                description = describe_connection_error(exception)

            if description is not None:
                # These are setup hints, not events: saying them once is enough.
                console.note_once(description, description)
                return

            if exception is not None:
                console.problem(
                    f"{msg or 'Server error'}: {type(exception).__name__}: {exception}",
                    traceback_module.format_exc(),
                )
                return

            if msg:
                console.note(msg, 'blue')

    return QuietServer


def serve_forever(wsgi_app, host, port, ssl_files=None, threads=DEFAULT_WORKER_THREADS):
    """Run the app on a threaded, keep-alive capable server.

    Werkzeug's development server sends ``Connection: close`` on every response, so each
    thumbnail, stylesheet, and download pays for a fresh TCP and TLS handshake. Over Wi-Fi
    that is what makes the page crawl once a few devices connect, so prefer cheroot.
    """
    try:
        from cheroot.wsgi import Server as CherootServer
    except ImportError:
        console.note('cheroot is not installed; falling back to the slower development server.')
        from werkzeug.serving import run_simple

        run_simple(host, port, wsgi_app, threaded=True,
                   ssl_context=tuple(ssl_files) if ssl_files else None)
        return

    install_quiet_unraisable_hook()

    server = build_quiet_server(CherootServer)(
        (host, port), wsgi_app, numthreads=threads, request_queue_size=128)
    if ssl_files:
        from cheroot.ssl.builtin import BuiltinSSLAdapter

        server.ssl_adapter = BuiltinSSLAdapter(*ssl_files)

    try:
        server.safe_start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        console.note('Dropit stopped.', 'blue')


def run_app():
    """Parse the command line, prepare the share folder, and start the server."""
    args = build_parser().parse_args()
    configure_app(password=args.password, maxsize=args.maxsize)

    ip = get_ip()
    port = DEFAULT_PORT
    scheme = 'http' if args.http else 'https'
    server_url = f"{scheme}://{ip}:{port}"

    upload_folder = app.config['UPLOAD_FOLDER']
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except OSError as error:
        print(print_colored(f"Could not create the share folder {upload_folder}: {error}", "red"))
        raise SystemExit(1)

    ssl_files = None
    if not args.http:
        try:
            ssl_files = ensure_certificate(ip)
        except (OSError, ValueError) as error:
            print(print_colored(f"Could not prepare the TLS certificate: {error}", "red"))
            print(print_colored("Start with --http to serve without encryption instead.", "yellow"))
            raise SystemExit(1)

    home_hint = "%USERPROFILE%" if os.name == "nt" else "$HOME"
    if args.getqr:
        create_qr_in_terminal(server_url)
    if args.geturl:
        # prints in color but won't clear your QR code
        print_colored_ip(ip, port, 0.5, cl=False, scheme=scheme)

    print(print_colored(f"Server is ready! Access it at: {server_url}", "green"))
    print(print_colored(f"Files are stored in: {upload_folder} (from {home_hint})", "blue"))
    if ssl_files:
        print(print_colored(
            f"Certificate: {CERTIFICATE_PATH} (reused across restarts)", "cyan"))
        print(print_colored(
            f"To stop the warning for good, open {server_url}/certificate on each device "
            f"and install it.", "cyan"))
    else:
        print(print_colored(
            "Serving plain HTTP: traffic is unencrypted and visible to others on this network.",
            "yellow"))

    try:
        serve_forever(AccessLog(app), '0.0.0.0', port, ssl_files=ssl_files)
    except OSError as error:
        if error.errno in (errno.EADDRINUSE, errno.EACCES):
            print(print_colored(f"Port {port} is already in use. Stop the other program and try again.", "red"))
            raise SystemExit(1)
        raise
    except KeyboardInterrupt:
        print()
        print(print_colored("Server stopped.", "blue"))


if __name__ == '__main__':
    run_app()
