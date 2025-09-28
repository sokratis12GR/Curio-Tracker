import os
import shutil
import sys

import pytesseract

import config as c
from logger import log_message


################################################################################
# Sets the Tesseract OCR location to either PATH, Bundled or User Set Location #
################################################################################
def set_tesseract_path():
    tesseract_bin = None

    # 1. Attempt to find from PATH
    path_from_system = shutil.which("tesseract")
    if path_from_system and os.path.isfile(path_from_system):
        tesseract_bin = path_from_system

    # 2. If not in PATH, attempt PyInstaller bundled executable
    if not tesseract_bin and hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(sys._MEIPASS, "tesseract", "tesseract.exe")
        if os.path.isfile(bundled_path):
            tesseract_bin = bundled_path

    # 3. Local dev fallback
    if not tesseract_bin:
        dev_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tesseract",
            "tesseract.exe"
        )
        if os.path.isfile(dev_path):
            tesseract_bin = dev_path

    # 4. Last fallback: hardcoded/config path
    if not tesseract_bin or not os.path.isfile(tesseract_bin):
        tesseract_bin = os.path.normpath(c.pytesseract_path)

    # --- Apply and verify ---
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    log_message(f"[DEBUG] Tesseract binary set to: {tesseract_bin}")

    tesseract_dir = os.path.dirname(tesseract_bin)
    tessdata_dir = os.path.join(tesseract_dir, "tessdata")

    if os.path.isdir(tessdata_dir):
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        log_message("[DEBUG] TESSDATA_PREFIX set to:", tessdata_dir)
        eng_path = os.path.join(tessdata_dir, "eng.traineddata")
        if os.path.isfile(eng_path):
            log_message("[DEBUG] eng.traineddata found:", eng_path)
        else:
            log_message("[ERROR] eng.traineddata NOT found in tessdata!")
    else:
        log_message("[ERROR] tessdata directory not found at:", tessdata_dir)

    try:
        import subprocess
        version = subprocess.check_output([tesseract_bin, "--version"], text=True)
        log_message(f"[DEBUG] Verified tesseract runs: {version.strip()}")
    except Exception as e:
        log_message(f"[ERROR] Could not run tesseract at {tesseract_bin}: {e}")
