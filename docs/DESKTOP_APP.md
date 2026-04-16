# LUMO Desktop App (Non-Invasive Setup)

This project can run as a desktop app without changing your existing website deployment flow.

## What this setup does

- Keeps your existing web app entry points unchanged (`app.py`, Gunicorn, Render/hosting setup).
- Adds a separate desktop launcher at `desktop/launcher.py`.
- Runs Flask locally on `127.0.0.1` and opens it in a native desktop window using `pywebview`.

## Why this does not interfere with your website

- No route changes.
- No blueprint changes.
- No production server command changes.
- Desktop mode is opt-in (you run it only when you want desktop behavior).

## Install desktop-only dependencies

From project root:

```powershell
pip install -r requirements.txt
pip install -r desktop/requirements.txt
```

## Run the desktop app

From project root:

```powershell
python desktop/launcher.py
```

This starts your Flask app on a random localhost port and opens a desktop window.

### Use the same database as your website (optional)

By default desktop mode uses a local SQLite database. To make desktop use the same remote database as your website, set:

```powershell
$env:LUMO_DESKTOP_USE_REMOTE_DB="1"
$env:DATABASE_URL="your_postgres_url"
python desktop/launcher.py
```

Without this flag, desktop and website users/profiles will be different because they are stored in different databases.

### Windows requirement for native window mode

Install **Microsoft Edge WebView2 Runtime**. Without it, launcher will fall back to opening in your browser.

Download: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

## Package as a Windows executable (optional)

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build:

```powershell
pyinstaller --noconfirm --windowed --name LUMO-Desktop desktop/launcher.py
```

For a single-file build, use:

```powershell
pyinstaller --noconfirm --onefile --windowed --name LUMO-Desktop desktop/launcher.py
```

Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File desktop/build_desktop.ps1
```

With custom icon (`.ico`):

```powershell
powershell -ExecutionPolicy Bypass -File desktop/build_desktop.ps1 -IconPath "static/images/logo.ico"
```

Output executable will be in `dist/LUMO-Desktop.exe`.

## Notes

- Your web deployment process stays exactly the same.
- Desktop launcher falls back to opening the app in a browser if native webview fails to initialize.
- On Windows dev runs (`python desktop/launcher.py`), taskbar icon is usually inherited from `python.exe`.
- To set a custom taskbar icon for the single-file build, pass an `.ico` file to the helper script.
- If you need an app icon and installer (`.msi`/`.exe` installer), add those in a later packaging step (Inno Setup, NSIS, or WiX).
