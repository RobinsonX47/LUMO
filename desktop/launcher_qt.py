import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from queue import Queue
from urllib.error import URLError
from urllib.request import urlopen

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, server_thread: threading.Thread, server_errors: Queue, timeout_seconds: float = 120.0) -> None:
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
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as exc:
        server_errors.put(f"Desktop server failed to start: {exc}")


def _configure_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_file = data_dir / "desktop.log"
    logging.basicConfig(filename=str(log_file), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


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

    data_dir = Path(os.environ.get("LUMO_DESKTOP_DATA_DIR") or (Path.home() / "AppData" / "Local" / "LUMO"))
    os.environ["LUMO_DESKTOP_DATA_DIR"] = str(data_dir)
    _configure_logging(data_dir)
    logging.info("LUMO Qt desktop launcher starting")

    port = _find_free_port()
    app_url = f"http://127.0.0.1:{port}"
    readiness_url = f"{app_url}/ready"

    server_errors: Queue = Queue()
    server_thread = threading.Thread(target=_run_server, args=(port, server_errors), daemon=True)
    server_thread.start()

    try:
        _wait_for_server(readiness_url, server_thread, server_errors)
    except Exception as exc:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "LUMO Startup Error", str(exc))
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("LUMO")

    icon_path = runtime_root / "static" / "images" / "logo.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    profile = QWebEngineProfile.defaultProfile()
    profile.setPersistentStoragePath(str(data_dir / "qtwebengine" / "storage"))
    profile.setCachePath(str(data_dir / "qtwebengine" / "cache"))

    view = QWebEngineView()
    view.setWindowTitle("LUMO")
    view.resize(1280, 820)
    view.setMinimumSize(1024, 680)
    view.load(QUrl(app_url))
    view.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
