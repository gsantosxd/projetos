from PyInstaller.utils.hooks import collect_all, collect_submodules

playwright_datas, playwright_binaries, playwright_hidden = collect_all("playwright")
hidden = playwright_hidden
hidden += collect_submodules("pypdf")
hidden += collect_submodules("docx")
hidden += ["googlesearch", "bs4", "requests"]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=playwright_binaries,
    datas=playwright_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ToNoCorre",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    version="version_info.txt",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ToNoCorre",
)
