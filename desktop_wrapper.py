import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

import webview
from werkzeug.serving import make_server


HOST = "127.0.0.1"
OAUTH_REDIRECT_HOST = "localhost"
DEFAULT_DESKTOP_PORT = 5000
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
MIN_WIDTH = 1024
MIN_HEIGHT = 640


SPLASH_HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Starting LUMO...</title>
  <style>
    :root {
      --bg-1: #0a1020;
      --bg-2: #111d37;
      --glass: rgba(255, 255, 255, 0.08);
      --text: #e6edf9;
      --muted: #9eb2d7;
      --accent: #7dd3fc;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--text);
      background: radial-gradient(1200px 600px at 20% 10%, #1f335a 0%, var(--bg-1) 50%),
                  linear-gradient(145deg, var(--bg-2), var(--bg-1));
      overflow: hidden;
    }
    .stage {
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .card {
      width: min(92vw, 520px);
      border-radius: 20px;
      padding: 28px;
      background: var(--glass);
      border: 1px solid rgba(255, 255, 255, 0.14);
      backdrop-filter: blur(16px);
      box-shadow: 0 24px 50px rgba(0, 0, 0, 0.35);
      text-align: center;
    }
    h1 {
      margin: 0;
      font-weight: 700;
      letter-spacing: 0.02em;
      font-size: clamp(1.6rem, 2.8vw, 2.1rem);
    }
    p {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 0.98rem;
    }
    .bar {
      margin-top: 20px;
      width: 100%;
      height: 6px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.1);
      overflow: hidden;
    }
    .bar > span {
      display: block;
      height: 100%;
      width: 40%;
      border-radius: 999px;
      background: linear-gradient(90deg, #7dd3fc, #bae6fd);
      animation: loading 1.15s ease-in-out infinite;
      transform-origin: left center;
    }
    @keyframes loading {
      0% { transform: translateX(-90%) scaleX(0.8); }
      50% { transform: translateX(95%) scaleX(1); }
      100% { transform: translateX(230%) scaleX(0.8); }
    }
  </style>
</head>
<body>
  <div class=\"stage\">
    <div class=\"card\">
      <h1>Starting LUMO</h1>
      <p>Initializing local server and desktop shell...</p>
      <div class=\"bar\"><span></span></div>
    </div>
  </div>
</body>
</html>
"""


DRAG_REGION_SCRIPT = r"""
(function () {
  if (window.__lumoDragRegionsInstalled) return;
  window.__lumoDragRegionsInstalled = true;

  function onDown(e) {
    if (e.button !== 0) return;
    if (e.target && e.target.closest && e.target.closest('button, a, input, select, textarea, [data-no-drag="true"]')) {
      return;
    }
    if (window.pywebview && window.pywebview.api && window.pywebview.api.begin_window_drag) {
      window.pywebview.api.begin_window_drag();
    }
  }

  function onUp() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.end_window_drag) {
      window.pywebview.api.end_window_drag();
    }
  }

  function wire() {
    var regions = document.querySelectorAll('[data-drag-region="true"], .desktop-drag-region, header, .app-header, .topbar');
    for (var i = 0; i < regions.length; i += 1) {
      var region = regions[i];
      if (region.dataset.lumoDragBound === '1') continue;
      region.dataset.lumoDragBound = '1';
      region.addEventListener('mousedown', onDown);
      region.addEventListener('mouseup', onUp);
      region.addEventListener('mouseleave', onUp);
    }
  }

  wire();

  var observer = new MutationObserver(function () { wire(); });
  observer.observe(document.documentElement || document.body, {
    childList: true,
    subtree: true
  });

  function syncNativeFullscreen(isFullscreen) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_native_fullscreen) {
      window.pywebview.api.set_native_fullscreen(Boolean(isFullscreen));
    }
  }

  function nativeFullscreenFromDocument() {
    return Boolean(document.fullscreenElement || document.webkitFullscreenElement);
  }

  document.addEventListener('fullscreenchange', function () {
    syncNativeFullscreen(nativeFullscreenFromDocument());
  });

  document.addEventListener('webkitfullscreenchange', function () {
    syncNativeFullscreen(nativeFullscreenFromDocument());
  });

  // Provide a consistent native fullscreen shortcut in desktop mode.
  window.addEventListener('keydown', function (e) {
    if (e.key === 'F11') {
      e.preventDefault();
      syncNativeFullscreen(!nativeFullscreenFromDocument());
    }
    if (e.key === 'Escape') {
      syncNativeFullscreen(false);
    }
  }, true);
})();
"""


def _runtime_root() -> Path:
  if getattr(sys, "frozen", False):
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
  return Path(__file__).resolve().parent


def _find_free_port() -> int:
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((HOST, 0))
    return int(sock.getsockname()[1])


def _port_is_available(port: int) -> bool:
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      sock.bind((HOST, port))
      return True
    except OSError:
      return False


class _ServerThread(threading.Thread):
  def __init__(self, host: str, port: int) -> None:
    super().__init__(daemon=True)
    self.host = host
    self.port = port
    self._server = None

  def run(self) -> None:
    from app import create_app

    app = create_app()
    self._server = make_server(self.host, self.port, app, threaded=True)
    self._server.serve_forever()

  def shutdown(self) -> None:
    if self._server is not None:
      self._server.shutdown()
      self._server.server_close()


def _wait_for_backend(url: str, timeout_seconds: float = 120.0) -> None:
  deadline = time.time() + timeout_seconds
  while time.time() < deadline:
    try:
      with urlopen(url, timeout=2):
        return
    except URLError:
      time.sleep(0.15)
    except Exception:
      time.sleep(0.15)
  raise TimeoutError(f"Timed out waiting for backend: {url}")


class DesktopBridge:
  def __init__(self, window: webview.Window):
    self.window = window
    self._native_fullscreen = False

  def begin_window_drag(self) -> bool:
    # Try the native drag API first when available.
    for method_name in ("start_drag", "drag", "begin_move_drag"):
      method = getattr(self.window, method_name, None)
      if callable(method):
        method()
        return True

    set_easy_drag = getattr(self.window, "set_easy_drag", None)
    if callable(set_easy_drag):
      set_easy_drag(True)
      return True

    return False

  def end_window_drag(self) -> bool:
    set_easy_drag = getattr(self.window, "set_easy_drag", None)
    if callable(set_easy_drag):
      set_easy_drag(False)
      return True
    return False

  def set_native_fullscreen(self, enabled: bool) -> bool:
    enabled = bool(enabled)
    if enabled == self._native_fullscreen:
      return True

    # Prefer explicit fullscreen setter methods when available.
    set_fullscreen = getattr(self.window, "set_fullscreen", None)
    if callable(set_fullscreen):
      set_fullscreen(enabled)
      self._native_fullscreen = enabled
      return True

    fullscreen_method = getattr(self.window, "fullscreen", None)
    if callable(fullscreen_method):
      try:
        fullscreen_method(enabled)
      except TypeError:
        fullscreen_method()
      self._native_fullscreen = enabled
      return True

    toggle_fullscreen = getattr(self.window, "toggle_fullscreen", None)
    if callable(toggle_fullscreen):
      toggle_fullscreen()
      self._native_fullscreen = enabled
      return True

    return False


def main() -> None:
  root = _runtime_root()
  desktop_data_dir = Path.home() / "AppData" / "Local" / "LUMO"
  desktop_data_dir.mkdir(parents=True, exist_ok=True)

  os.environ.setdefault("FLASK_ENV", "desktop")
  os.environ.setdefault("LUMO_RUNTIME_ROOT", str(root))
  os.environ.pop("LUMO_DESKTOP_MODE", None)
  os.environ.setdefault("LUMO_DESKTOP_DATA_DIR", str(desktop_data_dir))
  os.environ.setdefault("LUMO_USE_LOCAL_DB", "1")

  # Keep OAuth redirect URI stable across launches for Google Console matching.
  configured_port = os.environ.get("LUMO_DESKTOP_PORT", str(DEFAULT_DESKTOP_PORT)).strip()
  try:
    port = int(configured_port)
  except ValueError:
    raise RuntimeError(f"Invalid LUMO_DESKTOP_PORT value: {configured_port}")

  if not _port_is_available(port):
    raise RuntimeError(
      f"Desktop port {port} is already in use. Close the app/process using it or set LUMO_DESKTOP_PORT to a free port."
    )

  app_url = f"http://{HOST}:{port}"
  ready_url = f"{app_url}/ready"
  os.environ.setdefault("GOOGLE_REDIRECT_URI", f"http://{OAUTH_REDIRECT_HOST}:{port}/auth/callback/google")
  server = _ServerThread(HOST, port)
  startup_error: Optional[str] = None

  window = webview.create_window(
    title="LUMO",
    html=SPLASH_HTML,
    frameless=False,
    easy_drag=False,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    min_size=(MIN_WIDTH, MIN_HEIGHT),
    resizable=True,
  )

  bridge = DesktopBridge(window)
  window.expose(bridge.begin_window_drag, bridge.end_window_drag, bridge.set_native_fullscreen)

  def on_loaded() -> None:
    try:
      window.evaluate_js(DRAG_REGION_SCRIPT)
    except Exception:
      pass

  def on_closed() -> None:
    try:
      server.shutdown()
    except Exception:
      pass

  window.events.loaded += on_loaded
  window.events.closed += on_closed

  def bootstrap() -> None:
    nonlocal startup_error
    try:
      server.start()
      _wait_for_backend(ready_url)
      window.load_url(app_url)
    except Exception as exc:
      startup_error = f"{exc}\n\n{traceback.format_exc()}"
      window.load_html(
        "<h2 style='font-family:Segoe UI,sans-serif'>LUMO failed to start.</h2>"
        "<pre style='white-space:pre-wrap;font-family:Consolas,monospace'>"
        + startup_error
        + "</pre>"
      )

  webview.start(
    func=bootstrap,
    gui="edgechromium",
    debug=False,
    private_mode=False,
  )

  if startup_error:
    raise RuntimeError(startup_error)


if __name__ == "__main__":
  from multiprocessing import freeze_support

  freeze_support()
  main()
