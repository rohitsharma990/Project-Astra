"""Desktop companion host. Run from the repository root with `python ui/main.py`."""
from __future__ import annotations

import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QUrl, QTimer, Qt, Slot
from PySide6.QtGui import QCursor
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
        self._drag_cursor_offset = None
        self._drag_start_screen_pos = None
        self._drag_start_window_pos = None
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
        QTimer.singleShot(1000, lambda: self._inspect_windows("APP_INIT"))

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
        # Also run initial diagnostics
        self.page().runJavaScript("console.log('[JS_INIT] astraDiagnostics available:', typeof window.astraDiagnostics); window.astraDiagnostics?.();")

    def _inspect_windows(self, phase: str = ""):
        """Diagnostic: Print all top-level windows"""
        from PySide6.QtWidgets import QApplication
        widgets = QApplication.topLevelWidgets()
        print(f"[WINDOW_COUNT] {phase} | total={len(widgets)}")
        for idx, widget in enumerate(widgets):
            title = getattr(widget, 'windowTitle', lambda: 'N/A')()
            geom = widget.geometry()
            visible = widget.isVisible() if hasattr(widget, 'isVisible') else 'N/A'
            print(f"  [{idx}] {widget.__class__.__name__} title='{title}' pos=({geom.x()},{geom.y()}) size=({geom.width()}x{geom.height()}) visible={visible}")

    def _page_ready(self, loaded: bool):
        if loaded:
            self.page().runJavaScript(f"window.astraSettings({json.dumps(self.settings_data)});")

    @Slot(int, int)
    def begin_drag(self, screen_x: int, screen_y: int):
        """Begin drag using screen coordinates (from JS pointer event).
        Stores the anchor point for stable drag calculation.
        Args:
            screen_x: Screen X coordinate from pointer event (stable, not viewport-relative)
            screen_y: Screen Y coordinate from pointer event (stable, not viewport-relative)
        """
        self._inspect_windows("DRAG_BEGIN")
        window_pos = self.frameGeometry().topLeft()
        self._drag_start_window_pos = (window_pos.x(), window_pos.y())
        self._drag_start_screen_pos = (screen_x, screen_y)
        self._drag_cursor_offset = (screen_x, screen_y)
        print(f"[DRAG_START] screen=({screen_x},{screen_y}) window=({self._drag_start_window_pos[0]},{self._drag_start_window_pos[1]})")

    @Slot(int, int)
    def move_companion_to_cursor(self, screen_x: int, screen_y: int):
        """Move window to follow cursor using screen coordinates.
        Uses stable anchor: new_window = start_window + (current_screen - start_screen)
        Args:
            screen_x: Current screen X coordinate from pointer event (stable, not viewport-relative)
            screen_y: Current screen Y coordinate from pointer event (stable, not viewport-relative)
        """
        if self._drag_start_screen_pos is None:
            self.begin_drag(screen_x, screen_y)
            return
        
        # Calculate delta in screen space (stable, doesn't change as window moves)
        delta_x = screen_x - self._drag_start_screen_pos[0]
        delta_y = screen_y - self._drag_start_screen_pos[1]
        
        # New window position = starting position + screen delta
        new_x = self._drag_start_window_pos[0] + delta_x
        new_y = self._drag_start_window_pos[1] + delta_y
        
        self.move(new_x, new_y)
        print(f"[DRAG_MOVE] screen=({screen_x},{screen_y}) delta=({delta_x},{delta_y}) window=({new_x},{new_y})")

    @Slot()
    def end_drag(self):
        """End drag and reset state."""
        self._inspect_windows("DRAG_END")
        if self._drag_start_window_pos is not None:
            print(f"[DRAG_END] final_window=({self._drag_start_window_pos[0]},{self._drag_start_window_pos[1]})")
        self._drag_cursor_offset = None
        self._drag_start_screen_pos = None
        self._drag_start_window_pos = None

    # Kept for compatibility with older UI builds.
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
