# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
project = Path(SPECPATH)

a = Analysis(
    [str(project / 'b30.py')],
    pathex=[],
    binaries=[],
    datas=[(str(project / 'assets'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['UnityPy', 'numpy', 'PIL.AvifImagePlugin', 'PIL._avif', 'PIL.WebPImagePlugin', 'PIL._webp', 'PIL.ImageCms', 'PIL._imagingcms'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='InFalsusB30',
    version=str(project / 'version.txt'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
