# Dropit – Local HTTPS file drop

Dropit is a small Flask app that lets you share files with other devices on the same network. It runs a local HTTPS server with a drag-and-drop UI for uploading, downloading, and deleting files.

## Install
```bash
pip install dropit
```

Python ≥ 3.9 is supported.

## Commands and flags
```
dropit [--password <password>] [--geturl] [--getqr] [--maxsize <GB>] [--http] [--version]
```
- `--password <password>`: enable Basic Auth with username `admin`.
- `--http`: serve plain HTTP instead of HTTPS — no certificate warning, but traffic is unencrypted.
- `--geturl`: print the server URL in color to the terminal.
- `--getqr`: render the URL as an ASCII QR code in the terminal.
- `--maxsize <GB>`: maximum upload size in gigabytes (default: `2`).
- `--version`: print the installed Dropit version and exit.

Examples:
```bash
# start server and print URL
dropit --geturl

# start server and show an ASCII QR
dropit --getqr

# require a password (user: admin)
dropit --password "mypassword"

# allow larger uploads (10 GB)
dropit --maxsize 10

# just show the installed version
dropit --version

# no certificate warning (unencrypted — trusted networks only)
dropit --http
```

## Quick start
```bash
dropit --geturl
```
Then, from another device on the same network, open the URL shown (e.g., `https://<your-ip>:5001`).

## What you get
- Local HTTPS server on port `5001`, with a certificate that is reused across restarts.
- A file-manager UI: folders, breadcrumbs, search, type filters, details/icon views, image previews.
- Drag-and-drop upload, multi-file download as a ZIP, and delete.
- Optional Basic Auth: set a password and use the fixed username `admin`.
- Handy discovery: print the URL (`--geturl`) and an ASCII QR code (`--getqr`).
- Upload size limit configurable via `--maxsize` (default 2 GB).
- Files are stored under your home directory in `sharex` (`$HOME/sharex` on Linux/macOS, `%USERPROFILE%\\sharex` on Windows). The exact resolved path is printed on startup.
- A keep-alive HTTP server (cheroot) with a worker pool, so several devices can browse while
  others download.

## Certificates and the browser warning
Dropit serves HTTPS with a self-signed certificate stored at `~/.dropit/cert.pem`. It is
generated once, covers `localhost`, your machine's hostname, and your current LAN IP, and is
**reused on every restart** — so a device only has to be told to trust it once, rather than on
every run.

Three ways to deal with the warning, in order of least friction:

1. **Accept it per device.** Tap through the browser's "advanced → proceed" prompt. Because the
   certificate no longer changes between runs, most browsers stop asking after the first time.
2. **Install the certificate as trusted.** Open **`https://<your-ip>:5001/certificate`** on the
   device — that downloads the certificate and starts the system install flow. Then finish it
   (Android: *Settings → Security → Encryption & credentials → Install a certificate → CA
   certificate*; iOS: *Settings → General → VPN & Device Management* to install, then *General →
   About → Certificate Trust Settings* to enable full trust; macOS: open it in Keychain Access
   and mark it *Always Trust*). The warning is then gone for good.

   **This is the fix if downloads fail.** A phone's download manager is a separate component
   from the browser and does not inherit the "proceed anyway" exception you tapped through, so
   it rejects the certificate on its own and the transfer dies. Dropit prints a hint the first
   time it sees this.
3. **Skip TLS entirely** with `dropit --http` for devices that refuse self-signed certificates.
   There is no warning at all, but everything — including your `--password` credentials — travels
   the network in the clear, so only do this on a network you trust.

Dropit regenerates the certificate automatically if your LAN IP changes or it is about to expire.

## Using the web UI
- **Actions**: right-click an item (long-press on a phone or tablet) to get **Open**, **Select**,
  **Download**, and **Delete**. Right-clicking empty space in the list offers **Upload Files**,
  **Select All**, **Clear Selection**, and **Refresh**.
