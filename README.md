# Dropit – Local HTTPS file drop

Dropit is a small Flask app that lets you share files with other devices on the same network. It runs a local HTTPS server with a drag-and-drop UI for uploading, downloading, and deleting files.

## Install
```bash
pip install dropit
```

Python ≥ 3.6 is supported.

## Commands and flags
```
dropit [--password <password>] [--geturl] [--getqr] [--maxsize <GB>] [--version]
```
- `--password <password>`: enable Basic Auth with username `admin`.
- `--geturl`: print the server URL in color to the terminal.
- `--getqr`: render the URL as an ASCII QR code in the terminal.
- `--maxsize <GB>`: maximum upload size in gigabytes (default: `2`).
- `--version`: print the installed Dropit version and exit.

Examples:
```bash
# start server, print URL + QR
dropit --geturl --getqr

# require a password (user: admin)
dropit --password "mypassword"

# allow larger uploads (10 GB)
dropit --maxsize 10

# just show the installed version
dropit --version
```

## Quick start
```bash
dropit --geturl --getqr
```
Then, from another device on the same network, open the URL shown (e.g., `https://<your-ip>:5001`). Because the certificate is self-signed, your browser will show a warning; proceed/accept for your local session.

## What you get
- Local HTTPS server on port `5001` (self-signed cert generated on the fly).
- Drag-and-drop upload UI with file list (type/size) plus download/delete actions.
- Optional Basic Auth: set a password and use the fixed username `admin`.
- Handy discovery: print the URL (`--geturl`) and an ASCII QR code (`--getqr`).
- Upload size limit configurable via `--maxsize` (default 2 GB).
- Files are stored under your home directory in `sharex` (`$HOME/sharex` on Linux/macOS, `%USERPROFILE%\\sharex` on Windows). The exact resolved path is printed on startup.

## Using the web UI
- Upload: drag files into the drop zone or click to choose files, then hit **Upload Files**.
- Download/Delete: use the action chips next to each file in the list.
- Storage: uploaded files are saved to `~/sharex/` (expanded to your home directory).

## Authentication
- Default: open access.
- To require a password: start with `--password mysecret`. Sign in as `admin` with that password. Basic Auth is only enforced when a password is provided.

## Troubleshooting
- **Browser warning about HTTPS**: the app uses an ad-hoc self-signed cert; choose “proceed” for your local session.
- **Can’t reach the URL**: ensure devices are on the same network and that port `5001` is allowed through firewalls.
- **Upload fails due to size**: increase `--maxsize` to the number of gigabytes you need.

## Contributing
Issues and pull requests are welcome. For significant changes, please open an issue first to discuss what you’d like to adjust.
