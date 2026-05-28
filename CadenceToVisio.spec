# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Cadence to Visio GUI"""

import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(base_dir, "gui_app.py")],
    pathex=[base_dir],
    binaries=[],
    datas=[
        (os.path.join(base_dir, "circuit.vss"), "."),
        (os.path.join(base_dir, "cadence_to_visio_core.py"), "."),
        (os.path.join(base_dir, "cadence_to_visio_v2.py"), "."),
    ],
    hiddenimports=[
        "openpyxl",
        "win32com",
        "win32com.client",
        "pythoncom",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CadenceToVisio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可替换为 .ico 文件路径
)
