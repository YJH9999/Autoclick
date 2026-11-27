# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 文件夹版/单文件版共用配置。设置 AUTOCLICKER_ONEFILE=1 构建单文件。"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH)
datas = [(str(root / "assets" / "icon.ico"), "assets"), (str(root / "README.md"), ".")]
binaries = []
hiddenimports = ["PIL._tkinter_finder"]
for package in ("pystray", "pynput", "mss"):
    hiddenimports += collect_submodules(package)
ctk_data, ctk_binaries, ctk_imports = collect_all("customtkinter")
datas += ctk_data
binaries += ctk_binaries
hiddenimports += ctk_imports

onefile = os.environ.get("AUTOCLICKER_ONEFILE") == "1"
analysis = Analysis(
    [str(root / "run.py")], pathex=[str(root / "src")], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz, analysis.scripts,
    analysis.binaries if onefile else [], analysis.datas if onefile else [], [],
    name="AutoClicker", debug=False, bootloader_ignore_signals=False, strip=False,
    upx=False, console=False, disable_windowed_traceback=False,
    exclude_binaries=not onefile, icon=str(root / "assets" / "icon.ico"),
    version=str(root / "installer" / "version_info.txt"),
)
if not onefile:
    collection = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=False, name="AutoClicker")
