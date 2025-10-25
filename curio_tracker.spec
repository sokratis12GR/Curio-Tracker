# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob
import sysconfig
import shutil
import customtkinter
from PyInstaller.utils.hooks import collect_dynamic_libs

# ---- Collect dynamic libraries ----
opencv_libs = collect_dynamic_libs('cv2')
pillow_libs = collect_dynamic_libs('PIL')
pyautogui_libs = collect_dynamic_libs('pyautogui')

# ---- Base path for Tesseract ----
tesseract_base = os.path.abspath("tesseract")

# ---- Data files to bundle ----
datas = [
    ('all_valid_heist_terms.csv', '.'),
    ('body_armors.txt', '.'),
    ('curio_currency_fetch.py', '.'),
    ('curio_keybinds.py', '.'),
    ('curio_tiers_fetch.py', '.'),
    ('experimental_items.csv', '.'),
    ('keybinds_handlers.py', '.'),
    ('load_utils.py', '.'),
    ('ocr_utils.py', '.'),
    ('renderer.py', '.'),
    ('settings.py', '.'),
    ('shared_lock.py', '.'),
    ('themes.py', '.'),
    ('toasts.py', '.'),
    ('logger.py', '.'),
    ('tree_manager.py', '.'),
    ('csv_manager.py', '.'),
    ('tree_utils.py', '.'),
    ('version_utils.py', '.'),
    ('update_checker.py', '.'),
    ('font.py', '.'),
    ('currency_utils.py', '.'),
    ('curio_collection_fetch.py', '.'),
]

# ---- Add all files from /gui ----
gui_dir = os.path.abspath("gui")
for root, _, files in os.walk(gui_dir):
    for f in files:
        if f.endswith(".py"):  # only bundle Python source files
            src_file = os.path.join(root, f)
            rel_path = os.path.relpath(root, gui_dir)
            dest_dir = os.path.join("gui", rel_path)
            datas.append((src_file, dest_dir))

# ---- Add all files from /assets ----
assets_dir = os.path.abspath("assets")
for root, _, files in os.walk(assets_dir):
    for f in files:
        src_file = os.path.join(root, f)
        rel_path = os.path.relpath(root, assets_dir)
        # The destination path inside the exe
        dest_dir = os.path.join("assets", rel_path)
        datas.append((src_file, dest_dir))

# ---- Add all files from /ctk_themes ----
themes_dir = os.path.abspath("ctk_themes")
for root, _, files in os.walk(themes_dir):
    for f in files:
        src_file = os.path.join(root, f)
        rel_path = os.path.relpath(root, themes_dir)
        # The destination path inside the exe
        dest_dir = os.path.join("ctk_themes", rel_path)
        datas.append((src_file, dest_dir))

ctk_path = os.path.dirname(customtkinter.__file__)
datas.append((ctk_path, "customtkinter"))

# ---- Find Python DLL dynamically ----
dll_dir = sysconfig.get_config_var('BINDIR')
python_dlls = glob.glob(os.path.join(dll_dir, 'python3*.dll'))

if python_dlls:
    python_dll_path = python_dlls[0]
else:
    python_dll_path = os.path.join(sys.base_prefix, "python313.dll")

# ---- Binaries to bundle ----
binaries = [
    (python_dll_path, '.'), 
]

# ---- Add tesseract.exe and tessdata ----
path_tesseract = shutil.which("tesseract")

if path_tesseract and os.path.isfile(path_tesseract):
    # Use system-installed Tesseract
    binaries.append((path_tesseract, 'tesseract'))
else:
    # Bundle local tesseract.exe
    local_tesseract_exe = os.path.join(tesseract_base, 'tesseract.exe')
    binaries.append((local_tesseract_exe, 'tesseract'))

    # Bundle all traineddata files in tesseract/tessdata/
    tessdata_dir = os.path.join(tesseract_base, 'tessdata')
    for root, _, files in os.walk(tessdata_dir):
        for f in files:
            src_file = os.path.join(root, f)
            rel_path = os.path.relpath(root, tesseract_base)  # should be "tessdata"
            binaries.append((src_file, os.path.join('tesseract', rel_path)))

# Add collected libs
binaries += opencv_libs + pillow_libs + pyautogui_libs

# ---- Main Analysis ----
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[r"D:\Dev\Projects\Curio Tracker"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'encodings',  
        'keyboard',
        'pyautogui',
        'cv2',
        'numpy',
        'pytesseract',
        'PIL',
        'pygetwindow',
        'termcolor'
        'customtkinter'
    ],
    hookspath=['.'],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- Onefile EXE ----
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,            
    a.datas,             
    [],
    name='Heist Curio Tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icon.ico',
    version='version.txt',
    onefile=True,          
    exclude_binaries=False # ensure binaries are packed in exe
)
