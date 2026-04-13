# PyInstaller spec for Auto-Stamp Windows exe
# Run: pyinstaller auto_stamp.spec

import os
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "build_entry.py")],
    pathex=[str(project_root / "backend")],
    binaries=[],
    datas=[
        # Bundle built frontend
        (str(project_root / "frontend" / "dist"), "frontend/dist"),
        # Bundle backend source
        (str(project_root / "backend" / "app"), "backend/app"),
    ],
    hiddenimports=[
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # fastapi / starlette
        "fastapi",
        "fastapi.middleware",
        "fastapi.middleware.cors",
        "fastapi.staticfiles",
        "fastapi.responses",
        "starlette",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        "starlette.responses",
        "starlette.routing",
        "starlette.background",
        "starlette.datastructures",
        "starlette.exceptions",
        "starlette.requests",
        "starlette.types",
        "starlette.websockets",
        # pydantic
        "pydantic",
        "pydantic.v1",
        # file handling
        "fitz",
        "multipart",
        "python_multipart",
        "email.mime.multipart",
        "email.mime.text",
        # anyio / asyncio backends
        "anyio",
        "anyio._backends._asyncio",
        "anyio.from_thread",
        "sniffio",
        "h11",
        "h11._connection",
        "h11._events",
        "h11._readers",
        "h11._writers",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy", "pandas"],
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
