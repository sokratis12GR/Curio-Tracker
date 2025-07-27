# Thanks for downloading my heist curio data tool.

# SETUP

Would need to download some libraries to be able to use this tool, run the following command in cmd:
> pip install keyboard pyautogui opencv-python numpy pytesseract pillow pygetwindow termcolor

Afterwards make sure to download and install Tesseract OCR from https://github.com/tesseract-ocr/tesseract
Once installed replace the following in the script with your installation path of Tesseract-OCR:
> pytesseract.pytesseract.tesseract_cmd = r"D:\Dev\Tesseract-OCR\tesseract.exe"


# Usage

To use: open in cmd via 'py curio_tracker.py`