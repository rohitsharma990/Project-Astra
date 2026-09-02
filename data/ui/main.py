"""Desktop companion host. Run from the repository root with `python ui/main.py`."""
from __future__ import annotations

import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QUrl, QTimer, Qt, Slot
from PySide6.QtWidgets import QApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

try:
    from .backend_bridge import BackendBridge
    from .config import MODEL_PATH, load_settings, save_settings
except ImportError:
    from backend_bridge import BackendBridge
    from config import MODEL_PATH, load_settings, save_settings

UI_DIR = Path(__file__).resolve().parent
INDEX_PATH = UI_DIR / "index.html"
REQUIRED_ASSETS = (
    INDEX_PATH,
    UI_DIR / "app.js",
    UI_DIR / "styles.css",
    UI_DIR / "vendor" / "three.module.js",
    UI_DIR / "vendor" / "GLTFLoader.js",
    MODEL_PATH,
)


class _QuietHandler(SimpleHTTPRequestHandler):
    root: Path

    def log_message(self, format, *args):
        return

    def translate_path(self, path):
        candidate = Path(super().translate_path(path)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return str(self.root / "index.html")
        return str(candidate)


class UiServer:
    """Serve only this UI directory on the local machine."""

    def __init__(self, directory: Path):
        _QuietHandler.root = directory.resolve()
        handler = lambda *args, **kwargs: _QuietHandler(*args, directory=str(directory), **kwargs)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name="astra-ui-server", daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/index.html"

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class UiPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[Astra JS] {source}:{line}: {message}", file=sys.stderr)


class CompanionWindow(QWebEngineView):
    def __init__(self, ui_server: UiServer):
        super().__init__()
        self.ui_server = ui_server
        self.settings_data = load_settings()
        self.bridge = BackendBridge()
        self.setPage(UiPage(self))
        self.setWindowTitle("Astra Companion")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.settings_data["always_on_top"]:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.resize(self.settings_data["width"], self.settings_data["height"])
        self.move(self.settings_data["x"], self.settings_data["y"])
        self.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.page().settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.page().settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.page().settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.channel = QWebChannel(self.page())
        self.channel.registerObject("backend", self.bridge)
        self.channel.registerObject("host", self)
        self.page().setWebChannel(self.channel)
        self.loadFinished.connect(self._page_ready)
        self.bridge.status.connect(self._status_ready)
        self.bridge.response.connect(self._forward_response)
        self.bridge.event.connect(self._forward_event)
        self.loadStarted.connect(lambda: print(f"WebEngine load started: {self.url().toString()}"))
        self.loadFinished.connect(self._page_load_finished)
        final_url = QUrl.fromLocalFile(str(INDEX_PATH))
        print(f"UI directory: {UI_DIR}")
        print(f"index.html absolute path: {INDEX_PATH}")
        print(f"model absolute path: {MODEL_PATH}")
        print(f"model exists = {MODEL_PATH.exists()}")
        print(f"final WebEngine URL: {final_url.toString()}")
        self.load(final_url)
        self.bridge.startup()

    def _page_load_finished(self, loaded: bool):
        print(f"WebEngine load finished: success={loaded} url={self.url().toString()}")
        if loaded:
            self.page().runJavaScript(f"window.astraSettings({json.dumps(self.settings_data)});")
            QTimer.singleShot(3000, self._report_model_load)
        else:
            print(f"WebEngine page load error: url={self.url().toString()}", file=sys.stderr)

    def _report_model_load(self):
        probe = "JSON.stringify({started: window.astraScriptStarted === true, markerType: typeof window.astraModelLoaded, loaded: window.astraModelLoaded === true, loading: document.querySelector('#loading')?.textContent || '', error: window.astraModuleError || ''})"
        self.page().runJavaScript(probe, lambda value: print(f"Three.js GLB probe: {value}"))

    def _page_ready(self, loaded: bool):
        if loaded:
            self.page().runJavaScript(f"window.astraSettings({json.dumps(self.settings_data)});")

    @Slot(int, int)
    def move_companion(self, x: int, y: int):
        self.move(x, y)

    @Slot(result=dict)
    def get_position(self):
        return {"x": self.x(), "y": self.y()}

    @Slot(bool)
    def set_always_on_top(self, enabled: bool):
        self.settings_data["always_on_top"] = enabled
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    @Slot(float)
    def set_companion_scale(self, value: float):
        self.settings_data["scale"] = value

    @Slot(bool)
    def set_edge_behavior(self, enabled: bool):
        self.settings_data["edge_behavior"] = enabled

    @Slot()
    def reset_position(self):
        self.move(80, 120)
        self.settings_data.update({"x": 80, "y": 120})

    @Slot(dict)
    def _status_ready(self, payload):
        self.page().runJavaScript(f"window.astraStatus({json.dumps(payload)});")

    @Slot(dict)
    def _forward_response(self, payload):
        if payload.get("status") == "approval_required":
            payload = {**payload, "type": "approval_required", "description": payload.get("goal", "")}
        elif payload.get("mode") == "error":
            payload = {**payload, "type": "error", "message": payload.get("response", "")}
        elif payload.get("response"):
            payload = {**payload, "type": "response", "text": payload.get("response", "")}
        self.page().runJavaScript(f"window.astraResponse({json.dumps(payload)});")

    @Slot(dict)
    def _forward_event(self, payload):
        self.page().runJavaScript(f"window.astraEvent({json.dumps(payload)});")

    def closeEvent(self, event):
        self.settings_data.update({"x": self.x(), "y": self.y(), "width": self.width(), "height": self.height()})
        save_settings(self.settings_data)
        self.setUrl(QUrl("about:blank"))
        self.ui_server.stop()
        self.bridge.shutdown()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    for asset in REQUIRED_ASSETS:
        print(f"asset exists = {asset.exists()}: {asset}")
    if not MODEL_PATH.exists():
        print(f"Astra UI warning: required model is missing: {MODEL_PATH}", file=sys.stderr)
    ui_server = UiServer(UI_DIR)
    ui_server.start()
    window = CompanionWindow(ui_server)
    window.show()
    sys.exit(app.exec())
