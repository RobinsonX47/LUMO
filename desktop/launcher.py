import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from queue import Queue
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import urlopen, urlretrieve

import webview
import winreg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(
    url: str,
    server_thread: threading.Thread,
    server_errors: Queue,
    timeout_seconds: float = 120.0,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not server_errors.empty():
            raise RuntimeError(server_errors.get())

        if not server_thread.is_alive():
            raise RuntimeError("Desktop server thread exited before startup completed")

        try:
            with urlopen(url, timeout=2):
                return
        except URLError:
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)

    raise RuntimeError(f"Timed out waiting for desktop server at {url}")


def _configure_desktop_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_file = data_dir / "desktop.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _show_fatal_error(message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("LUMO Startup Error", message)
        root.destroy()
    except Exception:
        pass


def _is_webview2_installed() -> bool:
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Edge\BLBeacon"),
    ]

    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path):
                return True
        except OSError:
            continue

    return False


def _ensure_webview2_runtime() -> bool:
    if _is_webview2_installed():
        return True

    bootstrapper_url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
    installer_path = os.path.join(tempfile.gettempdir(), "MicrosoftEdgeWebView2Setup.exe")

    try:
        logging.info("WebView2 runtime not detected, downloading bootstrapper")
        urlretrieve(bootstrapper_url, installer_path)
        proc = subprocess.run(
            [installer_path, "/silent", "/install"],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        logging.info("WebView2 installer returned exit code %s", proc.returncode)
    except Exception as exc:
        logging.exception("WebView2 install attempt failed: %s", exc)
        return False

    return _is_webview2_installed()


def _run_server(port: int, server_errors: Queue) -> None:
    try:
        from app import create_app

        app = create_app()
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.logger.setLevel(logging.WARNING)

        try:
            from waitress import serve

            serve(app, host="127.0.0.1", port=port, threads=8)
        except Exception:
            app.run(
                host="127.0.0.1",
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
    except Exception as exc:
        server_errors.put(f"Desktop server failed to start: {exc}\n{traceback.format_exc()}")


def _launch_native_window(app_url: str) -> None:
    window = webview.create_window(
        title="LUMO",
        html="""
        <!doctype html>
        <html>
        <head>
            <meta charset=\"utf-8\" />
            <title>Starting LUMO</title>
            <style>
                body { margin:0; background:#0b1220; color:#e2e8f0; font-family:Segoe UI,sans-serif; }
                .wrap { height:100vh; display:grid; place-items:center; }
                .panel { text-align:center; padding:24px; }
            </style>
        </head>
        <body>
            <div class=\"wrap\"><div class=\"panel\"><h2>Starting LUMO...</h2><p>Initializing local desktop app.</p></div></div>
        </body>
        </html>
        """,
        min_size=(1024, 680),
        width=1280,
        height=820,
    )

    def _attach_url(target_window, target_url: str) -> None:
        target_window.load_url(target_url)

    # Use Edge/WebView2 by default so desktop rendering matches the website.
    preferred_gui = os.environ.get("LUMO_WEBVIEW_GUI", "edgechromium").strip() or None
    webview.start(func=_attach_url, args=(window, app_url), gui=preferred_gui, debug=False)


def main() -> None:
    os.environ.setdefault("FLASK_ENV", "desktop")
    os.environ.pop("LUMO_DESKTOP_MODE", None)
    use_remote_db = os.environ.get("LUMO_DESKTOP_USE_REMOTE_DB", "0").strip().lower() in {"1", "true", "yes", "on"}
    if use_remote_db:
        os.environ["LUMO_USE_LOCAL_DB"] = "0"
    else:
        os.environ.setdefault("LUMO_USE_LOCAL_DB", "1")

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal_dir = exe_dir / "_internal"
        if internal_dir.is_dir():
            runtime_root = internal_dir
        else:
            runtime_root = Path(getattr(sys, "_MEIPASS", exe_dir))
    else:
        runtime_root = PROJECT_ROOT
    os.environ["LUMO_RUNTIME_ROOT"] = str(runtime_root)

    os.environ.setdefault(
        "LUMO_DESKTOP_DATA_DIR",
        str(Path.home() / "AppData" / "Local" / "LUMO"),
    )

    desktop_data_dir = Path(os.environ["LUMO_DESKTOP_DATA_DIR"])
    _configure_desktop_logging(desktop_data_dir)
    logging.info("LUMO desktop launcher starting")

    port = _find_free_port()
    app_url = f"http://127.0.0.1:{port}"
    readiness_url = f"{app_url}/ready"

    server_errors: Queue = Queue()
    server_thread = threading.Thread(target=_run_server, args=(port, server_errors), daemon=True)
    server_thread.start()

    try:
        _wait_for_server(readiness_url, server_thread, server_errors, timeout_seconds=120.0)
    except Exception as exc:
        logging.exception("Server readiness failed")
        _show_fatal_error(str(exc))
        raise

    try:
        _launch_native_window(app_url)
        return
    except Exception as exc:
        logging.exception("Native webview init failed on first attempt")

    if _ensure_webview2_runtime():
        try:
            _launch_native_window(app_url)
            return
        except Exception as exc:
            logging.exception("Native webview init failed after runtime install")
            _show_fatal_error(f"Native desktop startup failed after runtime install:\n{exc}")
            raise

    _show_fatal_error(
        "LUMO could not initialize native desktop runtime.\n\n"
        "Install Microsoft Edge WebView2 Runtime and relaunch."
    )
    raise RuntimeError("Native webview initialization failed")


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    main()
