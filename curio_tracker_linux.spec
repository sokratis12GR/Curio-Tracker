# -*- mode: python ; coding: utf-8 -*-
# Linux counterpart to curio_tracker.spec (Windows). Key differences:
#  - no python3*.dll bundling (PyInstaller's Linux bootloader handles libpython itself)
#  - no bundled Tesseract: Linux users install the `tesseract-ocr` system package instead,
#    and set_tesseract_path.py finds it on PATH at runtime
#  - no bundled updater (the Linux updater is not implemented yet)
#  - no icon=/version= kwargs (both are Windows PE-only in PyInstaller)

import os

import customtkinter
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

opencv_libs = collect_dynamic_libs('cv2')
pillow_libs = collect_dynamic_libs('PIL')
pyautogui_libs = collect_dynamic_libs('pyautogui')

datas = [
    ('body_armors.txt', '.'),
    ('version.txt', '.'),
]

assets_dir = os.path.abspath("assets")
for root, _, files in os.walk(assets_dir):
    for f in files:
        src_file = os.path.join(root, f)
        rel_path = os.path.relpath(root, assets_dir)
        dest_dir = os.path.join("assets", rel_path)
        datas.append((src_file, dest_dir))

theme_file = os.path.abspath(os.path.join("ctk_themes", "heist_theme.json"))
if not os.path.isfile(theme_file):
    raise FileNotFoundError(f"CustomTkinter theme not found: {theme_file}")
datas.append((theme_file, "ctk_themes"))

ctk_path = os.path.dirname(customtkinter.__file__)
datas.append((ctk_path, "customtkinter"))

binaries = opencv_libs + pillow_libs + pyautogui_libs

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'pynput.keyboard._xorg',
        'pynput.keyboard._dummy',
        'pynput.mouse._xorg',
        'pynput.mouse._dummy',
        'pynput._util.xorg',
        'pynput._util.xorg_keysyms',
    ] + collect_submodules('Xlib'),
    hookspath=['.'],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HeistCurioTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    onefile=True,
    exclude_binaries=False
)
