# PyInstaller spec for Auto-Stamp Windows exe
# Run: pyinstaller auto_stamp.spec

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
project_root = Path(SPECPATH)

# Collect all submodules/datas for packages that use dynamic imports
_datas = []
_binaries = []
_hiddenimports = []

for pkg in ("fastapi", "starlette", "uvicorn", "pydantic", "anyio", "sniffio", "h11"):
    d, b, h = collect_all(pkg)
    _datas += d
    _binaries += b
    _hiddenimports += h

# Add frontend and backend source as data files
_datas += [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(project_root / "backend" / "app"), "backend/app"),
]

a = Analysis(
    [str(project_root / "build_entry.py")],
    pathex=[str(project_root / "backend")],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hiddenimports + [
        "fitz",
        "multipart",
        "python_multipart",
        "pythoncom",
        "pywintypes",
        "win32com",
        "win32com.client",
        "email.mime.multipart",
        "email.mime.text",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.websockets_impl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "numpy", "pandas", "pytest",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "wx", "gi", "gtk",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Auto-Stamp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Auto-Stamp",
)
