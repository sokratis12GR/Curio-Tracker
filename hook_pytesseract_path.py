import os
import sys
import pytesseract

# When running from PyInstaller, sys._MEIPASS is the temp extract folder
if hasattr(sys, '_MEIPASS'):
    tesseract_bin = os.path.join(sys._MEIPASS, 'tesseract.exe')
else:
    # Fallback to local dev path
    tesseract_bin = os.path.join('tesseract', 'tesseract.exe')

pytesseract.pytesseract.tesseract_cmd = tesseract_bin
