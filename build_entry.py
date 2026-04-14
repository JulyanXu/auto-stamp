"""
Windows exe entry point.
Starts the FastAPI/uvicorn server and opens the browser automatically.
"""
import multiprocessing
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_dir() -> Path:
    """Return the base resource directory (works both frozen and from source)."""
    if getattr(sys, "frozen", False):
        # Running inside PyInstaller bundle
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    """Writable data directory placed next to the exe (or project root in dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent / "data"


def _patch_config() -> None:
    """Redirect config paths to the correct locations before importing the app."""
    resource = _resource_dir()
    data = _data_dir()

    import app.config as cfg  # noqa: PLC0415

    cfg.FRONTEND_DIST_DIR = resource / "frontend" / "dist"
    cfg.DATA_DIR = data
    cfg.UPLOAD_DIR = data / "uploads"
    cfg.PREVIEW_DIR = data / "previews"
    cfg.RESULT_DIR = data / "results"
    cfg.SETTINGS_DIR = data / "settings"
    cfg.STAMP_IMAGE_PATH = data / "settings" / "stamp.png"
    cfg.STAMP_SETTINGS_PATH = data / "settings" / "stamp-settings.json"
    cfg.TEMPLATES_PATH = data / "settings" / "templates.json"


PORT = 8000
URL = f"http://localhost:{PORT}"


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open(URL)


def main() -> None:
    # Add backend directory to sys.path so `app` package is importable
    backend_dir = _resource_dir() / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    _patch_config()

    # Open browser in background thread
    threading.Thread(target=_open_browser, daemon=True).start()

    import uvicorn  # noqa: PLC0415

    # When frozen without a console (sys.stderr/stdout are None), uvicorn's
    # default logging formatter crashes on isatty(). Disable it entirely.
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=PORT,
        log_config=None,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
