# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_dynamic_libs

# Collect all dynamic libs for OpenCV and other packages
opencv_libs = collect_dynamic_libs('cv2')
pillow_libs = collect_dynamic_libs('PIL')
pyautogui_libs = collect_dynamic_libs('pyautogui')

# Base path for tesseract in your project
tesseract_base = os.path.abspath("tesseract")

# Add your data files
datas = [
    ('all_valid_heist_terms.csv', '.'),
    ('body_armors.txt', '.'),
    ('config.py', '.'),
    ('user_settings.ini', '.'),
]

# Add tesseract executable + tessdata
binaries = [
    (os.path.join(tesseract_base, 'tesseract.exe'), 'tesseract'),
]
# Add tessdata folder recursively
for root, _, files in os.walk(os.path.join(tesseract_base, 'tessdata')):
    for f in files:
        src_file = os.path.join(root, f)
        rel_path = os.path.relpath(root, tesseract_base)
        binaries.append((src_file, os.path.join('tesseract', rel_path)))

# Include OpenCV/Pillow/PyAutoGUI DLLs
binaries += opencv_libs + pillow_libs + pyautogui_libs

# The build spec
block_cipher = None

a = Analysis(
    ['curio_tracker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'keyboard',
        'pyautogui',
        'cv2',
        'numpy',
        'pytesseract',
        'PIL',
        'pygetwindow',
        'termcolor'
    ],
    hookspath=['.'],  # includes hook_pytesseract_path.py
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='curio_tracker-0.1.6',
    debug=False,          
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True          
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='curio_tracker-0.1.6'
)

app = BUNDLE(coll)