- **Selecting**: a plain click never selects, so you can browse without disturbing a selection.
  Use the row checkbox, the context menu's **Select**, `Ctrl`/`Cmd`-click to add one item, or
  `Shift`-click to extend a range. `Ctrl`/`Cmd`+`A` selects everything currently shown.
- **Opening**: double-click a row, or press `Enter` on the focused row. Folders open in place;
  images open in a preview dialog.
- **Downloading**: one selected file downloads directly; several items — or a whole folder —
  stream as a single ZIP that keeps the folder structure. Folders are walked recursively.
  Nothing is staged on disk first, so even a multi-gigabyte folder starts immediately.
- **Progress**: a tray in the bottom corner shows bytes transferred, percentage, speed, and
  time remaining, because the browser's own download manager is invisible to the page.
- **Upload**: drag files anywhere onto the page, or use **Upload** in the toolbar, then
  **Upload Here**. Uploads land in the folder you are currently viewing and never overwrite an
  existing file — a duplicate name is saved as `name (1).ext`.
- **Deleting**: folders must be empty before they can be removed.
- **Storage**: uploaded files are saved to `sharex` under your home directory (`$HOME/sharex` on
  Linux/macOS, `%USERPROFILE%\\sharex` on Windows).

### Keyboard
| Key | Action |
| --- | --- |
| `↑` `↓` `Home` `End` | Move between rows |
| `Space` | Toggle selection of the focused row |
| `Enter` | Open the focused row |
| `Ctrl`/`Cmd` + `A` | Select everything shown |
| `Ctrl`/`Cmd` + `F` | Jump to the search box |
| `Shift` + `F10` / Menu key | Open the context menu for the focused row |
| `Esc` | Close menus, the preview, or the Places panel |

## Authentication
- Default: open access.
- To require a password: start with `--password mysecret`. Sign in as `admin` with that password. Basic Auth is only enforced when a password is provided.

> **Anyone on your network can read, upload to, and delete from the shared folder** while the
> server is running. Without `--password` there is no access control at all, so start it only on
> networks you trust and keep private files out of `~/sharex`.

## Troubleshooting
- **Browser warning about HTTPS**: see [Certificates and the browser warning](#certificates-and-the-browser-warning). Quickest escape hatch is `dropit --http`.
- **A device refuses to open the page at all**: some Android builds will not let you past a self-signed certificate. Use `dropit --http`, or install the certificate as trusted.
- **Slow with several devices connected**: make sure you are on the release that uses the keep-alive server; large images are also served as icons rather than thumbnails past 2 MB.
- **Downloads start then fail on a phone**: the download manager is rejecting the self-signed certificate. Install it from `/certificate`, or use `--http`.
- **`certificate unknown` in the console**: same cause — a device has not been told to trust the certificate. Dropit prints the fix once rather than repeating the alert.
- **Can’t reach the URL**: ensure devices are on the same network and that port `5001` is allowed through firewalls.
- **Upload fails due to size**: increase `--maxsize` to the number of gigabytes you need.
- **Port 5001 is already in use**: stop the other program using it, then start Dropit again.

## Contributing
Issues and pull requests are welcome. For significant changes, please open an issue first to discuss what you’d like to adjust.

### Contribution flow
- Branch from `master` (e.g., `feature/...` or `fix/...`).
- Make your change. If it affects behavior, note how to verify in the PR.
- Quick local checks:
  - Create/activate a virtual env to avoid polluting your global Python: `python3 -m venv .venv && source .venv/bin/activate` (on Windows: `python -m venv .venv` then `.venv\Scripts\activate`)
  - `pip install .` (ensure dependencies and console entry work)
  - `dropit --version` (standalone; prints the version and exits)
  - `dropit --geturl` or `dropit --getqr` (separate run; starts the server and prints URL or QR, shows the resolved storage path)
- Push your branch and open a PR against `master` with a short description and verification steps.
- Releases: bump `dropit/__version__`, tag `vX.Y.Z`, and push the tag to trigger the publish workflow.
- For larger contributions: discuss design/approach in an issue first, keep PRs focused, and add tests/docs alongside code changes so reviewers can validate quickly.
